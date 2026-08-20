"""receiver_reliance — library API over the frozen engine + grounded 0.4 layer.

Supported layouts: an editable install from a repo checkout (`pip install
-e .`), any sys.path arrangement where this package sits beside
`grounded-0_4/` and `baseline-run/`, or a self-contained distribution that
carries those engine files under `receiver_reliance/_engine/`. Whichever
layout is found, import verifies every engine file against
`engine_manifest.json` by byte length and SHA-256 before executing any of
them, and refuses to import on drift -- so an installed copy proves it holds
the bytes the repository publishes rather than asserting it. Regenerate or
verify that manifest with `python -B
receiver_reliance/generate_engine_manifest.py [--check]`.

The heavy lifting lives in `grounded-0_4/rr_api.py`; this package is the
stable import surface:

    from receiver_reliance import decide_audited

`decide_audited(request)` is the ONE supported evidentiary decision API: it
returns the grounded audited decision (input-bound seal, governing-policy
digests, witness trace, closure findings, truncation-disclosed record
references). There is no supported bare-decision route: the former
top-level `decide` export returned sealed responses that bind no decision
facts (ERRATA E2) and bypass the 0.4 closures (E5), so it was withdrawn
from the supported surface (deep-scan findings csf_abbd6848 /
csf_0479d1a9, 2026-08-16). Frozen-engine execution for conformance
reproduction lives in `receiver_reliance.conformance` under an explicitly
non-evidentiary name. See TRUST_MODEL.md for what each seal proves and
HOST_OBLIGATIONS.md H5 for the host's transcript duty.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys
import time
from typing import Callable, NamedTuple

_HERE = pathlib.Path(__file__).resolve().parent
_ENGINE_ENTRY = "grounded-0_4/rr_api.py"


def _engine_root() -> pathlib.Path:
    """The directory the engine files are relative to, in either layout."""
    for candidate in (_HERE.parent, _HERE / "_engine"):
        if candidate.joinpath(*_ENGINE_ENTRY.split("/")).is_file():
            return candidate
    raise ImportError(
        "receiver_reliance cannot locate its engine: expected "
        f"{_ENGINE_ENTRY} either beside the package (repo checkout, looked at "
        f"{_HERE.parent}) or bundled at {_HERE / '_engine'}"
    )


def _reject_duplicate_keys(pairs: list) -> dict:
    """A duplicate member is ambiguous evidence, so refuse it rather than pick one.

    `json.loads` keeps the LAST value for a repeated key. A manifest carrying the
    real eleven rows followed by eleven forged ones therefore passes a
    `len(records) == file_count` check while the loader verifies engine bytes
    against the forged digests -- and a human reading the file, or any tool that
    takes the first value, sees the real ones. That is the ambiguous-evidence
    class `portability/strict_ingest.py` exists to close; this is the same law,
    restated here because the package ships in a wheel that does not carry
    `portability/`.
    """
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate object key: {key!r}")
        seen[key] = value
    return seen


def _strict_json_object(text: str) -> dict:
    value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(value, dict):
        raise ValueError("engine manifest is not a JSON object")
    return value


def _jcs(value: object) -> bytes:
    """Byte-identical to `generate_engine_manifest.jcs`, which produced the seal."""
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _self_zero(value: dict, field: str) -> str:
    probe = dict(value)
    probe[field] = "0" * 64
    return hashlib.sha256(_jcs(probe)).hexdigest().upper()


def _verify_engine(root: pathlib.Path) -> dict:
    """Refuse to import an engine whose bytes are not the published ones.

    The package is the surface a third party uses, so a partial checkout or a
    distribution built from the wrong tree has to fail here rather than produce
    decisions from unknown code.
    """
    manifest_path = _HERE / "engine_manifest.json"
    if not manifest_path.is_file():
        raise ImportError(f"receiver_reliance engine manifest absent: {manifest_path}")
    try:
        manifest = _strict_json_object(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ImportError(f"receiver_reliance engine manifest is malformed: {exc}") from None
    recorded_seal = manifest.get("manifest_sha256")
    if not isinstance(recorded_seal, str) or len(recorded_seal) != 64:
        raise ImportError("receiver_reliance engine manifest carries no self-seal")
    if _self_zero(manifest, "manifest_sha256") != recorded_seal.upper():
        raise ImportError(
            "receiver_reliance engine manifest self-seal does not match its own "
            "contents; the manifest has been edited since it was generated"
        )
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != manifest.get("file_count"):
        raise ImportError("receiver_reliance engine manifest is malformed")
    for record in records:
        path = root.joinpath(*record["path"].split("/"))
        if not path.is_file():
            raise ImportError(
                f"receiver_reliance engine file absent: {record['path']} (looked at {path})"
            )
        raw = path.read_bytes()
        if len(raw) != record["byte_length"] or hashlib.sha256(raw).hexdigest().upper() != record["sha256"]:
            raise ImportError(
                "receiver_reliance engine drift: "
                f"{record['path']} does not match engine_manifest.json "
                f"(expected {record['byte_length']} bytes / {record['sha256']}, "
                f"found {len(raw)} bytes / {hashlib.sha256(raw).hexdigest().upper()})"
            )
    return manifest


_REPO = _engine_root()
ENGINE_MANIFEST = _verify_engine(_REPO)
_RR_API = _REPO.joinpath(*_ENGINE_ENTRY.split("/"))
_spec = importlib.util.spec_from_file_location("receiver_reliance._rr_api", _RR_API)
_module = importlib.util.module_from_spec(_spec)
sys.modules["receiver_reliance._rr_api"] = _module
_spec.loader.exec_module(_module)

decide_audited = _module.decide_audited
closure_findings = _module.closure_findings
derive_record_references = _module.derive_record_references
AUDIT_FORMAT = _module.AUDIT_FORMAT

def verify_audit_seal(envelope: object) -> bool:
    """Recompute an audit envelope's self-zero seal from the envelope's own bytes.

    ``decide_audited`` seals every envelope it returns, and until this release
    nothing on the supported surface could CHECK that seal: a recipient had to
    reimplement RFC 8785 canonicalization plus the field-zeroing convention, or
    reach into the engine-internal ``b1`` handle that README declares reachable
    by construction and deliberately not an API. An artifact whose thesis is
    that its results are content-addressed and independently checkable could
    produce its central evidentiary object and could not verify one.

    This recomputes ``audit_sha256`` over the envelope with that field zeroed,
    exactly as the producer computed it, and compares. It is total: anything
    that is not a sealed envelope returns False rather than raising, so it is
    safe to call on bytes you did not produce.

    What a True proves: these envelope bytes are internally intact and were
    sealed by something implementing this contract. What it does NOT prove: who
    produced it, when, or that the facts it judged were true. Nothing in this
    repository is signed, deliberately (TRUST_MODEL.md), so a party who can
    author an envelope can author its seal. This detects corruption, truncation
    and tampering-in-transit. It is not authentication.
    """
    if not isinstance(envelope, dict):
        return False
    recorded = envelope.get("audit_sha256")
    if not isinstance(recorded, str) or len(recorded) != 64:
        return False
    try:
        recomputed = _module.b1.self_zero_sha256(envelope, "audit_sha256")
    except (TypeError, ValueError, RecursionError, AttributeError):
        return False
    return recomputed == recorded.upper()


# --- observability -------------------------------------------------------
#
# An observer is an ARGUMENT. There is no install call here, no module-level
# slot holding one, and no environment variable that turns one on, so two
# callers in one process cannot silently instrument each other and a caller
# that passes none is not instrumented at all.
#
# Observability here is a property of the WRAPPER, not of the engine. No
# sealed envelope records that an observer was attached, because no part of a
# decision depends on one: the same request yields the same envelope bytes and
# the same audit seal, observed or not. An envelope is therefore not evidence
# about who was watching and cannot be read as any.
#
# Why the seam exists at all: this artifact prices a decision by request
# length, and that proxy under-charges 43 of the 136 requests in its own
# measured corpus at p50 (2026-08-19 measurement phase; the same run put the
# probe body at well under a thousandth of a decision). An admission bound
# built on a proxy that is wrong a third of the time is a bound on paper.
# Measuring precedes bounding, so the measuring lands first and alone.

class DecisionObservation(NamedTuple):
    """What an observer is handed: one decision's outcome and cost, as scalars.

    Every field is an ``int``, a ``str`` or ``None``. The record holds no
    reference to the envelope, to the response bytes, or to the request, so an
    observer that keeps one cannot reach the decision through it, and a host
    may retain it without retaining request content.

    ``decision_class`` and ``exit_code`` are the envelope's own
    ``audited_behavior_class`` and ``exit_code``. ``request_bytes`` is the
    request's length when the request was exact wire bytes and ``None``
    otherwise: an object has no wire length until the engine canonicalizes it,
    and this wrapper does not canonicalize on the engine's behalf to obtain
    one. ``response_bytes`` is the serialized response's length, and is
    ``None`` from ``decide_audited_observed``, which forms no response bytes.

    The three spans partition the wrapper's wall time. ``ingest_ns`` is the
    wrapper's own pre-engine work and nothing else -- decoding, duplicate-key
    rejection, canonicalization and the size ceiling all happen inside the
    frozen engine behind ``decide_audited``, where a wrapper cannot see them.
    Today the wrapper admits nothing, so ``ingest_ns`` is the cost of reading a
    length; that is the honest report, and it is the number that would move
    first if an admission bound were ever added at this seam. ``decide_ns`` is
    the ``decide_audited`` call. ``serialize_ns`` is JCS serialization plus the
    terminating LF, and is ``None`` when nothing was serialized. ``wall_ns``
    spans the whole wrapper and is not the sum of the three: it also covers the
    wrapper's own bookkeeping between them.

    ``cpu_ns`` is process CPU time over that same span, from
    ``time.process_time_ns``. Two limits, both real. It is process-wide, so in
    a threaded host it counts other threads' work as well. And its granularity
    is the platform's: where a tick is coarser than a decision, ``cpu_ns`` is a
    tick counter rather than a measurement. Measured on Windows/CPython 3.12,
    the effective tick is 15,625,000 ns against a decision of roughly 2.8 ms,
    so nearly every record on that host reports zero -- while
    ``time.get_clock_info("process_time").resolution`` there *declares* 100 ns.
    No constant is published for this, because the interpreter's declared value
    is the one number that would be wrong. ``test_observe.py`` measures the
    effective tick on whatever host runs it and prints it; read that, not a
    declaration, before believing this field.
    """

    decision_class: str
    exit_code: int
    request_bytes: int | None
    response_bytes: int | None
    ingest_ns: int
    decide_ns: int
    serialize_ns: int | None
    wall_ns: int
    cpu_ns: int


def _notify(
    observer: Callable[[DecisionObservation], object],
    envelope: dict,
    request_bytes: int | None,
    response_bytes: int | None,
    ingest_ns: int,
    decide_ns: int,
    serialize_ns: int | None,
    wall_ns: int,
    cpu_ns: int,
) -> None:
    """Build one record and hand it over, after the result already exists.

    The observer's return value is discarded, so an observer cannot substitute
    a decision by returning one -- the shape that refuted the first attempt at
    this seam, where an observer returned the envelope and a host that added a
    correlation id to it moved the response from 1,774 bytes to 1,799.

    Every exception it raises is discarded too, of any class, so that "an
    observer cannot change a decision" is total rather than true for the
    exception classes someone remembered. Two consequences, disclosed rather
    than hidden: a broken observer is invisible to the caller and has to carry
    its own error channel, and a ``KeyboardInterrupt`` delivered while the
    observer is running is swallowed with it -- a window an observer widens by
    blocking. Constructing the record happens inside the same protected region,
    so a defect in this function cannot reach the caller either.

    What this does not do is sandbox. One frame above an observer there is
    nothing but the record and the observer itself -- the envelope is released
    before the call, and the suite pins that -- but an observer that walks
    ``f_back`` reaches the wrapper and the decision it is holding. That is not
    a hole this seam opened: a host able to pass an observer was already able
    to rebind ``decide_audited`` outright. The guarantee is that the seam hands
    over no reference and takes no authority, not that Python withholds
    authority the caller already had. ``receiver_reliance/test_observe.py``
    pins the limit with a frame-walking observer that must SUCCEED. An
    untrusted observer belongs in another process.
    """
    try:
        observation = DecisionObservation(
            decision_class=envelope["audited_behavior_class"],
            exit_code=envelope["exit_code"],
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            ingest_ns=ingest_ns,
            decide_ns=decide_ns,
            serialize_ns=serialize_ns,
            wall_ns=wall_ns,
            cpu_ns=cpu_ns,
        )
        # Load-bearing, not tidiness: without it this frame still holds the
        # envelope, and an observer reading one frame up would be handed the
        # decision after all. Extraction stays inside the protected region.
        del envelope
        observer(observation)
    except BaseException:
        return


def decide_audited_observed(
    request: object,
    observer: Callable[[DecisionObservation], object] | None = None,
) -> dict:
    """``decide_audited``, with one observation handed over after it returns.

    Returns what ``decide_audited(request)`` returns: equal as an object and
    byte-identical under JCS, for every input either accepts, with any observer
    or none. ``observer=None`` is the default and is a passthrough -- one
    identity test, then the same call, with no clock read taken and no record
    built. An observer is called exactly once per decision, never before the
    envelope is complete, and never on the passthrough.

    ``receiver_reliance/test_observe.py`` is the proof: ``examples/``, the 124
    committed semantic fixtures in both object and wire form, the
    protocol-error and object-refusal surfaces, and a deterministic
    ``fuzz/fuzz.py`` sample, each decided with and without observers and
    compared byte-for-byte.
    """
    if observer is None:
        return decide_audited(request)
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    request_bytes = len(request) if type(request) is bytes else None
    ingest_end = time.perf_counter_ns()
    envelope = decide_audited(request)
    decide_end = time.perf_counter_ns()
    end_cpu = time.process_time_ns()
    _notify(
        observer,
        envelope,
        request_bytes,
        None,
        ingest_end - start_wall,
        decide_end - ingest_end,
        None,
        decide_end - start_wall,
        end_cpu - start_cpu,
    )
    return envelope


def response_bytes_observed(
    request: object,
    observer: Callable[[DecisionObservation], object] | None = None,
) -> bytes:
    """One NDJSON response line, with one observation handed over after it exists.

    For exact wire bytes this returns what ``grounded-0_4/rr_batch.py``'s
    ``response_bytes`` returns -- the JCS envelope and a terminating LF -- and
    the proof suite pins that equality across the corpus rather than asserting
    it. It accepts the same input domain as ``decide_audited``, so an object
    request is answered with the line the engine would produce for its
    canonical bytes.

    This is the only route on which ``serialize_ns`` and ``response_bytes`` can
    be observed, because it is the only one where the wrapper forms response
    bytes. It reads and writes no stream: ``rr_batch.serve`` remains the
    transport, and a host wanting an observed stream calls this once per line.
    """
    if observer is None:
        return _module.b1.jcs_bytes(decide_audited(request)) + b"\n"
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    request_bytes = len(request) if type(request) is bytes else None
    ingest_end = time.perf_counter_ns()
    envelope = decide_audited(request)
    decide_end = time.perf_counter_ns()
    response = _module.b1.jcs_bytes(envelope) + b"\n"
    serialize_end = time.perf_counter_ns()
    end_cpu = time.process_time_ns()
    _notify(
        observer,
        envelope,
        request_bytes,
        len(response),
        ingest_end - start_wall,
        decide_end - ingest_end,
        serialize_end - decide_end,
        serialize_end - start_wall,
        end_cpu - start_cpu,
    )
    return response


ENGINE_MANIFEST_SHA256 = ENGINE_MANIFEST["manifest_sha256"]

__all__ = [
    "decide_audited",
    "decide_audited_observed",
    "response_bytes_observed",
    "verify_audit_seal",
    "closure_findings",
    "derive_record_references",
    "AUDIT_FORMAT",
    "DecisionObservation",
    "ENGINE_MANIFEST_SHA256",
]
# Tracks pyproject.toml's `version`, and the two move together. A `.devN`
# suffix means these bytes are past the last tag and are not a released
# version: `git describe --tags` names the tag they are ahead of. Cutting a
# release replaces the suffix; the next commit after a tag restores one.
__version__ = "1.3.0.dev0"
