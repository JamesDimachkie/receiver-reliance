"""Regressions for the admission deployment profile. Read-only on the repo.

    python -B deployment/test_admission.py

Three of these classes exist to prove the profile is honest rather than that it
works, and they are the ones to read first:

  * `ProfileIsOffUntilDeclared` — the unset state is the ungated call. Not
    "equivalent to"; the same forwarded object, checked envelope-by-envelope
    across the whole published corpus.
  * `TheProfileRejectsContractLegalRequests` — the cost of turning it on, as a
    test rather than a caveat: a request the frozen engine seals `ok` is
    refused by the profile, and the refusal says so in those words.
  * `TheProxyIsNotACostControl` — the member proxy anti-correlates with cost on
    the pair that matters, re-measured live so the claim cannot go stale.
"""
from __future__ import annotations

import base64
import copy
import gc
import hashlib
import json
import os
import pathlib
import statistics
import subprocess
import sys
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
for _path in (str(REPO), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import receiver_reliance as rr  # noqa: E402

import admission  # noqa: E402

b1 = sys.modules["receiver_reliance._rr_api"].b1

PACKS = (
    (
        "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
        "entries",
        "semantic_request_jcs_lf_base64",
    ),
    (
        "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
        "entries",
        "semantic_request_jcs_lf_base64",
    ),
)
WRAPPERS = (
    "baseline-run/fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json",
    "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
)

ADMISSION_ENV = (
    admission.MAX_REQUEST_BYTES_ENV,
    admission.MAX_STRUCTURAL_MEMBERS_ENV,
)


def corpus() -> list[bytes]:
    out: list[bytes] = []
    for rel, key, field in PACKS:
        pack = json.loads((REPO / rel).read_text(encoding="utf-8"))
        out += [base64.b64decode(entry[field]) for entry in pack[key]]
    for rel in WRAPPERS:
        pack = json.loads((REPO / rel).read_text(encoding="utf-8"))
        for pair in pack["pairs"]:
            for arm in ("b1_arm", "b1_attention_arm"):
                out.append(base64.b64decode(pair[arm]["request_jcs_lf_base64"]))
    return out


CORPUS = corpus()


def accepted_obl_01() -> dict:
    entries = json.loads(
        (REPO / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json").read_text(
            encoding="utf-8"
        )
    )["entries"]
    for entry in entries:
        if entry["obligation_id"] == "OBL-01" and entry["expected_response"]["ok"]:
            return copy.deepcopy(entry["semantic_request"])
    raise AssertionError("no accepted OBL-01 fixture in the published pack")


def contract_legal_maximal_request() -> bytes:
    """An OBL-01 request at the schema's declared caps: legal, large, comma-dense."""
    request = accepted_obl_01()
    request["decision_input"]["facts"]["purpose_ids"] = ["PURPOSE_A"] + ["," * 160] * 255
    request["decision_input"]["facts"]["vocabulary_terms"] = ["," * 160] * 256
    return b1.jcs_bytes(request) + b"\n"


class _NoAmbientProfile(unittest.TestCase):
    """Every case runs with the operator's own environment removed."""

    def setUp(self) -> None:
        self._saved = {name: os.environ.pop(name, None) for name in ADMISSION_ENV}
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class CorpusIsUnchanged(_NoAmbientProfile):
    """The gate must not perturb one byte of any envelope it admits."""

    def test_corpus_size_matches_the_published_denominator(self) -> None:
        self.assertEqual(len(CORPUS), admission.CORPUS_REQUESTS)

    def test_no_corpus_request_is_refused_and_no_envelope_changes(self) -> None:
        bound = admission.AdmissionBound(max_request_bytes=8192)
        refused = differing = 0
        for raw in CORPUS:
            ungated = rr.decide_audited(raw)
            refusal, gated = admission.decide_audited_admitted(raw, bound)
            if refusal is not None:
                refused += 1
                continue
            if b1.jcs_bytes(gated) != b1.jcs_bytes(ungated):
                differing += 1
        self.assertEqual((refused, differing), (0, 0))

    def test_corpus_max_request_bytes_is_what_the_module_claims(self) -> None:
        self.assertEqual(max(len(r) for r in CORPUS), admission.CORPUS_MAX_REQUEST_BYTES)


class ProfileIsOffUntilDeclared(_NoAmbientProfile):
    """NEGATIVE ARM: with nothing declared, this module changes nothing.

    `portability/pinned_tools.py`'s law, restated for this surface: an unset
    switch leaves behaviour byte-identical, so no receipt, digest or count in
    the repository moves when the module lands.
    """

    def test_an_undeclared_profile_is_none(self) -> None:
        self.assertIsNone(admission.from_environment())

    def test_unset_is_byte_identical_across_the_whole_corpus(self) -> None:
        differing = 0
        for raw in CORPUS:
            ungated = rr.decide_audited(raw)
            refusal, passthrough = admission.decide_audited_admitted(raw, None)
            self.assertIsNone(refusal)
            if b1.jcs_bytes(passthrough) != b1.jcs_bytes(ungated):
                differing += 1
        self.assertEqual(differing, 0)

    def test_unset_forwards_the_object_route_untouched(self) -> None:
        # The gated route takes wire bytes only. The UNGATED route must keep
        # every input type the supported surface has, including the ones it
        # refuses, or "byte-identical when unset" would be false off the wire.
        request = accepted_obl_01()
        _, passthrough = admission.decide_audited_admitted(request, None)
        self.assertEqual(
            b1.jcs_bytes(passthrough), b1.jcs_bytes(rr.decide_audited(request))
        )
        _, refused = admission.decide_audited_admitted(bytearray(b"{}\n"), None)
        self.assertEqual(refused["audit"]["object_request_error"], "ERR_JSON")

    def test_a_declared_profile_is_read_from_the_environment(self) -> None:
        os.environ[admission.MAX_REQUEST_BYTES_ENV] = "8192"
        os.environ[admission.MAX_STRUCTURAL_MEMBERS_ENV] = "4096"
        bound = admission.from_environment()
        self.assertEqual(
            (bound.max_request_bytes, bound.max_structural_members), (8192, 4096)
        )

    def test_a_malformed_declaration_raises_rather_than_degrading_to_none(self) -> None:
        for value in ("eight thousand", "0", "-1"):
            with self.subTest(value=value):
                os.environ[admission.MAX_REQUEST_BYTES_ENV] = value
                with self.assertRaises(RuntimeError):
                    admission.from_environment()

    def test_the_member_proxy_may_not_be_declared_on_its_own(self) -> None:
        os.environ[admission.MAX_STRUCTURAL_MEMBERS_ENV] = "4096"
        with self.assertRaises(RuntimeError):
            admission.from_environment()


class TheProfileRejectsContractLegalRequests(_NoAmbientProfile):
    """NEGATIVE ARM: the honest property. Turning this on narrows the contract.

    This is the test the profile exists to make un-ignorable. If it ever starts
    passing for the wrong reason — because the request stopped being legal, say
    — the profile's central disclosure has gone stale and the suite says so.
    """

    def setUp(self) -> None:
        super().setUp()
        self.legal = contract_legal_maximal_request()

    def test_the_request_is_one_the_frozen_engine_accepts(self) -> None:
        self.assertIs(rr.decide_audited(self.legal)["sealed_response"]["ok"], True)
        self.assertLess(len(self.legal), admission.CONTRACT_MAX_REQUEST_BYTES)

    def test_the_profile_refuses_it_anyway(self) -> None:
        bound = admission.AdmissionBound(max_request_bytes=8192)
        refusal, envelope = admission.decide_audited_admitted(self.legal, bound)
        self.assertIsNone(envelope)
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal["refused_on"]["bound"], "max_request_bytes")
        self.assertIs(refusal["refused_on"]["exceeds_frozen_ceiling"], False)
        self.assertIn("The published contract may well declare it valid", refusal["statement"])

    def test_the_gap_the_disclosure_quotes_is_the_gap_that_exists(self) -> None:
        # deployment/README.md quotes 771x. A reader must be able to check it.
        self.assertEqual(
            admission.CONTRACT_MAX_REQUEST_BYTES // admission.CORPUS_MAX_REQUEST_BYTES, 771
        )

    def test_no_bound_admits_the_contract_and_bounds_cost(self) -> None:
        # A bound wide enough to admit every contract-legal request is the
        # frozen ceiling itself, which is the situation the profile exists to
        # change. Stated as an assertion so the impossibility is in the suite.
        admitting_everything = admission.AdmissionBound(
            max_request_bytes=admission.CONTRACT_MAX_REQUEST_BYTES
        )
        self.assertIsNone(admitting_everything.admit(self.legal))
        self.assertGreater(
            admission.CONTRACT_MAX_REQUEST_BYTES,
            admission.CORPUS_MAX_REQUEST_BYTES * 700,
        )


