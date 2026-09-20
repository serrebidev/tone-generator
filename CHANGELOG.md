# Changelog

## 1.0.1 - 2026-09-20

- Adds "Find loudest frequency" (Ctrl+L, or the button in the Frequency area): records about three seconds from the default input device, finds the loudest spectral component between 20 Hz and 20 kHz, and puts it in the frequency control so it can be adjusted.
- Stops generated playback before listening, so the microphone does not measure this window's own tone, and does not restart it automatically.
- Announces the result in a message box, and explains what to do when no input device is available or no tone was heard.
- Ignores a capture that is silent, or that a driver handed back as unusable, instead of reporting a frequency from device noise.

## 1.0.0 - 2026-04-29

- First public release.
- Adds an accessible wxPython UI for generating test tones.
- Supports sine, square, triangle, and sawtooth waveforms.
- Supports preset frequencies, configurable step sizes, volume control, and stereo channel selection.
- Provides a single-file Windows executable built with PyInstaller.
