"""
Audio engine for the Tone Generator.

Pure logic: no UI code in this module. Produces a continuous stereo tone
via sounddevice's callback API. All parameters are thread-safe.

Listening has two sources: capture devices through sounddevice, and the
output of any playback device through soundcard's WASAPI loopback. Loopback
measures the signal Windows sends to an output device, so it needs no
microphone while something is playing.
"""

import threading

import numpy as np
import sounddevice as sd

try:
    import soundcard as _soundcard
except Exception:  # unsupported platform, or soundcard not installed
    _soundcard = None


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
# Loopback sources are synthetic devices, so they get indices no real capture
# device can occupy (PortAudio indices are always 0 or greater).
LOOPBACK_INDEX_BASE = -1000
LOOPBACK_FALLBACK_RATE = 48000
# Built by list_loopback_devices(), keyed by the synthetic index, because
# recording by index is all the rest of the engine gets to see.
_LOOPBACK_SPEAKERS: dict[int, object] = {}


def list_capture_devices() -> list[tuple[int, str]]:
    """Every device that can supply audio, as (index, label).

    Labels carry the host API because one physical device normally appears once
    per API under the same name.
    """
    return _list_devices("max_input_channels")


def list_playback_devices() -> list[tuple[int, str]]:
    """Every device that can play audio, as (index, label)."""
    return _list_devices("max_output_channels")


def list_loopback_devices() -> list[tuple[int, str]]:
    """What each output device is playing, as (index, label).

    Windows has no capture device that reports the mix going to a speaker, so
    these come from soundcard's WASAPI loopback and carry synthetic negative
    indices. Measuring one shows the signal after the system mixer and any
    system effects, which is what equalising at the system level changes. It
    says nothing about the acoustic output of the speaker itself.
    """
    _LOOPBACK_SPEAKERS.clear()
    if _soundcard is None:
        return []
    try:
        speakers = _soundcard.all_speakers()
    except Exception:
        return []
    found = []
    for offset, speaker in enumerate(speakers):
        index = LOOPBACK_INDEX_BASE - offset
        _LOOPBACK_SPEAKERS[index] = speaker
        found.append((index, f"{speaker.name} (loopback)"))
    return found


def is_loopback_device(device) -> bool:
    """True when `device` is one of the synthetic loopback indices."""
    return isinstance(device, int) and device <= LOOPBACK_INDEX_BASE


def _list_devices(channel_key: str) -> list[tuple[int, str]]:
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:
        return []
    found = []
    for index, device in enumerate(devices):
        if device[channel_key] <= 0:
            continue
        api = hostapis[device["hostapi"]]["name"]
        found.append((index, f"{device['name']} ({api})"))
    return found


def _input_samplerate(device=None) -> int:
    """Sample rate of `device`, or of the default input, or explain the failure."""
    try:
        if device is None:
            info = sd.query_devices(kind="input")
        else:
            info = sd.query_devices(device)
        return int(round(float(info["default_samplerate"])))
    except Exception as exc:
        raise RuntimeError(_unusable_input_message(device)) from exc


def _unusable_input_message(device=None) -> str:
    if device is None:
        what = "Windows has no default recording device set."
    else:
        try:
            name = sd.query_devices(device)["name"]
            what = f"The listening device {name} is not available."
        except Exception:
            what = "The selected listening device is not available."
    names = "; ".join(label for _index, label in list_capture_devices()) or "none"
    return f"{what} Devices Windows reports: {names}."


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
    """Record `seconds` of mono audio from `device`, or the default input.

    Returns (samples, sample_rate). Mono float32 capture at the device's own
    default sample rate. A loopback device records what that output device is
    playing instead, and follows the output's rate.
    """
    if is_loopback_device(device):
        return _record_loopback(seconds, device)
    if sample_rate is None:
        sample_rate = _input_samplerate(device)
    sample_rate = int(round(float(sample_rate)))
    frames = max(1, int(round(seconds * sample_rate)))
    data = sd.rec(
        frames, samplerate=sample_rate, channels=1, dtype="float32", device=device
    )
    sd.wait()
    return data[:, 0], sample_rate


def _record_loopback(seconds: float, device: int):
    """Record what the output device behind `device` is playing, as mono.

    Channels are averaged rather than one channel taken, so a tone panned hard
    to the right is still measured at full strength.
    """
    speaker = _LOOPBACK_SPEAKERS.get(device)
    if _soundcard is None or speaker is None:
        raise RuntimeError(_unusable_loopback_message())
    rate = _loopback_rate(speaker.name)
    channels = max(1, min(2, int(speaker.channels)))
    frames = max(1, int(round(seconds * rate)))
    try:
        microphone = _soundcard.get_microphone(
            id=str(speaker.id), include_loopback=True
        )
        with microphone.recorder(samplerate=rate, channels=channels) as recorder:
            data = recorder.record(numframes=frames)
    except Exception as exc:
        raise RuntimeError(_unusable_loopback_message(speaker.name, exc)) from exc
    samples = np.asarray(data, dtype=np.float64)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return samples, rate


def _loopback_rate(speaker_name: str) -> int:
    """Sample rate to capture a loopback at: the matching playback device's."""
    wanted = speaker_name.strip().casefold()
    for index, label in list_playback_devices():
        device_name, separator, _api = label.rpartition(" (")
        if not separator:
            device_name = label
        if device_name.strip().casefold() != wanted:
            continue
        try:
            info = sd.query_devices(index)
            return int(round(float(info["default_samplerate"])))
        except Exception:
            break
    return LOOPBACK_FALLBACK_RATE


def _unusable_loopback_message(speaker_name=None, cause=None) -> str:
    if _soundcard is None:
        return (
            "Listening to the output needs the soundcard package, which is "
            "missing from this installation."
        )
    if speaker_name is not None:
        return (
            f"Could not listen to the output of {speaker_name}. {cause}\n\n"
            "Make sure the output device is enabled and able to play in "
            "Windows sound settings."
        )
    names = "; ".join(label for _index, label in list_loopback_devices()) or "none"
    return (
        "The output device to listen to is not available any more. "
        f"Output devices Windows reports: {names}."
    )


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
        self.output_device = None
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
        # A chosen device may not run at the default rate, so follow whatever
        # rate it reports before building the stream.
        if self.output_device is not None:
            info = sd.query_devices(self.output_device)
            self.sample_rate = int(round(float(info["default_samplerate"])))
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            device=self.output_device,
            dtype="float32",
            callback=self._callback,
            blocksize=512,
        )
        self.stream.start()

    def set_output_device(self, device):
        """Play through `device`, or the system default when None."""
        if self.is_playing:
            self.stop()
        self.output_device = None if device is None else int(device)

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
