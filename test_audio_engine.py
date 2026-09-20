"""Unit tests for audio_engine pure detection logic."""

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


if __name__ == "__main__":
    unittest.main()
