import base64
import io
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import app


class MentorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.data_patch.start()
        app.init()

    def tearDown(self):
        self.data_patch.stop()
        self.temp.cleanup()

    def add(self, db, text='Kerberos utilise des tickets pour authentifier les utilisateurs du domaine.', **extra):
        return app.add_document(db, {'title':'Authentification', 'certification':'CDSA', 'text':text, **extra})

    def test_retrieval_scope_accents_delete_and_duplicates(self):
        with app.connect() as db:
            result = self.add(db)
            self.add(db, 'Une alerte est un signal à analyser avec les journaux.', certification='BTL1')
            self.assertEqual(app.retrieve(db,'Explique Kerberos','CDSA')[0]['document_id'],result['id'])
            self.assertFalse(app.retrieve(db,'Kerberos','BTL1'))
            self.assertFalse(app.retrieve(db,'inexistant'))
            self.assertTrue(app.retrieve(db,'résume ce document',document_id=result['id']))
            with self.assertRaises(ValueError): self.add(db)
            db.execute('DELETE FROM documents WHERE id=?',(result['id'],))
            self.assertFalse(app.retrieve(db,'Kerberos'))
            self.assertEqual(db.execute('SELECT count(*) FROM search').fetchone()[0],1)

    def test_binary_imports_and_empty_scan(self):
        from docx import Document
        from pypdf import PdfWriter
        stream=io.BytesIO(); doc=Document(); doc.add_paragraph('Un événement Windows doit être remis dans son contexte.'); doc.save(stream)
        with app.connect() as db:
            self.add(db,file=base64.b64encode(stream.getvalue()).decode(),filename='cours.docx')
            self.assertTrue(app.retrieve(db,'événement'))
            writer=PdfWriter();writer.add_blank_page(width=300,height=300);pdf=io.BytesIO();writer.write(pdf)
            with self.assertRaisesRegex(ValueError,'OCR'):
                self.add(db,file=base64.b64encode(pdf.getvalue()).decode(),filename='scan.pdf')
            with self.assertRaises(ValueError):
                self.add(db,file=base64.b64encode(b'text').decode(),filename='script.exe')

    def test_pdf_text_page_numbers_and_persistence(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer=PdfWriter()
        writer.add_blank_page(width=500,height=500)
        page=writer.add_blank_page(width=500,height=500)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 30 450 Td (Kerberos uses tickets for authentication.) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(content)
        stream=io.BytesIO();writer.write(stream)
        with app.connect() as db:
            result=self.add(db,file=base64.b64encode(stream.getvalue()).decode(),filename='example.pdf')
            self.assertEqual(result['empty_pages'],1)
        with app.connect() as db:
            self.assertEqual(app.retrieve(db,'Kerberos')[0]['page'],2)

    def test_cloud_models_are_excluded(self):
        with patch.object(app,'ollama',return_value={'models':[{'name':'qwen2.5:7b'},{'name':'x-cloud'},{'name':'aliased','remote_host':'https://example.com'}]}):
            self.assertEqual(app.local_models(),['qwen2.5:7b'])

    def test_grounded_chat_and_failure_atomicity(self):
        with app.connect() as db:
            self.add(db)
            with patch.object(app,'local_models',return_value=['qwen2.5:7b']), patch.object(app,'ollama',return_value={'message':{'content':'Kerberos utilise des tickets [S1].'}}) as fake:
                answer=app.ask(db,{'question':'Explique Kerberos','mode':'expliquer'})
                self.assertEqual(len(answer['sources']),1)
                sent=fake.call_args.args[1]
                self.assertIn('Kerberos utilise des tickets',sent['messages'][0]['content'])
                self.assertIn('Définir mon objectif',sent['messages'][0]['content'])
                self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],2)
            with patch.object(app,'local_models',return_value=[]):
                with self.assertRaises(ValueError): app.ask(db,{'question':'Kerberos ?'})
            self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],2)
            with patch.object(app,'local_models',return_value=['qwen2.5:7b']), patch.object(app,'ollama',return_value={'message':{'content':'Texte incomplet'},'done_reason':'length'}):
                with self.assertRaisesRegex(ValueError,'limite'): app.ask(db,{'question':'Kerberos ?'})
            self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],2)

    def test_http_access_validation_cards_and_backup(self):
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        port=server.server_address[1]
        port_patch=patch.object(app,'PORT',port);port_patch.start()
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,body=None,token=app.TOKEN,host=None,origin=None):
            headers={'X-CyberMentor-Token':token,'Content-Type':'application/json'}
            if host:headers['Host']=host
            if origin:headers['Origin']=origin
            req=urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            return urllib.request.urlopen(req)
        try:
            with request('state') as response: self.assertEqual(len(json.load(response)['certifications']),0)
            for kwargs in [{'token':'wrong'},{'origin':'https://evil.example'}]:
                with self.assertRaises(urllib.error.HTTPError) as ctx:request('cards',{},**kwargs)
                self.assertEqual(ctx.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError):request('state',host='evil.example')
            with request('cards',{'question':'Que fait DNS ?','answer':'Il résout les noms.','certification':'CDSA'}):pass
            with request('cards/review',{'id':1,'grade':'good'}):pass
            with request('state') as response:self.assertEqual(json.load(response)['cards'][0]['interval'],1)
            with request('cards/review',{'id':1,'grade':'again'}):pass
            with request('sessions',{'title':'Cours réseau'}) as response:new_session=json.load(response)['id']
            with request('state?session_id='+str(new_session)) as response:self.assertEqual(json.load(response)['messages'],[])
            with request('courses',{'name':'Cours Linux'}) as response:course=json.load(response)['id']
            with request('documents',{'course_id':course,'title':'Linux complet','text':'Les permissions Linux permettent de contrôler les accès aux fichiers.','prepare':True,'detailed':True}) as response:
                imported=json.load(response)
                self.assertIn('lesson_id',imported)
            with request('state') as response:
                data=json.load(response)
                self.assertEqual(next(d for d in data['documents'] if d['id']==imported['id'])['course_id'],course)
                self.assertEqual({j['kind'] for j in data['jobs'] if j['document_id']==imported['id']},{'summary','lesson'})
            with request('courses',{'id':course,'name':'Linux - école'}):pass
            with self.assertRaises(urllib.error.HTTPError):request('courses',{'name':'linux - école'})
            with self.assertRaises(urllib.error.HTTPError):request('documents',{'course_id':99999,'title':'Invalide','text':'Ce document ne doit pas être importé.'})
            with request('courses',{'name':'Cours réseau'}) as response:other_course=json.load(response)['id']
            with request('courses/attach',{'course_id':other_course,'document_id':imported['id']}):pass
            with request('state') as response:
                data=json.load(response)
                self.assertEqual(next(d for d in data['documents'] if d['id']==imported['id'])['course_id'],other_course)
            with app.connect() as db:
                doc=self.add(db)['id']
                job=app.learning.queue(db,doc,'cards','qwen2.5:7b')
                db.execute("UPDATE jobs SET status='done',result=? WHERE id=?",(json.dumps({'cards':[{'question':'Test ?','answer':'Réponse.'}]}),job['id']))
            for _ in range(2):
                with request('cards/accept',{'job_id':job['id'],'index':0}):pass
            with request('state') as response:self.assertEqual(len(json.load(response)['cards']),2)
            with request('backup') as response:raw=response.read()
            backup_path=Path(self.temp.name)/'restored.sqlite3'
            backup_path.write_bytes(raw)
            restored=sqlite3.connect(backup_path)
            self.assertEqual(restored.execute('SELECT interval FROM cards').fetchone()[0],0)
            restored.close()
        finally:
            server.shutdown();server.server_close();thread.join();port_patch.stop()


if __name__=='__main__': unittest.main()



