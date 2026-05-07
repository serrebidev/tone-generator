# Tone Generator Build and Release

Use `build.bat` for Windows builds and releases.

## Commands

```bat
build.bat build
build.bat dry-run
build.bat release
```

## Release Rules

- Release from `main`.
- Use `build.bat release` for official releases.
- GitHub releases must be published, never drafts.
- The release script explicitly marks the new release as latest and non-draft.
- The release script removes any remaining draft releases after publishing.
- Do not ship if the build shows unresolved warnings, errors, or dependency mismatches.

## Output

Build mode produces `dist\ToneGenerator.exe`.

Release mode updates version metadata, builds the executable, stages versioned EXE/ZIP assets plus SHA-256 sums under `dist\release`, commits the version bump, tags and pushes Git, and publishes the GitHub release.
