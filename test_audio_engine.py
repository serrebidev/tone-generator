"""Unit tests for audio_engine pure detection logic."""

import contextlib
import unittest
from unittest import mock

import numpy as np

import audio_engine


def tone(freq, rate, seconds=1.0, amp=0.5):
    t = np.arange(int(rate * seconds)) / rate
    return amp * np.sin(2 * np.pi * freq * t)


class DetectLoudestFrequencyTests(unittest.TestCase):
    def test_detects_a_pure_tone(self):
        rate = 44100
        samples = tone(1000.0, rate)
        self.assertAlmostEqual(
            audio_engine.detect_loudest_frequency(samples, rate), 1000.0, delta=11.0
        )

    def test_interpolates_between_fft_bins(self):
        rate = 44100
        samples = tone(1000.0, rate)
        self.assertAlmostEqual(
            audio_engine.detect_loudest_frequency(samples, rate), 1000.0, delta=1.0
        )

    def test_picks_the_louder_component_not_the_lowest(self):
        rate = 44100
        samples = tone(500.0, rate, amp=0.2) + tone(2000.0, rate, amp=0.8)
        self.assertAlmostEqual(
            audio_engine.detect_loudest_frequency(samples, rate), 2000.0, delta=5.0
        )

    def test_silence_is_reported_as_no_result(self):
        self.assertIsNone(
            audio_engine.detect_loudest_frequency(np.zeros(44100), 44100)
        )

    def test_empty_capture_is_reported_as_no_result(self):
        self.assertIsNone(audio_engine.detect_loudest_frequency([], 44100))

    def test_unusable_device_buffer_is_reported_as_no_result(self):
        # Some drivers hand back uninitialised memory rather than audio. Those
        # buffers are finite and far from silent (measured around 1e21 here),
        # so they must not be reported as a confident frequency.
        rate = 44100
        rng = np.random.default_rng(0)
        samples = rng.uniform(-1e21, 1e21, rate)
        self.assertIsNone(audio_engine.detect_loudest_frequency(samples, rate))

    def test_loudest_component_above_the_range_is_not_reported(self):
        rate = 96000
        samples = tone(30000.0, rate)
        detected = audio_engine.detect_loudest_frequency(
            samples, rate, min_hz=20.0, max_hz=20000.0
        )
        self.assertTrue(detected is None or detected <= 20000.0)

    def test_loudest_component_below_the_range_is_not_reported(self):
        rate = 44100
        samples = tone(1000.0, rate)
        detected = audio_engine.detect_loudest_frequency(
            samples, rate, min_hz=2000.0, max_hz=3000.0
        )
        self.assertTrue(detected is None or detected >= 2000.0)

    def test_empty_frequency_band_is_reported_as_no_result(self):
        rate = 44100
        samples = tone(1000.0, rate)
        self.assertIsNone(
            audio_engine.detect_loudest_frequency(
                samples, rate, min_hz=2000.0, max_hz=2000.0
            )
        )


