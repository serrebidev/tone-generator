# Tone Generator

Accessible Windows desktop test-tone generator built with wxPython, NumPy, and sounddevice.

## Features

- Continuous sine, square, triangle, and sawtooth tones.
- Frequency presets from 20 Hz to 15 kHz.
- Keyboard-accessible controls and menu shortcuts.
- Configurable small and large frequency step sizes.
- Stereo output options for both, left-only, or right-only playback.
- Single-file Windows executable built with PyInstaller.

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
