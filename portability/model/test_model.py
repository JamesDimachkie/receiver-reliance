"""Focused checks for finite model M and its accepted historical closures."""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import unittest
from collections import defaultdict
from dataclasses import asdict

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from portability.model.closures import RAW_CLOSURES
from portability.model.domain import BASE_ALPHABET, MAX_DEPTH, TOKENS
from portability.model.parser_model import (
    INITIAL_STATE,
    pack_state,
    replay_tokens,
    token_label_is_admissible,
    transition,
    unpack_state,
)
from portability.model.parser_model import explore_parser
from portability.model.reference_checker import explore_parser_retained
from portability.model.receipts.independent_full_refuter import independent_parser
from portability.model.transport_model import (
    RECORD_SHAPES,
    explore_scheduler,
    materialize_r3_schedule,
    partition_receipt,
)

FULL = "--full" in sys.argv
if FULL:
    sys.argv.remove("--full")

EXPECTED_PARSER = {
    "quotient_states": 37432306,
    "quotient_transitions": 294190481,
    "terminal_transitions": 68157505,
    "symbolic_terminal_traces": 34269567869926335890219352245333204780922262,
    "quotient_material_sha256": "2C233FBF0DD68F1BA3C73BFB9F344473B9EA265CF43D770934A76D586329DD2A",
}


def token(symbol: str, variant: str = "plain"):
    return next(item for item in TOKENS if item.symbol == symbol and item.variant == variant)


