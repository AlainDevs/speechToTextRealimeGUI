import queue
import numpy as np
import soundcard as sc
import threading
import sys
import warnings

# Suppress soundcard macOS loopback warning since we use virtual drivers
warnings.filterwarnings("ignore", message="macOS does not support loopback recording functionality")

def get_loopback_device():
    if sys.platform == 'darwin':
        # macOS doesn't support native loopback. Find BlackHole.
        for m in sc.all_microphones(include_loopback=True):
            if "BlackHole" in m.name or "ZoomAudioDevice" in m.name or "Teams" in m.name:
                return m
        return None
    else:
        # Windows/Linux support default speaker loopback
        return sc.default_speaker()

class SCKAudioRecorder:
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.q = queue.Queue()
        self.is_recording = False
        self._thread = None
        self._run_loop = None
        self._stream = None
        self._delegate = None

    def start(self):
        if self.is_recording:
            return
        self.is_recording = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_recording = False
        if self._stream:
            stream = self._stream
            try:
                stream.stopCaptureWithCompletionHandler_(None)
            except:
                pass
            self._delegate = None
        if self._run_loop:
            try:
                from CoreFoundation import CFRunLoopStop
                CFRunLoopStop(self._run_loop.getCFRunLoop())
            except:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self):
        try: # pragma: no cover
            import objc
            from ScreenCaptureKit import (
                SCShareableContent,
                SCStreamConfiguration,
                SCStream,
                SCContentFilter,
                SCStreamOutputTypeAudio
            )
            from CoreMedia import CMSampleBufferGetDataBuffer
            from Foundation import NSObject, NSRunLoop, NSDefaultRunLoopMode, NSDate
        except ImportError: # pragma: no cover
            print("ScreenCaptureKit not available")
            self.is_recording = False
            return

        # Avoid re-registering the Objective-C class if it was already created in a previous thread
        if not hasattr(self.__class__, "_sck_delegate_class"):
            class SCKAudioDelegate(NSObject):  # pragma: no cover
                def init_(self, recorder):
                    self = objc.super(SCKAudioDelegate, self).init()
                    if self is None: return None
                    self.recorder = recorder
                    return self

                def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, ofType):
                    if ofType == SCStreamOutputTypeAudio and self.recorder.is_recording:
                        from CoreMedia import CMBlockBufferCopyDataBytes, CMBlockBufferGetDataLength
                        import ctypes
                        block_buffer = CMSampleBufferGetDataBuffer(sampleBuffer)
                        if block_buffer:
                            try:
                                totalLength = CMBlockBufferGetDataLength(block_buffer)
                                if totalLength > 0:
                                    buffer_array = (ctypes.c_char * totalLength)()
                                    CMBlockBufferCopyDataBytes(block_buffer, 0, totalLength, buffer_array)
                                    buffer = bytes(buffer_array)
                                    audio_data = np.frombuffer(buffer, dtype=np.float32)
                                    audio_data = audio_data.reshape(-1, self.recorder.channels)
                                    self.recorder.q.put(audio_data)
                            except Exception:
                                pass
            self.__class__._sck_delegate_class = SCKAudioDelegate

        self._run_loop = NSRunLoop.currentRunLoop()  # pragma: no cover

        def completion_handler(content, error):  # pragma: no cover
            if error or not content:
                print(f"SCK Error: {error}")
                return

            displays = content.displays()
            if not displays:
                print("SCK: No displays found")
                return

            display = displays[0]

            config = SCStreamConfiguration.alloc().init()
            config.setCapturesAudio_(True)
            config.setSampleRate_(self.sample_rate)
            config.setChannelCount_(self.channels)

            filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
                display, [], []
            )

            self._stream = SCStream.alloc().initWithFilter_configuration_delegate_(
                filter, config, None
            )

            self._delegate = self.__class__._sck_delegate_class.alloc().init_(self)
            
            self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
                self._delegate, SCStreamOutputTypeAudio, None, None
            )
            self._stream.startCaptureWithCompletionHandler_(None)

        SCShareableContent.getShareableContentWithCompletionHandler_(completion_handler)  # pragma: no cover

        while self.is_recording:  # pragma: no cover
            self._run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.1))

