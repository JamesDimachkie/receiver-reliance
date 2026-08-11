"""Replay one committed live schedule twice on both real transports."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import shutil
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import controller  # noqa: E402


INFRASTRUCTURE_ERROR_ROOT = HERE / "infrastructure-errors"
HARNESS_FAULT_ROOT = HERE / "harness-faults"


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("ascii")


def _write_transport_error(
    schedule: pathlib.Path,
    transport: str,
    error: controller.TransportError,
    replay_number: int,
    completed: tuple[controller.RunResult, ...],
) -> tuple[pathlib.Path, bytes]:
    """Persist deterministic evidence for a non-divergence transport stop."""

    reason = str(error)
    schedule_bytes = schedule.read_bytes()
    identity = hashlib.sha256(
        _canonical_json(
            {
                # The full declared evidence is part of the identity: without
                # completed-replay content and schedule bytes, a later stop
                # with the same reason and basename silently overwrites
                # earlier evidence (F-LIVE-006).
                "completed_stable_sha256": [
                    hashlib.sha256(result.stable_bytes()).hexdigest().upper()
                    for result in completed
                ],
                "error_type": type(error).__name__,
                "reason": reason,
                "replay": replay_number,
                "schedule": schedule.name,
                "schedule_sha256": hashlib.sha256(schedule_bytes)
                .hexdigest()
                .upper(),
                "transport": transport,
            }
        )
    ).hexdigest()
    target = INFRASTRUCTURE_ERROR_ROOT / (
        f"{transport}-replay{replay_number}-{identity}"
    )
    target.mkdir(parents=True, exist_ok=True)
    (target / "schedule.ndjson").write_bytes(schedule_bytes)
    completed_receipts = []
    evidence_files = ["schedule.ndjson"]
    for index, result in enumerate(completed, 1):
        result_name = f"completed-replay-{index}.json"
        stdout_name = f"completed-replay-{index}.stdout.bin"
        stderr_name = f"completed-replay-{index}.stderr.bin"
        (target / result_name).write_bytes(_canonical_json(result.summary()))
        (target / stdout_name).write_bytes(result.stdout)
        (target / stderr_name).write_bytes(result.stderr)
        evidence_files.extend((result_name, stdout_name, stderr_name))
        completed_receipts.append(
            {
                "replay": index,
                "stable_sha256": hashlib.sha256(result.stable_bytes())
                .hexdigest()
                .upper(),
                "summary": result.summary(),
            }
        )

    receipt = {
        "classification": "INFRASTRUCTURE",
        "completed_replays": completed_receipts,
        "error": {"message": reason, "type": type(error).__name__},
        "evidence_files": evidence_files + ["receipt.json"],
        "failing_replay": replay_number,
        "schedule": {
            "bytes": len(schedule_bytes),
            "name": schedule.name,
            "sha256": hashlib.sha256(schedule_bytes).hexdigest().upper(),
        },
        "schema": "receiver-reliance-live-infrastructure-error-v1",
        "status": controller.TransportError.status,
        "transport": transport,
    }
    receipt_bytes = _canonical_json(receipt)
    (target / "receipt.json").write_bytes(receipt_bytes)
    return target, receipt_bytes


def _stop_on_transport_error(
    schedule: pathlib.Path,
    transport: str,
    error: controller.TransportError,
    replay_number: int,
    completed: tuple[controller.RunResult, ...],
) -> int:
    target, receipt = _write_transport_error(
        schedule, transport, error, replay_number, completed
    )
    print(
        _canonical_json(
            {
                "classification": "INFRASTRUCTURE",
                "evidence": (
                    "portability/live/infrastructure-errors/" + target.name
                ),
                "receipt_sha256": hashlib.sha256(receipt).hexdigest().upper(),
                "status": controller.TransportError.status,
            }
        ).decode("ascii"),
        end="",
    )
    return 2


def _write_harness_fault(
    schedule: pathlib.Path,
    transport: str,
    error: "controller.HarnessFaultError",
    replay_number: int,
    completed: tuple[controller.RunResult, ...],
) -> tuple[pathlib.Path, bytes]:
    """Persist deterministic evidence for an internal harness defect.

    A harness fault is neither a divergence nor transport infrastructure
    (F-LIVE-005); it invalidates the run and demands a controller fix.
    """

    reason = str(error)
    schedule_bytes = schedule.read_bytes()
    identity = hashlib.sha256(
        _canonical_json(
            {
                # Same evidence-identity rule as the infrastructure writer
                # (F-LIVE-006): completed-replay content and schedule bytes
                # participate so no later fault can overwrite earlier
                # evidence.
                "completed_stable_sha256": [
                    hashlib.sha256(result.stable_bytes()).hexdigest().upper()
                    for result in completed
                ],
                "error_type": type(error).__name__,
                "reason": reason,
                "replay": replay_number,
                "schedule": schedule.name,
                "schedule_sha256": hashlib.sha256(schedule_bytes)
                .hexdigest()
                .upper(),
                "transport": transport,
            }
        )
    ).hexdigest()
    target = HARNESS_FAULT_ROOT / (
        f"{transport}-replay{replay_number}-{identity}"
    )
    target.mkdir(parents=True, exist_ok=True)
    (target / "schedule.ndjson").write_bytes(schedule_bytes)
    completed_receipts = []
    evidence_files = ["schedule.ndjson"]
    for index, result in enumerate(completed, 1):
        result_name = f"completed-replay-{index}.json"
        stdout_name = f"completed-replay-{index}.stdout.bin"
        stderr_name = f"completed-replay-{index}.stderr.bin"
        (target / result_name).write_bytes(_canonical_json(result.summary()))
        (target / stdout_name).write_bytes(result.stdout)
        (target / stderr_name).write_bytes(result.stderr)
        evidence_files.extend((result_name, stdout_name, stderr_name))
        completed_receipts.append(
            {
                "replay": index,
                "stable_sha256": hashlib.sha256(result.stable_bytes())
                .hexdigest()
                .upper(),
                "summary": result.summary(),
            }
        )

    receipt = {
        "classification": "HARNESS",
        "completed_replays": completed_receipts,
        "error": {"message": reason, "type": type(error).__name__},
        "evidence_files": evidence_files + ["receipt.json"],
        "failing_replay": replay_number,
        "schedule": {
            "bytes": len(schedule_bytes),
            "name": schedule.name,
            "sha256": hashlib.sha256(schedule_bytes).hexdigest().upper(),
        },
        "schema": "receiver-reliance-live-harness-fault-v1",
        "status": controller.HarnessFaultError.status,
        "transport": transport,
    }
    receipt_bytes = _canonical_json(receipt)
    (target / "receipt.json").write_bytes(receipt_bytes)
    return target, receipt_bytes


def _stop_on_harness_fault(
    schedule: pathlib.Path,
    transport: str,
    error: "controller.HarnessFaultError",
    replay_number: int,
    completed: tuple[controller.RunResult, ...],
) -> int:
    target, receipt = _write_harness_fault(
        schedule, transport, error, replay_number, completed
    )
    print(
        _canonical_json(
            {
                "classification": "HARNESS",
                "evidence": ("portability/live/harness-faults/" + target.name),
                "receipt_sha256": hashlib.sha256(receipt).hexdigest().upper(),
                "status": controller.HarnessFaultError.status,
            }
        ).decode("ascii"),
        end="",
    )
    return 4


def _write_divergence(
    schedule: pathlib.Path,
    transport: str,
    first: controller.RunResult,
    second: controller.RunResult | None = None,
    expected: bytes | None = None,
) -> pathlib.Path:
    target = HERE / "divergences" / f"{schedule.stem}-{transport}"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(schedule, target / "schedule.ndjson")
    (target / "actual-1.bin").write_bytes(first.stdout)
    (target / "stderr-1.bin").write_bytes(first.stderr)
    (target / "result-1.json").write_text(
        json.dumps(first.summary(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    if second is not None:
        (target / "actual-2.bin").write_bytes(second.stdout)
        (target / "stderr-2.bin").write_bytes(second.stderr)
        (target / "result-2.json").write_text(
            json.dumps(second.summary(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    if expected is not None:
        (target / "expected.bin").write_bytes(expected)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schedule", type=pathlib.Path)
    args = parser.parse_args()
    schedule = args.schedule.resolve()
    steps = controller.load_schedule(schedule)
    records = []
    for transport in controller.TRANSPORTS:
        try:
            first = controller.run_schedule(schedule, transport, steps=steps)
        except controller.DivergenceError as error:
            evidence = _write_divergence(
                schedule, transport, error.result, expected=error.expected
            )
            print(
                json.dumps(
                    {"status": "DIVERGENCE", "evidence": str(evidence)},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 1
        except controller.TransportError as error:
            return _stop_on_transport_error(schedule, transport, error, 1, ())
        except controller.HarnessFaultError as error:
            return _stop_on_harness_fault(schedule, transport, error, 1, ())
        try:
            second = controller.run_schedule(schedule, transport, steps=steps)
        except controller.DivergenceError as error:
            evidence = _write_divergence(
                schedule, transport, error.result, expected=error.expected
            )
            print(
                json.dumps(
                    {"status": "DIVERGENCE", "evidence": str(evidence)},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 1
        except controller.TransportError as error:
            return _stop_on_transport_error(schedule, transport, error, 2, (first,))
        except controller.HarnessFaultError as error:
            return _stop_on_harness_fault(schedule, transport, error, 2, (first,))
        if first.stable_bytes() != second.stable_bytes():
            evidence = _write_divergence(schedule, transport, first, second=second)
            print(
                json.dumps(
                    {"status": "DIVERGENCE", "evidence": str(evidence)},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 1
        record = first.summary()
        record.update(
            {
                "status": "PASS",
                "replays": 2,
                "byte_identical": True,
                "stderr_b64": base64.b64encode(first.stderr).decode("ascii"),
            }
        )
        records.append(record)
    print(json.dumps(records, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
