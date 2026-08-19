"""A pre-engine admission bound: refuse a request on its BYTE LENGTH before the
frozen engine is asked to classify it.

**Off unless an operator turns it on.** With `RR_ADMISSION_MAX_REQUEST_BYTES`
unset there is no bound, `from_environment()` returns None, and
`decide_audited_admitted(raw, None)` is the ungated
`receiver_reliance.decide_audited(raw)` call itself — same object, same
envelope, same bytes. That mirrors `portability/pinned_tools.py`: hardening is
something an operator enables, not a migration the artifact performs.

Why it exists. The frozen 0.2/0.3 error law obliges the engine to prove no
ERR_SCHEMA (precedence 80) applies before it may emit ERR_LIMIT (precedence
90), and to select the smallest RFC 6901 pointer among all violations. Both are
full traversals, repeated once per `oneOf` branch, so the frozen bytes walk
every member of an attacker-supplied object after it has already failed. The
frozen ceiling is `MAX_INPUT_BYTES = 16,777,216`, and the cost of reaching it is
seconds per request. That is not fixable inside 0.2/0.3, whose exact bytes are
the subject of the published evidence. It is fixable here, by declining to ask
the question.

**What it costs, stated because it is not free.** Read
`deployment/README.md` before enabling anything here: no byte bound low enough
to matter admits every request the published contract declares valid. The
derived contract maximum is 3,392,691 bytes against a published corpus maximum
of 4,399 — a factor of 771 — so a deployment that bounds cost is a deployment
that has narrowed its own contract, and owes its callers that fact.
`HOST_OBLIGATIONS.md` H7 states the obligation; this module is one way to meet
it.

What this is NOT. Not a second implementation of the wire law: no schema, no
JSON pointer, no error code, no obligation id, no parser. It does not decode
UTF-8. It counts bytes. It is not a security boundary — `TRUST_MODEL.md` and
`README.md` disclaim security claims for every surface here, and this one adds
none.

Refusal-only. `admit()` has no accept path: it returns a refusal or None. None
means "not refused here" — the identical object goes to `decide_audited`, which
remains the sole classifier. Byte-identity of every admitted envelope is a
property of the construction, not of a test.
"""
from __future__ import annotations

import hashlib
import os
import sys
from typing import Any, Final

import receiver_reliance as _package  # import verifies engine bytes vs engine_manifest.json

_FROZEN: Final = sys.modules["receiver_reliance._rr_api"].b1

#: Own version, not a generation of the wire law. 0.5 is PROPOSED / NOT ADOPTED
#: (`orchestration/LEDGER.md` P7); naming it here would mint a wire format for
#: an unadopted generation, which is `ERRATA.md` E1's defect class.
ADMISSION_FORMAT: Final = "RR-ADMISSION-REFUSAL-1"

#: The environment variables an operator sets to declare a profile. Unset means
#: no profile, exactly as an unset `RR_TOOL_DIR` means ambient PATH resolution.
MAX_REQUEST_BYTES_ENV: Final = "RR_ADMISSION_MAX_REQUEST_BYTES"
MAX_STRUCTURAL_MEMBERS_ENV: Final = "RR_ADMISSION_MAX_STRUCTURAL_MEMBERS"

#: Derived from the two published contracts by taking, for every
#: `decision_input_schema/oneOf` branch, the maximum serialized size its
#: declared `maxItems`/`maxLength`/`const`/`enum` permit. These are NOT limits;
#: they are the numbers a deployment needs in order to know what a bound costs
#: it. Reproduce, and check against these constants, with
#: `python -B deployment/derive_admission_numbers.py --extent --check`.
CONTRACT_MAX_REQUEST_BYTES: Final = 3_392_691          # oneOf/27, OBL-28
CONTRACT_MAX_STRUCTURAL_TOKENS: Final = 454_409        # oneOf/13, OBL-14

#: The artifact's own fixture corpus: 124 core semantic requests plus 248
#: wrapper parity arms, as exact JCS+LF wire bytes. Observations, not limits.
CORPUS_REQUESTS: Final = 372
CORPUS_MAX_REQUEST_BYTES: Final = 4_399

_STRUCTURAL: Final = (b",", b"{", b"[")


