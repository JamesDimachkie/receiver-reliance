"""demo — drive rr-mcp-gate over real MCP stdio, end to end, five scenarios.

Spawns ``rr_mcp_gate.py`` as a subprocess and speaks MCP to it exactly as a host
would: ``initialize`` -> ``notifications/initialized`` -> ``tools/list`` ->
``tools/call``. Nothing is imported from the server module; the only channel is
the wire.

Scenarios, one per class the pipeline can reach:

  1. clean-record        an exact record, delivered bytes agree with the digest
                         the upstream declared            -> VALID / NO_FINDING
  2. identity-swap       the caller relied on T-42, the result carries T-99
                         -> preflight REJECTED_INVALID / HOLD
  3. digest-drift        the result's own declared revision digest disagrees with
                         its own delivered bytes
                         -> OMISSION_OR_INCOMPLETE / HOLD
  4. floating-reference  the caller relied on the alias LATEST rather than an
                         exact identity      -> MALFORMED_OR_BOUNDARY / HOLD
  5. out-of-scope        a computation result with no record semantics at all
                         -> preflight INSUFFICIENT_EVIDENCE / ABSTAIN

Then ``rr_gate_explain`` on scenario 3, showing the witness trace and the frozen
decision-table predicate that produced the class.

The demo writes to its own audit log in the host's temporary directory,
truncated at start, so a run is reproducible, the server's own log is left
alone, and running the demo never writes inside the checkout.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from rr_bridge import canonical_json_bytes  # noqa: E402  (host-side digest derivation)

SERVER = HERE / "rr_mcp_gate.py"
DEMO_LOG = pathlib.Path(tempfile.gettempdir()) / "rr_mcp_gate_demo.jsonl"
PYTHON = sys.executable


def digest(value: Any) -> str:
    """What an honest upstream would publish for these exact bytes."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


TICKET_RECORD = {
    "id": "res://tickets/T-42",
    "state": "OPEN",
    "assignee": "agent-b",
    "body": "Rotate the staging credential before Friday.",
}
TICKET_DIGEST = digest(TICKET_RECORD)
WRONG_DIGEST = "0" * 63 + "1"


