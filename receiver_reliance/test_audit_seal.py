"""Regression for `verify_audit_seal`, the recipient-side seal check.

Every test here has a negative arm. A seal verifier that returns True for a
genuine envelope proves nothing on its own -- `lambda _: True` passes that.
What has to be proven is that it returns False when the bytes moved, and that
it survives inputs a recipient did not produce, since the whole point is that
it can be called on something that arrived over a wire.

Run: python -B receiver_reliance/test_audit_seal.py
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import receiver_reliance  # noqa: E402

EXAMPLE = REPO / "examples" / "handoff-clean.json"


def sealed_envelope() -> dict:
    return receiver_reliance.decide_audited(EXAMPLE.read_bytes())


class SealVerifies(unittest.TestCase):
    def test_it_is_on_the_supported_surface(self) -> None:
        self.assertIn("verify_audit_seal", receiver_reliance.__all__)

    def test_a_genuine_envelope_verifies(self) -> None:
        self.assertTrue(receiver_reliance.verify_audit_seal(sealed_envelope()))

    def test_every_envelope_this_repository_can_produce_verifies(self) -> None:
        for name in sorted(p.name for p in (REPO / "examples").glob("*.json")):
            with self.subTest(example=name):
                envelope = receiver_reliance.decide_audited(
                    (REPO / "examples" / name).read_bytes()
                )
                self.assertTrue(receiver_reliance.verify_audit_seal(envelope))


class SealRefuses(unittest.TestCase):
    """The arms that make this a proof rather than an assertion."""

    def test_a_flipped_class_is_refused(self) -> None:
        envelope = sealed_envelope()
        self.assertEqual(envelope["audited_behavior_class"], "VALID")
        envelope["audited_behavior_class"] = "OMISSION_OR_INCOMPLETE"
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_a_swapped_nested_digest_is_refused(self) -> None:
        envelope = copy.deepcopy(sealed_envelope())
        envelope["audit"]["request_raw_sha256"] = "0" * 64
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_a_removed_field_is_refused(self) -> None:
        envelope = sealed_envelope()
        del envelope["exit_code"]
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_an_added_field_is_refused(self) -> None:
        envelope = sealed_envelope()
        envelope["appended_by_a_third_party"] = True
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_a_rewritten_seal_is_refused(self) -> None:
        envelope = sealed_envelope()
        envelope["audit_sha256"] = "F" * 64
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_a_sealed_response_swap_is_refused(self) -> None:
        """The frozen response is the thing a forger would most want to move."""
        clean = sealed_envelope()
        other = receiver_reliance.decide_audited(
            (REPO / "examples" / "handoff-inconsistent.json").read_bytes()
        )
        clean["sealed_response"] = other["sealed_response"]
        self.assertFalse(receiver_reliance.verify_audit_seal(clean))


class SealIsTotal(unittest.TestCase):
    """It is called on bytes the recipient did not produce, so it may not raise."""

    def test_non_envelopes_return_false_and_never_raise(self) -> None:
        for value in (
            None,
            42,
            -1.5,
            "",
            "not an envelope",
            b"bytes",
            [],
            {},
            {"audit_sha256": None},
            {"audit_sha256": ""},
            {"audit_sha256": "too-short"},
            {"audit_sha256": "0" * 63},
            {"audit_sha256": "0" * 65},
            {"audit_sha256": ["not", "a", "string"]},
        ):
            with self.subTest(value=repr(value)[:40]):
                self.assertFalse(receiver_reliance.verify_audit_seal(value))

    def test_an_unserialisable_envelope_returns_false(self) -> None:
        envelope = sealed_envelope()
        envelope["unserialisable"] = {1, 2, 3}
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_a_self_referential_envelope_returns_false(self) -> None:
        envelope = sealed_envelope()
        envelope["loop"] = envelope
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

    def test_case_insensitive_on_the_recorded_seal(self) -> None:
        envelope = sealed_envelope()
        envelope["audit_sha256"] = envelope["audit_sha256"].lower()
        self.assertTrue(receiver_reliance.verify_audit_seal(envelope))


class SealDoesNotOverclaim(unittest.TestCase):
    def test_a_reforged_envelope_verifies_because_nothing_is_signed(self) -> None:
        """The documented limit, pinned so it cannot be quietly overstated.

        Anyone who can author an envelope can author its seal. TRUST_MODEL.md
        says nothing is signed, deliberately. This test exists so that if the
        seal ever becomes authentication, the docstring stops being true and a
        maintainer has to notice.
        """
        envelope = sealed_envelope()
        envelope["audited_behavior_class"] = "OMISSION_OR_INCOMPLETE"
        self.assertFalse(receiver_reliance.verify_audit_seal(envelope))

        forged = json.loads(json.dumps(envelope))
        forged["audit_sha256"] = receiver_reliance._module.b1.self_zero_sha256(
            forged, "audit_sha256"
        )
        self.assertTrue(
            receiver_reliance.verify_audit_seal(forged),
            "re-sealing must succeed: this detects tampering, not forgery",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
