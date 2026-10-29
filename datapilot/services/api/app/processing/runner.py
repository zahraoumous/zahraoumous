"""Entry point for the short-lived restricted ingestion process."""

import argparse
import json
import os
import socket
import sys
from pathlib import Path

from app.processing.parser import ParseError, parse
from app.processing.sandbox import SandboxUnavailable, restrict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--kind", choices=("csv", "xlsx"))
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--jail")
    parser.add_argument("--identity", type=int)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    try:
        isolation = restrict(
            directory, jail=Path(args.jail) if args.jail else None, identity=args.identity
        )
        if args.jail:
            directory = Path("/job")
        result: dict
        if args.probe:
            try:
                socket.socket()
                network_denied = False
            except PermissionError:
                network_denied = True
            try:
                Path("/etc/passwd").read_text()
                filesystem_denied = False
            except (PermissionError, FileNotFoundError):
                filesystem_denied = True
            result = {
                "network_denied": network_denied,
                "filesystem_denied": filesystem_denied,
                "nonroot_parser": os.geteuid() != 0,
                "credentials_absent": not any(
                    name.startswith(("AWS_", "DATAPILOT_", "AZURE_", "OPENAI_"))
                    for name in os.environ
                ),
            }
        else:
            result = parse(directory / "input", args.kind, directory / "output.parquet")
            result["isolation"] = isolation
        (directory / "result.json").write_text(json.dumps(result, allow_nan=False))
        return 0
    except SandboxUnavailable:
        error = {
            "code": "sandbox_unavailable",
            "message": "Linux filesystem isolation and seccomp are required for file processing.",
        }
    except ParseError as exc:
        error = {"code": exc.code, "message": exc.message}
    except MemoryError:
        error = {
            "code": "memory_limit",
            "message": "The file exceeded the processing memory limit.",
        }
    except Exception:
        error = {"code": "processing_failed", "message": "The file could not be processed safely."}
    try:
        (directory / "error.json").write_text(json.dumps(error))
    except OSError:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
