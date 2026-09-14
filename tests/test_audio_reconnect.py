import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.client.audio.stream import AudioStreamManager
import sounddevice as sd


class AudioReconnectTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.app = SimpleNamespace(loop=self.loop, state=SimpleNamespace(stream=None))
        self.manager = AudioStreamManager(self.app)

    def tearDown(self):
        self.manager.stop()
        self.loop.close()

    def test_missing_microphone_does_not_read_stdin_or_exit(self):
        with patch('builtins.input', side_effect=EOFError) as stdin, \
             patch.object(sd, 'query_devices', side_effect=sd.PortAudioError('No device')):
            self.assertIsNone(self.manager.start())
        stdin.assert_not_called()
        self.assertIsNotNone(self.manager._restart_timer)
        self.assertTrue(self.manager._want_running)

    def test_finished_callback_defers_recovery(self):
        self.manager._want_running = True
        with patch.object(self.manager, '_schedule_restart') as schedule:
            self.manager._on_stream_finished()
            schedule.assert_not_called()
            self.loop.run_until_complete(asyncio.sleep(0))
            schedule.assert_called_once()

    def test_reconnect_releases_old_stream_without_unloading_cffi(self):
        old, new = Mock(), Mock()
        self.app.state.stream = old
        self.manager._want_running = True
        with patch.object(sd, '_terminate') as terminate, \
             patch.object(sd, '_initialize') as initialize, \
             patch.object(sd, '_ffi') as ffi, \
             patch.object(sd, 'query_devices', return_value={'max_input_channels': 1, 'name': 'test'}), \
             patch.object(sd, 'InputStream', return_value=new):
            self.assertIs(self.manager.reopen(), new)
        old.close.assert_called_once()
        new.start.assert_called_once()
        terminate.assert_called_once()
        initialize.assert_called_once()
        ffi.dlclose.assert_not_called()
        self.assertTrue(self.manager._running)

    def test_stop_cancels_retry_and_prevents_restart(self):
        self.manager._want_running = True
        self.manager._schedule_restart()
        timer = self.manager._restart_timer
        self.manager.stop()
        self.assertTrue(timer.finished.is_set())
        self.assertIsNone(self.manager.reopen())
        self.assertIsNone(self.manager._restart_timer)

    def test_repeated_finished_callbacks_schedule_only_one_retry(self):
        self.manager._want_running = True
        with patch('core.client.audio.stream.threading.Timer') as timer:
            self.manager._on_stream_finished()
            self.manager._on_stream_finished()
            self.loop.run_until_complete(asyncio.sleep(0))
            timer.assert_called_once()
            timer.return_value.start.assert_called_once()

    def test_device_returns_after_failed_start(self):
        stream = Mock(active=True)
        with patch.object(sd, 'query_devices', side_effect=[
            sd.PortAudioError('No device'), {'max_input_channels': 1, 'name': 'Reconnected mic'}
        ]), patch.object(sd, 'InputStream', return_value=stream), \
             patch.object(sd, '_terminate'), patch.object(sd, '_initialize'):
            self.assertIsNone(self.manager.start())
            self.manager._restart_timer.cancel()
            self.manager._retry()
        self.assertIs(self.app.state.stream, stream)
        self.assertTrue(self.manager._running)
        self.assertIsNone(self.manager._restart_timer)

    def test_device_disappears_during_stream_start(self):
        stream = Mock(active=False)
        with patch.object(sd, 'query_devices', return_value={'max_input_channels': 1}), \
             patch.object(sd, 'InputStream', return_value=stream):
            self.assertIsNone(self.manager.start())
        stream.close.assert_called_once()
        self.assertFalse(self.manager._running)
        self.assertIsNotNone(self.manager._restart_timer)

    def test_stop_before_deferred_callback_prevents_retry(self):
        self.manager._want_running = True
        self.manager._on_stream_finished()
        self.manager.stop()
        with patch('core.client.audio.stream.threading.Timer') as timer:
            self.loop.run_until_complete(asyncio.sleep(0))
            timer.assert_not_called()

    def test_device_name_encoding_error_keeps_default_device_fallback(self):
        stream = Mock(active=True)
        with patch.object(sd, 'query_devices', side_effect=UnicodeDecodeError('utf8', b'\xff', 0, 1, 'invalid')), \
             patch.object(sd, 'InputStream', return_value=stream):
            self.assertIs(self.manager.start(), stream)

    def test_finished_callback_ignores_closed_event_loop(self):
        self.manager._want_running = True
        self.loop.close()
        self.manager._on_stream_finished()
        self.assertIsNone(self.manager._restart_timer)


if __name__ == '__main__':
    unittest.main()
