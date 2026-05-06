from PyQt6.QtCore import QThread, pyqtSignal
from src.model import VoxtralModel
from src.audio import AudioRecorder
import os

class TranscriptionWorker(QThread):
    text_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, model_variant="4bit (Smaller/Faster)"):
        super().__init__()
        self.model_variant = model_variant
        self.is_running = False
        self.model = VoxtralModel()
        self.recorder = AudioRecorder(chunk_duration=3.0) # 3 seconds chunks

    def run(self):
        self.is_running = True
        
        try:
            self.status_update.emit("Loading model...")
            self.model.load_model(self.model_variant)
            self.status_update.emit("Model loaded. Starting microphone...")
            
            self.recorder.start_recording()
            self.status_update.emit("Recording and transcribing...")
            
            while self.is_running:
                # Wait for an audio chunk (blocking up to 1 sec)
                chunk_path = self.recorder.get_audio_chunk(timeout=1.0)
                
                if chunk_path:
                    if self.is_running:
                        try:
                            # Transcribe
                            text = self.model.transcribe_chunk(chunk_path)
                            if text and text.strip():
                                self.text_ready.emit(text)
                        except Exception as e:
                            self.error_occurred.emit(str(e))
                            
                    # Clean up temp file
                    try:
                        os.remove(chunk_path)
                    except OSError:
                        pass
                        
        except Exception as e:
            self.error_occurred.emit(f"Worker Error: {str(e)}")
        finally:
            self.recorder.stop_recording()
            self.status_update.emit("Stopped.")
            
    def stop(self):
        self.is_running = False
