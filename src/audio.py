import queue
import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
import os

class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1, chunk_duration=2.0):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.q = queue.Queue()
        self.stream = None
        self.is_recording = False
        
        # Calculate chunk size in frames
        self.chunk_size = int(self.sample_rate * self.chunk_duration)

    def audio_callback(self, indata, frames, time, status):
        """This is called for each audio block by sounddevice."""
        if status:
            print(f"Audio status: {status}")
        self.q.put(indata.copy())

    def start_recording(self):
        """Starts the audio recording stream."""
        if self.is_recording:
            return
            
        # Empty the queue
        while not self.q.empty():
            self.q.get_nowait()
            
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self.audio_callback,
            blocksize=self.chunk_size # Process in chunks
        )
        self.stream.start()
        self.is_recording = True

    def stop_recording(self):
        """Stops the audio recording stream."""
        if not self.is_recording:
            return
            
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        self.is_recording = False

    def get_audio_chunk(self, timeout=None):
        """Gets the next audio chunk from the queue and saves it to a temp file."""
        if not self.is_recording and self.q.empty():
            return None
            
        try:
            # Get data from queue
            data = self.q.get(timeout=timeout)
            
            # Save to temp wav file
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd) # Close file descriptor, sf.write opens it again
            
            sf.write(temp_path, data, self.sample_rate)
            return temp_path
            
        except queue.Empty:
            return None
