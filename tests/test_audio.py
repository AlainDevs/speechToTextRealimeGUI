import pytest
import numpy as np
import queue
import sys
import builtins
import ctypes
from src.audio import AudioRecorder, SCKAudioRecorder, get_loopback_device

@pytest.fixture
def recorder():
    return AudioRecorder(sample_rate=16000, chunk_duration=0.1, capture_mic=True, capture_sys=False)

def test_get_loopback_device(mocker):
    mocker.patch('sys.platform', 'darwin')
    mock_all_mic = mocker.patch('soundcard.all_microphones')
    mock_mic1 = mocker.MagicMock(name='Built-in')
    mock_mic1.name = "Built-in Microphone"
    mock_mic2 = mocker.MagicMock(name='BlackHole')
    mock_mic2.name = "BlackHole 2ch"
    
    mock_all_mic.return_value = [mock_mic1, mock_mic2]
    assert get_loopback_device() == mock_mic2
    
    mock_all_mic.return_value = [mock_mic1]
    assert get_loopback_device() is None
    
    mocker.patch('sys.platform', 'win32')
    mock_default_spk = mocker.patch('soundcard.default_speaker')
    assert get_loopback_device() == mock_default_spk.return_value

def test_recorder_init(recorder):
    assert recorder.sample_rate == 16000
    assert recorder.chunk_size == 1600
    assert not recorder.is_recording
    assert recorder.capture_mic is True
    assert recorder.capture_sys is False
    assert recorder.sck_recorder is None

def test_recorder_init_sck(mocker):
    mocker.patch('sys.platform', 'darwin')
    rec = AudioRecorder(sample_rate=16000, capture_mic=False, capture_sys=True, sys_audio_method='screencapturekit')
    assert rec.sck_recorder is not None

def test_start_stop_recording(recorder, mocker):
    mock_thread = mocker.patch('threading.Thread')
    recorder.q.put(np.zeros((10,1)))
    recorder.start_recording()
    assert recorder.is_recording
    assert recorder.q.empty()
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()
    
    recorder.start_recording()
    assert mock_thread.call_count == 1
    
    recorder._thread = mock_thread.return_value
    recorder.stop_recording()
    assert not recorder.is_recording
    mock_thread.return_value.join.assert_called_once()

def test_start_stop_recording_sck(mocker):
    mocker.patch('sys.platform', 'darwin')
    rec = AudioRecorder(sample_rate=16000, capture_mic=False, capture_sys=True, sys_audio_method='screencapturekit')
    mock_sck_start = mocker.patch.object(rec.sck_recorder, 'start')
    mock_sck_stop = mocker.patch.object(rec.sck_recorder, 'stop')
    mock_thread = mocker.patch('threading.Thread')
    
    rec.start_recording()
    mock_sck_start.assert_called_once()
    
    rec.stop_recording()
    mock_sck_stop.assert_called_once()

def test_sck_recorder_start_stop(mocker):
    sck = SCKAudioRecorder()
    assert not sck.is_recording
    
    mock_thread = mocker.patch('threading.Thread')
    sck.start()
    assert sck.is_recording
    mock_thread.assert_called_once()
    
    # Early return test
    sck.start()
    assert mock_thread.call_count == 1
    
    sck._stream = mocker.MagicMock()
    sck._run_loop = mocker.MagicMock()
    sck._thread = mock_thread.return_value
    
    import sys
    sys.modules['CoreFoundation'] = mocker.MagicMock()
    sck.stop()
    assert not sck.is_recording
    sck._stream.stopCaptureWithCompletionHandler_.assert_called_once()
    mock_thread.return_value.join.assert_called_once()
    assert sck._thread is None
    del sys.modules['CoreFoundation']

def test_sck_recorder_stop_exception(mocker):
    sck = SCKAudioRecorder()
    sck.is_recording = True
    sck._stream = mocker.MagicMock()
    sck._stream.stopCaptureWithCompletionHandler_.side_effect = Exception("error")
    sck._run_loop = mocker.MagicMock()
    
    import sys
    sys.modules['CoreFoundation'] = mocker.MagicMock()
    sys.modules['CoreFoundation'].CFRunLoopStop.side_effect = Exception("error")
    
    sck.stop()
    assert not sck.is_recording
    
    del sys.modules['CoreFoundation']

def test_sck_recorder_run_import_error(mocker):
    sck = SCKAudioRecorder()
    sck.is_recording = True
    
    # Mock ImportError by removing objc
    import sys
    sys.modules['objc'] = None
    
    sck._run()
    assert not sck.is_recording
    
    if 'objc' in sys.modules:
        del sys.modules['objc']

def test_get_audio_chunk_not_recording(recorder):
    assert recorder.get_audio_chunk() is None

def test_record_loop_no_loopback_device(recorder, mocker):
    mocker.patch('src.audio.get_loopback_device', return_value=None)
    mock_mic = mocker.patch('soundcard.default_microphone')
    mock_mic_rec = mock_mic.return_value.recorder.return_value
    
    mic_data = np.ones((1600, 1))
    
    recorder.capture_mic = True
    recorder.capture_sys = True
    recorder.sys_audio_method = 'soundcard'
    recorder.is_recording = True
    
    def stop_loop_mic(*args, **kwargs):
        recorder.is_recording = False
        return mic_data
    mock_mic_rec.record.side_effect = stop_loop_mic
    
    # capturing print output could be done, but we just want coverage
    recorder._record_loop()
    assert not recorder.q.empty()
    np.testing.assert_array_equal(recorder.get_audio_chunk(), mic_data)

