import io
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
import app
import media
import learning
import test_learning


class MediaTests(unittest.TestCase):
    setUp=test_learning.LearningTests.setUp
    tearDown=test_learning.LearningTests.tearDown

    def test_bounded_upload_cleans_incomplete_and_rejects_formats(self):
        folder=Path(self.temp.name)/'uploads'
        with self.assertRaises(ValueError):media.save_upload(io.BytesIO(b'ab'),10,folder,'film.mp4')
        self.assertEqual(list(folder.iterdir()),[])
        for name,size in [('film.exe',2),('film.mp4',media.MAX_BYTES+1)]:
            with self.assertRaises(ValueError):media.save_upload(io.BytesIO(b'ab'),size,folder,name)
        path,digest=media.save_upload(io.BytesIO(b'ab'),2,folder,'../../film.mp4')
        self.assertEqual(path.parent,folder)
        self.assertEqual(path.read_bytes(),b'ab')

    def test_http_video_job_transcript_and_retry(self):
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        port=server.server_address[1]
        def request(path,body=None,raw=None):
            payload=raw if raw is not None else json.dumps(body).encode() if body is not None else None
            return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=payload,headers={'X-CyberMentor-Token':app.TOKEN,'Content-Type':'application/octet-stream' if raw is not None else 'application/json'}))
        with patch.object(app,'PORT',port):
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with request('courses',{'name':'Vidéo test'}) as response:cid=json.load(response)['id']
                with request(f'media/upload?filename=test.mp4&course_id={cid}&interval=2',raw=b'fake-video') as response:jid=json.load(response)['id']
                with self.assertRaises(urllib.error.HTTPError):request(f'media/upload?filename=test.mp4&course_id={cid}',raw=b'fake-video')
                with self.assertRaises(urllib.error.HTTPError):request('media/upload?filename=x.mp4&course_id=9999',raw=b'x')
                with patch.object(media,'analyse',side_effect=ValueError('Piste illisible')):
                    media.run_job(app.connect,app.add_document,learning.queue,Path('models'),jid)
                with app.connect() as db:
                    job=dict(db.execute('SELECT * FROM media_jobs WHERE id=?',(jid,)).fetchone())
                    self.assertEqual(job['status'],'error');self.assertTrue(Path(job['path']).exists())
                with request('media/retry',{'id':jid}):pass
                pages=[(1,'[00:00:02 - AUDIO] DNS traduit les noms en adresses IP.'),(2,'[00:01:04 - ÉCRAN / OCR] pwd : afficher le dossier courant.')]
                with patch.object(media,'analyse',return_value=pages):
                    media.run_job(app.connect,app.add_document,learning.queue,Path('models'),jid)
                with app.connect() as db:
                    job=dict(db.execute('SELECT * FROM media_jobs WHERE id=?',(jid,)).fetchone())
                    self.assertEqual(job['status'],'done');self.assertFalse(Path(job['path']).exists())
                    doc=dict(db.execute('SELECT * FROM documents WHERE id=?',(job['document_id'],)).fetchone())
                    self.assertEqual(doc['course_id'],cid);self.assertEqual(doc['source_type'],'video')
                    self.assertEqual({r['kind'] for r in db.execute('SELECT kind FROM jobs WHERE document_id=?',(doc['id'],))},{'summary','lesson'})
                    self.assertIn('00:01:04',app.retrieve(db,'pwd',document_id=doc['id'])[0]['text'])
                with request(f"documents/{doc['id']}/text") as response:
                    text=response.read().decode();self.assertIn('00:00:02',text);self.assertIn('ÉCRAN',text)
            finally:
                server.shutdown();server.server_close();thread.join()
