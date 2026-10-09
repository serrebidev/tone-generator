# Changelog

## 1.0.8 - 2026-10-09

- Fix stereo capture frequency detection in `detect_loudest_frequency` (avoid halving measured frequencies from interleaved channels).
- Fix menu mnemonic conflict for the Frequency menu (`Alt+R` / `F&requency`) with File (`Alt+F`).
- Fix frequency input manual typing desynchronization by handling text change events and syncing before playback.
- Synchronize preset frequency dropdown selection dynamically when stepping or typing frequency, allowing re-selection of the same preset.
- Fix Play/Stop toggle button label desynchronization if playback cannot start on an output device change.
- Eliminate zero-crossing glitch in Square waveform and prevent NaN in Triangle waveform.
- Fix audio stream handle leaks on stream start failures and guarantee cleanup on stream stop.
- Support 2-channel fallback in mono capture for devices that reject 1-channel recording.
- Eliminate wxWidgets static box sizer parenting assertion warnings.

## 1.0.6 - 2026-09-28

- Dependency refresh: wxPython 4.3.1, NumPy 2.5.3, sounddevice 0.5.6, soundcard 0.4.6, PyInstaller 6.22.3.

## 1.0.3 - 2026-09-21

- Find loudest frequency (Ctrl+L) can now listen to the output. Every output device is offered as a loopback source in Settings -> Listening device, so a tone, music, or a sweep can be measured on speakers, headphones, or another interface without any microphone. PortAudio cannot open a playback device for capture, so this uses soundcard's WASAPI loopback.
- Listening to an output now works on machines where Windows reports no recording device at all, and where the only capture devices are WDM-KS ones that hand back uninitialised memory instead of audio.
- Leaves generated playback running while a loopback is measured, because a silent output has nothing to find. Microphone listening still stops the tone first, so it never measures this window's own output.
- Folds both loopback channels into the measurement, so a tone panned hard to one side is still found.
- Says what a loopback result is: the signal Windows sent to the output device, including system effects and equalisers, and not what the speaker or headphone itself produces.

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
