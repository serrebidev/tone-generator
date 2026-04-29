"""
Audio engine for the Tone Generator.

Pure logic: no UI code in this module. Produces a continuous stereo tone
via sounddevice's callback API. All parameters are thread-safe.
"""

import threading

import numpy as np
import sounddevice as sd


class ToneGenerator:
    WAVEFORMS = ["Sine", "Square", "Triangle", "Sawtooth"]
    CHANNELS = ["Both", "Left only", "Right only"]

    FREQ_MIN = 1.0
    FREQ_MAX = 24000.0
    VOL_MIN = 0.0
    VOL_MAX = 1.0

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.frequency = 1000.0
        self.volume = 0.3
        self.waveform = "Sine"
        self.channel = "Both"
        self.stream: sd.OutputStream | None = None
        self._phase = 0.0
        self._lock = threading.Lock()

    @property
    def is_playing(self) -> bool:
        return self.stream is not None and self.stream.active

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            freq = self.frequency
            vol = self.volume
            waveform = self.waveform
            channel = self.channel
            phase = self._phase

        t = (np.arange(frames) + phase) / self.sample_rate
        theta = 2 * np.pi * freq * t

        if waveform == "Sine":
            wave = np.sin(theta)
        elif waveform == "Square":
            wave = np.sign(np.sin(theta))
        elif waveform == "Triangle":
            wave = (2 / np.pi) * np.arcsin(np.sin(theta))
        else:  # Sawtooth
            wave = 2 * ((freq * t + 0.5) % 1.0) - 1

        wave = (wave * vol).astype(np.float32)

        out = np.zeros((frames, 2), dtype=np.float32)
        if channel in ("Both", "Left only"):
            out[:, 0] = wave
        if channel in ("Both", "Right only"):
            out[:, 1] = wave

        outdata[:] = out

        with self._lock:
            # Bound phase to avoid float precision drift over long sessions.
            self._phase = (phase + frames) % max(self.sample_rate, 1)

    def start(self):
        if self.is_playing:
            return
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            dtype="float32",
            callback=self._callback,
            blocksize=512,
        )
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            finally:
                self.stream = None
                with self._lock:
                    self._phase = 0.0

    def set_frequency(self, hz: float) -> float:
        clamped = max(self.FREQ_MIN, min(self.FREQ_MAX, float(hz)))
        with self._lock:
            self.frequency = clamped
        return clamped

    def set_volume(self, vol: float) -> float:
        clamped = max(self.VOL_MIN, min(self.VOL_MAX, float(vol)))
        with self._lock:
            self.volume = clamped
        return clamped

    def set_waveform(self, wf: str):
        if wf not in self.WAVEFORMS:
            raise ValueError(f"Unknown waveform: {wf}")
        with self._lock:
            self.waveform = wf

    def set_channel(self, ch: str):
        if ch not in self.CHANNELS:
            raise ValueError(f"Unknown channel: {ch}")
        with self._lock:
            self.channel = ch
