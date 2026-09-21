# Changelog

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
