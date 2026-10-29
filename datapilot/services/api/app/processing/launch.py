"""Parent-side bounded child launcher; uploads never run in the orchestrator process."""

import ctypes
import json
import math
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path

from app.processing.jail import prepare_jail
from app.processing.sandbox import SandboxUnavailable


class IngestionFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = (code, message)


def run_restricted(directory: Path, kind: str = "csv", *, probe: bool = False) -> dict:
    directory = directory.resolve()
    output_directory = directory
    jail = None
    identity = None
    libc = ctypes.CDLL(None, use_errno=True)
    if os.geteuid() == 0 or libc.syscall(444, 0, 0, 1) < 1:
        try:
            jail, output_directory, identity = prepare_jail(directory)
        except SandboxUnavailable as exc:
            raise IngestionFailure("sandbox_unavailable", str(exc)) from exc
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(directory),
        "TMPDIR": str(directory),
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "ARROW_NUM_THREADS": "1",
        "LC_ALL": "C.UTF-8",
    }
    command = [sys.executable, "-m", "app.processing.runner", "--directory", str(directory)]
    command += ["--probe"] if probe else ["--kind", kind]
    if jail is not None:
        command += ["--jail", str(jail), "--identity", str(identity)]
    process = subprocess.Popen(
        command,
        cwd=directory,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=115)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise IngestionFailure(
            "processing_timeout", "The file exceeded the processing time limit."
        ) from exc
    error_file = output_directory / "error.json"
    if code != 0:
        if error_file.exists() and error_file.stat().st_size <= 4096:
            error = json.loads(read_regular(error_file, 4096))
            raise IngestionFailure(error["code"], error["message"])
        raise IngestionFailure(
            "processing_failed", "Processing stopped or exceeded its resource limits."
        )
    manifest = output_directory / "result.json"
    if not manifest.is_file() or manifest.stat().st_size > 4 * 1024**2:
        raise IngestionFailure(
            "invalid_result", "The parser did not produce a bounded valid result."
        )
    result = json.loads(read_regular(manifest, 4 * 1024**2))
    if not probe:
        validate_result(result)
        if jail is not None:
            output = output_directory / "output.parquet"
            fd = os.open(output, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > 512 * 1024**2:
                    raise IngestionFailure("invalid_result", "Invalid parser output file.")
            finally:
                os.close(fd)
            output.replace(directory / "output.parquet")
    return result


def read_regular(path: Path, limit: int) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise IngestionFailure("invalid_result", "Invalid parser result file.")
        return handle.read(limit + 1).decode()


def validate_result(result: dict) -> None:
    try:
        rows, count = (result["row_count"], result["column_count"])
        require(isinstance(rows, int) and 0 <= rows <= 250000)
        require(isinstance(count, int) and 1 <= count <= 50)
        schema = result["schema_json"]
        columns, preview = (schema["columns"], schema["preview"])
        require(isinstance(columns, list) and len(columns) == count)
        names = set()
        for column in columns:
            require(isinstance(column["name"], str) and 0 < len(column["name"]) <= 125)
            require(column["name"] not in names)
            names.add(column["name"])
            require(column["type"] in ("integer", "number", "string", "date", "boolean"))
            require(isinstance(column["null_count"], int) and 0 <= column["null_count"] <= rows)
        require(isinstance(preview, list) and len(preview) <= min(rows, 100))
        for row in preview:
            require(isinstance(row, dict) and set(row) == names)
            for value in row.values():
                require(value is None or isinstance(value, (str, int, float, bool)))
                require(not isinstance(value, str) or len(value) <= 257)
                require(not isinstance(value, float) or math.isfinite(value))
        require(isinstance(schema["profile"], dict))
        require(isinstance(result["quality"], list) and len(result["quality"]) <= 110)
        for finding in result["quality"]:
            require(
                finding["rule_code"]
                in ("missing_values", "mixed_types", "duplicate_rows", "formula_like_values")
            )
            require(finding["severity"] in ("warning", "info"))
            require(finding["column_name"] is None or finding["column_name"] in names)
            require(
                isinstance(finding["affected_rows"], int) and 0 <= finding["affected_rows"] <= rows
            )
            require(isinstance(finding["details_json"], dict))
        require(isinstance(result["sha256"], str) and len(result["sha256"]) == 64)
        require(result["isolation"]["network_denied"] is True)
        require(result["isolation"]["filesystem_restricted"] is True)
    except (KeyError, TypeError, ValueError) as exc:
        raise IngestionFailure("invalid_result", "The parser returned an invalid result.") from exc


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("Invalid bounded parser result")