class RecordMonoTests(unittest.TestCase):
    def test_records_mono_at_the_default_input_sample_rate(self):
        captured = {}

        def fake_rec(frames, samplerate, channels, dtype, device):
            captured.update(
                frames=frames,
                samplerate=samplerate,
                channels=channels,
                dtype=dtype,
                device=device,
            )
            return np.zeros((frames, 1), dtype=dtype)

        with (
            mock.patch.object(
                audio_engine.sd,
                "query_devices",
                return_value={"default_samplerate": 48000.0},
            ),
            mock.patch.object(audio_engine.sd, "rec", side_effect=fake_rec),
            mock.patch.object(audio_engine.sd, "wait") as wait,
        ):
            samples, rate = audio_engine.record_mono(seconds=0.5)

        self.assertEqual(rate, 48000)
        self.assertEqual(captured["channels"], 1)
        self.assertEqual(captured["samplerate"], 48000)
        self.assertEqual(captured["frames"], 24000)
        self.assertEqual(samples.shape, (24000,))
        wait.assert_called_once()

    def test_explains_itself_when_no_input_device_is_set(self):
        # Windows can report no default recording device at all. The raw
        # PortAudio error ("Error querying device -1") means nothing to a user,
        # so the failure must say what is actually wrong.
        with mock.patch.object(
            audio_engine.sd,
            "query_devices",
            side_effect=RuntimeError("Error querying device -1"),
        ):
            with self.assertRaises(RuntimeError) as caught:
                audio_engine.record_mono(seconds=0.5)
        self.assertIn("default recording device", str(caught.exception))

    def test_recording_follows_the_chosen_device(self):
        captured = {}

        def fake_rec(frames, samplerate, channels, dtype, device):
            captured.update(frames=frames, samplerate=samplerate, device=device)
            return np.zeros((frames, 1), dtype=dtype)

        with (
            mock.patch.object(
                audio_engine.sd,
                "query_devices",
                return_value={"default_samplerate": 48000.0, "name": "Line In"},
            ),
            mock.patch.object(audio_engine.sd, "rec", side_effect=fake_rec),
            mock.patch.object(audio_engine.sd, "wait"),
        ):
            audio_engine.record_mono(seconds=0.5, device=7)

        self.assertEqual(captured["device"], 7)
        self.assertEqual(captured["samplerate"], 48000)
        self.assertEqual(captured["frames"], 24000)


