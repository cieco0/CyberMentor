import io
import json
from unittest.mock import patch
import test_learning
import unittest
import app
import learning
import pdf_export
from pypdf import PdfReader


class SectionTests(unittest.TestCase):
    setUp=test_learning.LearningTests.setUp
    tearDown=test_learning.LearningTests.tearDown
    def test_scope_isolation_jobs_retrieval_and_detailed_pdf(self):
        with app.connect() as db:
            with patch.object(app,'extract',return_value=[(1,'DNS : résoudre les noms et vérifier le cache.'),(2,'EXCLU : secrets du chapitre distinct sur Kerberos.')]):
                doc=app.add_document(db,{'title':'École','file':'YQ==','filename':'cours.pdf'})['id']
            sid=learning.add_section(db,{'document_id':doc,'title':'DNS','first_page':1,'last_page':1})['id']
            self.assertTrue(all(s['page']==1 for s in app.retrieve(db,'EXCLU',document_id=doc,section_id=sid)))
            global_job=learning.queue(db,doc,'summary','test')['id']
            cards=learning.queue(db,doc,'cards','test',sid)
            self.assertNotEqual(global_job,cards['dependency'])
            lesson=learning.queue(db,doc,'lesson','test',sid)
            self.assertEqual(lesson['id'],learning.queue(db,doc,'lesson','test',sid)['id'])
            learning.migrate(db)
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],4)
            with self.assertRaises(ValueError): learning.section(db,sid,doc+1)
            with self.assertRaises(ValueError): learning.add_section(db,{'document_id':doc,'title':'Hors cours','first_page':3,'last_page':4})
        prompts=[]
        def generate(model,system,prompt,**kwargs):
            prompts.append(prompt)
            return '# Définition\nDNS associe un nom à une adresse. [p. 1]\n\n## Exemple pédagogique\nChercher un nom avant une connexion.\n\n## À retenir\nVérifier le cache.'
        learning.run_job(app.connect,generate,lesson['id'])
        self.assertTrue(prompts)
        self.assertTrue(all('EXCLU' not in prompt for prompt in prompts))
        with app.connect() as db:
            job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(lesson['id'],)).fetchone())
            self.assertEqual(job['status'],'done')
            job['result']=json.loads(job['result'])
            self.assertEqual(job['result']['chunks_read'],1)
            job['parts']=[dict(p) for p in db.execute('SELECT * FROM summary_parts WHERE job_id=?',(lesson['id'],))]
            pdf=pdf_export.build({'title':'École - DNS'},job,learning.section(db,sid,doc))
        pages=PdfReader(io.BytesIO(pdf)).pages
        self.assertGreaterEqual(len(pages),2)
        text='\n'.join(p.extract_text() for p in pages)
        self.assertIn('Définition',text)
        self.assertIn('École',text)
        self.assertNotIn('EXCLU',text)
