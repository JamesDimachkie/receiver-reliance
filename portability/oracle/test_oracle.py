from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys
import unittest

import oracle


REGRESSIONS = (
    (
        "F-ORACLE-001",
        b'{"":0,""',
        "ERR_DUPLICATE_KEY",
        "",
        oracle.ZERO_REQUEST_ID,
        "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01",
    ),
    (
        "F-ORACLE-002",
        b"\n",
        "ERR_EMPTY_INPUT",
        "",
        oracle.ZERO_REQUEST_ID,
        "D157963B0C06176A634B0C3F8F016A05C9EECDEF3F0479EFAD62E62C51156752",
    ),
    (
        "F-ORACLE-003",
        b'{"request_id":"RUN_000000000000000000000001"}',
        "ERR_JSON",
        "",
        "RUN_000000000000000000000001",
        "69BDF8EB18E76E0C31692CC87977FAEB9437AEDB0935D2FBB8F616DC5FDE3B24",
    ),
    (
        "F-ORACLE-004",
        b'{"\\ud800":0,"\\ud800"',
        "ERR_DUPLICATE_KEY",
        "",
        oracle.ZERO_REQUEST_ID,
        "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01",
    ),
    (
        "F-ORACLE-005",
        b'["\\/",-0]\n',
        "ERR_JSON",
        "",
        oracle.ZERO_REQUEST_ID,
        "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2",
    ),
    (
        "F-ORACLE-006",
        b"0\n",
        "ERR_SCHEMA",
        "",
        oracle.ZERO_REQUEST_ID,
        "BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA",
    ),
    (
        "F-ORACLE-007",
        b'"\\u212B"\n',
        "ERR_JSON",
        "",
        oracle.ZERO_REQUEST_ID,
        "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2",
    ),
    (
        "F-ORACLE-008",
        b"{}\n",
        "ERR_SCHEMA",
        "/format_version",
        oracle.ZERO_REQUEST_ID,
        "309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF",
    ),
    (
        "F-ORACLE-009",
        b'{"request_id":"RUN_000000000000000000000004"}\r',
        "ERR_JSON",
        "",
        "RUN_000000000000000000000004",
        "8AED3D8C7B7465A17FC5BF1996FA5FAFE4877D1BAE4B23AB42BD3CA43848EBE1",
    ),
    (
        "F-ORACLE-010",
        b"\xef\xbb\xbf" + b"0" * 16_777_214,
        "ERR_LIMIT",
        "",
        oracle.ZERO_REQUEST_ID,
        "92F0618093EE73A5FFAC007FB12BC6003389B696C549CE2A6EA5FAEB1C4AE8D7",
    ),
    (
        "F-ORACLE-011",
        b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2"}\n',
        "ERR_SCHEMA",
        "",
        oracle.ZERO_REQUEST_ID,
        "BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA",
    ),
    (
        "F-ORACLE-012",
        b"[" * 497 + b"0" + b"]" * 497 + b"\n",
        "ERR_SCHEMA",
        "",
        oracle.ZERO_REQUEST_ID,
        "BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA",
    ),
    (
        "F-ORACLE-013",
        b"1" * 5_000 + b"\n",
        "ERR_NUMBER",
        "",
        oracle.ZERO_REQUEST_ID,
        "DD26E054DFC5F888F85E0C0323249B392F859292D047B923DB6343FF4E66C66F",
    ),
)


