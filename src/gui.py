import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QComboBox, 
                             QLabel, QFileDialog, QMessageBox, QStatusBar, QCheckBox)
from PyQt6.QtCore import Qt
from src.worker import TranscriptionWorker
from src.model import VoxtralModel

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

    def start_recording(self):
        selected_model = self.model_combo.currentText()
        
        self.worker = TranscriptionWorker(model_variant=selected_model)
        self.worker.text_ready.connect(self.append_text)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.status_update.connect(self.update_status)
        self.worker.finished.connect(self.on_worker_finished)
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.model_combo.setEnabled(False)
        
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