class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1, chunk_duration=0.1, capture_mic=True, capture_sys=False, sys_audio_method='soundcard'):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.capture_mic = capture_mic
        self.capture_sys = capture_sys
        self.sys_audio_method = sys_audio_method
        self.q = queue.Queue()
        self.is_recording = False
        
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        self._thread = None

        self.sck_recorder = None
        if self.capture_sys and self.sys_audio_method == 'screencapturekit' and sys.platform == 'darwin':
            self.sck_recorder = SCKAudioRecorder(sample_rate=self.sample_rate, channels=self.channels)

    def _record_loop(self):
        mic = sc.default_microphone() if self.capture_mic else None
        
        loopback_dev = None
        if self.capture_sys and self.sys_audio_method == 'soundcard':
            loopback_dev = get_loopback_device()
            if not loopback_dev:
                print("Warning: No loopback device found. System audio will not be captured.")

        mic_rec = mic.recorder(samplerate=self.sample_rate, channels=self.channels) if mic else None
        spk_rec = loopback_dev.recorder(samplerate=self.sample_rate, channels=self.channels) if loopback_dev else None

        if mic_rec: mic_rec.__enter__()
        if spk_rec: spk_rec.__enter__()

        try:
            sck_buffer = np.array([], dtype=np.float32).reshape(0, self.channels)
            while self.is_recording:
                mic_data = None
                sys_data = None
                
                if mic_rec:
                    mic_data = mic_rec.record(numframes=self.chunk_size)
                if spk_rec:
                    sys_data = spk_rec.record(numframes=self.chunk_size)

                # Mix with SCK data if available
                if self.sck_recorder:
                    # Accumulate SCK data until we have at least chunk_size (or if mic is disabled, just get what's available)
                    while not self.sck_recorder.q.empty():
                        sck_chunk = self.sck_recorder.q.get()
                        sck_buffer = np.vstack((sck_buffer, sck_chunk))
                    
                    if mic_data is not None:
                        # We need exactly self.chunk_size from sck_buffer to mix
                        if len(sck_buffer) >= len(mic_data):
                            sys_data = sck_buffer[:len(mic_data)]
                            sck_buffer = sck_buffer[len(mic_data):]
                        else:
                            # Not enough sys data yet, pad with zeros to match mic_data length for mixing
                            pad_len = len(mic_data) - len(sck_buffer)
                            sys_data = np.vstack((sck_buffer, np.zeros((pad_len, self.channels), dtype=np.float32)))
                            sck_buffer = np.array([], dtype=np.float32).reshape(0, self.channels)
                    else:
                        # If no mic, we can just output chunks of self.chunk_size
                        if len(sck_buffer) >= self.chunk_size:
                            sys_data = sck_buffer[:self.chunk_size]
                            sck_buffer = sck_buffer[self.chunk_size:]
                        else:
                            sys_data = None # Wait for more data

                if mic_data is not None and sys_data is not None:
                    min_len = min(len(mic_data), len(sys_data))
                    combined = (mic_data[:min_len] + sys_data[:min_len]) / 2.0
                    self.q.put(combined.copy())
                elif mic_data is not None:
                    self.q.put(mic_data.copy())
                elif sys_data is not None:
                    self.q.put(sys_data.copy())
                elif self.sck_recorder and mic_data is None and sys_data is None:
                    import time
                    time.sleep(0.01)
        finally:
            if mic_rec: mic_rec.__exit__(None, None, None)
            if spk_rec: spk_rec.__exit__(None, None, None)

    def start_recording(self):
        """Starts the audio recording stream."""
        if self.is_recording:
            return
            
        # Empty the queue
        while not self.q.empty():
            self.q.get_nowait()
            
        self.is_recording = True
        
        if self.sck_recorder:
            self.sck_recorder.start()

        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop_recording(self):
        """Stops the audio recording stream."""
        self.is_recording = False
        if self.sck_recorder:
            self.sck_recorder.stop()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_audio_chunk(self, timeout=None):
        """Gets the next audio chunk from the queue as a numpy array."""
        if not self.is_recording and self.q.empty():
            return None
            
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None
