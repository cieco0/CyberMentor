import unittest
from unittest.mock import patch
import hardware


class HardwareTests(unittest.TestCase):
    def test_recommendation_reserves_memory(self):
        self.assertEqual(hardware.recommend(32,8)[0],'qwen3.5:4b')
        self.assertEqual(hardware.recommend(32,16)[0],'qwen3.5:9b')
        self.assertEqual(hardware.recommend(8,0)[0],'qwen3.5:2b')

    def test_unknown_hardware_does_not_claim_gpu_support(self):
        with patch.object(hardware,'command',side_effect=OSError('unavailable')):
            result=hardware.scan('.')
        self.assertEqual(result['gpus'],[])
        self.assertEqual(result['ram'],0)
        self.assertTrue(result['notes'])

    def test_multiple_gpus_are_not_summed(self):
        with patch.object(hardware,'command',side_effect=['{"ram":34359738368,"cpu":"Test CPU"}','GPU 1, 8192\nGPU 2, 8192']):
            result=hardware.scan('.')
        self.assertEqual(result['model'],'qwen3.5:4b')
