"""Linux process restrictions for ingestion. No fallback to unrestricted execution.

Landlock denies access outside the per-job staging tree and read-only Python runtime.
Seccomp denies networking, program execution, process inspection and namespace changes.
These restrictions complement bounded parsing; they do not turn arbitrary Python into a
supported product feature. No caller-provided code is ever evaluated.
"""

import ctypes
import errno
import os
import resource
import sys
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    pass


class Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def restrict(
    job_directory: Path, *, jail: Path | None = None, identity: int | None = None
) -> dict[str, bool]:
    """Apply irreversible kernel restrictions in the child, before reading an upload."""
    if sys.platform != "linux":
        raise SandboxUnavailable("Linux sandbox required")
    try:
        seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise SandboxUnavailable("libseccomp required") from exc
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise SandboxUnavailable("Cannot set no_new_privs")
    if jail is not None:
        if identity is None or identity < 100000 or os.geteuid() != 0:
            raise SandboxUnavailable("Invalid chroot parser identity")
        os.chroot(jail)
        os.chdir("/job")
        os.setgroups([])
        os.setgid(identity)
        os.setuid(identity)
        if os.geteuid() == 0 or os.getgroups():
            raise SandboxUnavailable("Cannot drop parser privileges")
    else:
        abi = libc.syscall(444, 0, 0, 1)  # landlock_create_ruleset(VERSION)
        if abi < 1:
            raise SandboxUnavailable("Landlock support required")
        handled = (1 << 13) - 1
        if abi >= 2:
            handled |= 1 << 13
        if abi >= 3:
            handled |= 1 << 14
        attr = Ruleset(handled)
        ruleset_fd = libc.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
        if ruleset_fd < 0:
            raise SandboxUnavailable("Cannot create filesystem ruleset")
        readonly = (1 << 2) | (1 << 3)
        writable = readonly | (1 << 1) | (1 << 4) | (1 << 5) | (1 << 7) | (1 << 8)
        if abi >= 3:
            writable |= 1 << 14
        allowed: dict[Path, int] = {job_directory.resolve(): writable}
        for runtime_path in ("/usr", "/lib", "/lib64", sys.prefix, sys.base_prefix):
            p = Path(runtime_path)
            if p.exists():
                allowed[p.resolve()] = readonly
        allowed[Path(__file__).resolve().parent] = readonly
        try:
            for path, access in allowed.items():
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                try:
                    rule = PathRule(access, fd)
                    if libc.syscall(445, ruleset_fd, 1, ctypes.byref(rule), 0) != 0:
                        raise SandboxUnavailable("Cannot add filesystem restriction")
                finally:
                    os.close(fd)
            if libc.syscall(446, ruleset_fd, 0) != 0:
                raise SandboxUnavailable("Cannot enforce filesystem restrictions")
        finally:
            os.close(ruleset_fd)

    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise SandboxUnavailable("Cannot initialize seccomp")
    denied = (
        "socket",
        "socketpair",
        "connect",
        "bind",
        "listen",
        "accept",
        "accept4",
        "sendto",
        "recvfrom",
        "sendmsg",
        "recvmsg",
        "sendmmsg",
        "recvmmsg",
        "execve",
        "execveat",
        "ptrace",
        "process_vm_readv",
        "process_vm_writev",
        "mount",
        "umount2",
        "unshare",
        "setns",
        "bpf",
        "perf_event_open",
        "keyctl",
        "add_key",
        "request_key",
        "fork",
        "vfork",
        "io_uring_setup",
        "setuid",
        "setgid",
        "setresuid",
        "setresgid",
        "setreuid",
        "setregid",
        "capset",
        "chroot",
    )
    try:
        for name in denied:
            number = seccomp.seccomp_syscall_resolve_name(name.encode())
            if (
                number >= 0
                and seccomp.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0
            ):
                raise SandboxUnavailable("Cannot install syscall restriction")

        class ArgCompare(ctypes.Structure):
            _fields_ = [
                ("arg", ctypes.c_uint),
                ("op", ctypes.c_uint),
                ("datum_a", ctypes.c_uint64),
                ("datum_b", ctypes.c_uint64),
            ]

        # Deny clone without CLONE_THREAD. Python/Arrow may create threads, never
        # child processes that outlive the launcher. clone3 falls back to clone.
        seccomp.seccomp_rule_add_array.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(ArgCompare),
        ]
        clone = seccomp.seccomp_syscall_resolve_name(b"clone")
        comparison = ArgCompare(0, 7, 0x10000, 0)  # SCMP_CMP_MASKED_EQ
        if (
            clone >= 0
            and seccomp.seccomp_rule_add_array(
                context, 0x00050000 | errno.EPERM, clone, 1, ctypes.byref(comparison)
            )
            != 0
        ):
            raise SandboxUnavailable("Cannot restrict process creation")
        clone3 = seccomp.seccomp_syscall_resolve_name(b"clone3")
        if (
            clone3 >= 0
            and seccomp.seccomp_rule_add(context, 0x00050000 | errno.ENOSYS, clone3, 0) != 0
        ):
            raise SandboxUnavailable("Cannot restrict process creation")
        if seccomp.seccomp_load(context) != 0:
            raise SandboxUnavailable("Cannot enforce network restrictions")
    finally:
        seccomp.seccomp_release(context)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (105, 110))
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    return {
        "network_denied": True,
        "filesystem_restricted": True,
        "resource_limits": True,
        "nonroot_parser": os.geteuid() != 0,
    }