class RefusalIsNotEvidence(_NoAmbientProfile):
    """NEGATIVE ARM: a refusal must be unmistakable for a decision."""

    def setUp(self) -> None:
        super().setUp()
        self.bound = admission.AdmissionBound(max_request_bytes=4096)
        self.raw = b"{" + b"x" * 8192 + b"}\n"
        self.refusal = self.bound.admit(self.raw)
        self.assertIsNotNone(self.refusal)

    def test_it_does_not_pass_the_audit_seal_verifier(self) -> None:
        self.assertFalse(rr.verify_audit_seal(self.refusal))

    def test_it_carries_no_error_code_exit_code_or_seal(self) -> None:
        blob = json.dumps(self.refusal)
        self.assertNotIn("ERR_", blob)
        self.assertNotIn("exit_code", self.refusal)
        self.assertNotIn("audit_sha256", self.refusal)
        self.assertNotIn("sealed_response", self.refusal)
        self.assertIs(self.refusal["decision_made"], False)

    def test_its_format_string_names_no_wire_generation(self) -> None:
        # ERRATA E1 class: 0.5 is PROPOSED / NOT ADOPTED (LEDGER P7).
        self.assertEqual(self.refusal["format_version"], "RR-ADMISSION-REFUSAL-1")
        for generation in ("0.2", "0.3", "0.4", "0.5"):
            self.assertNotIn(generation, self.refusal["format_version"])

    def test_it_names_what_it_saw_with_a_bounded_prefix_digest(self) -> None:
        # rr_batch ERR_BATCH_RECORD_LIMIT law: name the prefix, never claim a
        # digest of a request you may not have received in full.
        self.assertEqual(self.refusal["request_prefix_bytes"], 4096)
        self.assertEqual(len(self.refusal["request_prefix_sha256"]), 64)
        self.assertEqual(
            self.refusal["request_prefix_sha256"],
            hashlib.sha256(self.raw[:4096]).hexdigest().upper(),
        )

    def test_a_sub_ceiling_refusal_does_not_claim_the_engine_agrees(self) -> None:
        self.assertIs(self.refusal["refused_on"]["exceeds_frozen_ceiling"], False)
        self.assertIn("this deployment declared", self.refusal["statement"])


