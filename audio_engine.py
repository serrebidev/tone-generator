"""
Audio engine for the Tone Generator.

Pure logic: no UI code in this module. Produces a continuous stereo tone
via sounddevice's callback API. All parameters are thread-safe.
"""

import threading

import numpy as np
import sounddevice as sd


DEFAULT_CAPTURE_SECONDS = 3.0
DETECT_MIN_HZ = 20.0
DETECT_MAX_HZ = 20000.0
DETECT_FRAME = 4096
SILENCE_RMS = 1e-5
_LOG_FLOOR = 1e-30
# Audio is nominally within +/-1.0. Some drivers return uninitialised memory
# instead, which shows up astronomically larger than full scale and must not be
# analysed as if it were sound.
MAX_SANE_PEAK = 16.0


def _default_input_samplerate() -> int:
    """Sample rate of the default input device, or explain why there is none."""
    try:
        info = sd.query_devices(kind="input")
    except Exception as exc:
        raise RuntimeError(
            "Windows has no default recording device set. "
            f"Input devices it reports: {_input_device_names()}."
        ) from exc
    return int(round(float(info["default_samplerate"])))


def _input_device_names() -> str:
    try:
        names = [
            str(device["name"])
            for device in sd.query_devices()
            if device["max_input_channels"] > 0
        ]
    except Exception:
        return "unknown"
    return "; ".join(names) if names else "none"


def detect_loudest_frequency(
    samples,
    sample_rate: int,
    min_hz: float = DETECT_MIN_HZ,
    max_hz: float = DETECT_MAX_HZ,
    frame_size: int = DETECT_FRAME,
) -> float | None:
    """Return the loudest spectral component of `samples`, in Hertz.

    DC is removed, then Hann-windowed frames (half-overlapping) have their
    rFFT power averaged before the strongest bin within [min_hz, max_hz] is
    chosen. The loudest spectral component is returned, which is not
    necessarily the musical fundamental. Returns None when no usable signal
    is present or the requested band holds no analysable bin.
    """
    x = np.asarray(samples, dtype=np.float64).ravel()
    if x.size == 0 or sample_rate <= 0 or frame_size < 4:
        return None
    x = x - x.mean()
    if not np.all(np.isfinite(x)):
        return None
    if float(np.max(np.abs(x))) > MAX_SANE_PEAK:
        return None
    if float(np.sqrt(np.mean(x**2))) < SILENCE_RMS:
        return None
    if x.size < frame_size:
        x = np.pad(x, (0, frame_size - x.size))

    window = np.hanning(frame_size)
    hop = frame_size // 2
    power = np.zeros(frame_size // 2 + 1)
    frames = 0
    for start in range(0, x.size - frame_size + 1, hop):
        spectrum = np.fft.rfft(x[start : start + frame_size] * window)
        power += np.abs(spectrum) ** 2
        frames += 1
    power /= frames

    freqs = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
    low = max(float(min_hz), 0.0)
    high = min(float(max_hz), freqs[-1])
    band = np.flatnonzero((freqs >= low) & (freqs <= high))
    band = band[band > 0]
    if low >= high or band.size == 0:
        return None

    best = int(band[np.argmax(power[band])])
    peak = float(freqs[best])

    # Parabolic interpolation on log power sharpens the peak to sub-bin
    # accuracy. Only applied to interior bins whose neighbours curve downward.
    if 0 < best < power.size - 1:
        left, mid, right = (
            float(np.log(power[best + step] + _LOG_FLOOR)) for step in (-1, 0, 1)
        )
        curvature = left - 2.0 * mid + right
        if curvature < 0.0:
            offset = 0.5 * (left - right) / curvature
            if -1.0 < offset < 1.0:
                peak += offset * (freqs[1] - freqs[0])

    return min(max(peak, low), high)


def record_mono(seconds: float = DEFAULT_CAPTURE_SECONDS, sample_rate=None, device=None):
    """Record `seconds` of mono audio from the default input device.

    Returns (samples, sample_rate). Mono float32 capture at the device's own
    default sample rate.
    """
    if sample_rate is None:
        sample_rate = _default_input_samplerate()
    sample_rate = int(round(float(sample_rate)))
    frames = max(1, int(round(seconds * sample_rate)))
    data = sd.rec(
        frames, samplerate=sample_rate, channels=1, dtype="float32", device=device
    )
    sd.wait()
    return data[:, 0], sample_rate


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
