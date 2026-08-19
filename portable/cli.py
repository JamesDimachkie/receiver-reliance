"""Stable stdlib-only entrypoint for the portable receiver-reliance bundle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import platform
import sys
import types
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VERSION_FILE = HERE / "VERSION"
MANIFEST_PATH = HERE / "MANIFEST.json"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_RUNTIME_MODULE_BYTES = 16 * 1024 * 1024
SHARED_INGEST_LAW = "portability/strict_ingest.py"
ZERO64 = "0" * 64
HEX = frozenset("0123456789ABCDEF")
SUPPORTED_IMPLEMENTATION = "CPython"
SUPPORTED_PYTHON_VERSIONS = frozenset({(3, 12), (3, 13), (3, 14)})


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in HEX for char in value)


def _canonical_manifest(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _read_bounded(path: pathlib.Path, max_bytes: int, label: str) -> bytes:
    """Read a regular nonsymlink file with a pre-allocation byte ceiling."""

    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} must be a regular nonsymlink file")
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise RuntimeError(f"{label} exceeds {max_bytes} bytes")
    return raw


def _bootstrap_shared_law() -> tuple[types.ModuleType, dict[str, bytes]]:
    """Execute ADOPTION A4's one ingest law, the sole pre-index bootstrap.

    The manifest index is what byte-authenticates every other declared module,
    and A4 requires the index itself to be admitted under the shared law, so the
    law's own bytes are the one thing the index cannot cover before it exists.
    They are not left unchecked: `_authenticate_bootstrap` re-checks every byte
    executed here against its declared manifest row as soon as the index is
    built -- before any other repository module loads and before any command
    runs -- so an undeclared or altered law stops this process at import.

    The law names the frozen core it reads its bounds from (`CORE_PATH`), so the
    core's path is read from the law rather than restated here.
    """

    name = "rr_strict_ingest"
    executed: dict[str, bytes] = {}
    module = sys.modules.get(name)
    if module is None:
        pure = pathlib.PurePosixPath(SHARED_INGEST_LAW)
        path = ROOT.joinpath(*pure.parts)
        raw = _read_bounded(path, MAX_RUNTIME_MODULE_BYTES, "shared ingest law")
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__spec__ = importlib.util.spec_from_loader(
            name, loader=None, origin=str(path)
        )
        sys.modules[name] = module
        try:
            exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        executed[SHARED_INGEST_LAW] = raw
    core = pathlib.Path(module.CORE_PATH)
    try:
        core_relative = core.relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"shared ingest law reads a core outside the bundle: {core}") from exc
    executed[core_relative] = _read_bounded(
        core, MAX_RUNTIME_MODULE_BYTES, "frozen ingest core"
    )
    return module, executed


def _read_manifest_index() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Authenticate the manifest index before any decision module executes."""

    raw = _read_bounded(MANIFEST_PATH, MAX_MANIFEST_BYTES, "portable manifest")
    try:
        manifest = _STRICT_INGEST.load_safe(raw, label="portable manifest")
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError(f"portable manifest is invalid: {exc}") from exc
    required = {
        "files",
        "format_version",
        "inventory_sha256",
        "manifest_sha256",
        "path_contract",
        "runtime_contract",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise RuntimeError("portable manifest top-level members are not closed")
    if manifest["format_version"] != "RR-PORTABLE-BUNDLE-MANIFEST-1":
        raise RuntimeError("portable manifest format is unsupported")
    if not _sha(manifest["manifest_sha256"]):
        raise RuntimeError("portable manifest seal is malformed")
    sealed = dict(manifest)
    expected_seal = sealed["manifest_sha256"]
    sealed["manifest_sha256"] = ZERO64
    actual_seal = hashlib.sha256(_canonical_manifest(sealed)).hexdigest().upper()
    if actual_seal != expected_seal:
        raise RuntimeError("portable manifest self-seal mismatch")
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("portable manifest files must be a nonempty array")
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"byte_length", "path", "role", "sha256"}:
            raise RuntimeError("portable manifest file row is not closed")
        relpath = row["path"]
        if not isinstance(relpath, str) or not relpath or relpath in index:
            raise RuntimeError("portable manifest path is invalid or duplicated")
        if (
            not isinstance(row["byte_length"], int)
            or isinstance(row["byte_length"], bool)
            or row["byte_length"] < 0
            or not _sha(row["sha256"])
        ):
            raise RuntimeError(f"portable manifest declaration is invalid: {relpath}")
        index[relpath] = row
    return manifest, index


