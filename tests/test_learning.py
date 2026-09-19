import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import learning


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.scope=patch.object(app,'DATA',Path(self.temp.name));self.scope.start();app.init()

    def tearDown(self):
        self.scope.stop();self.temp.cleanup()

    def document(self, long=False):
        text='Début : observer les journaux. '+('Partie centrale du cours. '*1400 if long else '')+' FIN_DU_COURS : conserver une chronologie vérifiable.'
        with app.connect() as db:
            return app.add_document(db,{'title':'Mon cours','text':text})['id']

    def queue(self,doc,kind='summary'):
        with app.connect() as db:return learning.queue(db,doc,kind,'qwen2.5:7b')['id']

    def test_length_limit_splits_and_resumes_completed_subparts(self):
        doc=self.document();jid=self.queue(doc)
        with app.connect() as db:job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
        blocks=['FIRST '+('a '*600),'LAST '+('b '*600)]
        calls=[]
        def interrupted(model,system,prompt,**kw):
            calls.append(prompt)
            if 'FIRST' in prompt and 'LAST' in prompt:raise learning.GenerationLimit('long')
            if 'LAST' in prompt:raise ValueError('temporary outage')
            return 'First finished.'
        with self.assertRaises(ValueError):learning.generate_parts(app.connect,interrupted,job,'system','instruction',blocks,1800)
        resumed=[]
        def finish(model,system,prompt,**kw):
            resumed.append(prompt)
            if 'FIRST' in prompt and 'LAST' in prompt:raise learning.GenerationLimit('long')
            return 'Last finished.'
        result=learning.generate_parts(app.connect,finish,job,'system','instruction',blocks,1800)
        self.assertIn('First finished.',result);self.assertIn('Last finished.',result)
        self.assertFalse(any('FIRST' in p and 'LAST' not in p for p in resumed))
        with patch.object(app,'local_models',return_value=['qwen2.5:7b']),patch.object(app,'ollama',return_value={'done_reason':'length','message':{'content':'TRUNCATED'}}):
            with self.assertRaises(learning.GenerationLimit):app.generate('qwen2.5:7b','s','p')

    def test_short_generation_has_one_bounded_larger_retry(self):
        jid=self.queue(self.document())
        with app.connect() as db:job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
        budgets=[]
        def long(model,system,prompt,**kw):
            budgets.append(kw['limit']);raise learning.GenerationLimit('long')
        with self.assertRaises(learning.GenerationLimit):learning.generate_parts(app.connect,long,job,'s','i',['short'],1800)
        self.assertEqual(budgets,[1800,6400])
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM generation_parts').fetchone()[0],0)

    def test_delete_conversations_preserves_learning_and_handles_last_session(self):
        doc=self.document()
        jid=self.queue(doc)
        with app.connect() as db:
            app.store_exchange(db,1,'Question','Réponse',[],jid,doc)
            db.execute('INSERT INTO memories(text,created) VALUES(?,?)',('À retenir',app.now()))
            replacement=learning.delete_session(db,1)['session_id']
            self.assertNotEqual(replacement,1)
            self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],1)
            self.assertEqual(app.state(db,1)['current_session']['id'],replacement)
            learning.migrate(db)
            self.assertIsNone(db.execute('SELECT 1 FROM sessions WHERE id=1').fetchone())
            other=db.execute('INSERT INTO sessions(title,created,updated) VALUES(?,?,?)',('Autre',app.now(),app.now())).lastrowid
            app.store_exchange(db,other,'Conserver','Historique',[],document_id=doc)
            self.assertEqual(learning.delete_session(db,replacement)['session_id'],other)
            self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],2)

    def test_migration_preserves_old_chat_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as old_dir:
            path=Path(old_dir)
            conn=sqlite3.connect(path/'mentor.sqlite3')
            conn.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT NOT NULL,content TEXT NOT NULL,sources TEXT NOT NULL,created TEXT NOT NULL)')
            conn.execute("INSERT INTO messages VALUES(42,'user','Ma question importante','[]','2026-01-01')")
            conn.commit();conn.close()
            with patch.object(app,'DATA',path):
                app.init();app.init()
                with app.connect() as db:
                    row=db.execute('SELECT * FROM messages WHERE id=42').fetchone()
                    self.assertEqual(row['content'],'Ma question importante')
                    self.assertEqual(row['session_id'],1)
                    self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],1)

    def test_sessions_do_not_share_recent_history_but_keep_personal_memory(self):
        with app.connect() as db:
            db.execute("INSERT INTO sessions(id,title,created,updated) VALUES(2,'Autre sujet',?,?)",(app.now(),app.now()))
            db.execute('INSERT INTO memories(text,created) VALUES(?,?)',('Je préfère des analogies.',app.now()))
            with patch.object(app,'local_models',return_value=['qwen2.5:7b']),patch.object(app,'ollama',return_value={'message':{'content':'Réponse.'}}) as model:
                app.ask(db,{'question':'Sujet SECRET_SESSION_UN','session_id':1})
                app.ask(db,{'question':'Un autre sujet','session_id':2})
                request=model.call_args.args[1]
                self.assertNotIn('SECRET_SESSION_UN',json.dumps(request,ensure_ascii=False))
                self.assertIn('Je préfère des analogies.',request['messages'][0]['content'])
            self.assertEqual(len(app.state(db,1)['messages']),2)
            self.assertEqual(len(app.state(db,2)['messages']),2)

    def test_complete_reading_covers_end_and_resume_keeps_finished_parts(self):
        doc=self.document(long=True);job=self.queue(doc)
        calls=[]
        def fail_second(model,system,prompt,**options):
            calls.append(prompt)
            if len(calls)==2:raise ValueError('Interruption simulée')
            return 'Notes de section.'
        learning.run_job(app.connect,fail_second,job)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(job,)).fetchone()[0],'error')
            self.assertEqual(db.execute('SELECT count(*) FROM summary_parts').fetchone()[0],1)
        self.assertEqual(self.queue(doc),job)
        resumed=[]
        def finish(model,system,prompt,**options):resumed.append(prompt);return 'Synthèse avec repères.'
        learning.run_job(app.connect,finish,job)
        self.assertTrue(any('FIN_DU_COURS' in prompt for prompt in resumed))
        self.assertFalse(any('Section 1/' in prompt for prompt in resumed))
        with app.connect() as db:
            result=db.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
            self.assertEqual(result['status'],'done')
            covered=json.loads(result['result'])['chunks_read']
            self.assertEqual(covered,db.execute('SELECT count(*) FROM chunks WHERE document_id=?',(doc,)).fetchone()[0])
            self.assertGreater(covered,7)

    def test_card_jobs_depend_on_complete_summary_and_validate_output(self):
        doc=self.document();cards=self.queue(doc,'cards')
        with app.connect() as db:summary=db.execute('SELECT dependency FROM jobs WHERE id=?',(cards,)).fetchone()[0]
        learning.run_job(app.connect,lambda *a,**k:'Un résumé complet.',summary)
        learning.run_job(app.connect,lambda *a,**k:'{"cards":[]}',cards)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(cards,)).fetchone()[0],'error')
            self.assertEqual(db.execute('SELECT count(*) FROM cards').fetchone()[0],0)
        self.queue(doc,'cards')
        valid={'cards':[{'question':f'Question {i} ?','answer':f'Explication {i}.','source_index':1} for i in range(5)]}
        learning.run_job(app.connect,lambda *a,**k:json.dumps(valid),cards)
        with app.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(cards,)).fetchone()
            self.assertEqual(row['status'],'done')
            self.assertEqual(len(json.loads(row['result'])['cards']),5)
            self.assertEqual(db.execute('SELECT count(*) FROM cards').fetchone()[0],0)

    def test_summary_requested_in_chat_is_updated_when_job_finishes(self):
        doc=self.document()
        with app.connect() as db,patch.object(app,'local_models',return_value=['qwen2.5:7b']):
            reply=app.ask(db,{'question':'Résume mon cours','document_id':doc})
            self.assertIn('job_id',reply)
        learning.run_job(app.connect,lambda *a,**k:'Le résumé demandé est prêt.',reply['job_id'])
        with app.connect() as db:
            messages=app.state(db)['messages']
            self.assertIn('Le résumé demandé est prêt.',messages[-1]['content'])
            self.assertEqual(len(messages),2)

    def test_explicit_memory_and_followup_about_summary(self):
        with app.connect() as db:
            with patch.object(app,'local_models',side_effect=AssertionError('No model needed to remember')):
                app.ask(db,{'question':'Retiens que je préfère les exemples concrets.'})
            self.assertEqual(db.execute('SELECT text FROM memories').fetchone()[0],'je préfère les exemples concrets.')
            with patch.object(app,'local_models',return_value=['qwen2.5:7b']),patch.object(app,'ollama',return_value={'message':{'content':'Une autre explication.'}}):
                answer=app.ask(db,{'question':"Je n’ai pas compris ce résumé, explique autrement."})
                self.assertNotIn('job_id',answer)


if __name__=='__main__':unittest.main()

