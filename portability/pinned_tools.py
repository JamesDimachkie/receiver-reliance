"""Resolve external tools from a pinned directory instead of the ambient PATH.

Every evidence harness in this repository shells out to `git` — and one to
`docker` — by bare name. `subprocess` then resolves that name through the
operator's `PATH`, so the program that answers "is the tree clean?" is whichever
executable named `git` happens to come first.

That is not theoretical. A verification lane planted a forged `git` earlier on
`PATH` and `verify_hygiene.py` reported `HYGIENE_PASS` with custody 17/17 while
the planted modification was still on disk; two forged invocations turned
`RECEIPT_STATUS FAIL` into `PASS` against a forged HEAD. `shutil.which("git")`
resolved to the planted binary, which is why `which` is not the fix — it answers
the same question `PATH` already answered.

What this module does, and deliberately does not do:

* If `RR_TOOL_DIR` names a directory, tools resolve to an executable inside it,
  by absolute path, and a tool missing from it is an error rather than a silent
  fallback to `PATH`.
* If `RR_TOOL_DIR` is unset, the argv is **byte-identical to today's** — the bare
  name, resolved by `PATH` exactly as before. This fail-open default is the whole
  reason the change is adoptable: no receipt digest moves, so none of the 49
  SHA-pinned receipts, the 17 custody hashes, or the 60-file portable manifest
  needs regenerating. Hardening becomes something an operator turns on, not a
  migration the artifact has to perform.

The trust root moves from the operator's `PATH` to the operator's configuration.
That is a real improvement and a bounded one: the pinned directory must be
writable only by an administrator, because `subprocess` cannot launch from an
already-verified open handle on either Windows or POSIX. So the caveat in
`TRUST_MODEL.md` stays — this narrows it, it does not close it, and a receipt
must not be read as proof that the host was sound.
"""
from __future__ import annotations

import os
import pathlib
import sys

#: Set this to a directory an unprivileged process cannot write.
TOOL_DIR_ENV = "RR_TOOL_DIR"

_WINDOWS_SUFFIXES = (".exe", ".cmd", ".bat", "")
_POSIX_SUFFIXES = ("",)


def tool_dir() -> pathlib.Path | None:
    """The pinned directory, or None when the operator has not configured one."""
    raw = os.environ.get(TOOL_DIR_ENV)
    if not raw:
        return None
    return pathlib.Path(raw)


def resolve(name: str) -> str:
    """The argv[0] to use for `name`.

    Returns an absolute path when a pinned directory is configured, and the bare
    name otherwise so that the default behaviour — and therefore every receipt
    produced under it — is unchanged.
    """
    directory = tool_dir()
    if directory is None:
        return name
    if not directory.is_dir():
        raise RuntimeError(
            f"{TOOL_DIR_ENV} is set to {directory!r}, which is not a directory; "
            "unset it to fall back to PATH resolution, or point it at the pinned tools"
        )
    suffixes = _WINDOWS_SUFFIXES if sys.platform == "win32" else _POSIX_SUFFIXES
    for suffix in suffixes:
        candidate = directory / f"{name}{suffix}"
        if candidate.is_file():
            return str(candidate.resolve())
    raise RuntimeError(
        f"{name!r} not found in the pinned tool directory {directory!r}. "
        "Resolution does not fall back to PATH: a pinned lane that silently used an "
        "ambient tool would report the guarantee without providing it."
    )


def git() -> str:
    """argv[0] for git."""
    return resolve("git")


def docker() -> str:
    """argv[0] for docker."""
    return resolve("docker")


def provenance() -> dict[str, object]:
    """How tools were resolved, for a harness that wants to say so in prose.

    Deliberately NOT written into any existing receipt: the gate receipts are
    byte-pinned with a canonical-identity assertion, and adding a field would
    move digests for zero prevention. A harness that wants to disclose this can
    print it; nothing consumes it.
    """
    directory = tool_dir()
    return {
        "resolution": "PINNED_DIRECTORY" if directory is not None else "AMBIENT_PATH",
        "tool_dir": str(directory) if directory is not None else None,
        "caveat": (
            "Pinned resolution moves the trust root from PATH to the configured "
            "directory; it does not prove the host was sound. See TRUST_MODEL.md."
        ),
    }
