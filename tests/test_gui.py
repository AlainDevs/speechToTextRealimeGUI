import pytest
import os
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from src.gui import MainWindow, DriverInstallerThread
import subprocess

@pytest.fixture(autouse=True)
def mock_audio_devices(mocker):
    mocker.patch('soundcard.all_microphones', return_value=[])

@pytest.fixture
def app_window(qtbot, mocker):
    mocker.patch('sys.platform', 'darwin')
    mocker.patch('subprocess.run', return_value=mocker.MagicMock(returncode=0))
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
    mock_worker_start = mocker.patch('src.worker.TranscriptionWorker.start')
    
    app_window.mic_cb.setChecked(True)
    qtbot.mouseClick(app_window.start_btn, Qt.MouseButton.LeftButton)
    
    assert not app_window.start_btn.isEnabled()
    assert app_window.stop_btn.isEnabled()
    assert not app_window.model_combo.isEnabled()
    assert not app_window.mic_cb.isEnabled()
    assert not app_window.sys_cb.isEnabled()
    assert app_window.worker is not None
    mock_worker_start.assert_called_once()

def test_start_recording_no_source(app_window, mocker, qtbot):
    mock_warning = mocker.patch.object(QMessageBox, 'warning')
    app_window.mic_cb.setChecked(False)
    app_window.sys_cb.setChecked(False)
    
    qtbot.mouseClick(app_window.start_btn, Qt.MouseButton.LeftButton)
    
    mock_warning.assert_called_once_with(app_window, "Warning", "Please select at least one audio source.")

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
    app_window.start_btn.setEnabled(False)
    app_window.stop_btn.setEnabled(True)
    app_window.model_combo.setEnabled(False)
    app_window.status_bar.showMessage("Stopping...")
    
    app_window.on_worker_finished()
    
    assert app_window.start_btn.isEnabled()
    assert not app_window.stop_btn.isEnabled()
    assert app_window.model_combo.isEnabled()
    assert app_window.mic_cb.isEnabled()
    assert app_window.sys_cb.isEnabled()
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
    mock_get_save = mocker.patch.object(QFileDialog, 'getSaveFileName', return_value=("/invalid/path/output.txt", ""))
    mock_critical = mocker.patch.object(QMessageBox, 'critical')
    
    app_window.save_output()
    mock_critical.assert_called_once()

def test_close_event(app_window, mocker):
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

def test_driver_installer_thread(mocker, qtbot):
    mock_run = mocker.patch('subprocess.run')
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    thread = DriverInstallerThread('install')
    
    with qtbot.waitSignal(thread.finished_signal, timeout=1000) as blocker:
        thread.run()
    assert blocker.args == [True, "Success"]
    assert mock_run.call_count == 2
    
    mock_run.reset_mock()
    thread.action = 'uninstall'
    with qtbot.waitSignal(thread.finished_signal, timeout=1000) as blocker:
        thread.run()
    assert blocker.args == [True, "Success"]
    
    mock_run.reset_mock()
    mock_result.returncode = 1
    mock_result.stderr = "Error msg"
    with qtbot.waitSignal(thread.finished_signal, timeout=1000) as blocker:
        thread.run()
    assert blocker.args == [False, "Error msg"]
    
    mock_run.reset_mock()
    mock_run.side_effect = Exception("Crash")
    with qtbot.waitSignal(thread.finished_signal, timeout=1000) as blocker:
        thread.run()
    assert blocker.args == [False, "Crash"]

def test_manage_driver(app_window, mocker):
    mock_thread_start = mocker.patch.object(DriverInstallerThread, 'start')
    
    app_window.manage_driver('install')
    assert not app_window.install_driver_btn.isEnabled()
    assert not app_window.uninstall_driver_btn.isEnabled()
    mock_thread_start.assert_called_once()
    
    mock_info = mocker.patch.object(QMessageBox, 'information')
    app_window._on_driver_managed(True, "Success")
    assert app_window.install_driver_btn.isEnabled()
    assert app_window.uninstall_driver_btn.isEnabled()
    mock_info.assert_called_once()
    
    mock_critical = mocker.patch.object(QMessageBox, 'critical')
    app_window._on_driver_managed(False, "Error")
    mock_critical.assert_called_once()

def test_sys_audio_cb_changed(app_window, mocker):
    mock_info = mocker.patch.object(QMessageBox, 'information')
    
    # Check ScreenCaptureKit branch
    app_window.sys_audio_method_combo.setCurrentIndex(0)
    app_window.sys_cb.setChecked(True)
    mock_info.assert_called_with(app_window, "ScreenCaptureKit Permissions", mocker.ANY)
    
    app_window.sys_cb.setChecked(False)
    
    # Check BlackHole branch
    app_window.sys_audio_method_combo.setCurrentIndex(1)
    app_window.sys_cb.setChecked(True)
    mock_info.assert_called_with(app_window, "macOS System Audio", mocker.ANY)

def test_sys_audio_method_combo_changed(app_window):
    assert app_window.bh_controls.isHidden()
    
    app_window.sys_audio_method_combo.setCurrentIndex(1)
    assert not app_window.bh_controls.isHidden()
    
    app_window.sys_audio_method_combo.setCurrentIndex(0)
    assert app_window.bh_controls.isHidden()

def test_start_recording_macos_method(app_window, mocker, qtbot):
    mock_worker_start = mocker.patch('src.worker.TranscriptionWorker.start')
    app_window.sys_cb.setChecked(True)
    
    app_window.sys_audio_method_combo.setCurrentIndex(1) # Blackhole -> soundcard
    qtbot.mouseClick(app_window.start_btn, Qt.MouseButton.LeftButton)
    assert app_window.worker.sys_audio_method == 'soundcard'
    app_window.worker.stop()
    
    app_window.start_btn.setEnabled(True)
    app_window.sys_audio_method_combo.setCurrentIndex(0) # SCK -> screencapturekit
    qtbot.mouseClick(app_window.start_btn, Qt.MouseButton.LeftButton)
    assert app_window.worker.sys_audio_method == 'screencapturekit'
