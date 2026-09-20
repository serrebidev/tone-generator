# Changelog

## 1.0.2 - 2026-09-20

- Find loudest frequency now listens to any capture device instead of only the microphone. Settings -> Listening device lists the system default plus every device that can supply audio, including line in and loopback devices such as Stereo Mix.
- Adds Settings -> Output device, so the tone can be played through chosen speakers, headphones, or another interface rather than only the system default.
- Remembers both devices by name, so the choice survives Windows renumbering devices as hardware is plugged in, and falls back to the system default when a remembered device is gone.
- Follows the chosen device's own sample rate instead of assuming 44.1 kHz.
- Fixes the release script's draft cleanup, which could delete the release it had just published.

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
