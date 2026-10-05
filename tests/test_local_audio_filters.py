import importlib.util
import pathlib
import sys
import types
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path, package=None):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if package:
        module.__package__ = package
    spec.loader.exec_module(module)
    return module


class LocalAudioFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = types.ModuleType('core.server.schema')
        schema.Task = type('Task', (), {})
        schema.Result = type('Result', (), {})
        sys.modules.setdefault('core.server.schema', schema)
        worker_package = types.ModuleType('test_worker_package')
        worker_package.logger = types.SimpleNamespace(info=lambda *a, **k: None)
        sys.modules['test_worker_package'] = worker_package
        cls.audio = load_module('test_audio_filter', ROOT / 'core/server/worker/audio.py', 'test_worker_package')
        cls.fillers = load_module('test_filler_filter', ROOT / 'core/server/worker/filler_filter.py')

    def test_silence_is_gated_but_quiet_speech_is_preserved(self):
        self.assertTrue(self.audio.is_near_silence(np.zeros(16000, dtype=np.float32), 16000))
        quiet_speech = np.sin(np.arange(16000) * (2 * np.pi * 180 / 16000)).astype(np.float32) * 0.003
        self.assertFalse(self.audio.is_near_silence(quiet_speech, 16000))

    def test_filler_only_suppression_and_substantive_text_preservation(self):
        self.assertTrue(self.fillers.is_filler_only('嗯，啊！'))
        self.assertTrue(self.fillers.is_filler_only('Uh-huh. Oh yeah!'))
        self.assertFalse(self.fillers.is_filler_only('嗯，我需要报税帮助。'))


if __name__ == '__main__':
    unittest.main()
