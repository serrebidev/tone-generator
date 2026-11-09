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
- Use `build.bat release` for official releases (needs `FORGEJO_TOKEN` set).
- Forgejo releases must be published, never drafts.
- The release script publishes the new release as non-draft via `tools/forgejo_release.py`.
- The release script removes any remaining draft releases after publishing.
- Pushes go to the `forgejo` remote (`https://git.serrebiradio.com/serrebi/tone-generator.git`); main is pushed before the tag is created. Never force-push.
- Local releases (this Windows host): `build.bat release` builds Windows locally, then `tools/release_other_platforms.py` builds Linux over `ssh root@serrebiradio.com` with `tools/build_linux_remote.sh` (throwaway ubuntu:24.04 container, launch check; `LINUX_BUILD_HOST` overrides) and uploads it to the Forgejo release. If that half fails after publishing, rerun `python tools/release_other_platforms.py vX.Y.Z`.
- macOS is skipped while GitHub Actions is suspended: `.github/workflows/macos-release.yml` and `.github/workflows/cloud-release.yml` cannot run.
- `build.sh` = macOS/Linux build. Linux needs distro wxPython (`python3-wxgtk4.0`) in a `--system-site-packages` venv, plus `libportaudio2`. Test Linux on `ssh root@serrebiradio.com` (Debian 13).

## Build Hygiene

Always fix any warnings, bugs, or errors encountered during the build when possible. Do not ship a build with unresolved warnings or errors.

## Agent skills

### Issue tracker

Issues are tracked in this repo's GitHub Issues, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
