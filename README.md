# Tone Generator

Accessible Windows desktop test-tone generator built with wxPython, NumPy, and sounddevice.

**Questions, bugs, or release news?** Join the [SerrebiProjects Telegram group](https://t.me/SerrebiProjects), the fastest place to get help.

## Features

- Continuous sine, square, triangle, and sawtooth tones.
- Frequency presets from 20 Hz to 15 kHz.
- Finds the loudest frequency heard by a microphone input and sets the frequency control to it (Ctrl+L).
- Keyboard-accessible controls and menu shortcuts.
- Configurable small and large frequency step sizes.
- Stereo output options for both, left-only, or right-only playback.
- Single-file Windows executable built with PyInstaller.

## Find The Loudest Frequency

Press Ctrl+L, choose Frequency then Find loudest frequency, or use the Find loudest frequency button in the Frequency area. Any generated tone stops, the app records about three seconds from the default Windows recording device, and the frequency control is set to the loudest component it heard between 20 Hz and 20 kHz. Playback does not restart by itself; press F5 to hear the detected frequency and then adjust it with the arrow keys.

A default recording device must be set in Windows sound settings. When none is set, the app says so and lists the input devices Windows reports.

## Download

For normal use, download `ToneGenerator.exe` from the latest GitHub release and run it directly on Windows.

## Run From Source

```powershell
python -m pip install -r requirements.txt
python tone_generator.py
```

## Build The Windows Executable

```powershell
build.bat build
```

The build output is `dist\ToneGenerator.exe`. The PyInstaller spec bundles wxPython, NumPy, sounddevice, and the PortAudio DLLs required by sounddevice.

## Release

Use `build.bat release` for official releases. It publishes the GitHub release as latest/non-draft and removes any remaining draft releases.

##Submit bugs in issues, or join my Telegram group!
(https://t.me/SerrebiProjects)