class CanonicalizationTests(unittest.TestCase):
    def test_rfc8785_utf16_order(self) -> None:
        value = {
            "\u20ac": "Euro Sign",
            "\r": "Carriage Return",
            "\ufb33": "Hebrew Letter Dalet With Dagesh",
            "1": "One",
            "\U0001f600": "Emoji: Grinning Face",
            "\u0080": "Control",
            "\u00f6": "Latin Small Letter O With Diaeresis",
        }
        encoded = oracle.jcs_dumps(value)
        values_in_order = [
            "Carriage Return",
            "One",
            "Control",
            "Latin Small Letter O With Diaeresis",
            "Euro Sign",
            "Emoji: Grinning Face",
            "Hebrew Letter Dalet With Dagesh",
        ]
        positions = [encoded.index(oracle.jcs_dumps(item)) for item in values_in_order]
        self.assertEqual(positions, sorted(positions))

    def test_string_escaping_is_lowercase_and_minimal(self) -> None:
        self.assertEqual(oracle.jcs_dumps("\x0f\n/\\\""), '"\\u000f\\n/\\\\\\\""')

    def test_surrogate_pair_escape_matches_scalar(self) -> None:
        parsed = oracle.StrictParser('"\\ud83d\\ude00"').parse()
        self.assertEqual(parsed, "\U0001f600")
        self.assertEqual(oracle.jcs_dumps(parsed), '"\U0001f600"')

    def test_lone_surrogate_is_not_jcs(self) -> None:
        value = oracle.StrictParser('"\\ud800"').parse()
        with self.assertRaises(oracle.JCSFault):
            oracle.jcs_dumps(value)

    def test_integer_jcs_is_independent_of_host_decimal_cap(self) -> None:
        huge_lexeme = "1" * 5_000
        self.assertEqual(oracle.jcs_dumps(oracle.JNumber(huge_lexeme)), huge_lexeme)
        self.assertEqual(oracle.jcs_dumps(oracle.SAFE_INTEGER_MAX), "9007199254740991")
        self.assertEqual(oracle.jcs_dumps(-oracle.SAFE_INTEGER_MAX), "-9007199254740991")
        with self.assertRaises(oracle.JCSFault):
            oracle.jcs_dumps(10**5_000)


