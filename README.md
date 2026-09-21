# Tone Generator

Accessible Windows desktop test-tone generator built with wxPython, NumPy, and sounddevice.

**Questions, bugs, or release news?** Join the [SerrebiProjects Telegram group](https://t.me/SerrebiProjects), the fastest place to get help.

## Features

- Continuous sine, square, triangle, and sawtooth tones.
- Frequency presets from 20 Hz to 15 kHz.
- Finds the loudest frequency heard by any chosen device and sets the frequency control to it (Ctrl+L).
- Measures what any output device is playing, without a microphone, through WASAPI loopback.
- Plays the tone through any chosen output device: speakers, headphones, or another interface.
- Keyboard-accessible controls and menu shortcuts.
- Configurable small and large frequency step sizes.
- Stereo output options for both, left-only, or right-only playback.
- Single-file Windows executable built with PyInstaller.

## Find The Loudest Frequency

Press Ctrl+L, choose Frequency then Find loudest frequency, or use the Find loudest frequency button in the Frequency area. The app records about three seconds from the listening device and sets the frequency control to the loudest component it heard between 20 Hz and 20 kHz. Playback does not restart by itself; press F5 to hear the detected frequency and then adjust it with the arrow keys.

Listening to a microphone stops any generated tone first, so the app does not measure its own output. Listening to an output does the opposite and leaves playback running, because a silent output has nothing to measure: start the tone with F5, or play music or a sweep in any other program, and Ctrl+L reports the loudest frequency in what that device is playing.

## Choosing Audio Devices

Settings then Listening device chooses what to listen to, and Settings then Output device chooses where the tone is played. Both list the system default plus every device Windows reports, with the host API in brackets because one physical device usually appears once per API.

The listening list starts with every output device marked "(loopback)". Choosing one measures what Windows is sending to that device, which needs no microphone at all and works even on machines where Windows reports no recording device. It reads the signal after the system mixer, so it shows what system effects and equalisers did to a tone. It cannot show what a speaker or headphone actually produces; that needs a microphone in the room.

Below those come the devices that can supply audio: a microphone, line in, a sound card input, a USB interface, or a driver loopback such as Stereo Mix. Not every driver offers one, and some, such as the WDM-KS devices Realtek exposes, hand back unusable data rather than audio. Where a microphone is wanted and none works, the output loopback entries above are the alternative. No microphone is needed to play a tone.

Choices are remembered by name, so they survive Windows renumbering devices as hardware is plugged in. When a remembered device is gone, the app falls back to the system default.

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