class AdmissionBound:
    """A deployment's declared admission limits, pinned under the frozen ones.

    `max_request_bytes` is the only cost control. Engine cost at a fixed input
    size is bounded above by the worst adversarial shape at that size;
    `deployment/README.md` tabulates the worst of five shapes tried, measured.

    `max_structural_members` is OPTIONAL and defaults to off. It counts `,`,
    `{` and `[` bytes, which dominates the member count of any document, so it
    bounds members. It does NOT bound cost, and must not be sold as if it did:
    measured on CPython 3.12.10 / Windows 11 10.0.26200 / AMD64, a
    contract-legal OBL-01 request at declared caps carries 82,363 structural
    tokens and costs 9.2 ms (3.5x a legitimate decision), while an adversarial
    request carrying 18,057 costs 566 ms (216x). The proxy is anti-correlated
    with cost on exactly the pair that matters, because commas inside string
    literals are structural tokens and are contract-legal.
    """

    __slots__ = ("max_request_bytes", "max_structural_members", "bound_sha256")

    def __init__(
        self, *, max_request_bytes: int, max_structural_members: int | None = None
    ) -> None:
        if type(max_request_bytes) is not int or max_request_bytes < 1:
            raise ValueError(
                f"max_request_bytes must be a positive int, got {max_request_bytes!r}"
            )
        if max_structural_members is not None and (
            type(max_structural_members) is not int or max_structural_members < 1
        ):
            raise ValueError(
                "max_structural_members must be a positive int or None, got "
                f"{max_structural_members!r}"
            )
        # Subordination: a bound above its frozen counterpart would make this
        # module an authority on the ceiling instead of a tightening of it.
        if max_request_bytes > _FROZEN.MAX_INPUT_BYTES:
            raise ValueError(
                f"max_request_bytes {max_request_bytes} exceeds the frozen "
                f"MAX_INPUT_BYTES {_FROZEN.MAX_INPUT_BYTES}; an admission bound "
                f"may only tighten the frozen ceiling, never raise it"
            )
        if (
            max_structural_members is not None
            and max_structural_members > _FROZEN.MAX_MEMBERS_OR_ITEMS
        ):
            raise ValueError(
                f"max_structural_members {max_structural_members} exceeds the "
                f"frozen MAX_MEMBERS_OR_ITEMS {_FROZEN.MAX_MEMBERS_OR_ITEMS}"
            )
        self.max_request_bytes = max_request_bytes
        self.max_structural_members = max_structural_members
        self.bound_sha256 = _FROZEN.sha256_upper(
            _FROZEN.jcs_bytes(
                {
                    "format_version": ADMISSION_FORMAT,
                    "frozen_max_input_bytes": _FROZEN.MAX_INPUT_BYTES,
                    "frozen_max_members_or_items": _FROZEN.MAX_MEMBERS_OR_ITEMS,
                    "max_request_bytes": max_request_bytes,
                    "max_structural_members": max_structural_members,
                }
            )
        )

    def _refusal(
        self, bound: str, declared: int, observed: int, frozen: int, raw: bytes
    ) -> dict[str, Any]:
        # A refusal names what it SAW, never a digest of a request it may not
        # have received in full — the `rr_batch` ERR_BATCH_RECORD_LIMIT law
        # (`TRUST_MODEL.md`). The prefix is bounded by the declared byte bound,
        # so the digest costs at most that much hashing.
        prefix = raw[: self.max_request_bytes]
        beyond_frozen = observed > frozen
        return {
            "format_version": ADMISSION_FORMAT,
            "admitted": False,
            "decision_made": False,
            "bound_sha256": self.bound_sha256,
            "request_prefix_sha256": hashlib.sha256(prefix).hexdigest().upper(),
            "request_prefix_bytes": len(prefix),
            "refused_on": {
                "bound": bound,
                "declared": declared,
                "observed": observed,
                "frozen_ceiling": frozen,
                "exceeds_frozen_ceiling": beyond_frozen,
            },
            "statement": (
                "Refused at admission, before evaluation. This is NOT a "
                "classification under the 0.2/0.3 wire law: no decision was "
                "made, no error code was assigned, no receipt or seal exists, "
                "and this object is not an audited envelope. "
                + (
                    "The request also exceeds the frozen ceiling, so the engine "
                    "would have refused it as well, though not necessarily for "
                    "this reason."
                    if beyond_frozen
                    else "The request exceeded a limit this deployment declared "
                    "below the frozen ceiling. The published contract may well "
                    "declare it valid; this deployment declined to spend the "
                    "CPU finding out."
                )
            ),
        }

    def admit(self, raw: bytes) -> dict[str, Any] | None:
        """Return a refusal object, or None if the request is not refused here.

        None is not acceptance. It means this gate has nothing to say.

        Wire bytes only, and `bytes` exactly. A `bytearray` or `memoryview` is
        not the wire form on the supported surface — `decide_audited` sends both
        down the object path, where they are refused as `ERR_JSON` (`README.md`,
        "What you may call"). Admitting one here would make the gated route
        accept what the ungated route rejects, and this gate may only narrow.
        Any other argument is a programming error in the host, not a refused
        request, and raises rather than manufacturing a refusal whose `observed`
        and `declared` would both be zero.
        """
        if type(raw) is not bytes:
            raise TypeError(
                "AdmissionBound.admit takes exact wire bytes (bytes, not "
                "bytearray or memoryview, and not a Python object); the object "
                "route receiver_reliance.decide_audited(obj) is an in-process "
                "convenience and is not gated here (HOST_OBLIGATIONS.md H7)"
            )
        size = len(raw)
        if size > self.max_request_bytes:
            return self._refusal(
                "max_request_bytes",
                self.max_request_bytes,
                size,
                _FROZEN.MAX_INPUT_BYTES,
                raw,
            )
        if self.max_structural_members is not None:
            tokens = 0
            for token in _STRUCTURAL:
                tokens += raw.count(token)
                if tokens > self.max_structural_members:
                    return self._refusal(
                        "max_structural_members",
                        self.max_structural_members,
                        tokens,
                        _FROZEN.MAX_MEMBERS_OR_ITEMS,
                        raw,
                    )
        return None


