"""Failure-oriented local checks; no network or credential access."""
import base64
from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pilot as p


class PilotChecks(unittest.TestCase):
    def response(self):
        return {"model": "jev-latest", "usage": {"input_tokens": 10}, "answers": {"support": {
            "type": "choice", "choice": "supports", "confidence": .95,
            "probabilities": {"supports": .98, "contradicts": .01, "insufficient": .01}}}}

    def test_no_gold_or_condition_leakage(self):
        for _, request in p.requests():
            self.assertEqual(set(request["state"]), {"claim", "source_text", "intended_use"})
        self.assertEqual(len(p.requests()), 30)

    def test_nonfinite_and_malformed_answers_fail_closed(self):
        for value in [float("nan"), float("inf"), -1, 1.1, True]:
            response = self.response()
            response["answers"]["support"]["confidence"] = value
            with self.assertRaises(ValueError):
                p.validate_response(response)
        response = self.response()
        response["answers"]["support"]["probabilities"]["supports"] = .50
        with self.assertRaises(ValueError):
            p.validate_response(response)

    def test_semantic_threshold_is_not_permission(self):
        answer = p.validate_response(self.response())
        self.assertTrue(p.sufficient(answer))
        case = next(c for c in p.cases() if c["transition"] == "revoked")
        common = p.make_common(case, {"kind": "jev", "answer": answer}, refreshed=True)
        self.assertFalse(p.conventional(common)[0])

    def test_presented_bytes_are_exact_and_bind_assessment(self):
        for case in p.cases():
            bank = {key: {"response": self.response()} for key, _ in p.requests()}
            assessment = p.assessment_for(case["current"], bank)
            doc = json.loads(p.make_common(case, assessment, refreshed=True))
            content = base64.b64decode(doc["delivered_artifact_envelope"]["content_b64"])
            payload = json.loads(content)
            self.assertEqual(payload["claim"], case["current"]["claim"])
            self.assertEqual(payload["assessment"], assessment)
            self.assertEqual(json.loads(payload["assessment"]["answer_json"]), self.response()["answers"]["support"])
            self.assertEqual(payload["source_sha256"], p.sha(case["current"]["source"].encode()))

    def test_bank_detects_changed_response_bytes(self):
        key, request = p.requests()[0]
        response = self.response()
        raw = json.dumps(response)
        record = dict(valid=True, request=request, response=response, raw_response_text=raw,
                      raw_response_sha256=p.sha(raw.encode()))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p.write_json(root / "live" / (key + ".json"), record)
            with patch.object(p, "HERE", root), patch.object(p, "requests", return_value=[(key, request)]):
                self.assertEqual(len(p.load_bank()), 1)
                record["response"]["model"] = "tampered"
                p.write_json(root / "live" / (key + ".json"), record)
                with self.assertRaises(RuntimeError):
                    p.load_bank()


if __name__ == "__main__":
    unittest.main()
