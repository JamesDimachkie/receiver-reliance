#!/usr/bin/env python3
"""Verify the two admitted WP5 receipts, raw pins, seals, and source pins."""
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
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt6.json":
        "F54B6300ACA8BB4E3D7BBE7F8F1A110B7D558A5E9E8D7448DD5F7315CC3B0166",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt9.json":
        "E082C27DB6CE00B95A594A26FD0460BC632D54E0CE4CB159C85A6EF56E8AB4AF",
}


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
            == "receiver-reliance/wp5-complete-execution-input-manifest-1",
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
            if source.is_file():
                check(
                    f"{label}:{source_label}:sha256",
                    sha256(source.read_bytes()) == expected_source,
                    sha256(source.read_bytes()),
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
