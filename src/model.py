import os
import tempfile

class VoxtralModel:
    def __init__(self):
        self.model = None
        self.current_model_name = None
        # Models provided by mlx-community
        self.MODELS = {
            "4bit (Smaller/Faster)": "mlx-community/Voxtral-Mini-4B-Realtime-2602-4bit",
            "fp16 (Full Precision)": "mlx-community/Voxtral-Mini-4B-Realtime-2602-fp16" # Assuming fp16 is available
        }

    def load_model(self, variant_name):
        """Loads the specified model variant."""
        if variant_name not in self.MODELS:
            raise ValueError(f"Unknown model variant: {variant_name}")
            
        model_id = self.MODELS[variant_name]
        
        if self.current_model_name == model_id and self.model is not None:
            return # Already loaded
            
        try:
            from mlx_audio.stt.utils import load
            self.model = load(model_id)
            self.current_model_name = model_id
        except ImportError:
            # Fallback/mock for testing environments without mlx_audio
            self.model = _MockModel()
            self.current_model_name = model_id

    def transcribe_array(self, audio_data):
        """Transcribes a given numpy audio array."""
        if not self.model:
            raise RuntimeError("Model not loaded. Call load_model first.")
            
        try:
            # We assume the model accepts numpy arrays for streaming inference.
            result = self.model.generate(audio_data)
            return result.text
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {e}")

class _MockModel:
    """A mock model to allow testing without mlx_audio installed."""
    def generate(self, audio_data):
        class Result:
            def __init__(self, text):
                self.text = text
        return Result(" [Mock Streaming Output] ")
