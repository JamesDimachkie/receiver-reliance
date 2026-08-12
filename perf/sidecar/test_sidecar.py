#!/usr/bin/env python3
"""Parity, envelope-correlation, and lifecycle probes for the stdio sidecar."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUNDED = REPO / "grounded-0_4"
TRACE_EXEC = HERE / "_trace_exec.py"
if str(GROUNDED) not in sys.path:
    sys.path.insert(0, str(GROUNDED))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _evidence import (  # noqa: E402
    execution_input_manifest,
    git_record,
    reexec_traced_worker,
    repo_label,
    runtime_record,
    traced_python_command,
    utc_now,
    write_new_receipt,
)

reexec_traced_worker(pathlib.Path(__file__).resolve())

import rr_api  # noqa: E402
import rr_batch  # noqa: E402
from supervised_client import SidecarFailure, SidecarProcess  # noqa: E402
from transport_envelope import (  # noqa: E402
    encode_request_frame,
    read_response_frame,
    sha256,
)


PACKS = (
    REPO / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    REPO / "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
)
LAUNCHER = HERE / "rr_sidecar.py"
ADVERSARY = HERE / "adversarial_child.py"


def load_requests() -> list[tuple[str, bytes]]:
    rows: list[tuple[str, bytes]] = []
    for path in PACKS:
        pack = json.loads(path.read_text(encoding="utf-8"))
        for entry in pack["entries"]:
            rows.append(
                (
                    entry["entry_id"],
                    base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True),
                )
            )
    rows.sort(key=lambda item: item[0].encode("utf-8"))
    if len(rows) != 124:
        raise RuntimeError(f"expected 124 semantic fixtures, got {len(rows)}")
    return rows


def supervisor_threads_stopped(client: SidecarProcess) -> bool:
    return all(
        thread is None or not thread.is_alive()
        for thread in (client._reader, client._stderr_reader)
    )


def adversary(mode: str, *args: str) -> list[str]:
    return traced_python_command(ADVERSARY, mode, *args)


def wait_stopped(client: SidecarProcess) -> bool:
    for _ in range(200):
        if client.returncode is not None:
            return True
        time.sleep(0.005)
    return client.returncode is not None


class ShortWriteStream:
    """Delegate to a real pipe while forcing valid short-write returns."""

    def __init__(self, wrapped: Any, limit: int) -> None:
        self.wrapped = wrapped
        self.limit = limit

    @property
    def closed(self) -> bool:
        return self.wrapped.closed

    def write(self, data: Any) -> int:
        return self.wrapped.write(data[: self.limit])

    def flush(self) -> None:
        self.wrapped.flush()

    def close(self) -> None:
        self.wrapped.close()


class ZeroWriteStream(ShortWriteStream):
    """Return zero without touching the real pipe."""

    def write(self, data: Any) -> int:
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=pathlib.Path)
    args = parser.parse_args(argv)
    started = utc_now()
    checks = 0
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(f"{name}: {detail}" if detail else name)

    requests = load_requests()
    expected = [rr_api.b1.jcs_bytes(rr_api.decide_audited(raw)) + b"\n" for _, raw in requests]
    identity = hashlib.sha256()
    for (entry_id, raw), response in zip(requests, expected, strict=True):
        identity.update(entry_id.encode("utf-8") + b"\0")
        identity.update(hashlib.sha256(raw).digest())
        identity.update(hashlib.sha256(response).digest())

    request_stream = b"".join(
        encode_request_frame(sequence, raw)
        for sequence, (_entry_id, raw) in enumerate(requests, 1)
    )
    direct_command = traced_python_command(LAUNCHER)
    direct = subprocess.run(
        direct_command,
        cwd=REPO,
        input=request_stream,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
    )
    check("launcher:exit-zero", direct.returncode == 0, str(direct.returncode))
    check("launcher:stderr-empty", direct.stderr == b"", repr(direct.stderr))
    direct_reader = io.BytesIO(direct.stdout)
    direct_payloads: list[bytes] = []
    for sequence, ((entry_id, raw), response) in enumerate(zip(requests, expected, strict=True), 1):
        try:
            frame = read_response_frame(direct_reader, 32 * 1024 * 1024)
        except Exception as error:
            check(f"launcher:{entry_id}:frame", False, str(error))
            break
        check(f"launcher:{entry_id}:frame-present", frame is not None)
        if frame is None:
            break
        check(
            f"launcher:{entry_id}:correlation",
            frame.sequence == sequence and frame.request_sha256 == sha256(raw),
            repr(frame),
        )
        check(f"launcher:{entry_id}:payload", frame.payload == response)
        direct_payloads.append(frame.payload)
    check("launcher:clean-frame-eof", read_response_frame(direct_reader, 32 * 1024 * 1024) is None)
    check("launcher:all-payload-bytes", b"".join(direct_payloads) == b"".join(expected))

    with SidecarProcess(traced_python_command(LAUNCHER)) as sidecar:
        first_pid = sidecar.pid
        for (entry_id, raw), response in zip(requests, expected, strict=True):
            observed = sidecar.request(raw)
            check(f"supervised:{entry_id}:bytes", observed == response)
            check(f"supervised:{entry_id}:same-process", sidecar.pid == first_pid)
        stable_state = sidecar.state_evidence()
        check("supervised:monotonic-sequences", stable_state["last_admitted_sequence"] == 124, repr(stable_state))
        check("supervised:still-running", sidecar.returncode is None)
    check("supervised:clean-eof", sidecar.returncode == 0, str(sidecar.returncode))
    check("supervised:reader-threads-stopped", supervisor_threads_stopped(sidecar))

    invalid = SidecarProcess()
    try:
        for name, raw in (("missing-lf", b"{}"), ("multiple-lines", b"{}\n{}\n")):
            try:
                invalid.request(raw)
            except ValueError:
                check(f"client:rejects-{name}", True)
            else:
                check(f"client:rejects-{name}", False)
    finally:
        invalid.stop(check=False)

    # The launcher itself rejects corrupt digests, stale/duplicate sequence,
    # reordered sequence, and truncated payloads without answering that frame.
    good_one = encode_request_frame(1, b"{}\n")
    bad_digest = good_one.replace(sha256(b"{}\n").encode("ascii"), b"0" * 64, 1)
    malformed_inputs = {
        "bad-request-digest": bad_digest,
        "reordered-first-sequence": encode_request_frame(2, b"{}\n"),
        "truncated-payload": good_one[:-1],
    }
    invalid_request_results: dict[str, Any] = {}
    for name, payload in malformed_inputs.items():
        result = subprocess.run(
            traced_python_command(LAUNCHER),
            cwd=REPO,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        check(f"launcher:{name}:exit-2", result.returncode == 2, str(result.returncode))
        check(f"launcher:{name}:stdout-empty", result.stdout == b"", repr(result.stdout))
        check(f"launcher:{name}:stderr-empty", result.stderr == b"", repr(result.stderr))
        invalid_request_results[name] = {
            "exit_code": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
        }
    duplicate_request = subprocess.run(
        traced_python_command(LAUNCHER),
        cwd=REPO,
        input=good_one + good_one,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    duplicate_reader = io.BytesIO(duplicate_request.stdout)
    duplicate_first = read_response_frame(duplicate_reader, 32 * 1024 * 1024)
    duplicate_tail = read_response_frame(duplicate_reader, 32 * 1024 * 1024)
    check("launcher:duplicate-request:exit-2", duplicate_request.returncode == 2)
    check("launcher:duplicate-request:first-only", duplicate_first is not None and duplicate_tail is None)

    dead = SidecarProcess([sys.executable, "-I", "-B", "-c", "raise SystemExit(7)"]).start()
    wait_stopped(dead)
    try:
        dead.request(b"{}\n")
    except SidecarFailure as error:
        check("supervisor:reports-pre-request-death", "returncode=7" in str(error), str(error))
    else:
        check("supervisor:reports-pre-request-death", False)
    finally:
        dead.stop(check=False)
    check("supervisor:pre-request-death-threads-stopped", supervisor_threads_stopped(dead))

    prewrite_command = adversary("prewrite-poison")
    prewrite = SidecarProcess(prewrite_command).start()
    for _ in range(200):
        if prewrite.state_evidence()["protocol_failure"] is not None:
            break
        time.sleep(0.005)
    try:
        prewrite.request(b"{}\n")
    except SidecarFailure as error:
        evidence = prewrite.state_evidence()
        check("supervisor:prewrite-output-rejected", "envelope reader" in str(error), str(error))
        check("supervisor:prewrite-output-no-attempt", evidence["request_attempt_count"] == 0, repr(evidence))
        check("supervisor:prewrite-output-no-write", evidence["request_write_count"] == 0, repr(evidence))
        check("supervisor:prewrite-output-no-response", evidence["response_count"] == 0, repr(evidence))
        check("supervisor:prewrite-output-child-stopped", wait_stopped(prewrite))
    else:
        check("supervisor:prewrite-output-rejected", False)
    finally:
        prewrite.stop(check=False)
    check("supervisor:prewrite-output-threads-stopped", supervisor_threads_stopped(prewrite))

    large_request = b"X" * (1024 * 1024) + b"\n"
    midwrite_results: list[dict[str, object]] = []
    midwrite_command = adversary("midwrite-poison")
    for repetition, chunk_size in enumerate((None, 4096)):
        midwrite = SidecarProcess(
            midwrite_command,
            timeout_seconds=2.0,
            max_write_chunk_bytes=chunk_size,
        )
        try:
            midwrite.request(large_request)
        except SidecarFailure as error:
            evidence = midwrite.state_evidence()
            check(
                f"supervisor:midwrite-{repetition}:rejected",
                "envelope reader" in str(evidence["protocol_failure"]),
                f"{error}; {evidence!r}",
            )
            check(f"supervisor:midwrite-{repetition}:one-attempt", evidence["request_attempt_count"] == 1, repr(evidence))
            check(
                f"supervisor:midwrite-{repetition}:write-count-is-not-identity",
                evidence["request_write_count"] in {0, 1},
                repr(evidence),
            )
            check(f"supervisor:midwrite-{repetition}:no-response", evidence["response_count"] == 0, repr(evidence))
            check(f"supervisor:midwrite-{repetition}:no-replay", evidence["automatic_replay_count"] == 0, repr(evidence))
            check(f"supervisor:midwrite-{repetition}:child-stopped", wait_stopped(midwrite))
            midwrite_results.append({"max_write_chunk_bytes": chunk_size, **evidence})
        else:
            check(f"supervisor:midwrite-{repetition}:rejected", False)
        finally:
            midwrite.stop(check=False)
        check(f"supervisor:midwrite-{repetition}:threads-stopped", supervisor_threads_stopped(midwrite))

    postwrite = SidecarProcess(adversary("postwrite-poison"))
    try:
        postwrite.request(b"{}\n")
    except SidecarFailure as error:
        postwrite_evidence = postwrite.state_evidence()
        check("supervisor:postwrite-output-rejected", "envelope reader" in str(error), str(error))
        check("supervisor:postwrite-one-completed-write", postwrite_evidence["request_write_count"] == 1, repr(postwrite_evidence))
        check("supervisor:postwrite-no-response", postwrite_evidence["response_count"] == 0, repr(postwrite_evidence))
        check("supervisor:postwrite-child-stopped", wait_stopped(postwrite))
    else:
        postwrite_evidence = postwrite.state_evidence()
        check("supervisor:postwrite-output-rejected", False)
    finally:
        postwrite.stop(check=False)
    check("supervisor:postwrite-threads-stopped", supervisor_threads_stopped(postwrite))

    partial = SidecarProcess(adversary("valid")).start()
    assert partial._process is not None and partial._process.stdin is not None
    partial._process.stdin = ShortWriteStream(partial._process.stdin, 7)  # type: ignore[assignment]
    try:
        partial_response = partial.request(large_request)
        partial_evidence = partial.state_evidence()
        check("supervisor:partial-write-response", partial_response == b"OK\n")
        check("supervisor:partial-write-completed", partial_evidence["request_write_count"] == 1, repr(partial_evidence))
        check("supervisor:partial-write-many-host-calls", partial_evidence["host_write_call_count"] > 1000, repr(partial_evidence))
        check("supervisor:partial-write-one-response", partial_evidence["response_count"] == 1, repr(partial_evidence))
    except SidecarFailure as error:
        partial_evidence = partial.state_evidence()
        check("supervisor:partial-write-response", False, f"{error}; {partial_evidence!r}")
    finally:
        partial.stop(check=False)
    check("supervisor:partial-write-threads-stopped", supervisor_threads_stopped(partial))

    zero = SidecarProcess(adversary("valid")).start()
    assert zero._process is not None and zero._process.stdin is not None
    zero._process.stdin = ZeroWriteStream(zero._process.stdin, 1)  # type: ignore[assignment]
    try:
        zero.request(b"{}\n")
    except SidecarFailure as error:
        zero_evidence = zero.state_evidence()
        check("supervisor:zero-write-rejected", "no progress" in str(error), str(error))
        check("supervisor:zero-write-no-completion", zero_evidence["request_write_count"] == 0, repr(zero_evidence))
        check("supervisor:zero-write-no-response", zero_evidence["response_count"] == 0, repr(zero_evidence))
        check("supervisor:zero-write-child-stopped", wait_stopped(zero))
    else:
        zero_evidence = zero.state_evidence()
        check("supervisor:zero-write-rejected", False)
    finally:
        zero.stop(check=False)
    check("supervisor:zero-write-threads-stopped", supervisor_threads_stopped(zero))

    correlation_results: dict[str, Any] = {}
    for mode in ("future-sequence", "wrong-request-digest", "wrong-response-digest"):
        corrupt = SidecarProcess(adversary(mode))
        try:
            corrupt.request(b"{}\n")
        except SidecarFailure as error:
            evidence = corrupt.state_evidence()
            check(f"supervisor:{mode}:rejected", evidence["response_count"] == 0, f"{error}; {evidence!r}")
            check(f"supervisor:{mode}:child-stopped", wait_stopped(corrupt))
            correlation_results[mode] = evidence
        else:
            check(f"supervisor:{mode}:rejected", False)
        finally:
            corrupt.stop(check=False)
        check(f"supervisor:{mode}:threads-stopped", supervisor_threads_stopped(corrupt))

    stale = SidecarProcess(adversary("stale-second"))
    try:
        first = stale.request(b'{"n":1}\n')
        check("supervisor:stale-sequence:first-admitted", first == b"FIRST\n")
        try:
            stale.request(b'{"n":2}\n')
        except SidecarFailure as error:
            stale_evidence = stale.state_evidence()
            check("supervisor:stale-sequence:second-rejected", "stale" in str(error), str(error))
            check("supervisor:stale-sequence:only-first-admitted", stale_evidence["response_count"] == 1, repr(stale_evidence))
            check("supervisor:stale-sequence:child-stopped", wait_stopped(stale))
        else:
            stale_evidence = stale.state_evidence()
            check("supervisor:stale-sequence:second-rejected", False)
    finally:
        stale.stop(check=False)
    check("supervisor:stale-sequence:threads-stopped", supervisor_threads_stopped(stale))

    duplicate = SidecarProcess(adversary("duplicate"))
    duplicate_returned: bytes | None = None
    try:
        try:
            duplicate_returned = duplicate.request(b"{}\n")
        except SidecarFailure:
            pass
        for _ in range(200):
            if duplicate.state_evidence()["protocol_failure"] is not None:
                break
            time.sleep(0.005)
        if duplicate.state_evidence()["protocol_failure"] is None:
            try:
                duplicate.request(b'{"next":true}\n')
            except SidecarFailure:
                pass
        duplicate_evidence = duplicate.state_evidence()
        check("supervisor:duplicate-frame-detected", duplicate_evidence["protocol_failure"] is not None, repr(duplicate_evidence))
        check("supervisor:duplicate-frame-at-most-first-admitted", duplicate_evidence["response_count"] <= 1, repr(duplicate_evidence))
        check("supervisor:duplicate-frame-valid-return-only", duplicate_returned in (None, b"ONE\n"), repr(duplicate_returned))
        check("supervisor:duplicate-frame-child-stopped", wait_stopped(duplicate))
    finally:
        duplicate.stop(check=False)
    check("supervisor:duplicate-frame-threads-stopped", supervisor_threads_stopped(duplicate))

    eof_live = SidecarProcess(adversary("eof-live"))
    try:
        eof_live.request(b"{}\n")
    except SidecarFailure as error:
        check("supervisor:eof-before-response-rejected", "closed stdout" in str(error), str(error))
        check("supervisor:eof-before-response-child-stopped", wait_stopped(eof_live))
    else:
        check("supervisor:eof-before-response-rejected", False)
    finally:
        eof_live.stop(check=False)
    check("supervisor:eof-before-response-threads-stopped", supervisor_threads_stopped(eof_live))

    stderr_results: list[dict[str, Any]] = []
    for name, mode, payload in (
        ("whitespace", "stderr-whitespace", b" \n\t"),
        ("long", "stderr-long", b"P" * 5000 + b"TAIL"),
    ):
        noisy = SidecarProcess(adversary(mode))
        try:
            noisy.request(b"{}\n")
        except SidecarFailure as error:
            evidence = noisy.stderr_evidence()
            check(f"supervisor:stderr-{name}-rejected", "stderr" in str(error), str(error))
            check(f"supervisor:stderr-{name}-exact-bytes", evidence["bytes"] == len(payload), repr(evidence))
            check(f"supervisor:stderr-{name}-sha256", evidence["sha256"] == sha256(payload), repr(evidence))
            check(f"supervisor:stderr-{name}-child-stopped", wait_stopped(noisy))
            stderr_results.append({"name": name, **evidence})
        else:
            check(f"supervisor:stderr-{name}-rejected", False)
        finally:
            noisy.stop(check=False)
        check(f"supervisor:stderr-{name}-threads-stopped", supervisor_threads_stopped(noisy))

    with tempfile.TemporaryDirectory(prefix="rr-wp5-timeout-marker-") as temporary:
        marker = pathlib.Path(temporary) / "accepted.bin"
        marker.write_bytes(b"")
        ready = pathlib.Path(temporary) / "ready.bin"
        counted_timeout_command = adversary("stall", str(marker), str(ready))
        counted_timeout = SidecarProcess(counted_timeout_command, timeout_seconds=0.5)
        # Start the child and wait for its readiness signal on a generous
        # bound BEFORE issuing the deliberately short request, so interpreter
        # cold start under process-creation churn is never charged against
        # the 0.5 s deadline (F-WP5-007: the previous shape failed 12/12
        # under 40-spawner churn on an idle-passing box).
        counted_timeout.start()
        ready_deadline = time.perf_counter() + 20.0
        while not ready.exists() and time.perf_counter() < ready_deadline:
            time.sleep(0.005)
        check("supervisor:counted-timeout-child-ready", ready.exists())
        try:
            counted_timeout.request(b"{}\n")
        except SidecarFailure as error:
            check("supervisor:counted-timeout-rejected", "not replayed" in str(error), str(error))
            check(
                "supervisor:counted-timeout-child-accepted-once",
                marker.read_bytes() == b"1",
                repr(marker.read_bytes()),
            )
            check("supervisor:counted-timeout-attempt-count", counted_timeout.request_attempt_count == 1)
            check("supervisor:counted-timeout-write-count", counted_timeout.request_write_count == 1)
            check("supervisor:counted-timeout-response-count", counted_timeout.response_count == 0)
            check("supervisor:counted-timeout-replay-count", counted_timeout.automatic_replay_count == 0)
            check("supervisor:counted-timeout-child-stopped", wait_stopped(counted_timeout))
        else:
            check("supervisor:counted-timeout-rejected", False)
        finally:
            counted_timeout.stop(check=False)
        counted_timeout_accepted = len(marker.read_bytes())
        check("supervisor:counted-timeout-threads-stopped", supervisor_threads_stopped(counted_timeout))

    with tempfile.TemporaryDirectory(prefix="rr-wp5-early-valid-") as early_temporary:
        # F-WP5-007 regression: a CORRECT correlated response emitted while
        # the host is still chunking its request write must be admitted once
        # the write completes, never poisoned for arriving early.  Identity
        # is the envelope digest, not phase timing.
        expected_path = pathlib.Path(early_temporary) / "expected.bin"
        early_line = b"y" * (1024 * 1024) + b"\n"
        expected_path.write_bytes(early_line)
        early = SidecarProcess(
            adversary("midwrite-valid", str(expected_path)),
            timeout_seconds=10.0,
            max_write_chunk_bytes=4096,
        )
        try:
            early_payload = early.request(early_line)
            check("supervisor:midwrite-valid-admitted", early_payload == b"OK\n", repr(early_payload))
            check("supervisor:midwrite-valid-response-count", early.response_count == 1)
            check("supervisor:midwrite-valid-no-failure", early.state_evidence()["protocol_failure"] is None)
        finally:
            early.stop(check=False)
        check("supervisor:midwrite-valid-threads-stopped", supervisor_threads_stopped(early))

    oversized = SidecarProcess(adversary("overlimit-response"), max_response_bytes=4)
    try:
        oversized.request(b"{}\n")
    except SidecarFailure as error:
        check("supervisor:response-bound-rejected", "outside the supported range" in str(error), str(error))
        check("supervisor:response-bound-child-stopped", wait_stopped(oversized))
    else:
        check("supervisor:response-bound-rejected", False)
    finally:
        oversized.stop(check=False)
    check("supervisor:response-bound-threads-stopped", supervisor_threads_stopped(oversized))

    engine_overlimit_request = b"X" * rr_api.b1.MAX_INPUT_BYTES + b"\n"
    with SidecarProcess(traced_python_command(LAUNCHER), timeout_seconds=30.0) as overlimit_request_client:
        engine_overlimit_response = overlimit_request_client.request(engine_overlimit_request)
    expected_overlimit_response = rr_batch._overlimit_response_bytes(sha256(engine_overlimit_request))
    check("sidecar:engine-overlimit-request-parity", engine_overlimit_response == expected_overlimit_response)
    check("sidecar:engine-overlimit-cleanup", supervisor_threads_stopped(overlimit_request_client))

    execution_manifest, complete_source_pins = execution_input_manifest()
    status = "PASS" if not failures else "FAIL"
    receipt: dict[str, Any] = {
        "schema": "receiver-reliance/wp5-sidecar-parity-receipt-2",
        "status": status,
        "started_utc": started,
        "finished_utc": utc_now(),
        "command": list(sys.orig_argv),
        "requested_argv": [repo_label(pathlib.Path(__file__)), *sys.argv[1:]],
        "runtime": runtime_record(),
        "git": git_record(),
        "execution_input_manifest": execution_manifest,
        "source_sha256": complete_source_pins,
        "workload": {
            "semantic_fixture_entries": len(requests),
            "ordering": "entry_id sorted by UTF-8 bytes",
            "identity_root_sha256": identity.hexdigest().upper(),
            "transport": "RR-SIDECAR/1 request/response frames",
        },
        "observed": {
            "checks": checks,
            "failures": len(failures),
            "failure_details": failures[:20],
            "direct_launcher_transport_bytes": len(direct.stdout),
            "direct_launcher_transport_sha256": sha256(direct.stdout),
            "direct_launcher_payload_sha256": sha256(b"".join(direct_payloads)),
            "long_lived_pid_stable": stable_state["last_admitted_sequence"] == 124,
            "stable_pid_requests": 124,
            "invalid_request_frames": invalid_request_results,
            "counted_timeout": {
                "child_accepted_requests": counted_timeout_accepted,
                "request_attempt_count": counted_timeout.request_attempt_count,
                "request_write_count": counted_timeout.request_write_count,
                "response_count": counted_timeout.response_count,
                "automatic_replay_count": counted_timeout.automatic_replay_count,
                "child_stopped": counted_timeout.returncode is not None,
            },
            "response_correlation": {
                "future_sequence": correlation_results.get("future-sequence"),
                "wrong_request_digest": correlation_results.get("wrong-request-digest"),
                "wrong_response_digest": correlation_results.get("wrong-response-digest"),
                "stale_second": stale_evidence,
                "duplicate": duplicate_evidence,
            },
            "write_boundary": {
                "admission_rule": (
                    "full versioned response correlation after complete host frame write and flush; "
                    "phase and queue timing never establish identity"
                ),
                "prewrite": prewrite.state_evidence(),
                "midwrite_request_bytes": len(large_request),
                "midwrite": midwrite_results,
                "postwrite": postwrite_evidence,
                "partial_write": partial_evidence,
                "zero_write": zero_evidence,
            },
            "eof_before_response_child_stopped": eof_live.returncode is not None,
            "stderr_probes": stderr_results,
            "engine_overlimit_request_bytes": len(engine_overlimit_request),
            "engine_overlimit_response_sha256": sha256(engine_overlimit_response),
            "probe_argv": {
                "direct_launcher": direct_command,
                "prewrite_output": prewrite_command,
                "midwrite_output": midwrite_command,
                "counted_timeout": counted_timeout_command,
            },
        },
        "claims_limit": (
            "Exact parity covers 124 committed semantic fixtures and one engine-overlimit request "
            "on this runtime. Supervision probes establish Python-observed local stdio behavior, "
            "not native or OS-wide I/O provenance or absence of all failures."
        ),
    }
    if args.receipt is not None:
        embedded, raw_digest = write_new_receipt(args.receipt, receipt)
        print(f"receipt={repo_label(args.receipt)} embedded_sha256={embedded} raw_sha256={raw_digest}")
    print(f"sidecar parity: checks={checks} failures={len(failures)} fixtures={len(requests)}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