class RawClassifierTests(unittest.TestCase):
    def test_all_minimized_regressions(self) -> None:
        for name, raw, code, pointer, request_id, expected_hash in REGRESSIONS:
            with self.subTest(name=name):
                classification = oracle.classify_record(raw)
                self.assertEqual(classification.code, code)
                self.assertEqual(classification.pointer, pointer)
                self.assertEqual(classification.request_id, request_id)
                response = oracle.error_response(code, pointer, request_id)
                self.assertEqual(hashlib.sha256(response).hexdigest().upper(), expected_hash)

    def test_array_root_schema(self) -> None:
        result = oracle.classify_record(b"[]\n")
        self.assertEqual((result.code, result.pointer), ("ERR_SCHEMA", ""))

    def test_missing_and_unknown_format_route_to_format_version(self) -> None:
        for raw in (b"{}\n", b'{"format_version":"UNKNOWN"}\n'):
            with self.subTest(raw=raw):
                result = oracle.classify_record(raw)
                self.assertEqual((result.code, result.pointer), ("ERR_SCHEMA", "/format_version"))

    def test_declared_format_missing_required_members_route_to_root(self) -> None:
        for format_version, required in oracle.DECLARED_FORMATS.items():
            complete = {name: 0 for name in required}
            complete["format_version"] = format_version
            complete["request_id"] = "RUN_00000000000000000000000A"
            removable = tuple(name for name in required if name != "format_version")
            for width in range(1, len(removable) + 1):
                for absent in itertools.combinations(removable, width):
                    value = dict(complete)
                    for name in absent:
                        del value[name]
                    raw = oracle.jcs_bytes(value) + b"\n"
                    result = oracle.classify_record(raw)
                    with self.subTest(format_version=format_version, absent=absent):
                        self.assertEqual((result.code, result.pointer), ("ERR_SCHEMA", ""))

    def test_present_invalid_member_uses_member_pointer(self) -> None:
        required = oracle.DECLARED_FORMATS["B1-SEMANTIC-DECISION-REQUEST-0.2"]
        value = {name: 0 for name in required}
        value["format_version"] = "B1-SEMANTIC-DECISION-REQUEST-0.2"
        value["request_id"] = "INVALID"
        result = oracle.classify_record(oracle.jcs_bytes(value) + b"\n")
        self.assertEqual((result.code, result.pointer), ("ERR_SCHEMA", "/request_id"))

    def test_required_root_error_precedes_member_limit_neighbor(self) -> None:
        def raw_with_members(total: int) -> bytes:
            extras = [f'"a{index:06d}":0'.encode("ascii") for index in range(total - 1)]
            declared = b'"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2"'
            return b"{" + b",".join((*extras, declared)) + b"}\n"

        at_limit = oracle.classify_record(raw_with_members(oracle.MAX_MEMBERS_OR_ITEMS))
        over_limit = oracle.classify_record(raw_with_members(oracle.MAX_MEMBERS_OR_ITEMS + 1))
        self.assertEqual((at_limit.code, at_limit.pointer, at_limit.limit_hit), ("ERR_SCHEMA", "", False))
        self.assertEqual((over_limit.code, over_limit.pointer, over_limit.limit_hit), ("ERR_SCHEMA", "", True))

    def test_json_canonicality_precedes_number_profile(self) -> None:
        self.assertEqual(oracle.classify_record(b"[-0]\n").code, "ERR_NUMBER")
        self.assertEqual(oracle.classify_record(b'["\\/",-0]\n').code, "ERR_JSON")

    def test_json_canonicality_precedes_nfc(self) -> None:
        self.assertEqual(oracle.classify_record(b'"\\u212B"\n').code, "ERR_JSON")
        self.assertEqual(oracle.classify_record('"\u212b"\n'.encode("utf-8")).code, "ERR_NFC")

    def test_utf8_and_bom_precedence(self) -> None:
        self.assertEqual(oracle.classify_record(b"\xff\n").code, "ERR_UTF8")
        self.assertEqual(oracle.classify_record(b"\xef\xbb\xbf{}\n").code, "ERR_BOM")

    def test_input_size_guard_precedes_decode_and_framing(self) -> None:
        oversize_bom = REGRESSIONS[9][1]
        result = oracle.classify_record(oversize_bom)
        self.assertEqual((result.code, result.pointer, result.limit_hit), ("ERR_LIMIT", "", True))

        at_limit_bom = b"\xef\xbb\xbf" + b"0" * (oracle.MAX_INPUT_BYTES - 3)
        self.assertEqual(len(at_limit_bom), oracle.MAX_INPUT_BYTES)
        self.assertEqual(oracle.classify_record(at_limit_bom).code, "ERR_BOM")
        self.assertEqual(oracle.classify_record(b"\xef\xbb\xbf{}\n").code, "ERR_BOM")

        oversize_invalid_utf8 = b"\xff" + b"0" * oracle.MAX_INPUT_BYTES
        at_limit_invalid_utf8 = b"\xff" + b"0" * (oracle.MAX_INPUT_BYTES - 1)
        self.assertEqual(oracle.classify_record(oversize_invalid_utf8).code, "ERR_LIMIT")
        self.assertEqual(oracle.classify_record(at_limit_invalid_utf8).code, "ERR_UTF8")

        oversize_unframed = b"0" * (oracle.MAX_INPUT_BYTES + 1)
        at_limit_unframed = b"[]" + b" " * (oracle.MAX_INPUT_BYTES - 2)
        self.assertEqual(oracle.classify_record(oversize_unframed).code, "ERR_LIMIT")
        self.assertEqual(oracle.classify_record(at_limit_unframed).code, "ERR_JSON")

    def test_surrounding_json_whitespace_retains_request_id(self) -> None:
        raw = b'{"request_id":"RUN_000000000000000000000004"}\r'
        result = oracle.classify_record(raw)
        self.assertEqual(result.request_id, "RUN_000000000000000000000004")
        self.assertEqual(result.code, "ERR_JSON")

    def test_deep_nonobject_roots_are_recursion_independent(self) -> None:
        expected_hash = "BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA"
        original_limit = sys.getrecursionlimit()
        try:
            # All exercised depths exceed this host recursion limit; the raw
            # ABI result must nevertheless be a contract result, not a Python
            # call-stack artifact.
            sys.setrecursionlimit(200)
            for depth in (496, 497, 1_024, 4_096):
                raw = b"[" * depth + b"0" + b"]" * depth + b"\n"
                result = oracle.classify_record(raw)
                response = oracle.error_response(result.code or "ERR_INTERNAL", result.pointer, result.request_id)
                with self.subTest(depth=depth):
                    self.assertEqual((result.code, result.pointer, result.limit_hit), ("ERR_SCHEMA", "", True))
                    self.assertEqual(hashlib.sha256(response).hexdigest().upper(), expected_hash)
        finally:
            sys.setrecursionlimit(original_limit)

    def test_deep_root_finding_hash_and_depth_neighbor(self) -> None:
        shallow = b"[" * 496 + b"0" + b"]" * 496 + b"\n"
        witness = next(raw for name, raw, *_ in REGRESSIONS if name == "F-ORACLE-012")
        self.assertEqual(len(witness), 996)
        self.assertEqual(
            hashlib.sha256(witness).hexdigest().upper(),
            "7CF05E162193A98C7ACB5104CBF719CC3D9301F1494CE4CE07E13128E7D67B3E",
        )
        self.assertEqual((oracle.classify_record(shallow).code, oracle.classify_record(witness).code), ("ERR_SCHEMA", "ERR_SCHEMA"))

    def test_deep_malformed_and_lower_precedence_neighbors(self) -> None:
        depth = 497
        malformed = b"[" * depth + b"0" + b"]" * (depth - 1) + b"\n"
        noncanonical = b"[" * depth + b" 0" + b"]" * depth + b"\n"
        duplicate = b"[" * depth + b'{"a":0,"a"' + b"]" * depth + b"\n"
        bad_number = b"[" * depth + b"-0" + b"]" * depth + b"\n"
        non_nfc = b"[" * depth + '"\u212b"'.encode("utf-8") + b"]" * depth + b"\n"
        self.assertEqual(oracle.classify_record(malformed).code, "ERR_JSON")
        self.assertEqual(oracle.classify_record(noncanonical).code, "ERR_JSON")
        self.assertEqual(oracle.classify_record(duplicate).code, "ERR_DUPLICATE_KEY")
        self.assertEqual(oracle.classify_record(bad_number).code, "ERR_NUMBER")
        self.assertEqual(oracle.classify_record(non_nfc).code, "ERR_NFC")

    def test_nesting_limit_neighbor_is_adjudicated_after_schema(self) -> None:
        required = oracle.DECLARED_FORMATS["B1-SEMANTIC-DECISION-REQUEST-0.2"]

        def complete_request(array_depth: int) -> bytes:
            nested: object = 0
            for _ in range(array_depth):
                nested = [nested]
            value = {name: 0 for name in required}
            value["decision_input"] = nested
            value["format_version"] = "B1-SEMANTIC-DECISION-REQUEST-0.2"
            value["request_id"] = "RUN_00000000000000000000000A"
            return oracle.jcs_bytes(value) + b"\n"

        at_limit = oracle.classify_record(complete_request(oracle.MAX_NESTING - 1))
        over_limit = oracle.classify_record(complete_request(oracle.MAX_NESTING))
        self.assertEqual((at_limit.code, at_limit.limit_hit), (None, False))
        self.assertEqual((over_limit.code, over_limit.limit_hit), ("ERR_LIMIT", True))

    def test_decimal_conversion_cap_boundary_and_finding_hashes(self) -> None:
        at_host_cap = b"1" * 4_300
        over_host_cap = b"1" * 4_301
        witness = next(raw for name, raw, *_ in REGRESSIONS if name == "F-ORACLE-013")
        self.assertEqual(
            hashlib.sha256(over_host_cap).hexdigest().upper(),
            "8AFECECF38E8946DF9CFF0BB388B1F2909AAA9F595A91450A1C0D69407C3EC36",
        )
        self.assertEqual(
            hashlib.sha256(witness).hexdigest().upper(),
            "3D980BE60158306FF0525F4803AC3F409B2967720FA56D6B006B75B26EEFA8ED",
        )
        self.assertEqual(oracle.classify_record(at_host_cap).code, "ERR_JSON")
        self.assertEqual(oracle.classify_record(over_host_cap).code, "ERR_JSON")
        result = oracle.classify_record(witness)
        self.assertEqual((result.code, result.pointer), ("ERR_NUMBER", ""))
        response = oracle.error_response(result.code or "ERR_INTERNAL", result.pointer, result.request_id)
        self.assertEqual(len(response), 348)
        self.assertEqual(
            hashlib.sha256(response).hexdigest().upper(),
            "DD26E054DFC5F888F85E0C0323249B392F859292D047B923DB6343FF4E66C66F",
        )

    def test_long_integer_profile_and_precedence_neighbors(self) -> None:
        digits = b"1" * 5_000
        cases = (
            (b"-" + digits + b"\n", "ERR_NUMBER", ""),
            (b"+" + digits + b"\n", "ERR_JSON", ""),
            (b"0" + digits + b"\n", "ERR_JSON", ""),
            (digits + b"e0\n", "ERR_NUMBER", ""),
            (digits + b"E+10\n", "ERR_NUMBER", ""),
            (digits + b".0\n", "ERR_NUMBER", ""),
            (b"[" + digits + b"]\n", "ERR_NUMBER", "/0"),
            (b'{"a/b~c":' + digits + b"}\n", "ERR_NUMBER", "/a~1b~0c"),
            (b" " + digits + b"\n", "ERR_JSON", ""),
            (b'{"b":' + digits + b',"a":0}\n', "ERR_JSON", ""),
        )
        for raw, code, pointer in cases:
            with self.subTest(raw_prefix=raw[:24], code=code, pointer=pointer):
                result = oracle.classify_record(raw)
                self.assertEqual((result.code, result.pointer), (code, pointer))

        for lexeme, expected in (
            ("0", True),
            ("-0", False),
            ("9007199254740991", True),
            ("9007199254740992", False),
            ("-9007199254740991", True),
            ("-9007199254740992", False),
            ("01", False),
            ("1e0", False),
            ("1.0", False),
        ):
            with self.subTest(lexeme=lexeme):
                self.assertEqual(oracle.JNumber(lexeme).valid_safe_integer, expected)

    def test_exact_record_limit_long_integer_is_bounded_and_classified(self) -> None:
        raw = b"1" * (oracle.MAX_INPUT_BYTES - 1) + b"\n"
        self.assertEqual(len(raw), oracle.MAX_INPUT_BYTES)
        result = oracle.classify_record(raw)
        self.assertEqual((result.code, result.pointer, result.limit_hit), ("ERR_NUMBER", "", False))

    def test_classification_ignores_altered_host_decimal_cap(self) -> None:
        get_cap = getattr(sys, "get_int_max_str_digits", None)
        set_cap = getattr(sys, "set_int_max_str_digits", None)
        if get_cap is None or set_cap is None:
            self.skipTest("runtime has no configurable decimal conversion cap")
        original = get_cap()
        try:
            for cap in (640, 1_000, 4_300, 0):
                set_cap(cap)
                with self.subTest(cap=cap):
                    self.assertEqual(oracle.classify_record(b"1" * 5_000 + b"\n").code, "ERR_NUMBER")
                    self.assertEqual(oracle.classify_record(b"1" * 4_301).code, "ERR_JSON")
                    self.assertEqual(oracle.jcs_dumps(oracle.JNumber("1" * 5_000)), "1" * 5_000)
        finally:
            set_cap(original)


class FixtureClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = oracle.FixtureOracle()

    def test_exact_four_pack_closure(self) -> None:
        receipt = self.oracle.validation_receipt()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["semantic_records"], 124)
        self.assertEqual(receipt["wrapper_records"], 248)
        self.assertEqual(receipt["total_unique_records"], 372)
        self.assertEqual(
            receipt["fixture_binding_sha256"],
            "78FC43470C9AD4C41932CD38926F8430A004D02FE18E065D3DD6BE59A5A4B80B",
        )

    def test_every_record_reclassifies_as_valid_raw_abi(self) -> None:
        for raw in self.oracle.records:
            with self.subTest(request_sha256=oracle.sha256_upper(raw)):
                self.assertIsNone(oracle.classify_record(raw).code)

    def test_every_expected_record_matches_bound_bytes(self) -> None:
        for raw, expected in self.oracle.records.items():
            with self.subTest(request_sha256=oracle.sha256_upper(raw)):
                self.assertEqual(self.oracle.expected_record(raw), expected)

    def test_response_receipts_are_self_zero_bound(self) -> None:
        for response in self.oracle.records.values():
            parsed = json.loads(response)
            seal_field = "receipt_sha256" if "receipt_sha256" in parsed else "response_sha256"
            self.assertEqual(oracle.self_zero_digest(parsed, seal_field), parsed[seal_field])


class RelationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = oracle.FixtureOracle()
        cls.fixture_records = list(cls.oracle.records)[:3]

    def test_physical_line_equality(self) -> None:
        self.assertTrue(oracle.relation_physical_line_equality(self.fixture_records, self.oracle))

    def test_input_partition_invariance_all_single_splits(self) -> None:
        raw = REGRESSIONS[8][1]
        for split in range(len(raw) + 1):
            with self.subTest(split=split):
                self.assertTrue(oracle.relation_input_partition_invariance(raw, (raw[:split], raw[split:]), self.oracle))

    def test_request_sequence_permutation_invariance(self) -> None:
        self.assertTrue(oracle.relation_request_sequence_permutation(self.fixture_records, self.oracle))

    def test_concurrency_vs_isolated_equality(self) -> None:
        tagged = [(f"caller-{index}", raw) for index, raw in enumerate(self.fixture_records)]
        self.assertTrue(oracle.relation_concurrency_vs_isolated(tagged, self.oracle))

    def test_oversize_drain_next_record_invariance(self) -> None:
        request = {
            "decision_input": {},
            "format_version": "B1-SEMANTIC-DECISION-REQUEST-0.2",
            "inner_input_sha256": "A" * 64,
            "inner_request": {},
            "inner_request_raw_sha256": "B" * 64,
            "obligation_id": "OBL-01",
            "operation_handle": "OPR_207429B87964D694CB8E3915",
            "padding": "x" * oracle.MAX_INPUT_BYTES,
            "request_id": "RUN_000000000000000000000009",
        }
        oversize = oracle.jcs_bytes(request) + b"\n"
        self.assertGreater(len(oversize), oracle.MAX_INPUT_BYTES)
        self.assertTrue(oracle.relation_oversize_drain_next_record(oversize, b"{}\n", self.oracle))
        self.assertTrue(oracle.relation_oversize_drain_next_record(REGRESSIONS[9][1], b"{}\n", self.oracle))

    def test_cross_process_byte_replay(self) -> None:
        raw = REGRESSIONS[8][1]
        command = [sys.executable, "-B", oracle.__file__, "classify-hex", raw.hex()]
        runs = [subprocess.run(command, check=False, capture_output=True) for _ in range(2)]
        self.assertTrue(all(run.returncode == 2 and run.stderr == b"" for run in runs))
        self.assertTrue(oracle.relation_deterministic_replay({"process-a": [runs[0].stdout], "process-b": [runs[1].stdout]}))

    def test_cross_platform_observation_comparator(self) -> None:
        expected = self.oracle.expected_record(self.fixture_records[0])
        observations = {"linux-x64": [expected, expected], "windows-x64": [expected], "macos-arm64": [expected]}
        self.assertTrue(oracle.relation_deterministic_replay(observations))
        self.assertFalse(oracle.relation_deterministic_replay({"a": [expected], "b": [expected + b"x"]}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
