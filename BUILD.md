# Tone Generator Build and Release

Use `build.bat` for Windows builds and releases.

## Commands

```bat
build.bat build
build.bat dry-run
build.bat release
```

macOS and Linux: `./build.sh` (see AGENTS.md). The `.github/workflows` releases cannot run while GitHub Actions is suspended.

## Release Rules

- Release from `main`.
- Use `build.bat release` for official releases (needs `FORGEJO_TOKEN` set).
- Forgejo releases must be published, never drafts.
- The release script publishes the new release as non-draft via `tools/forgejo_release.py`.
- The release script removes any remaining draft releases after publishing.
- Do not ship if the build shows unresolved warnings, errors, or dependency mismatches.

## Output

Build mode produces `dist\ToneGenerator.exe`.

Release mode updates version metadata, builds the executable, stages versioned EXE/ZIP assets plus SHA-256 sums under `dist\release`, commits the version bump, pushes to the `forgejo` remote, tags and pushes the tag, and publishes the Forgejo release.
