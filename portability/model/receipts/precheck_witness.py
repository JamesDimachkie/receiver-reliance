"""Phase-2b explicit witness regression for the F-MODEL-003 minimized divergence.

Authored additively for the post-F-MODEL-003 N=48 enumeration.  The same facts
are already asserted inside test_model.py
(``ModelStructureTests.test_key_a_raw_alias_has_one_contextual_label``); this
driver re-checks them standalone so the receipt can cite a direct, separately
executed witness rather than only a suite line.

Run from the repository root:
    python -B portability/model/receipts/precheck_witness.py
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from portability.model.domain import TOKENS
from portability.model.parser_model import (
    INITIAL_STATE,
    replay_tokens,
    terminal_class,
    token_label_is_admissible,
    transition,
)

KEY_A = next(item for item in TOKENS if item.symbol == "KEY_A")
KEY_A_REPEAT = next(item for item in TOKENS if item.symbol == "KEY_A_REPEAT")

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"WITNESS {status} {name}{(' ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


# Frozen physical identity of the alias group.
raw_framed = KEY_A.raw + b"\n"
check("alias_raw_bytes_identical", KEY_A.raw == KEY_A_REPEAT.raw, KEY_A.raw.hex())
check("framed_raw_hex", raw_framed.hex() == "2261220a", raw_framed.hex())
check(
    "framed_raw_sha256",
    hashlib.sha256(raw_framed).hexdigest().upper()
    == "EE195DB0CD14979ECE92E4AC42D91FEF87D1EE254F8DF170907CD674DAB12D44",
    hashlib.sha256(raw_framed).hexdigest().upper(),
)

# Witness 1: KEY_A from INITIAL_STATE transitions, and framed terminal is PARSE_OK.
state_a = transition(INITIAL_STATE, KEY_A)
check("key_a_admissible_at_initial", token_label_is_admissible(INITIAL_STATE, KEY_A))
check("key_a_transition_is_not_none", state_a is not None)
if state_a is not None:
    cls = terminal_class(state_a, True)
    check("key_a_framed_terminal_is_parse_ok", cls == "PARSE_OK", cls)
    check("key_a_replay_is_parse_ok", replay_tokens([KEY_A], True) == "PARSE_OK")

# Witness 2: KEY_A_REPEAT from INITIAL_STATE is outside M.
check(
    "key_a_repeat_not_admissible_at_initial",
    not token_label_is_admissible(INITIAL_STATE, KEY_A_REPEAT),
)
check("key_a_repeat_transition_is_none", transition(INITIAL_STATE, KEY_A_REPEAT) is None)
try:
    replay_tokens([KEY_A_REPEAT], True)
    check("key_a_repeat_replay_rejected", False, "no ValueError raised")
except ValueError as exc:
    check("key_a_repeat_replay_rejected", "outside M" in str(exc), repr(str(exc)))

print(f"WITNESS_SUMMARY failures={len(failures)} {'OK' if not failures else failures}")
raise SystemExit(1 if failures else 0)