def test_get_audio_chunk_empty_queue(recorder, mocker):
    mocker.patch('threading.Thread')
    recorder.start_recording()
    assert recorder.get_audio_chunk(timeout=0.01) is None
    recorder.stop_recording()

def test_get_audio_chunk_success(recorder, mocker):
    mocker.patch('threading.Thread')
    recorder.start_recording()
    dummy_data = np.zeros((1600, 1))
    recorder.q.put(dummy_data)
    chunk = recorder.get_audio_chunk()
    assert chunk is not None
    np.testing.assert_array_equal(chunk, dummy_data)
    recorder.stop_recording()

def test_record_loop(recorder, mocker):
    mocker.patch('src.audio.get_loopback_device', return_value=mocker.MagicMock())
    mock_mic = mocker.patch('soundcard.default_microphone')
    mock_spk = mocker.patch('src.audio.get_loopback_device')
    
    mock_mic_rec = mock_mic.return_value.recorder.return_value
    mock_spk_rec = mock_spk.return_value.recorder.return_value
    
    mic_data = np.ones((1600, 1))
    sys_data = np.ones((1600, 1)) * 3
    
    mock_mic_rec.record.return_value = mic_data
    mock_spk_rec.record.return_value = sys_data
    
    # Test only mic
    recorder.is_recording = True
    def stop_loop_mic(*args, **kwargs):
        recorder.is_recording = False
        return mic_data
    mock_mic_rec.record.side_effect = stop_loop_mic
    recorder._record_loop()
    assert not recorder.q.empty()
    np.testing.assert_array_equal(recorder.q.get(), mic_data)
    
    # Test only sys
    recorder.capture_mic = False
    recorder.capture_sys = True
    recorder.is_recording = True
    def stop_loop_sys(*args, **kwargs):
        recorder.is_recording = False
        return sys_data
    mock_spk_rec.record.side_effect = stop_loop_sys
    recorder._record_loop()
    assert not recorder.q.empty()
    np.testing.assert_array_equal(recorder.q.get(), sys_data)

    # Test both mic and sys
    recorder.capture_mic = True
    recorder.capture_sys = True
    recorder.is_recording = True
    call_count = [0]
    def stop_loop_both_mic(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] >= 2:
            recorder.is_recording = False
        return mic_data
    def stop_loop_both_sys(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] >= 2:
            recorder.is_recording = False
        return sys_data
        
    mock_mic_rec.record.side_effect = stop_loop_both_mic
    mock_spk_rec.record.side_effect = stop_loop_both_sys
    recorder._record_loop()
    
    assert not recorder.q.empty()
    np.testing.assert_array_equal(recorder.q.get(), np.ones((1600, 1)) * 2.0)

def test_record_loop_with_sck(mocker):
    mocker.patch('sys.platform', 'darwin')
    rec = AudioRecorder(sample_rate=16000, capture_mic=True, capture_sys=True, sys_audio_method='screencapturekit')
    
    mock_mic = mocker.patch('soundcard.default_microphone')
    mock_mic_rec = mock_mic.return_value.recorder.return_value
    
    mic_data = np.ones((1600, 1))
    sck_data = np.ones((1600, 1)) * 5
    
    rec.is_recording = True
    rec.sck_recorder.q.put(sck_data)
    
    def stop_loop_mic(*args, **kwargs):
        rec.is_recording = False
        return mic_data
    mock_mic_rec.record.side_effect = stop_loop_mic
    
    rec._record_loop()
    assert not rec.q.empty()
    chunk = rec.q.get()
    np.testing.assert_array_equal(chunk, np.ones((1600, 1)) * 3.0)

def test_record_loop_sck_only(mocker):
    mocker.patch('sys.platform', 'darwin')
    rec = AudioRecorder(sample_rate=16000, capture_mic=False, capture_sys=True, sys_audio_method='screencapturekit')
    
    sck_data = np.ones((1600, 1)) * 5
    rec.is_recording = True
    rec.sck_recorder.q.put(sck_data)
    
    original_get = rec.sck_recorder.q.get
    def mock_get():
        rec.is_recording = False
        return original_get()
        
    rec.sck_recorder.q.get = mock_get
    
    rec._record_loop()
    assert not rec.q.empty()
    chunk = rec.q.get()
    np.testing.assert_array_equal(chunk, sck_data)

def test_record_loop_sck_only_wait(mocker):
    mocker.patch('sys.platform', 'darwin')
    rec = AudioRecorder(sample_rate=16000, capture_mic=False, capture_sys=True, sys_audio_method='screencapturekit')
    
    rec.is_recording = True
    mock_sleep = mocker.patch('time.sleep')
    
    call_count = [0]
    def mock_sleep_side_effect(*args):
        call_count[0] += 1
        if call_count[0] >= 2:
            rec.is_recording = False
            
    mock_sleep.side_effect = mock_sleep_side_effect
    rec._record_loop()
    
    assert rec.q.empty()
    assert mock_sleep.call_count == 2
