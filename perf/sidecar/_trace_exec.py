#!/usr/bin/env python3
"""Run one Python source file under a repo-read audit trace.

The caller supplies a unique empty ``-X pycache_prefix`` directory and ``-B``.
This bootstrap installs the hook before opening the target source, records its
own already-opened source explicitly, then executes the target with ``runpy``.

F-WP5-006 bound 5: every recorded read carries the digest of the bytes AS
OPENED.  The manifest used to pin each unique input once, after the run, so a
file mutated mid-run was recorded at its post-run content and the receipt
asserted that content was the execution input.  Pinning at the read makes a
mid-run mutation two different digests for one path instead of one late digest
that hides both.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import runpy
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
RECEIPTS = REPO / "perf" / "receipts"
READ_CHUNK_BYTES = 1024 * 1024


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", required=True, type=pathlib.Path)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("target", type=pathlib.Path)
    parser.add_argument("target_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    target = args.target.resolve()
    trace_dir = args.trace_dir.resolve()
    trace_dir.mkdir(parents=True, exist_ok=True)
    prefix = pathlib.Path(sys.pycache_prefix or "").resolve() if sys.pycache_prefix else None
    if prefix is None or not prefix.is_dir() or any(prefix.iterdir()):
        raise SystemExit("WP5 trace requires an existing empty -X pycache_prefix directory")
    if not sys.dont_write_bytecode:
        raise SystemExit("WP5 trace requires -B / dont_write_bytecode")

    if not args.trace_id or any(character not in "0123456789abcdef" for character in args.trace_id):
        raise SystemExit("--trace-id must be nonempty lowercase hexadecimal")
    trace_path = trace_dir / f"opens-{args.trace_id}.jsonl"
    meta_path = trace_dir / f"meta-{args.trace_id}.json"
    event_index = 0
    pinning = False

    def read_time_pin(resolved: pathlib.Path) -> tuple[str | None, int | None]:
        """Digest and length of the file as this read opened it.

        Hashing is itself an open, so the audit hook would record it and
        recurse.  ``pinning`` suppresses exactly that reentrance and nothing
        else: it is set and cleared around one read with no yield point between,
        and the hook consults it before doing any work.

        An input that cannot be read at the moment it is opened is pinned as
        ``None`` rather than dropped.  Dropping it would shrink a manifest that
        calls itself complete; a null digest fails closed in
        ``_evidence.execution_input_manifest``.
        """
        nonlocal pinning
        pinning = True
        try:
            digest = hashlib.sha256()
            length = 0
            with open(resolved, "rb") as handle:
                while True:
                    chunk = handle.read(READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    digest.update(chunk)
                    length += len(chunk)
            return digest.hexdigest().upper(), length
        except OSError:
            return None, None
        finally:
            pinning = False

    def record_path(raw_path: object, event: str) -> None:
        nonlocal event_index
        if not isinstance(raw_path, (str, bytes, os.PathLike)):
            return
        try:
            path = pathlib.Path(os.fsdecode(raw_path))
            if not path.is_absolute():
                path = pathlib.Path.cwd() / path
            resolved = path.resolve(strict=False)
            label = resolved.relative_to(REPO).as_posix()
        except (OSError, TypeError, ValueError):
            return
        if label.startswith("perf/receipts/") or label.startswith(".git/"):
            return
        # Pin repository source/data inputs. Directory probes and output opens
        # are not executable inputs; a later existence check admits only files.
        if not resolved.is_file():
            return
        digest, length = read_time_pin(resolved)
        row = {
            "event": event,
            "index": event_index,
            "path": label,
            "pid": os.getpid(),
            "sha256": digest,
            "bytes": length,
        }
        event_index += 1
        payload = canonical(row) + b"\n"
        descriptor = os.open(trace_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)

    def audit(event: str, values: tuple[object, ...]) -> None:
        if pinning:
            return
        if event == "open" and values:
            mode = values[1] if len(values) > 1 else None
            flags = values[2] if len(values) > 2 else None
            reading = isinstance(mode, str) and "r" in mode
            if mode is None and isinstance(flags, int):
                reading = (flags & (os.O_WRONLY | os.O_RDWR)) == 0
            if reading:
                record_path(values[0], event)

    sys.addaudithook(audit)
    record_path(pathlib.Path(__file__).resolve(), "bootstrap-source")
    os.environ["RR_WP5_TRACE_DIR"] = str(trace_dir)
    sys.argv = [str(target), *args.target_args]
    exit_code = 0
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as error:
        if error.code is None:
            exit_code = 0
        elif isinstance(error.code, int):
            exit_code = error.code
        else:
            print(error.code, file=sys.stderr)
            exit_code = 1
    finally:
        meta = {
            "schema": "receiver-reliance/wp5-audit-trace-process-2",
            "pid": os.getpid(),
            "trace_id": args.trace_id,
            "target": target.relative_to(REPO).as_posix(),
            "trace_file": trace_path.name,
            "trace_file_sha256": (
                hashlib.sha256(trace_path.read_bytes()).hexdigest().upper()
                if trace_path.is_file()
                else None
            ),
            "event_count": event_index,
            "input_pin_time": "read",
            "pycache_prefix": str(prefix),
            "pycache_empty_at_start": True,
            "pycache_empty_at_end": not any(prefix.rglob("*")),
            "dont_write_bytecode": sys.dont_write_bytecode,
            "executed_argv": list(sys.orig_argv),
            "exit_code": exit_code,
        }
        meta_path.write_bytes(canonical(meta) + b"\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