class BoundIsSubordinate(_NoAmbientProfile):
    """NEGATIVE ARM: the gate may only tighten the frozen ceilings."""

    def test_a_byte_bound_above_the_frozen_ceiling_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            admission.AdmissionBound(max_request_bytes=b1.MAX_INPUT_BYTES + 1)

    def test_a_member_bound_above_the_frozen_ceiling_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            admission.AdmissionBound(
                max_request_bytes=8192,
                max_structural_members=b1.MAX_MEMBERS_OR_ITEMS + 1,
            )

    def test_the_object_route_raises_rather_than_manufacturing_a_refusal(self) -> None:
        bound = admission.AdmissionBound(max_request_bytes=8192)
        with self.assertRaises(TypeError):
            bound.admit({"operation": "OBL-01"})

    def test_the_gate_never_admits_what_the_ungated_route_refuses(self) -> None:
        # bytearray and memoryview take decide_audited's object path and are
        # refused ERR_JSON. Accepting them as wire bytes here would WIDEN the
        # surface, which a narrowing gate may never do.
        bound = admission.AdmissionBound(max_request_bytes=8192)
        for value in (bytearray(b"{}\n"), memoryview(b"{}\n")):
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(
                    rr.decide_audited(value)["audit"]["object_request_error"], "ERR_JSON"
                )
                with self.assertRaises(TypeError):
                    bound.admit(value)


class TheDeclaredNumbersAreDerivable(_NoAmbientProfile):
    """The contract extent the module publishes is recomputed, not asserted."""

    def test_the_derivation_agrees_with_the_module_constants(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(HERE / "derive_admission_numbers.py"),
                "--extent",
                "--check",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EXTENT CHECK: failures=0", result.stdout)
        self.assertIn(
            f"max_request_bytes={admission.CONTRACT_MAX_REQUEST_BYTES}", result.stdout
        )


class TheProxyIsNotACostControl(_NoAmbientProfile):
    """The measured claim the module's docstring makes, as a live check."""

    def test_a_contract_legal_request_can_out_token_an_attack_it_out_runs(self) -> None:
        legal_raw = contract_legal_maximal_request()

        attack = accepted_obl_01()
        for i in range(17957):
            attack["decision_input"]["facts"]["z%07d" % i] = 1
        attack_raw = b1.jcs_bytes(attack) + b"\n"

        def tokens(raw: bytes) -> int:
            return sum(raw.count(t) for t in (b",", b"{", b"["))

        def ms(raw: bytes) -> float:
            samples = []
            for _ in range(3):
                gc.collect()
                gc.disable()
                start = time.perf_counter_ns()
                rr.decide_audited(raw)
                end = time.perf_counter_ns()
                gc.enable()
                samples.append((end - start) / 1e6)
            return statistics.median(samples)

        self.assertTrue(rr.decide_audited(legal_raw)["sealed_response"]["ok"])
        self.assertGreater(tokens(legal_raw), tokens(attack_raw))
        self.assertLess(ms(legal_raw), ms(attack_raw))


class AmplificationIsBounded(_NoAmbientProfile):
    """The measured win, as a gate."""

    def test_the_ladder_refuses_in_microseconds(self) -> None:
        bound = admission.AdmissionBound(max_request_bytes=8192)
        for size in (10_000, 100_000, 1_000_000, 12_000_000):
            raw = b'{"a":' + b"1," * (size // 2) + b"1}\n"
            samples = []
            for _ in range(5):
                start = time.perf_counter_ns()
                refusal = bound.admit(raw)
                end = time.perf_counter_ns()
                samples.append((end - start) / 1e6)
            self.assertIsNotNone(refusal)
            self.assertLess(statistics.median(samples), 0.5, f"gate cost at {size} bytes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
