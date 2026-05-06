import pytest
import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from src.gui import MainWindow

@pytest.fixture
def app_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window

def test_initial_state(app_window):
    assert app_window.windowTitle() == "Voxtral Realtime Transcription"
    assert app_window.start_btn.isEnabled()
    assert not app_window.stop_btn.isEnabled()
    assert app_window.model_combo.isEnabled()
    assert app_window.output_text.isReadOnly()
    assert app_window.status_bar.currentMessage() == "Ready"

def test_start_recording(app_window, mocker, qtbot):
    # Mock the worker's start method to avoid thread running
    mock_worker_start = mocker.patch('src.worker.TranscriptionWorker.start')
    
    qtbot.mouseClick(app_window.start_btn, Qt.MouseButton.LeftButton)
    
    assert not app_window.start_btn.isEnabled()
    assert app_window.stop_btn.isEnabled()
    assert not app_window.model_combo.isEnabled()
    assert app_window.worker is not None
    mock_worker_start.assert_called_once()

def test_stop_recording(app_window, mocker, qtbot):
    mock_worker_start = mocker.patch('src.worker.TranscriptionWorker.start')
    qtbot.mouseClick(app_window.start_btn, Qt.MouseButton.LeftButton)
    
    mock_worker_stop = mocker.patch.object(app_window.worker, 'stop')
    mocker.patch.object(app_window.worker, 'isRunning', return_value=True)
    
    qtbot.mouseClick(app_window.stop_btn, Qt.MouseButton.LeftButton)
    
    assert app_window.status_bar.currentMessage() == "Stopping..."
    mock_worker_stop.assert_called_once()
    assert not app_window.stop_btn.isEnabled()

def test_append_text(app_window):
    app_window.append_text("Hello")
    assert app_window.output_text.toPlainText() == "Hello"
    
    app_window.append_text("World")
    assert app_window.output_text.toPlainText() == "Hello World"

def test_update_status(app_window):
    app_window.update_status("Testing Status")
    assert app_window.status_bar.currentMessage() == "Testing Status"

def test_handle_error(app_window, mocker):
    mock_critical = mocker.patch.object(QMessageBox, 'critical')
    app_window.handle_error("Test Error")
    mock_critical.assert_called_once_with(app_window, "Error", "Test Error")

def test_on_worker_finished(app_window):
    # Setup state as if recording
    app_window.start_btn.setEnabled(False)
    app_window.stop_btn.setEnabled(True)
    app_window.model_combo.setEnabled(False)
    app_window.status_bar.showMessage("Stopping...")
    
    app_window.on_worker_finished()
    
    assert app_window.start_btn.isEnabled()
    assert not app_window.stop_btn.isEnabled()
    assert app_window.model_combo.isEnabled()
    assert app_window.status_bar.currentMessage() == "Stopped."

def test_save_output_empty(app_window, mocker):
    mock_warning = mocker.patch.object(QMessageBox, 'warning')
    app_window.save_output()
    mock_warning.assert_called_once_with(app_window, "Warning", "No text to save.")

def test_save_output_success(app_window, mocker, tmp_path):
    app_window.output_text.setPlainText("Test Transcription")
    
    test_file = tmp_path / "output.txt"
    mock_get_save = mocker.patch.object(QFileDialog, 'getSaveFileName', return_value=(str(test_file), ""))
    
    app_window.save_output()
    
    assert os.path.exists(test_file)
    with open(test_file, 'r') as f:
        assert f.read() == "Test Transcription"
    assert f"Saved to {test_file}" in app_window.status_bar.currentMessage()

def test_save_output_error(app_window, mocker):
    app_window.output_text.setPlainText("Test Transcription")
    
    # Return a path that is invalid to force an exception
    # Alternatively mock open
    mock_get_save = mocker.patch.object(QFileDialog, 'getSaveFileName', return_value=("/invalid/path/output.txt", ""))
    mock_critical = mocker.patch.object(QMessageBox, 'critical')
    
    app_window.save_output()
    
    mock_critical.assert_called_once()

def test_close_event(app_window, mocker):
    # Setup worker
    mock_worker_start = mocker.patch('src.worker.TranscriptionWorker.start')
    app_window.start_recording()
    
    mock_worker_stop = mocker.patch.object(app_window.worker, 'stop')
    mock_worker_wait = mocker.patch.object(app_window.worker, 'wait')
    mocker.patch.object(app_window.worker, 'isRunning', return_value=True)
    
    class MockEvent:
        def __init__(self):
            self.accepted = False
        def accept(self):
            self.accepted = True
            
    event = MockEvent()
    app_window.closeEvent(event)
    
    mock_worker_stop.assert_called_once()
    mock_worker_wait.assert_called_once()
    assert event.accepted
