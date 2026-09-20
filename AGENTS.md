# Agent Notes - Tone Generator

## Project

Tone Generator is an accessible wxPython Windows desktop app for generating audio test tones. The entry point is `tone_generator.py`, and audio synthesis lives in `audio_engine.py`.

## Build

- Runtime dependencies are in `requirements.txt`.
- Build dependencies are in `requirements-build.txt`.
- Use `build.bat build` for local Windows executable builds.
- `tone_generator.spec` is the PyInstaller source of truth.
- Build output is `dist\ToneGenerator.exe`.

## Release

- Release from `main`.
- Use `build.bat release` for official releases.
- GitHub releases must be published, never drafts.
- The release script explicitly marks the new release as latest and non-draft.
- The release script removes any remaining draft releases after publishing.

## Build Hygiene

Always fix any warnings, bugs, or errors encountered during the build when possible. Do not ship a build with unresolved warnings or errors.
