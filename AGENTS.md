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
- Local releases (this Windows host) stay Windows-only: `build.bat release`.
- Cloud agents ONLY: `.github/workflows/cloud-release.yml` builds every platform on GitHub runners. Windows runs the same `build.bat release`; macOS (`ToneGenerator-vX.Y.Z-macos.zip`, app bundle) and Linux (`ToneGenerator-vX.Y.Z-linux-x86_64.tar.gz`) then build that tag with `build.sh` and attach. `gh workflow run cloud-release.yml -f dry_run=true` builds all three as workflow artifacts and publishes nothing; `-f dry_run=false` is a real release. Watch with `gh run watch <id> --exit-status`. Never run it while `build.bat release` runs: both bump from the latest tag.
- `build.sh` = macOS/Linux build. Linux needs distro wxPython (`python3-wxgtk4.0`) in a `--system-site-packages` venv, plus `libportaudio2`. Test Linux on `ssh root@serrebiradio.com` (Debian 13).

## Build Hygiene

Always fix any warnings, bugs, or errors encountered during the build when possible. Do not ship a build with unresolved warnings or errors.
