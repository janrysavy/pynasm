"""Small pinned live-oracle helper shared by new roadmap tests, not runtime code."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class OracleFailure(RuntimeError):
    """The reference failed to run; this is not a rejected assembly input."""


def verify_version(nasm: Path) -> str:
    try:
        result = subprocess.run([str(nasm), "-v"], capture_output=True,
                                text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OracleFailure(str(exc)) from exc
    version = result.stdout.strip()
    if result.returncode or not re.match(r"^NASM version 3\.02(?:\s|$)", version):
        raise OracleFailure(f"NASM 3.02 required; got {version!r}")
    return version


def reference(nasm: Path, source: str, level: int, *,
              files: dict[str, bytes] | None = None) -> bytes | None:
    """Return bytes or an ordinary NASM rejection; crashes/timeouts are errors."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, data in (files or {}).items():
            path = root / name
            if path.is_absolute() and root.resolve() not in path.resolve().parents:
                raise ValueError("oracle input must stay inside its temporary directory")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (root / "case.asm").write_text(source, encoding="ascii")
        try:
            result = subprocess.run([str(nasm), "-f", "bin", f"-O{level}",
                                     "-o", "case.bin", "case.asm"], cwd=root,
                                    capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OracleFailure(str(exc)) from exc
        if result.returncode == 1 and "error:" in result.stderr:
            return None
        if result.returncode:
            raise OracleFailure(f"NASM process failed ({result.returncode}): {result.stderr}")
        try:
            return (root / "case.bin").read_bytes()
        except OSError as exc:
            raise OracleFailure("NASM succeeded without producing its output") from exc
