import sys
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QComboBox, 
                             QLabel, QFileDialog, QMessageBox, QStatusBar, QCheckBox, QGroupBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from src.worker import TranscriptionWorker
from src.model import VoxtralModel
import soundcard as sc

class DriverInstallerThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, action):
        super().__init__()
        self.action = action # 'install' or 'uninstall'
        
    def run(self):
        try:
            if self.action == 'install':
                cmd = ['brew', 'install', 'blackhole-2ch']
            else:
                cmd = ['brew', 'uninstall', 'blackhole-2ch']
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Restart coreaudiod to apply changes
                subprocess.run(['killall', 'coreaudiod'], capture_output=True)
                self.finished_signal.emit(True, "Success")
            else:
                self.finished_signal.emit(False, result.stderr)
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voxtral Realtime Transcription")
        self.resize(600, 500)
        
        self.worker = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Controls layout
        controls_layout = QHBoxLayout()
        
        # Model Selection
        self.model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(list(VoxtralModel().MODELS.keys()))
        
        controls_layout.addWidget(self.model_label)
        controls_layout.addWidget(self.model_combo)
        
        # Audio Source Checkboxes
        self.mic_cb = QCheckBox("Capture Microphone")
        self.mic_cb.setChecked(True)
        self.sys_cb = QCheckBox("Capture System Audio")
        self.sys_cb.stateChanged.connect(self._on_sys_cb_changed)
        
        controls_layout.addWidget(self.mic_cb)
        controls_layout.addWidget(self.sys_cb)
        
        # macOS Virtual Driver Box
        if sys.platform == 'darwin':
            driver_box = QGroupBox("macOS System Audio Method")
            driver_layout = QVBoxLayout()
            
            self.sys_audio_method_combo = QComboBox()
            self.sys_audio_method_combo.addItems(["ScreenCaptureKit (Native, recommended)", "BlackHole (Virtual Driver)"])
            self.sys_audio_method_combo.currentIndexChanged.connect(self._on_sys_audio_method_changed)
            driver_layout.addWidget(self.sys_audio_method_combo)
            
            # Blackhole controls
            self.bh_controls = QWidget()
            bh_layout = QHBoxLayout(self.bh_controls)
            bh_layout.setContentsMargins(0, 0, 0, 0)
            
            self.install_driver_btn = QPushButton("Install BlackHole")
            self.uninstall_driver_btn = QPushButton("Uninstall BlackHole")
            
            self.install_driver_btn.clicked.connect(lambda: self.manage_driver('install'))
            self.uninstall_driver_btn.clicked.connect(lambda: self.manage_driver('uninstall'))
            
            bh_layout.addWidget(self.install_driver_btn)
            bh_layout.addWidget(self.uninstall_driver_btn)
            
            driver_layout.addWidget(self.bh_controls)
            self.bh_controls.setVisible(False) # Hidden by default since SCK is selected
            
            driver_box.setLayout(driver_layout)
            controls_layout.addWidget(driver_box)
            self._update_driver_buttons()
        
        # Start/Stop Buttons
        self.start_btn = QPushButton("Start Recording")
        self.start_btn.clicked.connect(self.start_recording)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        
        self.stop_btn = QPushButton("Stop Recording")
        self.stop_btn.clicked.connect(self.stop_recording)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        
        controls_layout.addWidget(self.start_btn)
        controls_layout.addWidget(self.stop_btn)
        
        controls_layout.addStretch()
        
        # Output Area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Transcription output will appear here...")
        
        # Bottom controls
        bottom_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("Clear Output")
        self.clear_btn.clicked.connect(self.output_text.clear)
        
        self.save_btn = QPushButton("Save Output")
        self.save_btn.clicked.connect(self.save_output)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.clear_btn)
        bottom_layout.addWidget(self.save_btn)
        
        # Add to main layout
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.output_text)
        main_layout.addLayout(bottom_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _on_sys_audio_method_changed(self, index):
        if index == 1:
            self.bh_controls.setVisible(True)
        else:
            self.bh_controls.setVisible(False)

    def _on_sys_cb_changed(self, state):
        if state == Qt.CheckState.Checked.value and sys.platform == 'darwin':
            if hasattr(self, 'sys_audio_method_combo') and self.sys_audio_method_combo.currentIndex() == 1:
                QMessageBox.information(self, "macOS System Audio", "To capture system audio on macOS:\n\n1. Ensure 'BlackHole' is installed.\n2. Open macOS System Settings -> Sound.\n3. Change your 'Output' device to 'BlackHole 2ch'.\n\nNote: You will not hear your computer's audio while BlackHole is set as the sole output. To hear it and record it, use 'Audio MIDI Setup' to create a Multi-Output Device.")
            elif hasattr(self, 'sys_audio_method_combo') and self.sys_audio_method_combo.currentIndex() == 0:
                QMessageBox.information(self, "ScreenCaptureKit Permissions", "ScreenCaptureKit natively captures system audio without virtual drivers.\n\nNOTE: You may be prompted to allow Screen Recording permissions in System Settings -> Privacy & Security for this application or your terminal.")

    def _update_driver_buttons(self):
        installed = False
        # Check if blackhole is installed via brew
        result = subprocess.run(['brew', 'list', 'blackhole-2ch'], capture_output=True)
        if result.returncode == 0:
            installed = True
                
        self.install_driver_btn.setVisible(not installed)
        self.uninstall_driver_btn.setVisible(installed)

    def manage_driver(self, action):
        self.install_driver_btn.setEnabled(False)
        self.uninstall_driver_btn.setEnabled(False)
        self.status_bar.showMessage(f"{action.capitalize()}ing BlackHole Virtual Driver... Please authorize if prompted.")
        
        self.driver_thread = DriverInstallerThread(action)
        self.driver_thread.finished_signal.connect(self._on_driver_managed)
        self.driver_thread.start()
        
    def _on_driver_managed(self, success, message):
        self.install_driver_btn.setEnabled(True)
        self.uninstall_driver_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", f"BlackHole Virtual Driver updated successfully.\n\nIMPORTANT: You must restart your Mac for the audio driver to appear in the system!\n\nAfter rebooting, to capture system audio, you must go to macOS System Settings -> Sound and set your Output to 'BlackHole 2ch'.")
            self._update_driver_buttons()
            self.status_bar.showMessage("Driver updated successfully", 5000)
        else:
            QMessageBox.critical(self, "Error", f"Failed to {self.driver_thread.action} BlackHole:\n{message}")
            self.status_bar.showMessage("Driver update failed", 5000)

    def start_recording(self):
        if not self.mic_cb.isChecked() and not self.sys_cb.isChecked():
            QMessageBox.warning(self, "Warning", "Please select at least one audio source.")
            return

        selected_model = self.model_combo.currentText()
        
        sys_method = 'soundcard'
        if sys.platform == 'darwin' and hasattr(self, 'sys_audio_method_combo'):
            if self.sys_audio_method_combo.currentIndex() == 0:
                sys_method = 'screencapturekit'
            else:
                sys_method = 'soundcard'
        
        self.worker = TranscriptionWorker(
            model_variant=selected_model,
            capture_mic=self.mic_cb.isChecked(),
            capture_sys=self.sys_cb.isChecked(),
            sys_audio_method=sys_method
        )
        self.worker.text_ready.connect(self.append_text)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.status_update.connect(self.update_status)
        self.worker.finished.connect(self.on_worker_finished)
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.model_combo.setEnabled(False)
        self.mic_cb.setEnabled(False)
        self.sys_cb.setEnabled(False)
        
        self.worker.start()

    def stop_recording(self):
        if self.worker and self.worker.isRunning():
            self.status_bar.showMessage("Stopping...")
            self.worker.stop()
            self.stop_btn.setEnabled(False) # Prevent multiple clicks

    def append_text(self, text):
        current_text = self.output_text.toPlainText()
        if current_text:
            self.output_text.setPlainText(current_text + " " + text)
        else:
            self.output_text.setPlainText(text)
            
        # Scroll to bottom
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_status(self, message):
        self.status_bar.showMessage(message)

    def handle_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)

    def on_worker_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.model_combo.setEnabled(True)
        self.mic_cb.setEnabled(True)
        self.sys_cb.setEnabled(True)
        if self.status_bar.currentMessage() == "Stopping...":
             self.status_bar.showMessage("Stopped.")

    def save_output(self):
        text = self.output_text.toPlainText()
        if not text:
            QMessageBox.warning(self, "Warning", "No text to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Transcription", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_bar.showMessage(f"Saved to {file_path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()

if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