def tool_result(record: dict[str, Any], revision: str) -> dict[str, Any]:
    return {
        "isError": False,
        "content": [{"type": "text", "text": json.dumps(record, sort_keys=True)}],
        "structuredContent": {"record": record, "revision_sha256": revision},
    }


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "clean-record",
        "story": (
            "Agent B asks the docs server for ticket T-42 and intends to act on it. "
            "The result carries T-42, and the revision digest it declares matches the "
            "bytes actually delivered."
        ),
        "expect": {"verdict": "NO_FINDING", "class": "VALID", "preflight": "READY"},
        "arguments": {
            "call": {
                "server": "docs",
                "tool": "get_record",
                "record_reference": {
                    "requested": "res://tickets/T-42",
                    "returned": "res://tickets/T-42",
                    "declared_revision_sha256": TICKET_DIGEST,
                    "revision_digest_domain": "canonical-json:/structuredContent/record",
                },
            },
            "result": tool_result(TICKET_RECORD, TICKET_DIGEST),
            "reliance": {
                "intent": "ACT_ON_RECORD",
                "description": "rotate the credential named in the ticket body",
            },
        },
    },
    {
        "id": "identity-swap",
        "story": (
            "Same request, but the result claims to be ticket T-99. The record the "
            "agent would act on is not the record it relied on."
        ),
        "expect": {"verdict": "HOLD", "class": None, "preflight": "REJECTED_INVALID"},
        "arguments": {
            "call": {
                "server": "docs",
                "tool": "get_record",
                "record_reference": {
                    "requested": "res://tickets/T-42",
                    "returned": "res://tickets/T-99",
                    "declared_revision_sha256": TICKET_DIGEST,
                    "revision_digest_domain": "canonical-json:/structuredContent/record",
                },
            },
            "result": tool_result(TICKET_RECORD, TICKET_DIGEST),
            "reliance": {"intent": "ACT_ON_RECORD", "description": "same rotation task"},
        },
    },
    {
        "id": "digest-drift",
        "story": (
            "The result carries the right identity, but the revision digest it declares "
            "for that identity is not the digest of the bytes it delivered. One record "
            "identity, two revisions: the version map is not a function."
        ),
        "expect": {
            "verdict": "HOLD",
            "class": "OMISSION_OR_INCOMPLETE",
            "preflight": "READY",
        },
        "arguments": {
            "call": {
                "server": "docs",
                "tool": "get_record",
                "record_reference": {
                    "requested": "res://tickets/T-42",
                    "returned": "res://tickets/T-42",
                    "declared_revision_sha256": WRONG_DIGEST,
                    "revision_digest_domain": "canonical-json:/structuredContent/record",
                },
            },
            "result": tool_result(TICKET_RECORD, WRONG_DIGEST),
            "reliance": {"intent": "ACT_ON_RECORD", "description": "same rotation task"},
        },
    },
    {
        "id": "floating-reference",
        "story": (
            "The agent relied on the alias LATEST rather than an exact record identity. "
            "Whatever came back, the reliance target itself was never pinned."
        ),
        "expect": {
            "verdict": "HOLD",
            "class": "MALFORMED_OR_BOUNDARY",
            "preflight": "READY",
        },
        "arguments": {
            "call": {
                "server": "docs",
                "tool": "get_record",
                "record_reference": {
                    "requested": "LATEST",
                    "returned": "LATEST",
                    "declared_revision_sha256": TICKET_DIGEST,
                    "revision_digest_domain": "canonical-json:/structuredContent/record",
                },
            },
            "result": tool_result(TICKET_RECORD, TICKET_DIGEST),
            "reliance": {"intent": "ACT_ON_RECORD", "description": "act on the newest ticket"},
        },
    },
    {
        "id": "out-of-scope",
        "story": (
            "A calculator result. There is no record identity to resolve, so the mapper "
            "declines rather than forcing a mapping, and the preflight abstains. "
            "Abstention is the designed outcome; forcing this mapping is the measured "
            "route to false holds."
        ),
        "expect": {
            "verdict": "ABSTAIN",
            "class": None,
            "preflight": "INSUFFICIENT_EVIDENCE",
        },
        "arguments": {
            "call": {"server": "mathkit", "tool": "add", "record_reference": {}},
            "result": {"isError": False, "content": [{"type": "text", "text": "7"}]},
            "reliance": {"intent": "USE_VALUE", "description": "sum two line items"},
        },
    },
]


class MCPClient:
    """Minimal MCP stdio client: newline-delimited JSON-RPC 2.0."""

    def __init__(self, command: list[str], env: dict[str, str]) -> None:
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=str(HERE),
        )
        self._next_id = 0

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        self._send(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}}
        )
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"server closed the stream during {method}: {stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(f"{method} returned error: {response['error']}")
        return response["result"]

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self) -> str:
        assert self.process.stdin is not None
        self.process.stdin.close()
        self.process.wait(timeout=30)
        return self.process.stderr.read() if self.process.stderr else ""


def rule(text: str = "") -> None:
    print("-" * 78)
    if text:
        print(text)
        print("-" * 78)


