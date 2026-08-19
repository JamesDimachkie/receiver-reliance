"""Byte-identity proof for the observability wrapper, with its negative arms.

The claim this suite has to establish is not that an observer sees useful
numbers. It is that attaching one changes nothing a recipient could detect: the
same envelope, the same response line, the same audit seal, the same error
surface, with any observer or none. An earlier attempt at this seam was refuted
by exactly that test -- an observer returned the envelope, a host added a
correlation id to it, and the response moved from 1,774 bytes to 1,799 -- so the
positive arm here runs over every request corpus this repository ships and the
negative arms run the hostile observers that failure implies.

The corpora, all committed and all recomputed here rather than replayed:

  * `examples/*.json`, the three requests the README hands a new reader;
  * the 124 committed semantic fixtures (112 in the 0.2 pack, 12 in the 0.3
    pack), each decided twice -- once as exact wire bytes, once as the Python
    object -- because the two take different paths through `decide_audited`;
  * the error surfaces: protocol errors from non-JSON bytes, and the
    object-refusal codes ERR_JSON, ERR_NUMBER and ERR_LIMIT, which are the
    paths where an envelope is produced without the engine ever classifying;
  * a deterministic `fuzz/fuzz.py` sample -- its `DEFAULT_SEED`, its
    `generate_cases`, every strategy covered five times over, generated in
    process because only the request bytes are wanted here and not the
    subprocess differential the fuzzer itself performs.

Run: python -B receiver_reliance/test_observe.py
"""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import pathlib
import sys
import time
import types
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "grounded-0_4") not in sys.path:
    sys.path.insert(0, str(REPO / "grounded-0_4"))

import receiver_reliance  # noqa: E402
import rr_batch  # noqa: E402

ENGINE = sys.modules["receiver_reliance._rr_api"]
JCS = ENGINE.b1.jcs_bytes

FUZZ_CASES_PER_STRATEGY = 5
PACKS = (
    "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
)