def _positive_int_from_environment(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw.strip(), 10)
    except ValueError:
        raise RuntimeError(
            f"{name} is set to {raw!r}, which is not a base-ten integer; unset it "
            f"to run without an admission profile, or set a positive byte count"
        ) from None
    if value < 1:
        raise RuntimeError(
            f"{name} is set to {value}, which admits nothing; unset it to run "
            f"without an admission profile"
        )
    return value


def from_environment() -> AdmissionBound | None:
    """The operator's declared profile, or None when they have not declared one.

    Returning None is the default and the whole reason this is adoptable: no
    published count, digest, or receipt moves, because nothing about an ungated
    deployment changes. A malformed or half-declared profile RAISES rather than
    degrading to None — an operator who declared a bound and silently got none
    would be holding a control that is not in the decision path, which is the
    defect class `ADOPTION.md` A5 records twice.
    """
    max_bytes = _positive_int_from_environment(MAX_REQUEST_BYTES_ENV)
    max_members = _positive_int_from_environment(MAX_STRUCTURAL_MEMBERS_ENV)
    if max_bytes is None:
        if max_members is not None:
            raise RuntimeError(
                f"{MAX_STRUCTURAL_MEMBERS_ENV} is set without "
                f"{MAX_REQUEST_BYTES_ENV}. The member proxy does not bound cost "
                f"(see deployment/README.md); it is only ever a second bound "
                f"beside a byte bound, never one on its own"
            )
        return None
    return AdmissionBound(
        max_request_bytes=max_bytes, max_structural_members=max_members
    )


def decide_audited_admitted(
    raw: Any, bound: AdmissionBound | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """`(refusal, envelope)` — exactly one is None.

    `bound is None` is the unset state, and it is not a fast path around the
    gate: it is the ungated call. `raw` is forwarded untouched to
    `receiver_reliance.decide_audited`, so every input type behaves exactly as
    it would with this module absent, including the Python-object route.

    With a bound declared, admitted bytes are forwarded as the same object, so
    the envelope is byte-identical to an ungated call on the same bytes.
    """
    if bound is None:
        return None, _package.decide_audited(raw)
    refusal = bound.admit(raw)
    if refusal is not None:
        return refusal, None
    return None, _package.decide_audited(raw)
