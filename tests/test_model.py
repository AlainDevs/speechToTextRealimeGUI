import pytest
import numpy as np
from src.model import VoxtralModel, _MockModel

def test_model_init():
    model = VoxtralModel()
    assert model.model is None
    assert model.current_model_name is None
    assert "4bit (Smaller/Faster)" in model.MODELS

def test_load_model_invalid_variant():
    model = VoxtralModel()
    with pytest.raises(ValueError, match="Unknown model variant"):
        model.load_model("NonExistent")

def test_load_model_mock_fallback(mocker):
    # Force ImportError on mlx_audio.stt.utils
    mocker.patch.dict("sys.modules", {"mlx_audio": None})
    
    model = VoxtralModel()
    model.load_model("4bit (Smaller/Faster)")
    
    assert isinstance(model.model, _MockModel)
    assert model.current_model_name == model.MODELS["4bit (Smaller/Faster)"]

def test_load_model_success_import(mocker):
    # Mock the actual load function
    mock_load = mocker.MagicMock()
    
    class DummyMLXAudio:
        class stt:
            class utils:
                load = mock_load
                
    mocker.patch.dict("sys.modules", {
        "mlx_audio": DummyMLXAudio,
        "mlx_audio.stt": DummyMLXAudio.stt,
        "mlx_audio.stt.utils": DummyMLXAudio.stt.utils
    })
    
    model = VoxtralModel()
    model.load_model("4bit (Smaller/Faster)")
    
    assert model.model == mock_load.return_value
    mock_load.assert_called_once_with(model.MODELS["4bit (Smaller/Faster)"])

def test_load_model_already_loaded(mocker):
    mocker.patch.dict("sys.modules", {"mlx_audio": None})
    model = VoxtralModel()
    model.load_model("4bit (Smaller/Faster)")
    first_model_instance = model.model
    
    # Load same again
    model.load_model("4bit (Smaller/Faster)")
    assert model.model is first_model_instance # Should not reload

def test_transcribe_array_not_loaded():
    model = VoxtralModel()
    with pytest.raises(RuntimeError, match="Model not loaded"):
        model.transcribe_array(np.zeros(16000))

def test_transcribe_array_success(mocker):
    mocker.patch.dict("sys.modules", {"mlx_audio": None})
    model = VoxtralModel()
    model.load_model("4bit (Smaller/Faster)")
    
    result = model.transcribe_array(np.zeros(16000))
    assert "Mock Streaming Output" in result

def test_transcribe_array_failure(mocker):
    mocker.patch.dict("sys.modules", {"mlx_audio": None})
    model = VoxtralModel()
    model.load_model("4bit (Smaller/Faster)")
    
    # Mock model.generate to raise Exception
    mocker.patch.object(model.model, 'generate', side_effect=Exception("Generation error"))
    
    with pytest.raises(RuntimeError, match="Transcription failed: Generation error"):
        model.transcribe_array(np.zeros(16000))