def _load_fuzz() -> types.ModuleType:
    """Load `fuzz/fuzz.py` by path; it is not an importable package member."""
    spec = importlib.util.spec_from_file_location(
        "receiver_reliance_test_observe_fuzz", REPO / "fuzz" / "fuzz.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def wire_corpus() -> list[tuple[str, bytes]]:
    """Every committed request this repository can hand the engine, as bytes."""
    cases: list[tuple[str, bytes]] = []
    for path in sorted((REPO / "examples").glob("*.json")):
        cases.append((f"example:{path.name}", path.read_bytes()))
    for relative in PACKS:
        pack = json.loads((REPO / relative).read_text(encoding="utf-8"))
        label = relative.rsplit("/", 1)[-1].split("_FIXTURE", 1)[0]
        for entry in pack["entries"]:
            cases.append(
                (
                    f"fixture:{label}:{entry['entry_id']}",
                    base64.b64decode(entry["semantic_request_jcs_lf_base64"]),
                )
            )
    for label, raw in (
        ("error:empty", b""),
        ("error:not-json", b"not json\n"),
        ("error:root-scalar", b"7\n"),
        ("error:bom", b"\xef\xbb\xbf{}\n"),
        ("error:invalid-utf8", b"\xff\xfe{}\n"),
        ("error:duplicate-key", b'{"a":1,"a":2}\n'),
        ("error:unterminated", b'{"a":1'),
    ):
        cases.append((label, raw))
    fuzz = _load_fuzz()
    strategies = list(fuzz.STRATEGIES)
    generated = fuzz.generate_cases(
        fuzz.DEFAULT_SEED,
        len(strategies) * FUZZ_CASES_PER_STRATEGY,
        strategies,
    )
    for case in generated:
        cases.append((f"fuzz:{case.case_id}", case.raw))
    return cases


def object_corpus() -> list[tuple[str, object]]:
    """Requests that reach `decide_audited` as Python objects, not wire bytes."""
    cases: list[tuple[str, object]] = []
    for relative in PACKS:
        pack = json.loads((REPO / relative).read_text(encoding="utf-8"))
        label = relative.rsplit("/", 1)[-1].split("_FIXTURE", 1)[0]
        for entry in pack["entries"]:
            cases.append(
                (
                    f"object:{label}:{entry['entry_id']}",
                    copy.deepcopy(entry["semantic_request"]),
                )
            )
    cyclic: dict = {}
    cyclic["self"] = cyclic
    deep: dict = {}
    for _ in range(ENGINE.b1.MAX_NESTING + 1):
        deep = {"nested": deep}
    cases.extend(
        [
            ("object-error:cyclic", cyclic),
            ("object-error:non-string-key", {1: "value"}),
            ("object-error:non-finite", {"value": float("nan")}),
            ("object-error:lone-surrogate", {"value": "\ud800"}),
            ("object-error:deep", deep),
            (
                "object-error:aggregate-members",
                {"values": [None] * (ENGINE.b1.MAX_MEMBERS_OR_ITEMS + 1)},
            ),
            ("object:not-a-mapping", "a string request"),
            ("object:none", None),
            ("object:bytearray", bytearray(b'{"a":1}\n')),
        ]
    )
    return cases


WIRE = wire_corpus()
OBJECTS = object_corpus()


class Recorder:
    """The benign observer: keeps every record, touches nothing else."""

    def __init__(self) -> None:
        self.seen: list[receiver_reliance.DecisionObservation] = []

    def __call__(self, observation: object) -> None:
        self.seen.append(observation)


def _null_observer(_observation: object) -> None:
    return None


class CorpusIsNotEmpty(unittest.TestCase):
    def test_every_corpus_has_the_expected_shape(self) -> None:
        self.assertEqual(
            len([label for label, _ in WIRE if label.startswith("example:")]), 3
        )
        self.assertEqual(
            len([label for label, _ in WIRE if label.startswith("fixture:")]), 124
        )
        self.assertEqual(
            len([label for label, _ in OBJECTS if label.startswith("object:")]),
            124 + 3,
        )
        fuzz_cases = [label for label, _ in WIRE if label.startswith("fuzz:")]
        self.assertEqual(len(fuzz_cases), 31 * FUZZ_CASES_PER_STRATEGY)
        self.assertEqual(len(set(fuzz_cases)), len(fuzz_cases))


class ObservingChangesNoByte(unittest.TestCase):
    """The positive arm: identical output, over every corpus, every observer."""

    def test_wire_envelopes_are_byte_identical(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                expected = receiver_reliance.decide_audited(raw)
                observed = receiver_reliance.decide_audited_observed(raw, Recorder())
                self.assertEqual(JCS(expected), JCS(observed))
                self.assertEqual(expected, observed)
                self.assertTrue(receiver_reliance.verify_audit_seal(observed))

    def test_object_envelopes_are_byte_identical(self) -> None:
        for label, request in OBJECTS:
            with self.subTest(case=label):
                expected = receiver_reliance.decide_audited(copy.deepcopy(request))
                observed = receiver_reliance.decide_audited_observed(
                    copy.deepcopy(request), Recorder()
                )
                self.assertEqual(JCS(expected), JCS(observed))
                self.assertEqual(expected, observed)

    def test_response_lines_equal_the_transport_byte_for_byte(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                expected = rr_batch.response_bytes(raw)
                self.assertEqual(
                    expected, receiver_reliance.response_bytes_observed(raw)
                )
                self.assertEqual(
                    expected,
                    receiver_reliance.response_bytes_observed(raw, Recorder()),
                )

    def test_the_passthrough_is_the_engine_call(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                self.assertEqual(
                    JCS(receiver_reliance.decide_audited(raw)),
                    JCS(receiver_reliance.decide_audited_observed(raw)),
                )

    def test_repeated_observation_does_not_accumulate_state(self) -> None:
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        first = receiver_reliance.decide_audited_observed(raw, Recorder())
        for _ in range(20):
            receiver_reliance.decide_audited_observed(raw, Recorder())
        after = receiver_reliance.decide_audited_observed(raw, Recorder())
        unobserved = receiver_reliance.decide_audited(raw)
        self.assertEqual(JCS(first), JCS(after))
        self.assertEqual(JCS(unobserved), JCS(after))


class TheObserverIsAnArgument(unittest.TestCase):
    """No global, no ambient switch, no residue between callers."""

    def test_there_is_no_installation_surface(self) -> None:
        for forbidden in (
            "install_observer",
            "set_observer",
            "uninstall_observer",
            "OBSERVER",
            "_OBSERVER",
            "Observatory",
        ):
            self.assertFalse(hasattr(receiver_reliance, forbidden), forbidden)

    def test_the_default_notifies_nobody(self) -> None:
        recorder = Recorder()
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        receiver_reliance.decide_audited_observed(raw, recorder)
        receiver_reliance.decide_audited_observed(raw)
        receiver_reliance.response_bytes_observed(raw)
        self.assertEqual(len(recorder.seen), 1)

    def test_one_observer_does_not_see_another_callers_decisions(self) -> None:
        first, second = Recorder(), Recorder()
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        receiver_reliance.decide_audited_observed(raw, first)
        receiver_reliance.decide_audited_observed(raw, second)
        receiver_reliance.decide_audited_observed(raw, second)
        self.assertEqual((len(first.seen), len(second.seen)), (1, 2))

    def test_exactly_one_notification_per_decision(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                recorder = Recorder()
                receiver_reliance.decide_audited_observed(raw, recorder)
                self.assertEqual(len(recorder.seen), 1)
                recorder = Recorder()
                receiver_reliance.response_bytes_observed(raw, recorder)
                self.assertEqual(len(recorder.seen), 1)


class TheRecordHandsOverNothingMutable(unittest.TestCase):
    """The negative arm by construction: there is no reference to reach."""

    def observation_for(self, raw: bytes) -> receiver_reliance.DecisionObservation:
        recorder = Recorder()
        receiver_reliance.decide_audited_observed(raw, recorder)
        return recorder.seen[0]

    def test_every_field_is_an_immutable_scalar(self) -> None:
        permitted = (int, str, type(None))
        for label, raw in WIRE:
            with self.subTest(case=label):
                observation = self.observation_for(raw)
                for field, value in observation._asdict().items():
                    self.assertIsInstance(value, permitted, field)
                    self.assertNotIsInstance(value, (bytes, bytearray, dict, list))

    def test_the_record_rejects_mutation(self) -> None:
        observation = self.observation_for(
            (REPO / "examples" / "handoff-clean.json").read_bytes()
        )
        with self.assertRaises(AttributeError):
            observation.decision_class = "VALID"  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            object.__setattr__(observation, "exit_code", 0)
        with self.assertRaises(TypeError):
            observation[0] = "VALID"  # type: ignore[index]

    def test_a_mutating_observer_cannot_move_a_byte(self) -> None:
        def mutator(observation: object) -> None:
            observation.decision_class = "VALID"  # type: ignore[attr-defined]
            observation.exit_code = 0  # type: ignore[attr-defined]

        for label, raw in WIRE:
            with self.subTest(case=label):
                expected = JCS(receiver_reliance.decide_audited(raw))
                self.assertEqual(
                    expected, JCS(receiver_reliance.decide_audited_observed(raw, mutator))
                )
                self.assertEqual(
                    rr_batch.response_bytes(raw),
                    receiver_reliance.response_bytes_observed(raw, mutator),
                )

    def test_a_replacing_observer_is_ignored(self) -> None:
        """The refuted shape: an observer that returns a decision of its own."""
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        forged = receiver_reliance.decide_audited(raw)
        forged["host_trace_id"] = "trace-1"
        forged["audited_behavior_class"] = "VALID"

        def replacer(_observation: object) -> dict:
            return forged

        expected = receiver_reliance.decide_audited(raw)
        observed = receiver_reliance.decide_audited_observed(raw, replacer)
        self.assertEqual(JCS(expected), JCS(observed))
        self.assertNotIn("host_trace_id", observed)
        self.assertEqual(
            rr_batch.response_bytes(raw),
            receiver_reliance.response_bytes_observed(raw, replacer),
        )


class ObserverFailureCannotReachTheCaller(unittest.TestCase):
    """Disposition of an observer's exceptions: discarded, of any class."""

    RAISERS = (
        ("MemoryError", MemoryError("emitter oom")),
        ("RuntimeError", RuntimeError("observer bug")),
        ("KeyError", KeyError("missing")),
        ("KeyboardInterrupt", KeyboardInterrupt()),
        ("SystemExit", SystemExit(3)),
        ("GeneratorExit", GeneratorExit()),
        ("BaseException", BaseException("bare")),
    )

    def test_no_exception_class_changes_the_result(self) -> None:
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        expected_envelope = JCS(receiver_reliance.decide_audited(raw))
        expected_line = rr_batch.response_bytes(raw)
        for name, error in self.RAISERS:
            def raiser(_observation: object, error: BaseException = error) -> None:
                raise error

            with self.subTest(raises=name):
                self.assertEqual(
                    expected_envelope,
                    JCS(receiver_reliance.decide_audited_observed(raw, raiser)),
                )
                self.assertEqual(
                    expected_line,
                    receiver_reliance.response_bytes_observed(raw, raiser),
                )

    def test_a_raising_observer_over_every_error_surface(self) -> None:
        def raiser(_observation: object) -> None:
            raise MemoryError("emitter oom")

        for label, raw in WIRE:
            if not label.startswith(("error:", "fuzz:")):
                continue
            with self.subTest(case=label):
                self.assertEqual(
                    JCS(receiver_reliance.decide_audited(raw)),
                    JCS(receiver_reliance.decide_audited_observed(raw, raiser)),
                )

    def test_a_non_callable_observer_still_returns_the_decision(self) -> None:
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        for not_callable in (object(), "observer", 7, {"observe": True}):
            with self.subTest(observer=type(not_callable).__name__):
                self.assertEqual(
                    JCS(receiver_reliance.decide_audited(raw)),
                    JCS(receiver_reliance.decide_audited_observed(raw, not_callable)),
                )

    def test_engine_exceptions_are_not_caught(self) -> None:
        """The wrapper suppresses the observer, never the engine."""
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        original = receiver_reliance.decide_audited
        sentinel = RuntimeError("engine failure")

        def exploding(_request: object) -> dict:
            raise sentinel

        receiver_reliance.decide_audited = exploding
        try:
            with self.assertRaises(RuntimeError) as caught:
                receiver_reliance.decide_audited_observed(raw, Recorder())
            self.assertIs(caught.exception, sentinel)
            with self.assertRaises(RuntimeError):
                receiver_reliance.response_bytes_observed(raw, Recorder())
            with self.assertRaises(RuntimeError):
                receiver_reliance.decide_audited_observed(raw)
        finally:
            receiver_reliance.decide_audited = original


class NotificationFollowsTheBytes(unittest.TestCase):
    """Ordering, proven by what the record could not otherwise contain."""

    def test_the_record_reports_the_response_length_it_was_serialized_from(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                recorder = Recorder()
                line = receiver_reliance.response_bytes_observed(raw, recorder)
                observation = recorder.seen[0]
                self.assertEqual(observation.response_bytes, len(line))
                self.assertIsNotNone(observation.serialize_ns)

    def test_the_envelope_route_serializes_nothing(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                recorder = Recorder()
                receiver_reliance.decide_audited_observed(raw, recorder)
                self.assertIsNone(recorder.seen[0].response_bytes)
                self.assertIsNone(recorder.seen[0].serialize_ns)

    def test_the_record_reports_the_decision_it_followed(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                recorder = Recorder()
                envelope = receiver_reliance.decide_audited_observed(raw, recorder)
                observation = recorder.seen[0]
                self.assertEqual(
                    observation.decision_class, envelope["audited_behavior_class"]
                )
                self.assertEqual(observation.exit_code, envelope["exit_code"])
                self.assertEqual(observation.request_bytes, len(raw))

    def test_an_object_request_reports_no_wire_length(self) -> None:
        for label, request in OBJECTS:
            with self.subTest(case=label):
                recorder = Recorder()
                receiver_reliance.decide_audited_observed(
                    copy.deepcopy(request), recorder
                )
                self.assertIsNone(recorder.seen[0].request_bytes)

    def test_spans_are_non_negative_and_bounded_by_the_whole(self) -> None:
        for label, raw in WIRE:
            with self.subTest(case=label):
                recorder = Recorder()
                receiver_reliance.response_bytes_observed(raw, recorder)
                observation = recorder.seen[0]
                spans = (
                    observation.ingest_ns,
                    observation.decide_ns,
                    observation.serialize_ns,
                )
                for span in spans:
                    self.assertGreaterEqual(span, 0)
                self.assertGreaterEqual(observation.wall_ns, sum(spans))
                self.assertGreaterEqual(observation.cpu_ns, 0)


class TheDisclosedLimits(unittest.TestCase):
    """What the seam does NOT prevent, pinned so nobody reads it as more."""

    def test_a_frame_walking_observer_can_still_reach_the_envelope(self) -> None:
        """Not a sandbox. An in-process observer keeps the caller's authority.

        This test must SUCCEED at mutating the envelope. The seam's guarantee
        is that it hands over no reference and takes no authority -- not that
        Python withholds authority the observer already had. A host that can
        pass an observer can equally rebind `decide_audited`, which the engine
        exception test above does deliberately. An untrusted observer belongs
        in another process.
        """

        def frame_walker(_observation: object) -> None:
            frame = sys._getframe(1)
            while frame is not None:
                envelope = frame.f_locals.get("envelope")
                if isinstance(envelope, dict) and "audit_sha256" in envelope:
                    envelope["host_trace_id"] = "reached"
                    return
                frame = frame.f_back

        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        reached = receiver_reliance.decide_audited_observed(raw, frame_walker)
        self.assertEqual(reached.get("host_trace_id"), "reached")
        self.assertFalse(receiver_reliance.verify_audit_seal(reached))

    def test_one_frame_up_from_an_observer_holds_only_the_record(self) -> None:
        """The reference the seam does control: the notifying frame is bare."""

        captured: dict = {}

        def peeker(_observation: object) -> None:
            captured.update(sys._getframe(1).f_locals)

        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        receiver_reliance.decide_audited_observed(raw, peeker)
        self.assertNotIn("envelope", captured)
        self.assertIn("observation", captured)
        for name, value in captured.items():
            if name == "observer":
                continue
            self.assertNotIsInstance(value, (dict, bytes, bytearray, list), name)
            for member in value if isinstance(value, tuple) else ():
                self.assertIsInstance(member, (int, str, type(None)), name)

    def test_a_blocking_observer_delays_the_caller(self) -> None:
        """Latency is the host's to bound; nothing here bounds it."""

        def slow(_observation: object) -> None:
            time.sleep(0.05)

        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        start = time.perf_counter_ns()
        receiver_reliance.decide_audited_observed(raw, slow)
        self.assertGreater(time.perf_counter_ns() - start, 50_000_000)

    def test_the_envelope_does_not_record_that_anyone_watched(self) -> None:
        raw = (REPO / "examples" / "handoff-clean.json").read_bytes()
        observed = receiver_reliance.decide_audited_observed(raw, Recorder())
        unobserved = receiver_reliance.decide_audited(raw)
        self.assertEqual(sorted(observed), sorted(unobserved))
        self.assertEqual(observed["audit_sha256"], unobserved["audit_sha256"])
        self.assertNotIn("observer", json.dumps(observed).lower())


class TheSupportedSurface(unittest.TestCase):
    def test_the_names_are_exported(self) -> None:
        for name in (
            "decide_audited_observed",
            "response_bytes_observed",
            "DecisionObservation",
        ):
            self.assertIn(name, receiver_reliance.__all__)
            self.assertTrue(hasattr(receiver_reliance, name))

    def test_the_record_fields_are_the_declared_ones(self) -> None:
        self.assertEqual(
            receiver_reliance.DecisionObservation._fields,
            (
                "decision_class",
                "exit_code",
                "request_bytes",
                "response_bytes",
                "ingest_ns",
                "decide_ns",
                "serialize_ns",
                "wall_ns",
                "cpu_ns",
            ),
        )

    def test_the_decision_class_is_the_closed_six_value_set(self) -> None:
        closed = {
            "VALID",
            "MALFORMED_OR_BOUNDARY",
            "BINDING_OR_CONFLICT",
            "OMISSION_OR_INCOMPLETE",
            "AUDIT_INCOMPLETE",
            "PROTOCOL_ERROR",
        }
        observed = set()
        for _label, raw in WIRE:
            recorder = Recorder()
            receiver_reliance.decide_audited_observed(raw, recorder)
            observed.add(recorder.seen[0].decision_class)
        self.assertTrue(observed <= closed, observed - closed)
        self.assertGreaterEqual(len(observed), 2)


def _effective_cpu_tick_ns(samples: int = 200_000) -> int:
    """Measure this host's real process-CPU granularity rather than declare it.

    `time.get_clock_info("process_time").resolution` reports 100 ns on
    Windows/CPython 3.12 while the clock in fact advances once per 15,625,000
    ns. A field documented against the declared number would be documented
    against a number that is wrong on the host this artifact is built on, so
    the suite measures it wherever it runs and prints the result.
    """
    seen = set()
    process_time = time.process_time_ns
    for _ in range(samples):
        seen.add(process_time())
    ordered = sorted(seen)
    deltas = [later - earlier for earlier, later in zip(ordered, ordered[1:])]
    return min(deltas) if deltas else 0


if __name__ == "__main__":
    print(
        "observe: wire_cases=%d object_cases=%d "
        "declared_cpu_resolution_ns=%d effective_cpu_tick_ns=%d"
        % (
            len(WIRE),
            len(OBJECTS),
            int(round(time.get_clock_info("process_time").resolution * 1_000_000_000)),
            _effective_cpu_tick_ns(),
        )
    )
    unittest.main(verbosity=2)
