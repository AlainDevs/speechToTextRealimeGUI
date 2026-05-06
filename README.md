# Voxtral Realtime GUI

A desktop application for realtime speech-to-text transcription using Mistral's Voxtral 4B parameter model via `mlx-audio`.

## Features
- Realtime speech transcription using microphone input.
- Select between 4bit (smaller/faster) and fp16 (full precision) models.
- Start/Stop transcription streams.
- Save transcription output to a text file.
- Built with PyQt6 for a responsive UI and multithreading.

## Prerequisites
- macOS (Apple Silicon recommended for `mlx` performance)
- Python 3.9 or higher
- System microphone

## Installation

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Make sure your virtual environment is active, then run:

```bash
python -m src.gui
```

## Running Tests

To run the unit tests and check test coverage (requires `pytest` and `pytest-cov`):

```bash
pytest --cov=src tests/
```
