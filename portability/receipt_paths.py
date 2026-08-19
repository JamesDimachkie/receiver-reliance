"""Remove the operator's home directory from paths a receipt writer records.

ERRATA E15 discloses that fifty-two tracked files in this public repository
record absolute paths under the maintainer's home directory.  Every one of them
is frozen or recorded evidence: editing them destroys what they attest, so the
disclosure is the only available treatment for the bytes already published.
This module is the treatment for the bytes not published yet.  Four harnesses
write receipts -- ``perf/profile.py``, ``perf/sidecar/_evidence.py``,
``portability/concurrency/ladder.py`` and ``portability/matrix/receipt.py`` --
and each of them recorded ``sys.executable``, an ``executed_argv``, a
temporary-directory root or a traceback verbatim.  On a public artifact that is
a leak with no evidentiary purpose: the interpreter identity that matters is the
implementation, version and build, all recorded separately, and the account name
carries none of it.

``portability/run_local_expanded_gate.py`` solved this first, for itself, with a
private ``_redact``.  A private solution in one of five writers is the failure
shape this repository names twice already -- a control outside the decision path
-- so the implementation moved here and that file now calls it.  There is one
implementation, not five.

Two properties are deliberate:

* **Redaction applies to what a writer RECORDS, never to what it reads.**  A
  path this module rewrote must never be opened, hashed, or compared against the
  filesystem afterwards.  Callers apply it at the write boundary.
* **The match is case-insensitive and separator-insensitive**, because the E15
  gate's own pattern is.  A receipt that spelled the home directory with forward
  slashes or a lowercase drive letter would satisfy a case-sensitive redactor
  and still fail the gate, which would make this module report a guarantee it
  did not provide.

Residue, stated rather than smoothed over: this rewrites the home directory as
``pathlib.Path.home()`` spells it.  A path reaching the receipt through an 8.3
short name, a UNC spelling, a substituted drive, or a symlink to the same
directory is a different string and is not redacted.  The E15 gate is the
backstop -- it recomputes over tracked bytes and fails on any undeclared
instance -- so an unredacted spelling surfaces as a gate failure rather than as
a silent leak.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any


#: What a redacted home-directory prefix is replaced with.  Chosen by
#: ``run_local_expanded_gate.py`` before this module existed; kept byte-exact so
#: the receipts it already wrote and the receipts written from here agree.
HOME_MARKER = "<HOME>"


def home() -> str:
    """The home directory this process would redact, as a string.

    Total by design.  A process whose environment names no home directory --
    hosted Windows runners hand matrix children a scrubbed environment with
    no ``USERPROFILE`` -- has nothing to redact, so this returns ``""`` and
    every redaction below degrades to the identity.  Raising here would turn
    an absent environment variable into a failed receipt writer, which is
    ERRATA E17's ambient-variable class approached from the other side: the
    first hosted run of this module failed all six Windows normative cells
    on exactly that ``RuntimeError`` while every POSIX cell stayed green.
    """
    try:
        return str(pathlib.Path.home())
    except (RuntimeError, KeyError):
        return ""


def _spellings(base: str) -> tuple[str, ...]:
    """Every separator spelling of one home directory, longest first."""
    forward = base.replace("\\", "/")
    backward = forward.replace("/", "\\")
    ordered = [value for value in (base, forward, backward) if value]
    return tuple(dict.fromkeys(ordered))


def redact(value: Any, *, base: str | None = None) -> Any:
    """Replace the home directory in one recorded value with ``HOME_MARKER``.

    Non-strings are returned unchanged, so this is safe to apply to a receipt
    field of unknown type.  Path structure below the home directory is
    preserved: only the prefix is removed.
    """
    if not isinstance(value, str):
        return value
    resolved = home() if base is None else base
    if not resolved:
        return value
    for spelling in _spellings(resolved):
        value = re.sub(re.escape(spelling), lambda _: HOME_MARKER, value, flags=re.IGNORECASE)
    return value


def redact_tree(value: Any, *, base: str | None = None) -> Any:
    """Redact every string in a receipt tree, keys included.

    Applied at a writer's serialization boundary this covers fields nobody
    enumerated: a traceback, a child's argv, a cProfile function label.  The
    enumerate-the-fields alternative was rejected for the reason ADOPTION A5
    records -- a hand-kept list of known instances is not a control, because the
    instance it does not name is exactly the one that ships.

    Keys are redacted too.  If two distinct keys redact to one key the receipt
    would silently lose a field, so that raises instead.

    This walks the tree recursively, at roughly the depth an encoder recursing
    over the same tree would use, so it suits a writer whose encoder recurses
    anyway (``json.dumps``).  A writer with a NON-recursive encoder and its own
    depth bound must not call this: it would hit a ``RecursionError`` before its
    own bound applied, turning a bounded rejection into an unbounded failure.
    Such a writer redacts at its keys and string leaves instead, inheriting its
    own traversal -- ``portability/matrix/receipt.py`` is the worked example, and
    its depth-bound case is what found this.
    """
    resolved = home() if base is None else base
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            new_key = redact(key, base=resolved)
            if new_key in redacted:
                raise ValueError(f"home-directory redaction collides two receipt keys: {new_key!r}")
            redacted[new_key] = redact_tree(item, base=resolved)
        return redacted
    if isinstance(value, list):
        return [redact_tree(item, base=resolved) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_tree(item, base=resolved) for item in value)
    return redact(value, base=resolved)
