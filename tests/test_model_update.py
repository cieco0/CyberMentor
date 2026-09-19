import io
import json
import unittest
from unittest.mock import patch
from model_update import ModelUpdate


class ModelUpdateTests(unittest.TestCase):
    def test_stream_success_and_request(self):
        updater=ModelUpdate()
        stream=io.BytesIO(b'{"status":"pulling","completed":12,"total":20}\n{"status":"success"}\n')
        with patch('model_update.urllib.request.urlopen',return_value=stream) as opened:
            updater.run('qwen2.5:7b')
        self.assertEqual(updater.snapshot()['status'],'done')
        request=opened.call_args.args[0]
        self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/pull')
        self.assertEqual(json.loads(request.data),{'model':'qwen2.5:7b','stream':True})

    def test_incomplete_and_failed_streams(self):
        for content in [b'{"status":"pulling"}\n',b'{"error":"model not found"}\n']:
            updater=ModelUpdate()
            with patch('model_update.urllib.request.urlopen',return_value=io.BytesIO(content)):
                updater.run('missing')
            self.assertEqual(updater.snapshot()['status'],'error')

    def test_validation_and_concurrent_download(self):
        updater=ModelUpdate()
        for name in [None,'','../model','https://host/model','model:cloud','a b']:
            with self.assertRaises(ValueError):updater.start(name)
        with patch('model_update.threading.Thread') as thread:
            updater.start('qwen2.5:7b')
            thread.return_value.start.assert_called_once()
            with self.assertRaises(ValueError):updater.start('qwen2.5:3b')
