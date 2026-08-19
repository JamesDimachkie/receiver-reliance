#!/usr/bin/env python3
"""Replay the incident corpus through the receiver-reliance preflight and engine.

For every directory under ``incidents/`` this runner reads ``expected.json``,
replays each record through

  1. ``adapters.preflight`` over the incident's native evidence (and, where the
     incident is in a calibrated family, its ``RR-PORTABLE-FACT-PROFILE-1``
     envelope), then
  2. ``grounded-0_4/rr_api.py::decide_audited`` over the exact request bytes on
     disk,

and compares both results plus the request digest and the audit self-seal
against the pinned expectations.

What a green run demonstrates: RR *classifies* each adapted record into the
pinned behaviour class, and each clean twin into ``VALID``. It demonstrates
nothing about whether RR would have prevented, stopped, or secured the
underlying incident — see each incident's ``METHOD.md``.

Stdlib only, apart from the engine import. Deterministic: no clock, no
randomness, no network, no ambient environment. Safe to run with ``-B``.

Usage (from anywhere):

    python -B replay_incidents.py [--repo PATH] [--incident NAME] [--verbose]

Exit code 0 only when every pinned expectation holds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
INCIDENTS_DIR = HERE / "incidents"

# The closed governing-authority key set of the audited envelope this corpus
# replays against.  It is asserted as a closed set, not a subset, so that a key
# appearing or disappearing turns the run red rather than passing silently.
#
# It moved once already.  The corpus was authored against the pre-0.4.2 engine,
# which named four authorities; ERRATA E8 sealed both decision-table contracts
# into the envelope and the set became six (``grounded-0_4/rr_api.py``,
# ``GOVERNING_AUTHORITIES``).  Replaying the unchanged corpus against the
# released engine failed all 27 records on this one assertion and on nothing
# else -- every class, conclusion, exit code, request digest and self-zero seal
# still held.  Re-pinning here is the repair; the closed-set shape is the point.
GOVERNING_AUTHORITY_KEYS = frozenset(
    {
        "closure_policy_sha256",
        "authority_register_sha256",
        "engine_capabilities_sha256",
        "engine_runner_sha256",
        "decision_table_contract_sha256",
        "composed_contract_sha256",
    }
)


def find_repo(explicit: str | None) -> pathlib.Path:
    """Locate the receiver-reliance checkout without embedding an absolute path."""
    candidates: list[pathlib.Path] = []
    if explicit:
        candidates.append(pathlib.Path(explicit).expanduser().resolve())
    for parent in [HERE, *HERE.parents]:
        candidates.append(parent)
        candidates.append(parent / "receiver-reliance")
    for candidate in candidates:
        if (candidate / "grounded-0_4" / "rr_api.py").is_file():
            return candidate
    raise SystemExit(
        "replay-incidents: cannot locate a receiver-reliance checkout "
        "(no grounded-0_4/rr_api.py found); pass --repo PATH"
    )


def load_surfaces(repo: pathlib.Path):
    """Import the audited decision API and the portable preflight."""
    sys.path.insert(0, str(repo / "grounded-0_4"))
    sys.path.insert(0, str(repo))
    import rr_api  # noqa: PLC0415

    from adapters import preflight  # noqa: PLC0415

    return rr_api, preflight


def sha256_upper(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def read_json(path: pathlib.Path):
    return json.loads(path.read_bytes().decode("utf-8"))


class Failure(Exception):
    pass


def replay_record(rr_api, preflight, base: pathlib.Path, spec: dict, verbose: bool) -> dict:
    """Replay one record; return its observed outcome or raise Failure."""
    problems: list[str] = []

    request_path = base / spec["request"]
    raw = request_path.read_bytes()
    digest = sha256_upper(raw)
    if digest != spec["request_raw_sha256"]:
        problems.append(
            f"request-bytes-drift expected={spec['request_raw_sha256']} got={digest}"
        )

    native = None
    profile = None
    if spec.get("native_evidence"):
        native = read_json(base / spec["native_evidence"])
    if spec.get("fact_profile"):
        profile = read_json(base / spec["fact_profile"])

    preflight_status = None
    preflight_codes: list[str] = []
    if native is not None:
        result = preflight(native, profile)
        preflight_status = result.status
        preflight_codes = sorted({issue.code for issue in result.issues})
        if preflight_status != spec["expected_preflight_status"]:
            problems.append(
                f"preflight-status expected={spec['expected_preflight_status']} "
                f"got={preflight_status}"
            )
        if preflight_codes != spec["expected_preflight_issue_codes"]:
            problems.append(
                f"preflight-issues expected={spec['expected_preflight_issue_codes']} "
                f"got={preflight_codes}"
            )

    audited = rr_api.decide_audited(raw)
    sealed = audited["sealed_response"]
    output = sealed.get("output") or {}
    result_object = output.get("result_object") or {}
    audit = audited.get("audit") or {}

    observed = {
        "sealed_behavior_class": result_object.get("behavior_class"),
        "audited_behavior_class": audited.get("audited_behavior_class"),
        "conclusion": result_object.get("conclusion"),
        "exit_code": audited.get("exit_code"),
    }
    for key, expected_key in (
        ("sealed_behavior_class", "expected_sealed_behavior_class"),
        ("audited_behavior_class", "expected_audited_behavior_class"),
        ("conclusion", "expected_conclusion"),
        ("exit_code", "expected_exit_code"),
    ):
        if observed[key] != spec[expected_key]:
            problems.append(f"{key} expected={spec[expected_key]!r} got={observed[key]!r}")

    # The audit must seal the exact bytes we replayed, and must re-seal itself.
    if audit.get("request_raw_sha256") != digest:
        problems.append(
            f"audit-input-binding expected={digest} got={audit.get('request_raw_sha256')}"
        )
    reseal = rr_api.b1.self_zero_sha256(audited, "audit_sha256")
    if reseal != audited.get("audit_sha256"):
        problems.append("audit-seal does not recompute")
    if set(audit.get("governing_authorities") or {}) != GOVERNING_AUTHORITY_KEYS:
        problems.append(
            "governing-authorities key set unexpected: "
            f"got={sorted(audit.get('governing_authorities') or {})}"
        )

    if verbose:
        print(
            f"      {spec['id']:46s} preflight={preflight_status} "
            f"audited={observed['audited_behavior_class']} "
            f"conclusion={observed['conclusion']} audit_sha256={audited['audit_sha256'][:16]}"
        )

    if problems:
        raise Failure("; ".join(problems))
    observed["preflight_status"] = preflight_status
    return observed


def replay_incident(rr_api, preflight, base: pathlib.Path, verbose: bool) -> dict:
    expected = read_json(base / "expected.json")
    records = expected["records"]
    counters = {
        "records": len(records),
        "defective": 0,
        "holds": 0,
        "clean": 0,
        "clean_pass": 0,
        "failures": 0,
    }
    messages: list[str] = []
    for spec in records:
        try:
            observed = replay_record(rr_api, preflight, base, spec, verbose)
        except Failure as failure:
            counters["failures"] += 1
            messages.append(f"FAIL {expected['incident_id']}/{spec['id']}: {failure}")
            if spec["role"] == "defective":
                counters["defective"] += 1
            else:
                counters["clean"] += 1
            continue
        except (OSError, KeyError, ValueError) as error:
            counters["failures"] += 1
            messages.append(
                f"FAIL {expected['incident_id']}/{spec['id']}: replay error {error!r}"
            )
            continue
        if spec["role"] == "defective":
            counters["defective"] += 1
            held = (
                observed["audited_behavior_class"] not in ("VALID", None)
                or observed["preflight_status"] == "REJECTED_INVALID"
            )
            if held:
                counters["holds"] += 1
            else:
                counters["failures"] += 1
                messages.append(
                    f"FAIL {expected['incident_id']}/{spec['id']}: defective record did not hold"
                )
        else:
            counters["clean"] += 1
            if observed["audited_behavior_class"] == "VALID":
                counters["clean_pass"] += 1
            else:
                counters["failures"] += 1
                messages.append(
                    f"FAIL {expected['incident_id']}/{spec['id']}: clean twin did not classify VALID"
                )
    counters["incident_id"] = expected["incident_id"]
    counters["obligation_id"] = expected["obligation_id"]
    counters["preflight_lane"] = expected["preflight_lane"]
    counters["messages"] = messages
    return counters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=None, help="path to a receiver-reliance checkout")
    parser.add_argument("--incident", default=None, help="replay one incident directory")
    parser.add_argument("--verbose", action="store_true", help="print per-record detail")
    args = parser.parse_args(argv)

    repo = find_repo(args.repo)
    rr_api, preflight = load_surfaces(repo)

    directories = sorted(
        path
        for path in INCIDENTS_DIR.iterdir()
        if path.is_dir() and (path / "expected.json").is_file()
    )
    if args.incident:
        directories = [path for path in directories if path.name == args.incident]
        if not directories:
            print(f"replay-incidents: no incident named {args.incident!r}")
            return 2

    totals = {
        "incidents": 0,
        "executable": 0,
        "records": 0,
        "holds": 0,
        "clean_pass": 0,
        "failures": 0,
    }
    for base in directories:
        counters = replay_incident(rr_api, preflight, base, args.verbose)
        totals["incidents"] += 1
        totals["records"] += counters["records"]
        totals["holds"] += counters["holds"]
        totals["clean_pass"] += counters["clean_pass"]
        totals["failures"] += counters["failures"]
        executable = counters["failures"] == 0
        if executable:
            totals["executable"] += 1
        for message in counters["messages"]:
            print(message)
        print(
            f"incident={counters['incident_id']} obligation={counters['obligation_id']} "
            f"preflight_lane={counters['preflight_lane']} records={counters['records']} "
            f"defective={counters['defective']} holds={counters['holds']} "
            f"clean={counters['clean']} clean_pass={counters['clean_pass']} "
            f"failures={counters['failures']} executable={'yes' if executable else 'no'}"
        )

    # ``checks`` is the replayed-record count in the battery's own vocabulary,
    # so ``portability/matrix/plan.json`` can pin it: a dropped incident moves
    # the number instead of passing quietly on a smaller corpus.
    print(
        f"replay-incidents: incidents={totals['incidents']} "
        f"executable={totals['executable']} checks={totals['records']} "
        f"holds={totals['holds']} clean_pass={totals['clean_pass']} "
        f"failures={totals['failures']}"
    )
    return 1 if totals["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
