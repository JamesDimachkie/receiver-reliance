"""Subprocess helpers with repository-bytecode isolation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
CLI_FLAGS = ("-I", "-B", "-X", "pycache_prefix=<unique-empty-temp-root>")


def run_candidate_cli(raw: bytes) -> subprocess.CompletedProcess[bytes]:
    """Execute the candidate CLI with an empty, per-process pycache root."""
    with tempfile.TemporaryDirectory(prefix="rr2-cli-pycache-") as cache_text:
        cache = Path(cache_text)
        if any(cache.iterdir()):
            raise RuntimeError("candidate CLI pycache root was not empty at start")
        process = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-X",
                f"pycache_prefix={cache}",
                str(HERE / "cli.py"),
                "execute",
            ],
            input=raw,
            capture_output=True,
            check=False,
        )
        if any(cache.rglob("*")):
            raise RuntimeError("candidate CLI wrote a pycache artifact")
        return process