def main() -> int:
    calibration = subprocess.run(
        [PYTHON, "-B", str(SERVER), "--calibrate"],
        capture_output=True,
        text=True,
        cwd=str(HERE),
    )
    print(calibration.stdout.strip())
    if calibration.returncode != 0:
        print("calibration failed; refusing to run the demo")
        print("rr-mcp-demo: scenarios=0 valid=0 holds=0 abstained=0 failures=1")
        return 1

    DEMO_LOG.parent.mkdir(parents=True, exist_ok=True)
    if DEMO_LOG.exists():
        DEMO_LOG.unlink()

    env = dict(os.environ)
    env["RR_MCP_GATE_AUDIT_LOG"] = str(DEMO_LOG)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("RR_MCP_GATE_ENFORCE", None)  # observe-only, explicitly

    client = MCPClient([PYTHON, "-B", str(SERVER)], env)
    failures = 0
    counts = {"NO_FINDING": 0, "HOLD": 0, "ABSTAIN": 0}
    drift_decision_id: str | None = None

    try:
        rule("MCP handshake")
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "rr-mcp-demo", "version": "0.1.0"},
            },
        )
        print(f"  protocolVersion : {init['protocolVersion']}")
        print(f"  serverInfo      : {init['serverInfo']['name']} {init['serverInfo']['version']}")
        client.notify("notifications/initialized")

        listed = client.request("tools/list")
        print(f"  tools           : {', '.join(t['name'] for t in listed['tools'])}")

        for scenario in SCENARIOS:
            rule(f"[{scenario['id']}]")
            print(f"  {scenario['story']}")
            result = client.request(
                "tools/call",
                {"name": "rr_gate_check", "arguments": scenario["arguments"]},
            )
            verdict = result["structuredContent"]
            expect = scenario["expect"]
            problems = []
            if verdict["verdict"] != expect["verdict"]:
                problems.append(f"verdict {verdict['verdict']} != {expect['verdict']}")
            if verdict["audited_behavior_class"] != expect["class"]:
                problems.append(
                    f"class {verdict['audited_behavior_class']} != {expect['class']}"
                )
            if verdict["preflight_status"] != expect["preflight"]:
                problems.append(
                    f"preflight {verdict['preflight_status']} != {expect['preflight']}"
                )
            if result.get("isError"):
                problems.append("observe-only run returned isError")

            print()
            print(f"  verdict         : {verdict['verdict']}   (posture {verdict['posture']}, "
                  f"action {verdict['enforcement_action']})")
            print(f"  stage           : {verdict['stage']}")
            print(f"  preflight       : {verdict['preflight_status']}"
                  + (f"  {verdict['preflight_issue_codes']}" if verdict["preflight_issue_codes"] else ""))
            print(f"  obligation      : {verdict['obligation_id'] or '(none mapped)'}")
            print(f"  audited class   : {verdict['audited_behavior_class'] or '(engine not invoked)'}")
            print(f"  reason          : {verdict['reason']}")
            print(f"  audit seal      : {verdict['audit_sha256'] or '(no engine seal)'}")
            if verdict["audit_sha256"]:
                print(f"  seal verified   : {verdict['seal_verified']}   "
                      f"({verdict['audit_format']})")
            print(f"  decision id     : {verdict['decision_id']}")
            if verdict["audit_sha256"] and verdict["seal_verified"] is not True:
                problems.append("audited envelope seal did not verify")
            if problems:
                failures += 1
                print(f"  UNEXPECTED      : {'; '.join(problems)}")
            counts[verdict["verdict"]] += 1
            if scenario["id"] == "digest-drift":
                drift_decision_id = verdict["decision_id"]

        rule("rr_gate_explain on [digest-drift]")
        explained = client.request(
            "tools/call",
            {"name": "rr_gate_explain", "arguments": {"decision_id": drift_decision_id}},
        )["structuredContent"]
        engine = explained["engine"]
        print(f"  obligation      : {explained['obligation_id']}")
        print(f"  seal re-checked : {engine['seal_verified']}   "
              f"(recomputed from the logged bytes)")
        print(f"  audited class   : {engine['audited_behavior_class']}")
        print(f"  first match     : {json.dumps(engine['first_match_predicates'], sort_keys=True)}")
        print(f"  witness trace   : {json.dumps(engine['matched_class_witness'], sort_keys=True)}")
        print(f"  predicate fired : {json.dumps(engine['predicate_source'], sort_keys=True)}")
        print(f"  record refs     : {engine['record_references']}")
        print(f"  input digest    : {engine['decision_input_sha256']}")
        print(f"  governing keys  : {sorted(engine['governing_authorities'])}")
        if not engine["matched_class_witness"]:
            failures += 1
            print("  UNEXPECTED      : empty witness trace on a non-VALID class")

        rule("audit trail")
        lines = DEMO_LOG.read_text(encoding="utf-8").strip().splitlines()
        print(f"  {len(lines)} audited decisions appended to {DEMO_LOG.name}")
        if len(lines) != len(SCENARIOS):
            failures += 1
            print(f"  UNEXPECTED      : expected {len(SCENARIOS)} audit lines")
    finally:
        stderr = client.close()
        if stderr.strip():
            rule("server stderr")
            print(stderr.strip())

    rule()
    print(
        f"rr-mcp-demo: scenarios={len(SCENARIOS)} valid={counts['NO_FINDING']} "
        f"holds={counts['HOLD']} abstained={counts['ABSTAIN']} failures={failures}"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
