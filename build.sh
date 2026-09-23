#!/usr/bin/env bash
# macOS/Linux build. Windows uses build.bat. Output:
#   macOS: dist/ToneGenerator-macos.zip (ToneGenerator.app)
#   Linux: dist/ToneGenerator-linux-x86_64.tar.gz (ToneGenerator binary)
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
"$PYTHON" -m pip install -r requirements-build.txt
"$PYTHON" -m PyInstaller --noconfirm --clean tone_generator.spec
case "$(uname -s)" in
  Darwin)
    codesign --force --deep --sign - dist/ToneGenerator.app
    (cd dist && ditto -c -k --sequesterRsrc --keepParent ToneGenerator.app ToneGenerator-macos.zip)
    ;;
  Linux)
    tar -C dist -czf dist/ToneGenerator-linux-x86_64.tar.gz ToneGenerator
    ;;
  *) echo "build.sh is for macOS and Linux; use build.bat on Windows." >&2; exit 1 ;;
esac
ls -l dist
