import io
import json
import unittest
from unittest.mock import patch
import app
import test_learning


class ModelManagementTests(unittest.TestCase):
    setUp=test_learning.LearningTests.setUp
    tearDown=test_learning.LearningTests.tearDown

    def test_list_excludes_cloud_and_marks_active(self):
        tags={'models':[{'name':'qwen2.5:7b','size':100},{'name':'remote','remote_host':'server'},{'name':'model:cloud'}]}
        with app.connect() as db,patch.object(app,'ollama',return_value=tags):
            models=app.installed_models(db)
        self.assertEqual(len(models),1)
        self.assertTrue(models[0]['active'])

    def test_delete_protects_active_busy_and_missing(self):
        for values in [{'name':'model:7b','active':True,'busy':False},{'name':'model:7b','active':False,'busy':True},None]:
            with app.connect() as db,patch.object(app,'installed_models',return_value=[values] if values else []),patch('app.urllib.request.urlopen') as opened:
                with self.assertRaises(ValueError):app.delete_model(db,'model:7b')
                opened.assert_not_called()

    def test_delete_uses_ollama_api_without_modifying_documents(self):
        with app.connect() as db:
            before=db.execute('SELECT count(*) FROM documents').fetchone()[0]
        with app.connect() as db,patch.object(app,'installed_models',return_value=[{'name':'unused:7b','active':False,'busy':False}]),patch('app.urllib.request.urlopen',return_value=io.BytesIO(b'')) as opened:
            self.assertTrue(app.delete_model(db,'unused:7b')['ok'])
            self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],before)
        request=opened.call_args.args[0]
        self.assertEqual(request.method,'DELETE')
        self.assertEqual(request.full_url,app.OLLAMA+'/api/delete')
        self.assertEqual(json.loads(request.data),{'model':'unused:7b'})
