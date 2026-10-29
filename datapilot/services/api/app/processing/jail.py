"""Trusted runtime-only chroot trees for kernels without Landlock.

The orchestration container needs CHROOT/SETUID/SETGID/CHOWN capabilities. Each parser
gets its own root filesystem: shared immutable runtime files are hardlinked from a
root-owned template, and its one writable /job directory has a fresh numeric identity.
No host credential directory, application configuration or sibling job is included.
"""

import fcntl
import os
import secrets
import shutil
import sys
from pathlib import Path

from app.processing.sandbox import SandboxUnavailable


def _copy_runtime(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def runtime_template() -> Path:
    if os.geteuid() != 0:
        raise SandboxUnavailable("A restricted root orchestrator is required for chroot isolation")
    root = Path("/tmp/datapilot-runtime")
    lockpath = Path("/tmp/datapilot-runtime.lock")
    with lockpath.open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not (root / ".complete").is_file():
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(mode=0o755)
            paths = {Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve()}
            # Dynamic libraries are trusted runtime dependencies; no /etc, /proc,
            # /home, /root, cloud metadata, application config or devices are copied.
            paths.update(Path(p) for p in ("/usr/lib", "/usr/lib64") if Path(p).exists())
            for source in sorted(paths, key=lambda p: len(str(p))):
                target = root / source.relative_to("/")
                _copy_runtime(source, target)
            for name in ("lib", "lib64"):
                source = Path("/") / name
                if source.is_symlink():
                    (root / name).symlink_to(os.readlink(source))
                elif source.exists():
                    _copy_runtime(source, root / name)
            for directory, _, files in os.walk(root):
                os.chmod(directory, 0o755)
                for filename in files:
                    path = Path(directory) / filename
                    if not path.is_symlink():
                        mode = path.stat().st_mode
                        os.chmod(path, 0o755 if mode & 0o111 else 0o644)
            (root / ".complete").write_text("trusted-runtime-v1")
        if root.stat().st_uid != 0:
            raise SandboxUnavailable("Runtime template must be owned by root")
    return root


def prepare_jail(directory: Path) -> tuple[Path, Path, int]:
    template = runtime_template()
    jail = directory / ".root"
    shutil.copytree(template, jail, symlinks=True, copy_function=os.link)
    os.chmod(jail, 0o755)
    job = jail / "job"
    job.mkdir(mode=0o700)
    identity = 100000 + secrets.randbelow(1_000_000_000)
    os.chown(job, identity, identity)
    input_file = directory / "input"
    if input_file.exists():
        shutil.copyfile(input_file, job / "input")
        os.chmod(job / "input", 0o400)
        os.chown(job / "input", identity, identity)
    return jail, job, identity
