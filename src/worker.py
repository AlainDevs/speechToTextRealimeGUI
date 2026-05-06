from PyQt6.QtCore import QThread, pyqtSignal
from src.model import VoxtralModel
from src.audio import AudioRecorder
import numpy as np
import time

class TranscriptionWorker(QThread):
    text_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, model_variant="4bit (Smaller/Faster)", capture_mic=True, capture_sys=False, sys_audio_method='soundcard'):
        super().__init__()
        self.model_variant = model_variant
        self.capture_mic = capture_mic
        self.capture_sys = capture_sys
        self.sys_audio_method = sys_audio_method
        self.is_running = False
        self.model = VoxtralModel()
        # 0.5 seconds chunks for low latency, fast continuous processing
        self.recorder = AudioRecorder(chunk_duration=0.5, capture_mic=self.capture_mic, capture_sys=self.capture_sys, sys_audio_method=self.sys_audio_method)
        self.silence_threshold = 0.01  # VAD threshold

    def run(self):
        self.is_running = True
        
        try:
            self.status_update.emit("Loading model...")
            self.model.load_model(self.model_variant)
            self.status_update.emit("Model loaded. Starting audio capture...")
            
            self.recorder.start_recording()
            self.status_update.emit("Recording and transcribing...")
            
            audio_buffer = []
            silence_frames = 0
            
            while self.is_running:
                # Wait for an audio chunk (blocking up to 1 sec)
                chunk_data = self.recorder.get_audio_chunk(timeout=1.0)
                
                if chunk_data is not None:
                    # Simple VAD: check max amplitude
                    if np.max(np.abs(chunk_data)) > self.silence_threshold:
                        audio_buffer.append(chunk_data)
                        silence_frames = 0
                    else:
                        if len(audio_buffer) > 0:
                            silence_frames += 1
                            audio_buffer.append(chunk_data)
                    
                    # If we have accumulated enough audio (e.g. >= 2.0 seconds) or
                    # we detected enough silence (e.g. 1.0 seconds) after speech, process it.
                    buffer_duration = len(audio_buffer) * self.recorder.chunk_duration
                    
                    if (buffer_duration >= 3.0) or (silence_frames * self.recorder.chunk_duration >= 1.0 and len(audio_buffer) > 0):
                        if self.is_running:
                            try:
                                # Combine all chunks in the buffer
                                combined_audio = np.concatenate(audio_buffer)
                                
                                # We might need to squeeze it if soundcard returns 2D arrays (frames, channels)
                                # and the model expects 1D. Let's do it safely.
                                if combined_audio.ndim > 1:
                                    combined_audio = combined_audio[:, 0]  # Take first channel
                                    
                                # Transcribe directly from array
                                text = self.model.transcribe_array(combined_audio)
                                if text and text.strip() and "[Mock" not in text:
                                    self.text_ready.emit(text.strip())
                                elif text and "[Mock" in text:
                                    self.text_ready.emit(text.strip())
                            except Exception as e:
                                self.error_occurred.emit(str(e))
                                
                        # Reset buffer
                        audio_buffer = []
                        silence_frames = 0
                        
        except Exception as e:
            self.error_occurred.emit(f"Worker Error: {str(e)}")
        finally:
            self.recorder.stop_recording()
            self.status_update.emit("Stopped.")
            
    def stop(self):
        self.is_running = False
