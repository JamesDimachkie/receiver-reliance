#!/usr/bin/env python3
"""Verify the two admitted WP5 receipts, raw pins, seals, and source pins.

Seven source pins are stale by design and carry ERRATA E14: the receipts record
which bytes produced a 2026-08-12 profiling run, and the hardening campaign
deliberately changed four of those files afterwards.  Those rows verify against
the erratum instead of being rebound, so the receipts keep an honest historical
provenance pin while a FURTHER undisclosed move of any of the four fails here.
``perf/sidecar/findings/F-WP5-008.md`` carries the record.

THIS COMMAND IS RED UNTIL THE WP5 EVIDENCE-REGENERATION EVENT, BY DESIGN.  The
F-WP5-006 supervision repairs move ``supervised_client.py``, ``_trace_exec.py``
and ``_evidence.py``, which the admitted receipts pin byte-exactly, and read-time
input pinning moves the execution-input manifest from schema
``...-manifest-1`` to ``...-manifest-2``.  The 2026-08-19 regeneration event
recorded both receipts fresh at those bytes -- profile attempt8 and parity
attempt11, schema ``-2``, read-time pinning, writer redaction -- so ADMITTED,
the inventory and the manifest bind runs the current sources actually
produced.  ERRATA E12 and E14 describe the event shape this followed; the
superseded 2026-08-12 attempts stay on disk as chronology.

Only schema ``-2`` is admitted.  The ``-1`` receipts are not kept as a legacy
branch because nothing reads them here: this verifier checks exactly the entries
of ``ADMITTED``, and the superseded attempts on disk are chronology, not inputs.
A legacy branch would be a validator arm no receipt exercises.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _evidence import canonical, sha256  # noqa: E402


ADMITTED = {
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260819-attempt8.json":
        "088BF9FED9E29D960CF304124D8568DE6F0068BAC142DC2D0A4370052027FC63",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260819-attempt11.json":
        "29ECC8D4E74CDA6BB63869BFE7FEA06469036E5A5DECA7EC66A9BA90FAE71C71",
}

# ERRATA E14 mechanism, table currently empty.  The 2026-08-19 regeneration
# event recorded fresh receipts whose ``source_sha256`` maps pin the CURRENT
# bytes -- the supervision bounds (A6), the pinned-tools migration (A5) and
# the writer redaction included -- so no admitted pin is drifted and no
# erratum row exists.  The mechanism stays: if a pinned source deliberately
# moves again before the next regeneration, the move is declared here as
# (receipt label, source label) -> (digest the receipt pins, current digest),
# and an undisclosed move fails the plain sha256 check below.
SOURCE_PIN_ERRATA: dict[tuple[str, str], tuple[str, str]] = {}


def main() -> int:
    checks = 0
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(f"{name}: {detail}" if detail else name)

    for label, expected_raw in ADMITTED.items():
        path = REPO / label
        check(f"{label}:exists", path.is_file())
        if not path.is_file():
            continue
        raw = path.read_bytes()
        check(f"{label}:raw-sha256", sha256(raw) == expected_raw, sha256(raw))
        try:
            doc: Any = json.loads(raw.decode("ascii"))
        except (UnicodeError, json.JSONDecodeError) as error:
            check(f"{label}:strict-json", False, str(error))
            continue
        check(f"{label}:object", isinstance(doc, dict))
        if not isinstance(doc, dict):
            continue
        embedded = doc.pop("receipt_sha256", None)
        check(f"{label}:embedded-shape", isinstance(embedded, str) and len(embedded) == 64)
        check(f"{label}:embedded-sha256", embedded == sha256(canonical(doc)))
        check(f"{label}:status-pass", doc.get("status") == "PASS", repr(doc.get("status")))
        pins = doc.get("source_sha256")
        check(f"{label}:source-pins-object", isinstance(pins, dict))
        if not isinstance(pins, dict):
            continue
        manifest = doc.get("execution_input_manifest")
        check(f"{label}:manifest-object", isinstance(manifest, dict))
        if not isinstance(manifest, dict):
            continue
        labels = manifest.get("repo_paths")
        check(
            f"{label}:manifest-complete",
            manifest.get("complete") is True
            and manifest.get("schema")
            == "receiver-reliance/wp5-complete-execution-input-manifest-2"
            and manifest.get("input_pin_time") == "read"
            and manifest.get("read_pinned_events") == manifest.get("repo_open_events"),
            f"schema={manifest.get('schema')!r} "
            f"input_pin_time={manifest.get('input_pin_time')!r} "
            f"read_pinned_events={manifest.get('read_pinned_events')!r} "
            f"repo_open_events={manifest.get('repo_open_events')!r}",
        )
        check(
            f"{label}:manifest-labels",
            isinstance(labels, list)
            and labels == sorted(set(labels))
            and all(isinstance(item, str) and item for item in labels),
        )
        if not isinstance(labels, list):
            continue
        check(
            f"{label}:traced-equals-declared-pins",
            set(labels) == set(pins),
            f"trace_only={sorted(set(labels)-set(pins))!r} pins_only={sorted(set(pins)-set(labels))!r}",
        )
        check(
            f"{label}:no-repo-pyc-input",
            not any(item.lower().endswith((".pyc", ".pyo")) for item in labels),
        )
        current = manifest.get("current_process")
        children = manifest.get("completed_child_processes")
        check(
            f"{label}:current-empty-pycache",
            isinstance(current, dict)
            and current.get("dont_write_bytecode") is True
            and current.get("pycache_empty_at_manifest") is True,
        )
        check(
            f"{label}:child-empty-pycaches",
            isinstance(children, dict)
            and children.get("all_dont_write_bytecode") is True
            and children.get("all_pycache_empty_at_start") is True
            and children.get("all_pycache_empty_at_end") is True,
        )
        command = doc.get("command")
        check(
            f"{label}:real-argv-receipt-bound",
            isinstance(command, list)
            and "--receipt" in command
            and any(str(item).endswith(path.name) for item in command),
            repr(command),
        )
        for source_label, expected_source in pins.items():
            source = REPO / source_label
            check(f"{label}:{source_label}:exists", source.is_file())
            if not source.is_file():
                continue
            actual_source = sha256(source.read_bytes())
            errata = SOURCE_PIN_ERRATA.get((label, source_label))
            if errata is None:
                check(
                    f"{label}:{source_label}:sha256",
                    actual_source == expected_source,
                    actual_source,
                )
                continue
            pinned_at_run, current_bytes = errata
            check(
                f"{label}:{source_label}:errata-matches-receipt",
                pinned_at_run == expected_source,
                "the erratum must quote the digest the receipt still pins; "
                f"receipt={expected_source} erratum={pinned_at_run}",
            )
            check(
                f"{label}:{source_label}:errata-current-sha256",
                actual_source == current_bytes,
                f"erratum={current_bytes} actual={actual_source}",
            )

        if doc.get("schema") == "receiver-reliance/wp5-profile-receipt-3":
            evidence = doc.get("accepted_single_pass_equivalence") or {}
            check(
                f"{label}:single-pass-bound",
                evidence.get("checks") == 1142
                and evidence.get("failures") == 0
                and evidence.get("reduced_fixtures") == 93
                and evidence.get("atomic_calls_saved") == 116
                and evidence.get("work_nonincrease_failures") == [],
                repr(evidence),
            )
            contention = doc.get("contention_observation") or {}
            before = contention.get("before") or {}
            after = contention.get("after") or {}
            check(
                f"{label}:platform-specific-process-observation",
                all(
                    isinstance(item, dict)
                    and item.get("platform") == doc.get("runtime", {}).get("system")
                    and "not a universal process census" in str(item.get("scope"))
                    for item in (before, after)
                ),
                repr(contention),
            )
        if doc.get("schema") == "receiver-reliance/wp5-sidecar-parity-receipt-2":
            observed = doc.get("observed") or {}
            counted = observed.get("counted_timeout") or {}
            check(
                f"{label}:no-replay-bound",
                counted.get("child_accepted_requests") == 1
                and counted.get("request_attempt_count") == 1
                and counted.get("request_write_count") == 1
                and counted.get("response_count") == 0
                and counted.get("automatic_replay_count") == 0
                and counted.get("child_stopped") is True,
                repr(counted),
            )
            correlation = observed.get("response_correlation") or {}
            check(
                f"{label}:sequence-and-digest-correlation-bound",
                isinstance(correlation, dict)
                and all(
                    isinstance(correlation.get(name), dict)
                    and correlation[name].get("phase") == "FAILED"
                    and correlation[name].get("response_count") in {0, 1}
                    for name in (
                        "future_sequence",
                        "wrong_request_digest",
                        "wrong_response_digest",
                        "stale_second",
                        "duplicate",
                    )
                )
                and correlation["future_sequence"].get("response_count") == 0
                and correlation["wrong_request_digest"].get("response_count") == 0
                and correlation["wrong_response_digest"].get("response_count") == 0
                and correlation["stale_second"].get("response_count") == 1
                and correlation["duplicate"].get("response_count") <= 1,
                repr(correlation),
            )
            boundary = observed.get("write_boundary") or {}
            midwrite = boundary.get("midwrite") or []
            check(
                f"{label}:complete-write-flush-bound",
                "phase and queue timing never establish identity"
                in str(boundary.get("admission_rule"))
                and boundary.get("midwrite_request_bytes") == 1048577
                and isinstance(midwrite, list)
                and len(midwrite) == 2
                and all(
                    item.get("request_attempt_count") == 1
                    and item.get("request_write_count") in {0, 1}
                    and item.get("response_count") == 0
                    and item.get("automatic_replay_count") == 0
                    and item.get("phase") == "FAILED"
                    for item in midwrite
                )
                and (boundary.get("partial_write") or {}).get("response_count") == 1
                and (boundary.get("zero_write") or {}).get("response_count") == 0,
                repr(boundary),
            )
            check(
                f"{label}:stable-pid-bound",
                observed.get("long_lived_pid_stable") is True
                and observed.get("stable_pid_requests") == 124,
                repr(observed.get("stable_pid_requests")),
            )
            stderr = observed.get("stderr_probes") or []
            check(
                f"{label}:raw-stderr-bound",
                isinstance(stderr, list)
                and [item.get("bytes") for item in stderr] == [3, 5004]
                and all(isinstance(item.get("sha256"), str) for item in stderr),
                repr(stderr),
            )
            check(
                f"{label}:eof-child-stopped",
                observed.get("eof_before_response_child_stopped") is True,
            )

    for failure in failures:
        print(f"FAIL {failure}")
    print(f"wp5 receipt verification: checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
