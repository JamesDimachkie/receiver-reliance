"""Stable stdlib-only entrypoint for the portable receiver-reliance bundle."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import platform
import sys


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VERSION_FILE = HERE / "VERSION"
SECOND = ROOT / "second-implementation"
SIDECAR = ROOT / "perf" / "sidecar"
for path in (ROOT, SECOND, SIDECAR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load_beside(name: str):
    """Path-bound import of a module shipped beside this file.

    Binding by explicit file path instead of bare module name keeps the
    verifier import inside the manifest-covered local set — an ambient
    same-name module elsewhere on sys.path can never substitute for it —
    and works under isolated-mode spawning (`-I`), which removes the
    script directory from sys.path.
    """

    spec = importlib.util.spec_from_file_location(f"portable_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_verify_bundle = _load_beside("verify_bundle")
MANIFEST = _verify_bundle.MANIFEST
verify = _verify_bundle.verify


USAGE = "usage: python -B portable/cli.py {verify|doctor|preflight|decide|sidecar}\n"
EXIT_USAGE = 64
EXIT_STARTUP = 70


def _verified() -> bool:
    count, failures = verify()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return False
    return count > 0


def _doctor() -> int:
    count, failures = verify()
    manifest_seal = None
    if not failures:
        manifest_seal = json.loads(MANIFEST.read_text(encoding="utf-8"))["manifest_sha256"]
    record = {
        "bundle_files": count,
        "bundle_version": VERSION_FILE.read_text(encoding="ascii").strip(),
        "format_version": "RR-PORTABLE-DOCTOR-1",
        "implementation": platform.python_implementation(),
        "manifest_sha256": manifest_seal,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "status": "READY" if not failures else "NOT_READY",
        "system": platform.system(),
    }
    sys.stdout.buffer.write(
        (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )
    return 0 if not failures else EXIT_STARTUP


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"verify", "doctor", "preflight", "decide", "sidecar"}:
        # Binary write: byte-exact LF on every OS (no text-mode translation).
        sys.stderr.buffer.write(USAGE.encode("utf-8"))
        sys.stderr.buffer.flush()
        return EXIT_USAGE
    mode = args[0]
    if mode == "verify":
        count, failures = verify()
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"portable bundle: files={count} failures={len(failures)}")
        return 1 if failures else 0
    if mode == "doctor":
        return _doctor()
    if not _verified():
        return EXIT_STARTUP
    try:
        if mode == "preflight":
            from adapters.portable_preflight import process_jsonl

            return process_jsonl(sys.stdin, sys.stdout)
        if mode == "decide":
            from rr2 import execute

            code, output = execute(sys.stdin.buffer.read())
            sys.stdout.buffer.write(output)
            return code
        if mode == "sidecar":
            from rr_sidecar import serve

            return serve(sys.stdin.buffer, sys.stdout.buffer)
    except (BrokenPipeError, OSError, RuntimeError, ValueError):
        sys.stderr.write("portable-cli: bounded runtime failure\n")
        return EXIT_STARTUP
    raise AssertionError(mode)


if __name__ == "__main__":
    raise SystemExit(main())
