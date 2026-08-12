"""Focused deterministic tests for the live OS transport schedule library."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
SCHEDULES = HERE / "schedules"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import controller  # noqa: E402
import replay  # noqa: E402
import worker  # noqa: E402


EXPECTED_SCHEDULES = {
    "broken_pipe.ndjson",
    "child_kill.ndjson",
    "delayed_flush.ndjson",
    "full_close.ndjson",
    "half_close.ndjson",
    "multi_response_buffering.ndjson",
    "partial_final_eof.ndjson",
    "pause_every_byte.ndjson",
}


class _ExplodingControlStream:
    """Test stream with an acknowledged boundary before a deterministic failure."""

    def __init__(
        self,
        records: tuple[bytes, ...],
        *,
        gate_failure: bool = False,
        close_error: bool = False,
    ) -> None:
        self.records = iter(records)
        self.gate_failure = gate_failure
        self.close_error = close_error
        self.failure_entered = threading.Event()
        self.release_failure = threading.Event()

    def readline(self, unused_size: int = -1) -> bytes:
        try:
            return next(self.records)
        except StopIteration:
            self.failure_entered.set()
            if self.gate_failure:
                self.release_failure.wait()
            raise OSError("deterministic control read failure after valid event")

    def close(self) -> None:
        if self.close_error:
            raise OSError("deterministic control close failure")


class _CloseExplodingControlStream(_ExplodingControlStream):
    def readline(self, unused_size: int = -1) -> bytes:
        try:
            return next(self.records)
        except StopIteration:
            return b""


class LiveTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = sorted(SCHEDULES.glob("*.ndjson"))
        cls.runs: dict[tuple[str, str], tuple[controller.RunResult, controller.RunResult]] = {}
        for path in cls.paths:
            steps = controller.load_schedule(path)
            for transport in controller.TRANSPORTS:
                first = controller.run_schedule(path, transport, steps=steps)
                second = controller.run_schedule(path, transport, steps=steps)
                cls.runs[(path.name, transport)] = (first, second)

    def test_inventory_is_exact_and_small(self) -> None:
        self.assertEqual(EXPECTED_SCHEDULES, {path.name for path in self.paths})
        for path in self.paths:
            self.assertLess(path.stat().st_size, 16 * 1024, path.name)

    def test_two_replays_are_byte_identical(self) -> None:
        for key, (first, second) in self.runs.items():
            with self.subTest(schedule=key[0], transport=key[1]):
                self.assertEqual(first.stable_bytes(), second.stable_bytes())

    def test_both_real_transport_classes_are_exercised(self) -> None:
        seen = {result.transport for pair in self.runs.values() for result in pair}
        self.assertEqual({"pipe", "socketpair"}, seen)
        source = (HERE / "controller.py").read_text(encoding="utf-8")
        worker = (HERE / "worker.py").read_text(encoding="utf-8")
        self.assertNotIn("BytesIO", source + worker)
        self.assertIn("subprocess.PIPE", source)
        self.assertIn("socket.socketpair()", source)

    def test_backpressure_faults_reach_os_acknowledgment(self) -> None:
        for schedule in (
            "broken_pipe.ndjson",
            "child_kill.ndjson",
            "multi_response_buffering.ndjson",
        ):
            for transport in controller.TRANSPORTS:
                with self.subTest(schedule=schedule, transport=transport):
                    result = self.runs[(schedule, transport)][0]
                    self.assertTrue(result.backpressure_observed)

    def test_close_and_kill_exit_semantics(self) -> None:
        for transport in controller.TRANSPORTS:
            with self.subTest(transport=transport):
                self.assertEqual(self.runs[("half_close.ndjson", transport)][0].returncode, 0)
                self.assertEqual(self.runs[("full_close.ndjson", transport)][0].returncode, 0)
                self.assertNotEqual(
                    self.runs[("broken_pipe.ndjson", transport)][0].returncode, 0
                )
                self.assertNotEqual(self.runs[("child_kill.ndjson", transport)][0].returncode, 0)

    def test_delayed_record_completion_flushes_before_eof(self) -> None:
        for transport in controller.TRANSPORTS:
            result = self.runs[("delayed_flush.ndjson", transport)][0]
            with self.subTest(transport=transport):
                self.assertEqual(0, result.returncode)
                self.assertEqual(1, result.flush_count)
                self.assertEqual(812, len(result.stdout))

    def test_partial_final_request_is_processed_at_eof(self) -> None:
        expected = controller.isolated_expected(b"{")
        for transport in controller.TRANSPORTS:
            result = self.runs[("partial_final_eof.ndjson", transport)][0]
            with self.subTest(transport=transport):
                self.assertEqual(expected, result.stdout)
                self.assertEqual(0, result.returncode)

    def test_multi_response_buffering_preserves_every_record(self) -> None:
        steps = controller.load_schedule(SCHEDULES / "multi_response_buffering.ndjson")
        raw = b"".join(step.payload for step in steps if step.action == "write")
        expected = controller.isolated_expected(raw)
        response_count = raw.count(b"\n")
        for transport in controller.TRANSPORTS:
            result = self.runs[("multi_response_buffering.ndjson", transport)][0]
            with self.subTest(transport=transport):
                self.assertEqual(expected, result.stdout)
                self.assertEqual(response_count, result.flush_count)
                self.assertEqual(0, result.os_short_write_count)
                self.assertEqual(0, result.returncode)

    def test_complete_w_domain_forces_and_acknowledges_real_write_boundaries(self) -> None:
        response_size = len(controller.isolated_expected(b"x\n"))
        for transport in controller.TRANSPORTS:
            result = self.runs[("pause_every_byte.ndjson", transport)][0]
            with self.subTest(transport=transport):
                self.assertEqual(response_size, result.w_partition_count)
                self.assertEqual(response_size, result.write_boundary_count)
                self.assertEqual(response_size - 1, result.forced_short_write_count)
                self.assertEqual(0, result.os_short_write_count)
                self.assertEqual(response_size, result.pause_count)
                self.assertEqual(response_size, result.resume_count)
                self.assertEqual(response_size, result.write_resume_ack_count)
                self.assertEqual(response_size, result.flush_count)
                self.assertEqual(
                    controller.isolated_expected(b"x\n" * response_size),
                    result.stdout,
                )

                pauses = [
                    ack for ack in result.acknowledgments if ack["action"] == "pause"
                ]
                resumes = [
                    ack for ack in result.acknowledgments if ack["action"] == "resume"
                ]
                self.assertEqual(
                    [
                        [0, split, response_size]
                        for split in range(1, response_size)
                    ]
                    + [[0, response_size]],
                    [ack["w_partition"] for ack in pauses],
                )
                self.assertTrue(
                    all(ack["writer_event"] == "write_boundary" for ack in pauses)
                )
                self.assertEqual(
                    [True] * (response_size - 1) + [False],
                    [ack["forced_short_write"] for ack in pauses],
                )
                self.assertEqual(
                    list(range(1, response_size + 1)),
                    [ack["prefix_bytes_read"] for ack in resumes],
                )
                self.assertTrue(
                    all(ack["writer_event"] == "write_resumed" for ack in resumes)
                )

    def test_control_gated_w_ack_is_not_mislabeled_as_os_backpressure(self) -> None:
        for transport in controller.TRANSPORTS:
            with self.subTest(transport=transport):
                result = self.runs[("pause_every_byte.ndjson", transport)][0]
                self.assertFalse(result.backpressure_observed)
                self.assertGreater(result.write_resume_ack_count, 0)

    def test_schedule_transitions_have_no_timing_primitive(self) -> None:
        source = (HERE / "controller.py").read_text(encoding="utf-8")
        worker = (HERE / "worker.py").read_text(encoding="utf-8")
        for forbidden in ("time.sleep", "time.monotonic", "perf_counter", "Timer("):
            self.assertNotIn(forbidden, source + worker)

    def test_transport_watchdog_eof_and_control_mismatch_are_infrastructure_errors(
        self,
    ) -> None:
        class FakeCondition:
            def __init__(self, notified: bool) -> None:
                self.notified = notified

            def __enter__(self) -> "FakeCondition":
                return self

            def __exit__(self, *unused: object) -> None:
                return None

            def wait(self, unused_timeout: int) -> bool:
                return self.notified

        watchdog = object.__new__(controller._ControlMonitor)
        watchdog.events = []
        watchdog.finished = False
        watchdog.condition = FakeCondition(False)
        with self.assertRaisesRegex(
            controller.TransportError, "watchdog waiting for child event"
        ) as caught:
            watchdog.wait_for("flush")
        self.assertEqual("INFRASTRUCTURE_ERROR", caught.exception.status)
        self.assertNotIsInstance(caught.exception, controller.DivergenceError)

        eof = object.__new__(controller._ControlMonitor)
        eof.events = []
        eof.finished = True
        eof.condition = FakeCondition(True)
        with self.assertRaisesRegex(
            controller.TransportError, "child exited before event"
        ):
            eof.wait_for("flush")

        class FakeProcess:
            @staticmethod
            def poll() -> int:
                return 1

        class MismatchedMonitor:
            events: list[dict[str, object]] = []
            stderr = bytearray()

            @staticmethod
            def wait_for(unused_event: str, unused_occurrence: int = 1) -> dict[str, object]:
                return {
                    "event": "write_boundary",
                    "forced_short_write": True,
                    "offered": 812,
                    "os_offered": 1,
                    "response_index": 99,
                    "split": 1,
                    "written": 1,
                }

            @staticmethod
            def count(unused_event: str) -> int:
                return 0

        class FakeConnection:
            def __init__(self) -> None:
                self.process = FakeProcess()
                self.monitor = MismatchedMonitor()
                self.input_closed = False
                self.output_closed = False

            @staticmethod
            def send_control(unused_command: dict[str, object]) -> None:
                return None

            @staticmethod
            def write_all(unused_data: bytes) -> None:
                return None

            def close_full(self) -> None:
                self.input_closed = True
                self.output_closed = True

        schedule = SCHEDULES / "pause_every_byte.ndjson"
        steps = controller.load_schedule(schedule)
        with mock.patch.object(controller, "_spawn", return_value=FakeConnection()):
            with self.assertRaisesRegex(
                controller.TransportError,
                "write-boundary acknowledgment mismatch",
            ):
                controller.run_schedule(schedule, "pipe", steps=steps)

    def test_control_monitor_sticks_failure_after_a_valid_event(self) -> None:
        ready = {"event": "ready", "transport": "pipe"}
        record = (
            controller.CONTROL_PREFIX
            + json.dumps(ready, sort_keys=True, separators=(",", ":")).encode("ascii")
            + b"\n"
        )
        stream = _ExplodingControlStream((record,), gate_failure=True)
        with mock.patch.object(threading, "excepthook") as exception_hook:
            monitor = controller._ControlMonitor(stream)
            try:
                self.assertTrue(stream.failure_entered.wait(1))
                self.assertEqual(ready, monitor.wait_for("ready"))
            finally:
                stream.release_failure.set()
                monitor.thread.join(1)

            self.assertFalse(monitor.thread.is_alive())
            for operation in (
                lambda: monitor.wait_for("ready"),
                lambda: monitor.count("ready"),
                monitor.finish,
            ):
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(
                        controller.TransportError,
                        "^control-channel read failure: OSError$",
                    ):
                        operation()
            exception_hook.assert_not_called()

    def test_control_monitor_sticks_failure_before_any_event(self) -> None:
        stream = _ExplodingControlStream(())
        with mock.patch.object(threading, "excepthook") as exception_hook:
            monitor = controller._ControlMonitor(stream)
            monitor.thread.join(1)
            self.assertFalse(monitor.thread.is_alive())
            for operation in (
                lambda: monitor.wait_for("ready"),
                lambda: monitor.count("ready"),
                monitor.finish,
            ):
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(
                        controller.TransportError,
                        "^control-channel read failure: OSError$",
                    ):
                        operation()
            exception_hook.assert_not_called()

    def test_control_monitor_preserves_first_failure_and_normalizes_close_error(
        self,
    ) -> None:
        malformed = _ExplodingControlStream((b"RRCTL []\n",))
        malformed_monitor = controller._ControlMonitor(malformed)
        malformed_monitor.thread.join(1)
        self.assertFalse(malformed_monitor.thread.is_alive())
        with self.assertRaisesRegex(
            controller.TransportError,
            "^invalid child control record: object required$",
        ):
            malformed_monitor.finish()

        ready = {"event": "ready", "transport": "pipe"}
        record = (
            controller.CONTROL_PREFIX
            + json.dumps(ready, sort_keys=True, separators=(",", ":")).encode("ascii")
            + b"\n"
        )
        closing = _CloseExplodingControlStream((record,), close_error=True)
        close_monitor = controller._ControlMonitor(closing)
        self.assertEqual(ready, close_monitor.wait_for("ready"))
        with self.assertRaisesRegex(
            controller.TransportError,
            "^control-channel close failure: OSError$",
        ):
            close_monitor.finish()
        with self.assertRaisesRegex(
            controller.TransportError,
            "^control-channel close failure: OSError$",
        ):
            close_monitor.count("ready")

    def test_monitor_read_failures_write_canonical_cli_receipts(self) -> None:
        ready = b'RRCTL {"event":"ready","transport":"pipe"}\n'
        failures = []
        for records, expected_events in (((ready,), 1), ((), 0)):
            monitor = controller._ControlMonitor(_ExplodingControlStream(records))
            monitor.thread.join(1)
            self.assertEqual(expected_events, len(monitor.events))
            with self.assertRaises(controller.TransportError) as caught:
                monitor.finish()
            failures.append(caught.exception)

        schedule = SCHEDULES / "half_close.ndjson"
        with tempfile.TemporaryDirectory() as temporary:
            for index, failure in enumerate(failures):
                with self.subTest(message=str(failure)):
                    root = pathlib.Path(temporary) / str(index)
                    output = io.StringIO()
                    with (
                        mock.patch.object(replay, "INFRASTRUCTURE_ERROR_ROOT", root),
                        mock.patch.object(
                            replay.controller,
                            "run_schedule",
                            side_effect=failure,
                        ),
                        mock.patch.object(sys, "argv", ["replay.py", str(schedule)]),
                        contextlib.redirect_stdout(output),
                    ):
                        self.assertEqual(2, replay.main())

                    stop = json.loads(output.getvalue())
                    receipt_bytes = (next(root.iterdir()) / "receipt.json").read_bytes()
                    receipt = json.loads(receipt_bytes)
                    self.assertEqual("INFRASTRUCTURE_ERROR", stop["status"])
                    self.assertEqual("INFRASTRUCTURE", receipt["classification"])
                    self.assertEqual("TransportError", receipt["error"]["type"])
                    self.assertEqual(str(failure), receipt["error"]["message"])
                    self.assertEqual(replay._canonical_json(receipt), receipt_bytes)
                    self.assertEqual(
                        hashlib.sha256(receipt_bytes).hexdigest().upper(),
                        stop["receipt_sha256"],
                    )

    def test_monitor_body_valueerror_is_harness_fault_not_transport(self) -> None:
        # F-LIVE-005 minimized witness: a programmer ValueError raised by the
        # monitor loop body was previously laundered as transport
        # INFRASTRUCTURE_ERROR by the loop-wide (OSError, ValueError) catch.
        ready = b'RRCTL {"event":"ready","transport":"pipe"}\n'
        with mock.patch.object(threading, "excepthook") as exception_hook:
            with mock.patch.object(
                controller,
                "_decode_control_record",
                side_effect=ValueError("injected monitor defect"),
            ):
                monitor = controller._ControlMonitor(io.BytesIO(ready))
                monitor.thread.join(1)
            self.assertFalse(monitor.thread.is_alive())
            self.assertIsNone(monitor.transport_error)
            for operation in (
                lambda: monitor.wait_for("ready"),
                lambda: monitor.count("ready"),
                monitor.finish,
            ):
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(
                        controller.HarnessFaultError,
                        "^monitor harness fault: ValueError: injected monitor defect$",
                    ):
                        operation()
            exception_hook.assert_not_called()

    def test_monitor_faults_cross_the_background_thread_boundary_exactly(self) -> None:
        # Before F-LIVE-005 a non-(OSError, ValueError) defect escaped the
        # monitor entirely: the thread died through threading.excepthook and
        # later waits surfaced a misleading transport classification.
        ready = b'RRCTL {"event":"ready","transport":"pipe"}\n'
        with mock.patch.object(threading, "excepthook") as exception_hook:
            with mock.patch.object(
                controller,
                "_validate_control_event",
                side_effect=TypeError("injected type defect"),
            ):
                monitor = controller._ControlMonitor(io.BytesIO(ready))
                monitor.thread.join(1)
            self.assertFalse(monitor.thread.is_alive())
            self.assertIsNone(monitor.transport_error)
            with self.assertRaisesRegex(
                controller.HarnessFaultError,
                "^monitor harness fault: TypeError: injected type defect$",
            ):
                monitor.wait_for("ready")
            exception_hook.assert_not_called()

        # BaseException is deliberately not harness evidence, but simply
        # allowing it to leave a background thread does not propagate it to
        # the caller.  The monitor must retain and re-raise the exact object
        # before a later wait can relabel the silent exit as infrastructure.
        for abort_type in (KeyboardInterrupt, SystemExit):
            with self.subTest(abort_type=abort_type.__name__):
                abort = abort_type("injected control abort")
                with mock.patch.object(threading, "excepthook") as exception_hook:
                    with mock.patch.object(
                        controller,
                        "_decode_control_record",
                        side_effect=abort,
                    ):
                        monitor = controller._ControlMonitor(io.BytesIO(ready))
                        monitor.thread.join(1)
                    self.assertFalse(monitor.thread.is_alive())
                    self.assertIsNone(monitor.transport_error)
                    self.assertIsNone(monitor.harness_fault)
                    for operation in (
                        lambda: monitor.wait_for("ready"),
                        lambda: monitor.count("ready"),
                        monitor.finish,
                    ):
                        with self.subTest(operation=operation):
                            with self.assertRaises(abort_type) as caught:
                                operation()
                            self.assertIs(caught.exception, abort)
                    exception_hook.assert_not_called()

                cleanup_monitor = controller._ControlMonitor(io.BytesIO(ready))
                cleanup_abort = abort_type("abort before ready")
                cleanup_monitor.thread.join(1)
                cleanup_monitor.control_abort = cleanup_abort
                connection = mock.Mock()
                connection.monitor = cleanup_monitor
                connection.process.poll.return_value = None
                with self.assertRaises(abort_type) as caught:
                    controller._await_ready(connection)
                self.assertIs(caught.exception, cleanup_abort)
                connection.process.kill.assert_called_once_with()
                connection.process.wait.assert_called_once()
                connection.close_full.assert_called_once_with()

    def test_closed_stream_read_remains_transport_normalized(self) -> None:
        # The physical readline stays the one transport-normalization site:
        # the deterministic closed-stream ValueError is still infrastructure,
        # never a harness fault.
        stream = io.BytesIO(b"")
        stream.close()
        monitor = controller._ControlMonitor(stream)
        monitor.thread.join(1)
        self.assertFalse(monitor.thread.is_alive())
        self.assertIsNone(monitor.harness_fault)
        with self.assertRaisesRegex(
            controller.TransportError,
            "^control-channel read failure: ValueError$",
        ):
            monitor.wait_for("ready")

    def test_replay_cli_persists_canonical_harness_fault_receipts(self) -> None:
        fault = controller.HarnessFaultError(
            "monitor harness fault: TypeError: injected type defect"
        )
        schedule = SCHEDULES / "half_close.ndjson"
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary) / "faults"
            output = io.StringIO()
            with (
                mock.patch.object(replay, "HARNESS_FAULT_ROOT", root),
                mock.patch.object(
                    replay.controller, "run_schedule", side_effect=fault
                ),
                mock.patch.object(sys, "argv", ["replay.py", str(schedule)]),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(4, replay.main())

            stop = json.loads(output.getvalue())
            receipt_bytes = (next(root.iterdir()) / "receipt.json").read_bytes()
            receipt = json.loads(receipt_bytes)
            self.assertEqual("HARNESS_FAULT", stop["status"])
            self.assertEqual("HARNESS", receipt["classification"])
            self.assertEqual("HarnessFaultError", receipt["error"]["type"])
            self.assertEqual(str(fault), receipt["error"]["message"])
            self.assertEqual(
                "receiver-reliance-live-harness-fault-v1", receipt["schema"]
            )
            self.assertEqual(replay._canonical_json(receipt), receipt_bytes)
            self.assertEqual(
                hashlib.sha256(receipt_bytes).hexdigest().upper(),
                stop["receipt_sha256"],
            )

    def test_fault_renderer_failure_is_still_recorded_durably(self) -> None:
        # R-LIVE-5 refutation witness: an exception whose own __str__ raises
        # must still become a sticky harness fault instead of escaping the
        # handler and dying through threading.excepthook.
        class UnprintableDefect(Exception):
            def __str__(self) -> str:
                raise ValueError("fault renderer failed")

        ready = b'RRCTL {"event":"ready","transport":"pipe"}\n'
        with mock.patch.object(threading, "excepthook") as exception_hook:
            with mock.patch.object(
                controller,
                "_decode_control_record",
                side_effect=UnprintableDefect(),
            ):
                monitor = controller._ControlMonitor(io.BytesIO(ready))
                monitor.thread.join(1)
            self.assertFalse(monitor.thread.is_alive())
            self.assertIsNone(monitor.transport_error)
            with self.assertRaisesRegex(
                controller.HarnessFaultError,
                "^monitor harness fault: UnprintableDefect: "
                "<unprintable fault detail>$",
            ):
                monitor.wait_for("ready")
            exception_hook.assert_not_called()

    def test_fault_type_name_trap_is_still_recorded_durably(self) -> None:
        # R-LIVE-5 second renderer witness: a metaclass that raises on the
        # __name__ lookup must not escape the guards either; the fallback may
        # not repeat the failing lookup.
        class NameTrapMeta(type):
            def __getattribute__(cls, name: str):
                if name == "__name__":
                    raise ValueError("type-name renderer failed")
                return super().__getattribute__(name)

        class NameTrapDefect(Exception, metaclass=NameTrapMeta):
            pass

        ready = b'RRCTL {"event":"ready","transport":"pipe"}\n'
        with mock.patch.object(threading, "excepthook") as exception_hook:
            with mock.patch.object(
                controller,
                "_decode_control_record",
                side_effect=NameTrapDefect(),
            ):
                monitor = controller._ControlMonitor(io.BytesIO(ready))
                monitor.thread.join(1)
            self.assertFalse(monitor.thread.is_alive())
            self.assertIsNone(monitor.transport_error)
            with self.assertRaisesRegex(
                controller.HarnessFaultError,
                "^monitor harness fault: <unprintable exception type>: ",
            ):
                monitor.wait_for("ready")
            exception_hook.assert_not_called()

    def test_fault_name_value_trap_is_still_recorded_durably(self) -> None:
        # R-LIVE-5 third renderer witness: __name__ succeeds but returns a
        # hostile str subclass that raises on formatting; the last-resort
        # constant must record the fault without formatting it again.
        class HostileName(str):
            def __format__(self, spec: str) -> str:
                raise ValueError("type-name formatting failed")

        class NameValueTrapMeta(type):
            def __getattribute__(cls, name: str):
                if name == "__name__":
                    return HostileName("NameValueTrapDefect")
                return super().__getattribute__(name)

        class NameValueTrapDefect(Exception, metaclass=NameValueTrapMeta):
            pass

        ready = b'RRCTL {"event":"ready","transport":"pipe"}\n'
        with mock.patch.object(threading, "excepthook") as exception_hook:
            with mock.patch.object(
                controller,
                "_decode_control_record",
                side_effect=NameValueTrapDefect(),
            ):
                monitor = controller._ControlMonitor(io.BytesIO(ready))
                monitor.thread.join(1)
            self.assertFalse(monitor.thread.is_alive())
            self.assertIsNone(monitor.transport_error)
            with self.assertRaisesRegex(
                controller.HarnessFaultError,
                "^monitor harness fault: <unprintable fault>$",
            ):
                monitor.wait_for("ready")
            exception_hook.assert_not_called()

    def test_stop_receipt_identity_binds_completed_replay_evidence(self) -> None:
        # F-LIVE-006: two second-replay stops with identical reasons but
        # different completed first replays must land in distinct evidence
        # directories, preserving both receipts.
        schedule = SCHEDULES / "half_close.ndjson"

        def result_with(stdout: bytes) -> controller.RunResult:
            return controller.RunResult(
                schedule=schedule.name,
                transport="pipe",
                stdout=stdout,
                stderr=b"",
                returncode=0,
                acknowledgments=(),
                backpressure_observed=False,
                flush_count=1,
                w_partition_count=0,
                pause_count=0,
                resume_count=0,
                write_boundary_count=0,
                forced_short_write_count=0,
                os_short_write_count=0,
                write_resume_ack_count=0,
            )

        cases = (
            (
                replay._write_transport_error,
                "INFRASTRUCTURE_ERROR_ROOT",
                controller.TransportError(
                    "control-channel read failure: OSError"
                ),
            ),
            (
                replay._write_harness_fault,
                "HARNESS_FAULT_ROOT",
                controller.HarnessFaultError(
                    "monitor harness fault: TypeError: injected type defect"
                ),
            ),
        )
        for writer, root_name, error in cases:
            with self.subTest(writer=writer.__name__):
                with tempfile.TemporaryDirectory() as temporary:
                    root = pathlib.Path(temporary)
                    with mock.patch.object(replay, root_name, root):
                        first_target, first_receipt = writer(
                            schedule, "pipe", error, 2, (result_with(b"first-A"),)
                        )
                        second_target, second_receipt = writer(
                            schedule, "pipe", error, 2, (result_with(b"first-B"),)
                        )
                    self.assertNotEqual(first_target, second_target)
                    self.assertNotEqual(first_receipt, second_receipt)
                    self.assertEqual(len(first_target.name.rsplit("-", 1)[1]), 64)
                    self.assertEqual(len(second_target.name.rsplit("-", 1)[1]), 64)
                    self.assertEqual(
                        first_receipt,
                        (first_target / "receipt.json").read_bytes(),
                    )
                    self.assertEqual(
                        second_receipt,
                        (second_target / "receipt.json").read_bytes(),
                    )

        # Different schedule bytes sharing one basename must also diverge:
        # the identity binds schedule content, not just its filename.
        for writer, root_name, error in cases:
            with self.subTest(writer=writer.__name__, axis="schedule-bytes"):
                with tempfile.TemporaryDirectory() as temporary:
                    root = pathlib.Path(temporary)
                    first_schedule = root / "a" / "same.ndjson"
                    second_schedule = root / "b" / "same.ndjson"
                    first_schedule.parent.mkdir()
                    second_schedule.parent.mkdir()
                    first_schedule.write_bytes(
                        b'{"step":0,"action":"close_full","barrier":"a"}\n'
                    )
                    second_schedule.write_bytes(
                        b'{"step":0,"action":"close_full","barrier":"b"}\n'
                    )
                    with mock.patch.object(replay, root_name, root / "out"):
                        first_target, first_receipt = writer(
                            first_schedule, "pipe", error, 1, ()
                        )
                        second_target, second_receipt = writer(
                            second_schedule, "pipe", error, 1, ()
                        )
                    self.assertNotEqual(first_target, second_target)
                    self.assertNotEqual(first_receipt, second_receipt)
                    self.assertEqual(len(first_target.name.rsplit("-", 1)[1]), 64)
                    self.assertEqual(len(second_target.name.rsplit("-", 1)[1]), 64)
                    self.assertEqual(
                        first_receipt,
                        (first_target / "receipt.json").read_bytes(),
                    )
                    self.assertEqual(
                        second_receipt,
                        (second_target / "receipt.json").read_bytes(),
                    )

    def test_control_monitor_rejects_non_object_without_attribute_error(self) -> None:
        monitor = controller._ControlMonitor(io.BytesIO(b"RRCTL []\n"))
        with self.assertRaisesRegex(
            controller.TransportError,
            "invalid child control record: object required",
        ) as caught:
            monitor.wait_for("ready")
        self.assertNotIsInstance(caught.exception, AttributeError)
        with self.assertRaisesRegex(
            controller.TransportError,
            "invalid child control record: object required",
        ):
            monitor.finish()

        with tempfile.TemporaryDirectory() as temporary:
            hostile_worker = pathlib.Path(temporary) / "hostile_worker.py"
            hostile_worker.write_text(
                "import os, sys\n"
                "os.write(2, b'RRCTL []\\n')\n"
                "sys.stdin.buffer.read()\n",
                encoding="utf-8",
            )
            processes = []
            real_popen = controller.subprocess.Popen

            def capturing_popen(*args: object, **kwargs: object) -> object:
                process = real_popen(*args, **kwargs)
                processes.append(process)
                return process

            with (
                mock.patch.object(controller, "WORKER", hostile_worker),
                mock.patch.object(
                    controller.subprocess, "Popen", side_effect=capturing_popen
                ),
                self.assertRaisesRegex(
                    controller.TransportError,
                    "invalid child control record: object required",
                ),
            ):
                controller._spawn("pipe")
            self.assertEqual(1, len(processes))
            self.assertIsNotNone(processes[0].poll())

    def test_control_monitor_rejects_ambiguous_or_unsafe_records(self) -> None:
        hostile_records = (
            b"RRCTL {\"event\":\"flush\",\"event\":\"ready\"}\n",
            b"RRCTL {\"event\":\"backpressure\",\"offered\":NaN}\n",
            b"RRCTL {\"event\":\"flush\",\"extra\":0}\n",
            b"RRCTL {\"event\":7}\n",
            b"RRCTL {\"event\":\"unknown\"}\n",
            b"RRCTL {\"event\":\"backpressure\",\"offered\":true}\n",
            b"RRCTL {\"event\":\"backpressure\",\"offered\":9223372036854775808}\n",
            b"RRCTL " + (b"[" * 1100) + b"0" + (b"]" * 1100) + b"\n",
            b"RRCTL \xff\n",
            b"RRCTL \xef\xbb\xbf{\"event\":\"flush\"}\n",
            b"RRCTL {}",
            b"RRCTL " + (b" " * controller.MAX_CONTROL_RECORD_BYTES) + b"\n",
        )
        for record in hostile_records:
            with self.subTest(record_bytes=len(record)):
                monitor = controller._ControlMonitor(io.BytesIO(record))
                with self.assertRaisesRegex(
                    controller.TransportError, "invalid child control record"
                ):
                    monitor.wait_for("flush")
                monitor.thread.join(1)
                self.assertFalse(monitor.thread.is_alive())
                monitor.stream.close()

        valid_events = (
            {"event": "flush"},
            {"event": "ready", "transport": "pipe"},
            {"event": "ready", "send_buffer": 8192, "transport": "socketpair"},
            {"event": "backpressure", "offered": 812},
            {"event": "short_write", "offered": 812, "written": 1},
            {
                "event": "unexpected_os_short_write",
                "requested": 2,
                "response_index": 0,
                "written": 1,
            },
            {
                "event": "write_boundary",
                "forced_short_write": True,
                "offered": 812,
                "os_offered": 1,
                "response_index": 0,
                "split": 1,
                "written": 1,
            },
            {"event": "write_resumed", "response_index": 0, "split": 1},
        )
        for event in valid_events:
            with self.subTest(event=event["event"]):
                record = (
                    controller.CONTROL_PREFIX
                    + json.dumps(event, sort_keys=True, separators=(",", ":")).encode(
                        "ascii"
                    )
                    + b"\n"
                )
                monitor = controller._ControlMonitor(io.BytesIO(record))
                self.assertEqual(event, monitor.wait_for(event["event"]))
                monitor.finish()

    def test_replay_cli_persists_canonical_transport_error_receipts(self) -> None:
        schedule = SCHEDULES / "half_close.ndjson"
        cases = (
            "watchdog waiting for child event 'flush'",
            "child exited before event 'flush'",
            "write-boundary acknowledgment mismatch at W split 1",
        )
        with tempfile.TemporaryDirectory() as temporary:
            for index, reason in enumerate(cases):
                with self.subTest(reason=reason):
                    root = pathlib.Path(temporary) / str(index)
                    output = io.StringIO()
                    with (
                        mock.patch.object(replay, "INFRASTRUCTURE_ERROR_ROOT", root),
                        mock.patch.object(
                            replay.controller,
                            "run_schedule",
                            side_effect=controller.TransportError(reason),
                        ),
                        mock.patch.object(sys, "argv", ["replay.py", str(schedule)]),
                        contextlib.redirect_stdout(output),
                    ):
                        self.assertEqual(2, replay.main())

                    stop = json.loads(output.getvalue())
                    self.assertEqual("INFRASTRUCTURE_ERROR", stop["status"])
                    self.assertEqual("INFRASTRUCTURE", stop["classification"])
                    targets = list(root.iterdir())
                    self.assertEqual(1, len(targets))
                    receipt_bytes = (targets[0] / "receipt.json").read_bytes()
                    receipt = json.loads(receipt_bytes)
                    self.assertEqual(
                        replay._canonical_json(receipt),
                        receipt_bytes,
                    )
                    self.assertEqual("INFRASTRUCTURE_ERROR", receipt["status"])
                    self.assertEqual("TransportError", receipt["error"]["type"])
                    self.assertEqual(reason, receipt["error"]["message"])
                    self.assertEqual(1, receipt["failing_replay"])
                    self.assertEqual([], receipt["completed_replays"])
                    self.assertEqual(
                        hashlib.sha256(schedule.read_bytes()).hexdigest().upper(),
                        receipt["schedule"]["sha256"],
                    )
                    self.assertEqual(
                        hashlib.sha256(receipt_bytes).hexdigest().upper(),
                        stop["receipt_sha256"],
                    )

    def test_malformed_control_replay_writes_canonical_infrastructure_receipt(
        self,
    ) -> None:
        schedule = SCHEDULES / "half_close.ndjson"
        monitor = controller._ControlMonitor(io.BytesIO(b"RRCTL []\n"))
        with self.assertRaises(controller.TransportError) as caught:
            monitor.wait_for("ready")
        monitor.thread.join(1)
        monitor.stream.close()
        failure = caught.exception

        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            output = io.StringIO()
            with (
                mock.patch.object(replay, "INFRASTRUCTURE_ERROR_ROOT", root),
                mock.patch.object(
                    replay.controller, "run_schedule", side_effect=failure
                ),
                mock.patch.object(sys, "argv", ["replay.py", str(schedule)]),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(2, replay.main())

            stop = json.loads(output.getvalue())
            receipt_bytes = (next(root.iterdir()) / "receipt.json").read_bytes()
            receipt = json.loads(receipt_bytes)
            self.assertEqual("INFRASTRUCTURE_ERROR", stop["status"])
            self.assertEqual("INFRASTRUCTURE", receipt["classification"])
            self.assertEqual("TransportError", receipt["error"]["type"])
            self.assertEqual(
                "invalid child control record: object required",
                receipt["error"]["message"],
            )
            self.assertEqual(replay._canonical_json(receipt), receipt_bytes)
            self.assertEqual(
                hashlib.sha256(receipt_bytes).hexdigest().upper(),
                stop["receipt_sha256"],
            )

    def test_second_replay_transport_error_retains_completed_first_replay(self) -> None:
        schedule = SCHEDULES / "half_close.ndjson"
        first = self.runs[(schedule.name, "pipe")][0]
        failure = controller.TransportError("watchdog: child did not terminate after schedule")
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            output = io.StringIO()
            with (
                mock.patch.object(replay, "INFRASTRUCTURE_ERROR_ROOT", root),
                mock.patch.object(
                    replay.controller,
                    "run_schedule",
                    side_effect=(first, failure),
                ),
                mock.patch.object(sys, "argv", ["replay.py", str(schedule)]),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(2, replay.main())

            target = next(root.iterdir())
            receipt = json.loads((target / "receipt.json").read_bytes())
            self.assertEqual(2, receipt["failing_replay"])
            self.assertEqual(1, len(receipt["completed_replays"]))
            self.assertEqual(
                hashlib.sha256(first.stable_bytes()).hexdigest().upper(),
                receipt["completed_replays"][0]["stable_sha256"],
            )
            self.assertEqual(
                first.stdout, (target / "completed-replay-1.stdout.bin").read_bytes()
            )


class WorkerPeerCloseAbortTests(unittest.TestCase):
    def test_peer_close_abort_is_deterministic_and_never_launders_faults(self) -> None:
        # F-LIVE-009: two hosted replays of broken_pipe.ndjson on socketpair
        # differed only in which accepted-server syscall first observed the
        # peer close, so the embedded traceback broke byte-identical replay.
        # The abort boundary emits one bare control event and a fixed exit
        # code.  Review correction: exception class alone cannot establish
        # which endpoint raised, so translation to the internal sentinel
        # happens only at the physical data endpoints; a raw connection-abort
        # class reaching _serve from anywhere else propagates unchanged.
        events: list[tuple[str, dict[str, object]]] = []
        with (
            mock.patch.object(
                worker.rr_batch,
                "serve",
                side_effect=worker._PeerCloseAbort("data sink peer close"),
            ),
            mock.patch.object(
                worker,
                "_control",
                lambda event, **fields: events.append((event, fields)),
            ),
        ):
            exit_code = worker._serve(None, None)
        self.assertEqual(exit_code, worker.PEER_CLOSE_EXIT)
        self.assertEqual(events, [("transport_abort", {})])

        # Raw abort classes, harness faults, and other OS errors all
        # propagate: nothing outside the data endpoints is laundered.
        for defect in (
            BrokenPipeError("control channel"),
            ConnectionResetError("control channel"),
            ConnectionAbortedError("control channel"),
            ValueError("harness defect"),
            OSError("other os error"),
        ):
            with self.subTest(defect=type(defect).__name__):
                with (
                    mock.patch.object(
                        worker.rr_batch, "serve", side_effect=defect
                    ),
                    mock.patch.object(worker, "_control") as control,
                ):
                    with self.assertRaises(type(defect)):
                        worker._serve(None, None)
                control.assert_not_called()

    def test_only_physical_data_endpoints_translate_peer_close(self) -> None:
        class _AbortingSocket:
            def setblocking(self, value: bool) -> None:
                pass

            def send(self, data: object) -> int:
                raise ConnectionResetError("peer closed data endpoint")

            def makefile(self, mode: str, buffering: int) -> object:
                outer = self

                class _Raw:
                    def readline(self, size: int = -1) -> bytes:
                        raise BrokenPipeError("peer closed data endpoint")

                    def close(self) -> None:
                        pass

                return _Raw()

        endpoint = _AbortingSocket()
        with mock.patch.object(worker, "socket") as socket_module:
            socket_module.socket = _AbortingSocket
            sink = worker.NonBlockingSink.__new__(worker.NonBlockingSink)
            sink.endpoint = endpoint
            sink._is_socket = True
            sink.boundary_control = None
            sink._control_reader = None
            sink._response_index = 0
            sink._boundary_complete = False
            with self.assertRaises(worker._PeerCloseAbort):
                sink._write_once(memoryview(b"x"))

        source = worker.BlockingSocketSource.__new__(worker.BlockingSocketSource)
        source.endpoint = endpoint
        source.raw = endpoint.makefile("rb", 0)
        with self.assertRaises(worker._PeerCloseAbort):
            source.readline()


class FaultScheduleIdentityTests(unittest.TestCase):
    @staticmethod
    def _result(**overrides: object) -> controller.RunResult:
        base: dict[str, object] = dict(
            schedule="child_kill.ndjson",
            transport="socketpair",
            stdout=b"data",
            stderr=b"RRCTL control-tail",
            returncode=5,
            acknowledgments=({"step": 0, "action": "write", "barrier": "b"},),
            backpressure_observed=True,
            flush_count=7,
            w_partition_count=0,
            pause_count=1,
            resume_count=0,
            write_boundary_count=0,
            forced_short_write_count=0,
            os_short_write_count=0,
            write_resume_ack_count=0,
            fault_schedule=True,
        )
        base.update(overrides)
        return controller.RunResult(**base)  # type: ignore[arg-type]

    def test_fault_schedule_identity_excludes_death_racy_fields(self) -> None:
        # F-LIVE-010: an asynchronous fault (kill, or full close during
        # observed backpressure) cuts the child at a kernel-scheduled
        # instant; the control-event tail length, stop path, and stderr tail
        # are artifacts of that instant and must not break replay identity.
        first = self._result()
        for racy in (
            self._result(flush_count=8),
            self._result(returncode=-9),
            self._result(stderr=b"RRCTL control-tail plus traceback"),
        ):
            self.assertEqual(first.stable_bytes(), racy.stable_bytes())
        # The schedule-driven surfaces stay bound for fault schedules.
        self.assertNotEqual(
            first.stable_bytes(), self._result(stdout=b"other").stable_bytes()
        )
        self.assertNotEqual(
            first.stable_bytes(), self._result(pause_count=2).stable_bytes()
        )
        # Orderly schedules keep the full binding, and the flag itself is
        # part of identity so the two receipt shapes can never alias.
        orderly = self._result(fault_schedule=False)
        self.assertNotEqual(first.stable_bytes(), orderly.stable_bytes())
        self.assertNotEqual(
            orderly.stable_bytes(),
            self._result(fault_schedule=False, flush_count=8).stable_bytes(),
        )
        self.assertNotEqual(
            orderly.stable_bytes(),
            self._result(fault_schedule=False, returncode=-9).stable_bytes(),
        )
        # Durable evidence retains the excluded values for every schedule.
        summary = first.summary()
        self.assertEqual(summary["returncode"], 5)

    def test_controller_transport_watchdog_bounds(self) -> None:
        # F-LIVE-011: every controller data-plane OS call carries the same
        # watchdog bound as the event waits, so a stalled child produces a
        # minimized TransportError witness instead of an unbounded hang.
        connection = controller._spawn("socketpair")
        try:
            assert connection.endpoint is not None
            self.assertEqual(
                connection.endpoint.gettimeout(), controller.WATCHDOG_SECONDS
            )
        finally:
            connection.kill()
            connection.process.wait(timeout=controller.WATCHDOG_SECONDS)
            connection.monitor.thread.join(controller.WATCHDOG_SECONDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
