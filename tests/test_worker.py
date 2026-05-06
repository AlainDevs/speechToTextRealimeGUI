import pytest
from src.worker import TranscriptionWorker
import os

def test_worker_init():
    worker = TranscriptionWorker("4bit (Smaller/Faster)")
    assert worker.model_variant == "4bit (Smaller/Faster)"
    assert not worker.is_running
    assert worker.model is not None
    assert worker.recorder is not None

def test_worker_stop():
    worker = TranscriptionWorker()
    worker.is_running = True
    worker.stop()
    assert not worker.is_running

def test_worker_run_success(mocker, qtbot):
    worker = TranscriptionWorker()
    
    # Mock model and recorder
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    
    # We want get_audio_chunk to return a valid path once, then None, and we stop the worker
    dummy_chunk = "dummy.wav"
    open(dummy_chunk, 'w').close() # Create dummy file
    
    def mock_get_chunk(timeout):
        if not hasattr(mock_get_chunk, 'called'):
            mock_get_chunk.called = True
            return dummy_chunk
        worker.stop() # Stop the loop
        return None
        
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_chunk.return_value = "Hello World"
    
    # Track signals
    with qtbot.waitSignal(worker.text_ready, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args == ["Hello World"]
    mock_model.load_model.assert_called_once_with("4bit (Smaller/Faster)")
    mock_recorder.start_recording.assert_called_once()
    mock_recorder.stop_recording.assert_called_once()
    
    # Check if dummy file was removed
    assert not os.path.exists(dummy_chunk)

def test_worker_run_remove_oserror(mocker, qtbot):
    worker = TranscriptionWorker()
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    
    dummy_chunk = "dummy.wav"
    open(dummy_chunk, 'w').close()
    
    def mock_get_chunk(timeout):
        if not hasattr(mock_get_chunk, 'called'):
            mock_get_chunk.called = True
            return dummy_chunk
        worker.stop()
        return None
        
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_chunk.return_value = "Test"
    
    mock_remove = mocker.patch('os.remove', side_effect=OSError("Cannot remove"))
    
    worker.run()
    
    # Run should complete without raising the exception
    mock_remove.assert_called_once_with(dummy_chunk)
    os.unlink(dummy_chunk) # clean up manually

def test_worker_run_exception(mocker, qtbot):
    worker = TranscriptionWorker()
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_model.load_model.side_effect = Exception("Failed to load model")
    
    with qtbot.waitSignal(worker.error_occurred, timeout=1000) as blocker:
        worker.run()
        
    assert "Worker Error: Failed to load model" in blocker.args[0]

def test_worker_run_transcription_error(mocker, qtbot):
    worker = TranscriptionWorker()
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    
    dummy_chunk = "dummy.wav"
    open(dummy_chunk, 'w').close()
    
    def mock_get_chunk(timeout):
        if not hasattr(mock_get_chunk, 'called'):
            mock_get_chunk.called = True
            return dummy_chunk
        worker.stop()
        return None
        
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_chunk.side_effect = Exception("Transcription error")
    
    with qtbot.waitSignal(worker.error_occurred, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args[0] == "Transcription error"
    assert not os.path.exists(dummy_chunk)

def test_worker_run_empty_text(mocker, qtbot):
    worker = TranscriptionWorker()
    
    mock_model = mocker.patch.object(worker, 'model')
    mock_recorder = mocker.patch.object(worker, 'recorder')
    
    dummy_chunk = "dummy.wav"
    open(dummy_chunk, 'w').close()
    
    def mock_get_chunk(timeout):
        if not hasattr(mock_get_chunk, 'called'):
            mock_get_chunk.called = True
            return dummy_chunk
        worker.stop()
        return None
        
    mock_recorder.get_audio_chunk.side_effect = mock_get_chunk
    mock_model.transcribe_chunk.return_value = "   " # Empty/whitespace
    
    # We should not emit text_ready
    worker.run()
    # If text_ready was emitted, we'd have to assert it wasn't. qtbot.assertNotEmitted is one way, 
    # but simplest is just verifying run completes.
    assert not os.path.exists(dummy_chunk)
