"""Linux half of a release from the Windows release host.

Run once the Windows release is published on Forgejo: builds Linux over SSH
with tools/build_linux_remote.sh and uploads it to the Forgejo release.
macOS is skipped while GitHub Actions is suspended (macos-release.yml and
cloud-release.yml cannot run).

    python tools/release_other_platforms.py vX.Y.Z
"""
import os
import posixpath
import subprocess
import sys

HOST = os.environ.get("LINUX_BUILD_HOST", "root@serrebiradio.com")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def main(tag):
    if os.environ.get("GITHUB_ACTIONS"):
        return
    print("Skipping macOS: GitHub Actions is suspended.", flush=True)

    print(f"Building Linux for {tag} on {HOST}...", flush=True)
    with open(os.path.join(ROOT, "tools", "build_linux_remote.sh"), "rb") as script:
        out = run("ssh", "-o", "BatchMode=yes", HOST, "bash", "-s", "--", tag,
                  stdin=script, stdout=subprocess.PIPE).stdout
    remote = out.decode().strip().splitlines()[-1]
    local = os.path.join(ROOT, "dist", posixpath.basename(remote))
    os.makedirs(os.path.dirname(local), exist_ok=True)
    run("scp", "-o", "BatchMode=yes", f"{HOST}:{remote}", local)
    if remote.startswith("/tmp/"):
        run("ssh", "-o", "BatchMode=yes", HOST, "rm -rf -- " + posixpath.dirname(remote))
    run(sys.executable, os.path.join("tools", "forgejo_release.py"), "upload", tag, local)
    print(f"{tag}: Linux asset attached.")


if __name__ == "__main__":
    main(sys.argv[1])