class ModelStructureTests(unittest.TestCase):
    def test_frozen_alphabet(self) -> None:
        self.assertEqual(len(BASE_ALPHABET), 12)
        self.assertEqual(len(TOKENS), 14)
        self.assertEqual({item.variant for item in TOKENS if item.symbol == "KEY_B"}, {"plain", "non_nfc", "lone_surrogate"})

    def test_terminal_representatives(self) -> None:
        self.assertEqual(replay_tokens([token("INT_1")], True), "PARSE_OK")
        self.assertEqual(replay_tokens([token("RBRACE")], True), "ERR_JSON")
        self.assertEqual(replay_tokens([token("GARBAGE_FF")], True), "ERR_UTF8")
        self.assertEqual(replay_tokens([token("KEY_B", "non_nfc")], True), "ERR_NFC")
        self.assertEqual(replay_tokens([token("KEY_B", "lone_surrogate")], True), "ERR_JSON")
        duplicate = [
            token("LBRACE"), token("KEY_A"), token("COLON"), token("INT_1"),
            token("COMMA"), token("KEY_A_REPEAT"),
        ]
        self.assertEqual(replay_tokens(duplicate, False), "ERR_DUPLICATE_KEY")

    def test_key_b_variants_have_distinct_decoded_identities(self) -> None:
        prefix = [
            token("LBRACE"), token("KEY_B"), token("COLON"), token("INT_1"),
            token("COMMA"), token("KEY_B", "non_nfc"),
        ]
        self.assertEqual(replay_tokens(prefix, False), "ERR_JSON")
        self.assertEqual(
            replay_tokens(prefix + [token("COLON"), token("INT_1"), token("RBRACE")], True),
            "ERR_NFC",
        )
        reversed_prefix = [
            token("LBRACE"), token("KEY_B", "non_nfc"), token("COLON"), token("INT_1"),
            token("COMMA"), token("KEY_B"),
        ]
        self.assertEqual(replay_tokens(reversed_prefix, False), "ERR_JSON")

    def test_key_b_identical_and_lone_surrogate_neighbors(self) -> None:
        for variant in ("non_nfc", "lone_surrogate"):
            repeated = [
                token("LBRACE"), token("KEY_B", variant), token("COLON"), token("INT_1"),
                token("COMMA"), token("KEY_B", variant),
            ]
            self.assertEqual(replay_tokens(repeated, False), "ERR_DUPLICATE_KEY")

        for first, second in (("plain", "lone_surrogate"), ("lone_surrogate", "plain")):
            distinct = [
                token("LBRACE"), token("KEY_B", first), token("COLON"), token("INT_1"),
                token("COMMA"), token("KEY_B", second),
            ]
            self.assertEqual(replay_tokens(distinct, False), "ERR_JSON")

    def test_key_a_raw_alias_has_one_contextual_label(self) -> None:
        key_a = token("KEY_A")
        repeat_a = token("KEY_A_REPEAT")
        raw = key_a.raw + b"\n"
        self.assertEqual(key_a.raw, repeat_a.raw)
        self.assertEqual(raw.hex(), "2261220a")
        self.assertEqual(
            hashlib.sha256(raw).hexdigest().upper(),
            "EE195DB0CD14979ECE92E4AC42D91FEF87D1EE254F8DF170907CD674DAB12D44",
        )
        self.assertTrue(token_label_is_admissible(INITIAL_STATE, key_a))
        self.assertFalse(token_label_is_admissible(INITIAL_STATE, repeat_a))
        self.assertEqual(replay_tokens([key_a], True), "PARSE_OK")
        with self.assertRaisesRegex(ValueError, "outside M"):
            replay_tokens([repeat_a], True)

        state = INITIAL_STATE
        for item in (
            token("LBRACE"), token("KEY_A"), token("COLON"),
            token("INT_1"), token("COMMA"),
        ):
            state = transition(state, item)
            self.assertIsNotNone(state)
        assert state is not None
        self.assertFalse(token_label_is_admissible(state, key_a))
        self.assertTrue(token_label_is_admissible(state, repeat_a))
        self.assertIsNone(transition(state, key_a))
        self.assertIsNotNone(transition(state, repeat_a))
        self.assertEqual(
            replay_tokens((
                token("LBRACE"), token("KEY_A"), token("COLON"),
                token("INT_1"), token("COMMA"), repeat_a,
            ), False),
            "ERR_DUPLICATE_KEY",
        )

    def test_all_frozen_raw_aliases_are_declared(self) -> None:
        by_raw = defaultdict(list)
        for item in TOKENS:
            by_raw[item.raw].append(item.label)
        aliases = {
            raw.hex(): tuple(labels)
            for raw, labels in by_raw.items()
            if len(labels) > 1
        }
        self.assertEqual(aliases, {"226122": ("KEY_A", "KEY_A_REPEAT")})

    def test_bounded_reachable_states_have_one_label_per_physical_alias(self) -> None:
        bound = 16
        by_raw = defaultdict(list)
        for item in TOKENS:
            if item.symbol != "LF":
                by_raw[item.raw].append(item)
        alias_groups = [items for items in by_raw.values() if len(items) > 1]
        self.assertEqual(len(alias_groups), 1)

        layers = [set() for _ in range(bound + 1)]
        layers[0].add(INITIAL_STATE)
        seen = set()
        checked_alias_contexts = 0
        for length, states in enumerate(layers):
            for state in states:
                seen.add(state)
                for items in by_raw.values():
                    raw = items[0].raw
                    if length + len(raw) > bound:
                        continue
                    admitted = [item for item in items if token_label_is_admissible(state, item)]
                    if len(items) > 1:
                        checked_alias_contexts += 1
                        self.assertEqual(len(admitted), 1, (state, [item.label for item in admitted]))
                        for rejected in set(items) - set(admitted):
                            self.assertIsNone(transition(state, rejected), (state, rejected.label))
                    for item in admitted:
                        nxt = transition(state, item)
                        if nxt is not None:
                            layers[nxt.byte_length].add(nxt)
        self.assertGreater(len(seen), 1000)
        self.assertGreater(checked_alias_contexts, 1000)

    def test_depth_and_duplicate_frontiers(self) -> None:
        state = INITIAL_STATE
        state = transition(state, token("LBRACE"))
        self.assertIsNotNone(state)
        for _ in range(MAX_DEPTH - 1):
            for item in (token("KEY_A"), token("COLON"), token("LBRACE")):
                assert state is not None
                state = transition(state, item)
                self.assertIsNotNone(state)
        for item in (token("KEY_A"), token("COLON")):
            assert state is not None
            state = transition(state, item)
            self.assertIsNotNone(state)
        assert state is not None
        self.assertIsNone(transition(state, token("LBRACE")))

        state = INITIAL_STATE
        sequence = [token("LBRACE"), token("KEY_A"), token("COLON"), token("INT_1")]
        for item in sequence:
            state = transition(state, item)
            assert state is not None
        for _ in range(3):
            for item in (token("COMMA"), token("KEY_A_REPEAT"), token("COLON"), token("INT_1")):
                state = transition(state, item)
                assert state is not None
        state = transition(state, token("COMMA")); assert state is not None
        self.assertIsNone(transition(state, token("KEY_A_REPEAT")))

    def test_streaming_explorer_matches_retained_reference(self) -> None:
        for bound in (0, 1, 2, 4, 7, 10, 13, 16):
            with self.subTest(N=bound):
                self.assertEqual(
                    asdict(explore_parser(bound)),
                    asdict(explore_parser_retained(bound)),
                )
        independent, alias_edges = independent_parser(16)
        streaming = asdict(explore_parser(16))
        self.assertEqual(
            independent,
            {
                "quotient_states": streaming["states"],
                "quotient_transitions": streaming["transitions"],
                "terminal_transitions": streaming["terminal_transitions"],
                "symbolic_terminal_traces": streaming["symbolic_terminal_traces"],
                "excluded_frontier_edges": streaming["excluded_edges"],
                "excluded_trace_prefixes": streaming["excluded_trace_prefixes"],
                "terminal_classes": streaming["terminal_classes"],
                "representative_hex": streaming["representative_hex"],
                "quotient_material_sha256": streaming[
                    "quotient_material_sha256"
                ],
            },
        )
        self.assertGreater(alias_edges, 1000)

    def test_packed_state_is_lossless_over_reachable_prefixes(self) -> None:
        seen = {INITIAL_STATE}
        frontier = {INITIAL_STATE}
        for _ in range(10):
            next_frontier = set()
            for state in frontier:
                self.assertEqual(unpack_state(pack_state(state), state.byte_length), state)
                for item in TOKENS:
                    if item.symbol == "LF":
                        continue
                    nxt = transition(state, item)
                    if nxt is not None and nxt not in seen:
                        seen.add(nxt)
                        next_frontier.add(nxt)
            frontier = next_frontier
        packed = {(state.byte_length, pack_state(state)) for state in seen}
        self.assertEqual(len(packed), len(seen))

    def test_complete_scheduler_counts(self) -> None:
        expected = {
            (1, 1): (14, 16, 8, 24),
            (1, 2): (27, 32, 64, 576),
            (2, 1): (196, 448, 38589788, 347308092),
            (2, 2): (729, 1728, 7021875387712248, 568771906404692088),
        }
        for key, counts in expected.items():
            got = explore_scheduler(*key)
            self.assertEqual((got.states, got.transitions, got.concrete_schedule_traces, got.terminal_sequence_schedule_cases), counts)
            self.assertEqual(got.terminal_states, 1)

    def test_partitions_are_complete_combinatorial_counts(self) -> None:
        receipt = partition_receipt()
        for family in ("request_partitions_C", "response_partitions_W"):
            for item in receipt[family].values():
                n = item["interior_points"]
                self.assertEqual(item["sets_size_le_2"], 1 + n + n * (n - 1) // 2)
                self.assertEqual(item["total"], item["sets_size_le_2"] + item["boundary_sets_size_3"])
        self.assertEqual(RECORD_SHAPES["ERR_JSON"].response_bytes, 812)
        self.assertEqual(RECORD_SHAPES["VALID_CORE"].request_bytes, 2466)

    def test_committed_r3_recipes_terminate_deterministically(self) -> None:
        data = json.loads((HERE / "r3_schedules.json").read_text(encoding="utf-8"))
        first = [materialize_r3_schedule(spec, data["seed"]) for spec in data["schedules"]]
        second = [materialize_r3_schedule(spec, data["seed"]) for spec in data["schedules"]]
        self.assertEqual(first, second)
        self.assertTrue(all(item["terminal"] and item["steps"] > 0 for item in first))


class AcceptedClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        grounded = REPO / "grounded-0_4"
        sys.path.insert(0, str(grounded))
        import rr_batch
        cls.rr_batch = rr_batch

    def test_ri1_through_ri4_exact_raw_closures(self) -> None:
        b1 = self.rr_batch.rr_api.b1
        runner = self.rr_batch.rr_api.pcb_runner
        for closure in RAW_CLOSURES:
            raw = bytes.fromhex(closure.raw_hex)
            self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), closure.raw_sha256, closure.closure_id)
            response, exit_code = runner._execute(raw)
            output = b1.jcs_bytes(response) + b"\n"
            error = response["errors"][0]
            self.assertEqual(exit_code, 2, closure.closure_id)
            self.assertEqual(error["code"], closure.expected_code, closure.closure_id)
            self.assertEqual(error["pointer"], closure.expected_pointer, closure.closure_id)
            self.assertEqual(hashlib.sha256(output).hexdigest().upper(), closure.expected_response_sha256, closure.closure_id)

    def test_ro1_short_write_every_first_response_index(self) -> None:
        response = self.rr_batch.response_bytes(b"\n")
        for first_count in range(1, len(response)):
            class Sink:
                def __init__(self) -> None:
                    self.data = bytearray()
                    self.calls = 0
                    self.flushes = 0

                def write(inner, data):
                    inner.calls += 1
                    count = first_count if inner.calls == 1 else len(data)
                    inner.data.extend(data[:count])
                    return count

                def flush(inner) -> None:
                    inner.flushes += 1

            sink = Sink()
            self.rr_batch._write_all(sink, response)
            self.assertEqual(bytes(sink.data), response, first_count)
            self.assertEqual(sink.flushes, 0, first_count)
            sink.flush()
            self.assertEqual(sink.flushes, 1, first_count)

    def test_ro1_ro2_actual_oversize_drain_alignment(self) -> None:
        maximum = self.rr_batch.rr_api.b1.MAX_INPUT_BYTES

        class Source:
            def __init__(inner) -> None:
                inner.body = maximum
                inner.first_lf = True
                inner.second_lf = True
                inner.digest = hashlib.sha256()
                inner.max_piece = 0

            def readline(inner, size=-1):
                self.assertGreater(size, 0)
                if inner.body:
                    count = min(size, inner.body)
                    piece = b"x" * count
                    inner.body -= count
                    inner.digest.update(piece)
                elif inner.first_lf:
                    inner.first_lf = False
                    piece = b"\n"
                    inner.digest.update(piece)
                elif inner.second_lf:
                    inner.second_lf = False
                    piece = b"\n"
                else:
                    piece = b""
                inner.max_piece = max(inner.max_piece, len(piece))
                return piece

        source = Source()
        sink = io.BytesIO()
        self.assertEqual(self.rr_batch.serve(source, sink), 0)
        expected = self.rr_batch._overlimit_response_bytes(source.digest.hexdigest().upper())
        expected += self.rr_batch.response_bytes(b"\n")
        self.assertEqual(sink.getvalue(), expected)
        self.assertLessEqual(source.max_piece, self.rr_batch._READ_CHUNK_BYTES)


@unittest.skipUnless(FULL, "full N=48 enumeration requested only with --full")
class FullEnumerationTest(unittest.TestCase):
    def test_frozen_full_counts(self) -> None:
        from portability.model.explorer import build_receipt
        parser = build_receipt()["parser"]
        for key, value in EXPECTED_PARSER.items():
            self.assertEqual(parser[key], value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
