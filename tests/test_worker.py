import pytest
import numpy as np
from src.worker import TranscriptionWorker

def test_worker_init():
    worker = TranscriptionWorker("4bit (Smaller/Faster)")
    assert worker.model_variant == "4bit (Smaller/Faster)"
    assert not worker.is_running
    assert worker.model is not None
    assert worker.recorder is not None
    assert worker.capture_mic is True
    assert worker.capture_sys is False

def test_worker_stop():
    worker = TranscriptionWorker()
    worker.is_running = True
    worker.stop()
    assert not worker.is_running

def test_worker_run_success_mock(mocker, qtbot):
    worker = TranscriptionWorker()
    worker.silence_threshold = 0.0 # Make it process always
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    mock_recorder.chunk_duration = 0.5
    
    dummy_chunk = np.ones((16000, 1))
    silent_chunk = np.zeros((16000, 1))
    
    call_count = [0]
    def mock_get_chunk(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return dummy_chunk
        elif call_count[0] <= 3:
            return silent_chunk
        else:
            worker.stop()
            return None
        
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_array.return_value = " [Mock Streaming Output] "
    
    with qtbot.waitSignal(worker.text_ready, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args == ["[Mock Streaming Output]"]

def test_worker_run_success(mocker, qtbot):
    worker = TranscriptionWorker()
    worker.silence_threshold = 0.0 # Make it process always
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    mock_recorder.chunk_duration = 0.5
    
    # We want get_audio_chunk to return a valid chunk a few times, then None and stop
    # To trigger the >= 3.0s processing or silence processing. Let's trigger silence processing.
    # 0.5s chunk, if we send 1 chunk then silence, it should process
    
    dummy_chunk = np.ones((16000, 1)) # high energy
    silent_chunk = np.zeros((16000, 1))
    
    call_count = [0]
    def mock_get_chunk(timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return dummy_chunk
        elif call_count[0] <= 3:
            return silent_chunk
        else:
            worker.stop()
            return None
        
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_array.return_value = "Hello World"
    
    # Track signals
    with qtbot.waitSignal(worker.text_ready, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args == ["Hello World"]
    mock_model.load_model.assert_called_once_with("4bit (Smaller/Faster)")
    mock_recorder.start_recording.assert_called_once()
    mock_recorder.stop_recording.assert_called_once()
    mock_model.transcribe_array.assert_called_once()

def test_worker_run_exception(mocker, qtbot):
    worker = TranscriptionWorker()
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_model.load_model.side_effect = Exception("Failed to load model")
    
    with qtbot.waitSignal(worker.error_occurred, timeout=1000) as blocker:
        worker.run()
        
    assert "Worker Error: Failed to load model" in blocker.args[0]

def test_worker_run_transcription_error(mocker, qtbot):
    worker = TranscriptionWorker()
    worker.silence_threshold = 0.0
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    mock_recorder.chunk_duration = 0.5
    
    dummy_chunk = np.ones((16000, 1))
    silent_chunk = np.zeros((16000, 1))
    
    call_count = [0]
    def mock_get_chunk(timeout):
        call_count[0] += 1
        if call_count[0] == 1: return dummy_chunk
        elif call_count[0] <= 3: return silent_chunk
        else:
            worker.stop()
            return None
            
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_array.side_effect = Exception("Transcription error")
    
    with qtbot.waitSignal(worker.error_occurred, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args[0] == "Transcription error"

def test_worker_run_empty_text(mocker, qtbot):
    worker = TranscriptionWorker()
    worker.silence_threshold = 0.0
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    mock_recorder.chunk_duration = 0.5
    
    dummy_chunk = np.ones((16000, 1))
    silent_chunk = np.zeros((16000, 1))
    
    call_count = [0]
    def mock_get_chunk(timeout):
        call_count[0] += 1
        if call_count[0] == 1: return dummy_chunk
        elif call_count[0] <= 3: return silent_chunk
        else:
            worker.stop()
            return None
            
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_array.return_value = "   " # Empty/whitespace
    
    worker.run()
    # verify run completes without emitting text_ready