class DeviceListingTests(unittest.TestCase):
    """The picker must offer anything that can move audio, not just microphones."""

    DEVICES = [
        {
            "name": "Speakers",
            "hostapi": 0,
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
        },
        {
            "name": "Stereo Mix",
            "hostapi": 1,
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
        {
            "name": "Microphone",
            "hostapi": 1,
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
    ]
    HOSTAPIS = [{"name": "MME"}, {"name": "Windows WASAPI"}]

    def test_lists_capture_devices_only_and_names_their_api(self):
        with (
            mock.patch.object(
                audio_engine.sd, "query_devices", return_value=self.DEVICES
            ),
            mock.patch.object(
                audio_engine.sd, "query_hostapis", return_value=self.HOSTAPIS
            ),
        ):
            devices = audio_engine.list_capture_devices()

        # Stereo Mix is a speaker loopback, so it has to be offered alongside
        # the microphone. The API is part of the label because one physical
        # device appears once per API under the same name.
        self.assertEqual(
            devices,
            [
                (1, "Stereo Mix (Windows WASAPI)"),
                (2, "Microphone (Windows WASAPI)"),
            ],
        )

    def test_lists_playback_devices_only(self):
        with (
            mock.patch.object(
                audio_engine.sd, "query_devices", return_value=self.DEVICES
            ),
            mock.patch.object(
                audio_engine.sd, "query_hostapis", return_value=self.HOSTAPIS
            ),
        ):
            devices = audio_engine.list_playback_devices()

        self.assertEqual(devices, [(0, "Speakers (MME)")])

    def test_a_broken_audio_backend_lists_nothing_rather_than_crashing(self):
        with mock.patch.object(
            audio_engine.sd, "query_devices", side_effect=RuntimeError("no audio")
        ):
            self.assertEqual(audio_engine.list_capture_devices(), [])
            self.assertEqual(audio_engine.list_playback_devices(), [])


class _FakeSpeaker:
    def __init__(self, name, identifier, channels=2):
        self.name = name
        self.id = identifier
        self.channels = channels


class _FakeSoundcard:
    """Stands in for soundcard: speaker listing plus its loopback recorder."""

    def __init__(self, samples, speakers):
        self.samples = samples
        self.speakers = speakers
        self.opened = {}

    def all_speakers(self):
        return list(self.speakers)

    def get_microphone(self, id, include_loopback):
        self.opened["id"] = id
        self.opened["include_loopback"] = include_loopback
        return self

    def recorder(self, samplerate, channels):
        self.opened["samplerate"] = samplerate
        self.opened["channels"] = channels
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def record(self, numframes):
        self.opened["numframes"] = numframes
        return self.samples


class LoopbackTests(unittest.TestCase):
    """Listening to what an output device is playing, without a microphone."""

    SPEAKERS = [_FakeSpeaker("Speakers", "speaker-id", 2)]
    OUTPUT_DEVICE = {
        "name": "Speakers",
        "hostapi": 0,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
    }
    HOSTAPIS = [{"name": "Windows WASAPI"}]

    @contextlib.contextmanager
    def _devices(self, backend):
        """Pretend `backend` is soundcard, with one WASAPI output device."""

        def query_devices(device=None):
            if device is None:
                return [self.OUTPUT_DEVICE]
            return self.OUTPUT_DEVICE

        with (
            mock.patch.object(audio_engine, "_soundcard", backend),
            mock.patch.object(audio_engine.sd, "query_devices", query_devices),
            mock.patch.object(
                audio_engine.sd, "query_hostapis", return_value=self.HOSTAPIS
            ),
        ):
            yield backend

    def test_every_output_device_is_offered_as_a_loopback_source(self):
        backend = _FakeSoundcard(np.zeros((10, 2)), self.SPEAKERS)
        with self._devices(backend):
            devices = audio_engine.list_loopback_devices()

        self.assertEqual(devices, [(-1000, "Speakers (loopback)")])
        self.assertTrue(audio_engine.is_loopback_device(devices[0][0]))

    def test_a_loopback_index_can_never_be_a_capture_index(self):
        # PortAudio indices start at zero, so the synthetic loopback range must
        # stay below it or a remembered device could name the wrong thing.
        self.assertFalse(audio_engine.is_loopback_device(None))
        self.assertFalse(audio_engine.is_loopback_device(0))
        self.assertFalse(audio_engine.is_loopback_device(7))
        self.assertTrue(
            audio_engine.is_loopback_device(audio_engine.LOOPBACK_INDEX_BASE)
        )

    def test_no_loopback_sources_without_soundcard(self):
        with mock.patch.object(audio_engine, "_soundcard", None):
            self.assertEqual(audio_engine.list_loopback_devices(), [])

    def test_recording_a_loopback_follows_the_output_device_rate(self):
        captured = np.zeros((24000, 2), dtype="float32")
        backend = _FakeSoundcard(captured, self.SPEAKERS)
        with self._devices(backend):
            devices = audio_engine.list_loopback_devices()
            samples, rate = audio_engine.record_mono(
                seconds=0.5, device=devices[0][0]
            )

        self.assertEqual(rate, 48000)
        self.assertEqual(backend.opened["samplerate"], 48000)
        self.assertEqual(backend.opened["numframes"], 24000)
        self.assertEqual(backend.opened["id"], "speaker-id")
        self.assertTrue(backend.opened["include_loopback"])
        self.assertEqual(samples.shape, (24000,))

    def test_recording_a_loopback_averages_the_channels(self):
        # A tone panned hard right still has to be measured, so both channels
        # are folded in rather than one being read.
        captured = np.zeros((100, 2), dtype="float32")
        captured[:, 1] = 0.8
        backend = _FakeSoundcard(captured, self.SPEAKERS)
        with self._devices(backend):
            devices = audio_engine.list_loopback_devices()
            samples, _rate = audio_engine.record_mono(
                seconds=0.5, device=devices[0][0]
            )

        self.assertEqual(backend.opened["channels"], 2)
        self.assertAlmostEqual(float(np.max(samples)), 0.4, places=6)

    def test_a_loopback_device_that_is_gone_is_reported_as_unusable(self):
        backend = _FakeSoundcard(np.zeros((10, 2)), self.SPEAKERS)
        with mock.patch.object(audio_engine, "_soundcard", backend):
            audio_engine.list_loopback_devices()
            audio_engine._LOOPBACK_SPEAKERS.clear()
            with self.assertRaises(RuntimeError) as caught:
                audio_engine.record_mono(seconds=0.5, device=-1000)

        self.assertIn("not available", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
