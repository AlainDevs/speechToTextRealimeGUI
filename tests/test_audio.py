import pytest
import numpy as np
import queue
import os
from src.audio import AudioRecorder

@pytest.fixture
def recorder():
    return AudioRecorder(sample_rate=16000, chunk_duration=1.0)

def test_recorder_init(recorder):
    assert recorder.sample_rate == 16000
    assert recorder.chunk_size == 16000
    assert not recorder.is_recording

def test_start_stop_recording(recorder, mocker):
    mock_stream = mocker.patch('sounddevice.InputStream')
    
    # Put something in queue to test emptying
    recorder.q.put(np.zeros((10,1)))
    
    recorder.start_recording()
    assert recorder.is_recording
    assert recorder.q.empty()
    mock_stream.assert_called_once()
    mock_stream.return_value.start.assert_called_once()
    
    # Starting again should return early
    recorder.start_recording()
    assert mock_stream.call_count == 1
    
    recorder.stop_recording()
    assert not recorder.is_recording
    mock_stream.return_value.stop.assert_called_once()
    mock_stream.return_value.close.assert_called_once()
    
    # Stopping again should return early
    recorder.stop_recording()
    assert mock_stream.return_value.stop.call_count == 1

def test_audio_callback(recorder):
    dummy_data = np.zeros((100, 1))
    recorder.audio_callback(dummy_data, 100, None, None)
    
    assert not recorder.q.empty()
    queued_data = recorder.q.get_nowait()
    np.testing.assert_array_equal(queued_data, dummy_data)

def test_audio_callback_with_status(recorder, capsys):
    dummy_data = np.zeros((100, 1))
    recorder.audio_callback(dummy_data, 100, None, "input overflow")
    
    captured = capsys.readouterr()
    assert "Audio status: input overflow" in captured.out

def test_get_audio_chunk_not_recording(recorder):
    assert recorder.get_audio_chunk() is None

def test_get_audio_chunk_empty_queue(recorder, mocker):
    mocker.patch('sounddevice.InputStream')
    recorder.start_recording()
    assert recorder.get_audio_chunk(timeout=0.1) is None
    recorder.stop_recording()

def test_get_audio_chunk_success(recorder, mocker):
    mocker.patch('sounddevice.InputStream')
    mock_sf_write = mocker.patch('soundfile.write')
    
    recorder.start_recording()
    
    # Put fake data
    dummy_data = np.zeros((16000, 1))
    recorder.q.put(dummy_data)
    
    chunk_path = recorder.get_audio_chunk()
    
    assert chunk_path is not None
    assert chunk_path.endswith('.wav')
    mock_sf_write.assert_called_once()
    assert mock_sf_write.call_args[0][0] == chunk_path
    
    # Cleanup
    if os.path.exists(chunk_path):
        os.remove(chunk_path)
    recorder.stop_recording()