def _authenticate_bootstrap() -> None:
    """Bind the pre-index bootstrap bytes to the index they were used to read."""

    for relpath, raw in sorted(_BOOTSTRAP_BYTES.items()):
        row = _MANIFEST_ROWS.get(relpath)
        if row is None:
            raise RuntimeError(f"bootstrap module is undeclared: {relpath}")
        if (
            len(raw) != row["byte_length"]
            or hashlib.sha256(raw).hexdigest().upper() != row["sha256"]
        ):
            raise RuntimeError(f"bootstrap module failed byte authentication: {relpath}")


_STRICT_INGEST, _BOOTSTRAP_BYTES = _bootstrap_shared_law()
_MANIFEST, _MANIFEST_ROWS = _read_manifest_index()
_authenticate_bootstrap()


def _declared_source(relpath: str) -> tuple[pathlib.Path, bytes]:
    """Read one declared repository module with a pre-allocation byte ceiling."""

    row = _MANIFEST_ROWS.get(relpath)
    if row is None:
        raise RuntimeError(f"runtime module is undeclared: {relpath}")
    expected_length = row["byte_length"]
    if expected_length > MAX_RUNTIME_MODULE_BYTES:
        raise RuntimeError(f"runtime module exceeds {MAX_RUNTIME_MODULE_BYTES} bytes: {relpath}")
    pure = pathlib.PurePosixPath(relpath)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise RuntimeError(f"runtime module path is unsafe: {relpath}")
    path = ROOT.joinpath(*pure.parts)
    cursor = ROOT
    for part in pure.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise RuntimeError(f"runtime module path crosses a symlink: {relpath}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"runtime module is unavailable: {relpath}: {exc}") from exc
    if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
        raise RuntimeError(f"runtime module is outside the repository or not a file: {relpath}")
    with resolved.open("rb") as stream:
        raw = stream.read(expected_length + 1)
    if (
        len(raw) != expected_length
        or hashlib.sha256(raw).hexdigest().upper() != row["sha256"]
    ):
        raise RuntimeError(f"runtime module failed byte authentication: {relpath}")
    return resolved, raw


def _load_manifest_module(
    name: str,
    relpath: str,
    *,
    aliases: tuple[tuple[str, types.ModuleType], ...] = (),
) -> types.ModuleType:
    """Execute only authenticated declared bytes, with project imports path-bound."""

    path, raw = _declared_source(relpath)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    module.__spec__ = importlib.util.spec_from_loader(name, loader=None, origin=str(path))
    absent = object()
    previous_path = list(sys.path)
    previous_modules = {
        alias: sys.modules.get(alias, absent) for alias, _target in aliases
    }
    previous_name = sys.modules.get(name, absent)
    sys.modules[name] = module
    for alias, target in aliases:
        sys.modules[alias] = target
    try:
        exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    except BaseException:
        if previous_name is absent:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous_name
        raise
    finally:
        sys.path[:] = previous_path
        for alias, previous in previous_modules.items():
            if previous is absent:
                sys.modules.pop(alias, None)
            else:
                sys.modules[alias] = previous
    return module


_verify_bundle = _load_manifest_module(
    "_receiver_reliance_portable_verify_bundle", "portable/verify_bundle.py"
)
MANIFEST = _verify_bundle.MANIFEST
verify = _verify_bundle.verify


USAGE = "usage: python -B portable/cli.py {verify|doctor|preflight|decide|sidecar}\n"
EXIT_USAGE = 64
EXIT_STARTUP = 70


def _binary(stream: Any) -> Any:
    return getattr(stream, "buffer", stream)


def _write_bytes(stream: Any, raw: bytes) -> None:
    target = _binary(stream)
    target.write(raw)
    target.flush()


def _runtime_identity() -> tuple[str, tuple[int, int]]:
    return platform.python_implementation(), (sys.version_info.major, sys.version_info.minor)


def _runtime_failures() -> list[str]:
    implementation, version = _runtime_identity()
    if implementation == SUPPORTED_IMPLEMENTATION and version in SUPPORTED_PYTHON_VERSIONS:
        return []
    return [
        "runtime:unsupported:"
        f"{implementation}-{version[0]}.{version[1]}:requires-CPython-3.12-3.14"
    ]


def _verification() -> tuple[int, list[str]]:
    count, failures = verify()
    return count, [*failures, *_runtime_failures()]


def _emit_failures(failures: list[str], stream: Any) -> None:
    for failure in failures:
        _write_bytes(stream, f"FAIL {failure}\n".encode("utf-8", errors="backslashreplace"))


def _verified() -> bool:
    count, failures = _verification()
    if failures:
        _emit_failures(failures, sys.stderr)
        return False
    return count > 0


def _doctor() -> int:
    count, failures = _verification()
    manifest_seal = None
    if not failures:
        manifest_seal = _MANIFEST["manifest_sha256"]
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
    _write_bytes(
        sys.stdout,
        (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
    )
    return 0 if not failures else EXIT_STARTUP


def _preflight_module() -> types.ModuleType:
    return _load_manifest_module(
        "_receiver_reliance_portable_preflight", "adapters/portable_preflight.py"
    )


def _decision_module() -> types.ModuleType:
    return _load_manifest_module(
        "_receiver_reliance_portable_rr2", "second-implementation/rr2.py"
    )


def _sidecar_module() -> types.ModuleType:
    rr_api = _load_manifest_module(
        "_receiver_reliance_portable_rr_api", "grounded-0_4/rr_api.py"
    )
    rr_batch = _load_manifest_module(
        "_receiver_reliance_portable_rr_batch",
        "grounded-0_4/rr_batch.py",
        aliases=(("rr_api", rr_api),),
    )
    transport = _load_manifest_module(
        "_receiver_reliance_portable_transport_envelope",
        "perf/sidecar/transport_envelope.py",
    )
    return _load_manifest_module(
        "_receiver_reliance_portable_rr_sidecar",
        "perf/sidecar/rr_sidecar.py",
        aliases=(("rr_batch", rr_batch), ("transport_envelope", transport)),
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"verify", "doctor", "preflight", "decide", "sidecar"}:
        _write_bytes(sys.stderr, USAGE.encode("utf-8"))
        return EXIT_USAGE
    mode = args[0]
    if mode == "verify":
        count, failures = _verification()
        _emit_failures(failures, sys.stdout)
        _write_bytes(
            sys.stdout,
            f"portable bundle: files={count} failures={len(failures)}\n".encode("utf-8"),
        )
        return 1 if failures else 0
    if mode == "doctor":
        return _doctor()
    if not _verified():
        return EXIT_STARTUP
    try:
        if mode == "preflight":
            process_jsonl = _preflight_module().process_jsonl
            return process_jsonl(_binary(sys.stdin), _binary(sys.stdout))
        if mode == "decide":
            engine = _decision_module()
            # Bounded acquisition BEFORE any allocation-scale read: at most
            # MAX_RAW_BYTES + 1 bytes enter memory; the engine's own limit
            # law then classifies the over-size case deterministically.
            limit = engine.MAX_RAW_BYTES
            code, output = engine.execute(_binary(sys.stdin).read(limit + 1))
            _write_bytes(sys.stdout, output)
            return code
        if mode == "sidecar":
            return _sidecar_module().serve(_binary(sys.stdin), _binary(sys.stdout))
    except (BrokenPipeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
        _write_bytes(sys.stderr, b"portable-cli: bounded runtime failure\n")
        return EXIT_STARTUP
    raise AssertionError(mode)


if __name__ == "__main__":
    raise SystemExit(main())
