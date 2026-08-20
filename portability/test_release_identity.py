#!/usr/bin/env python3
"""Release-identity recompute gate: the version/citation pair fails in both directions.

Charter gate ``release_identity`` (wayfinder tickets 01+03, decided 2026-08-20).
Before this file, the rule "``CITATION.cff`` pins the last cut release and moves
in the tag commit" was a comment (`CITATION.cff:17-21`) with no program behind
it — exactly the shape this campaign names decoration (`TRUST_MODEL.md:129-135`:
a present-tense claim nobody re-measures; `CAMPAIGN_LEDGER.md`: "a disclosure
must recompute against current bytes and fail in both directions").

What it enforces, each failing loudly in both directions:

1. ``pyproject.toml`` ``[project] version`` equals ``receiver_reliance.__version__``
   (their agreement was previously a prose comment at ``__init__.py:426``).
2. ``README.md``'s H1 equals ``CITATION.cff``'s ``title`` — one canonical name.
3. ``CITATION.cff``'s ``version`` names the LATEST release tag reachable from
   ``HEAD`` — not merely some existing tag. A CFF left pinned to an older
   release passes an existence check and is exactly the decay this gate is
   for, so existence is not the bar (found by cross-author review,
   2026-08-20: substituting the older real tag passed the first cut of this
   gate). A tag on an unrelated or unmerged history cannot satisfy the check.
4. ``CITATION.cff``'s ``date-released`` is that tag's date, UTC: the tagger date
   of an annotated tag, the committer date of a lightweight one. "Cut date" IS
   the tag's own timestamp — decided semantics, so a CFF bumped ahead of the tag
   and a CFF left stale behind it both fail.
5. When the package version carries no ``.devN`` suffix (the tree is a cut),
   the CFF version must equal it.

Why the git data is read by hand: this gate runs in three lanes — the host
receipt runner, ``verify_live``, and the hardened container — and the container
image carries no ``git`` binary while fresh clones keep every object in pack
files. Shelling out would make the gate's verdict depend on which lane runs it
(and on ambient tool resolution, the trust-root problem ``pinned_tools.py``
exists for). So refs, loose objects, and pack files are parsed directly from
``.git`` with the stdlib: one code path, no subprocess, every lane identical.

Stdlib-only, deterministic, network-free, read-only. SHA-1 object format
only, declared and checked: a repository with ``extensions.objectformat =
sha256`` fails closed with a named reason rather than misparsing.
"""
from __future__ import annotations

import binascii
import pathlib
import re
import struct
import sys
import tomllib
import unittest
import zlib
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Minimal read-only .git access: refs, loose objects, pack v2/v3 with deltas.
# --------------------------------------------------------------------------


class GitReadError(RuntimeError):
    """The .git data needed for the identity checks could not be read."""


def _git_dir(repo: pathlib.Path) -> pathlib.Path:
    """Resolve ``.git`` through the worktree ``gitdir:`` indirection."""
    dotgit = repo / ".git"
    if dotgit.is_dir():
        return dotgit
    if dotgit.is_file():
        text = dotgit.read_text(encoding="utf-8").strip()
        if not text.startswith("gitdir:"):
            raise GitReadError(f".git file has no gitdir pointer: {text!r}")
        target = pathlib.Path(text.split(":", 1)[1].strip())
        if not target.is_absolute():
            target = (repo / target).resolve()
        return target
    raise GitReadError(f"no .git directory or file at {repo}")


def _common_dir(git_dir: pathlib.Path) -> pathlib.Path:
    """Worktree git dirs delegate refs/objects to the main repository."""
    marker = git_dir / "commondir"
    if marker.is_file():
        target = pathlib.Path(marker.read_text(encoding="utf-8").strip())
        if not target.is_absolute():
            target = (git_dir / target).resolve()
        return target
    return git_dir


def _tag_ref_sha(common: pathlib.Path, tag_name: str) -> str:
    """The object id ``refs/tags/<tag_name>`` points at, loose refs first."""
    loose = common / "refs" / "tags" / tag_name
    if loose.is_file():
        sha = loose.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
        raise GitReadError(f"loose ref {tag_name} is not an object id: {sha!r}")
    packed = common / "packed-refs"
    if packed.is_file():
        want = f"refs/tags/{tag_name}"
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith(("#", "^")) or not line.strip():
                continue
            sha, _, name = line.partition(" ")
            if name.strip() == want and re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha
    raise GitReadError(f"tag {tag_name!r} not found in loose refs or packed-refs")


def _object_format_guard(common: pathlib.Path) -> None:
    """Fail closed, by name, on SHA-256 repositories (declared limit)."""
    config = common / "config"
    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^\s*objectformat\s*=\s*(\S+)", text, re.MULTILINE)
        if match and match.group(1).lower() != "sha1":
            raise GitReadError(
                f"object format {match.group(1)!r} is not supported: this gate "
                "reads SHA-1 repositories only (declared limit)"
            )


def _release_tags(common: pathlib.Path) -> dict[str, str]:
    """Every ``v<digits[.digits...]>`` tag -> object id, loose refs winning."""
    tags: dict[str, str] = {}
    packed = common / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith(("#", "^")) or not line.strip():
                continue
            sha, _, name = line.partition(" ")
            name = name.strip()
            if name.startswith("refs/tags/") and re.fullmatch(r"[0-9a-f]{40}", sha):
                short = name[len("refs/tags/"):]
                if re.fullmatch(r"v\d+(\.\d+)*", short):
                    tags[short] = sha
    loose_dir = common / "refs" / "tags"
    if loose_dir.is_dir():
        for path in loose_dir.iterdir():
            if path.is_file() and re.fullmatch(r"v\d+(\.\d+)*", path.name):
                sha = path.read_text(encoding="utf-8").strip()
                if re.fullmatch(r"[0-9a-f]{40}", sha):
                    tags[path.name] = sha
    return tags


def _peel_to_commit(common: pathlib.Path, sha: str) -> str:
    """Follow annotated-tag objects to the commit they name (bounded)."""
    for _ in range(10):
        obj_type, body = _read_object(common, sha)
        if obj_type == "commit":
            return sha
        if obj_type != "tag":
            raise GitReadError(f"object {sha} peels to a {obj_type}, not a commit")
        match = re.match(rb"object ([0-9a-f]{40})\n", body)
        if match is None:
            raise GitReadError(f"tag object {sha} has no object line")
        sha = match.group(1).decode("ascii")
    raise GitReadError("tag chain deeper than ten objects")


def _head_commit(common: pathlib.Path, git_dir: pathlib.Path) -> str:
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        loose = common / ref
        if loose.is_file():
            return loose.read_text(encoding="utf-8").strip()
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.startswith(("#", "^")) or not line.strip():
                    continue
                sha, _, name = line.partition(" ")
                if name.strip() == ref:
                    return sha
        raise GitReadError(f"HEAD ref {ref!r} not found")
    if re.fullmatch(r"[0-9a-f]{40}", head):
        return head
    raise GitReadError(f"unreadable HEAD: {head!r}")


def _reachable(common: pathlib.Path, target: str, head: str, cap: int = 200_000) -> bool:
    """BFS over commit parents from HEAD; bounded so a pathological history
    fails loudly instead of hanging."""
    seen: set[str] = set()
    frontier = [head]
    while frontier:
        if len(seen) > cap:
            raise GitReadError(f"history walk exceeded {cap} commits")
        sha = frontier.pop()
        if sha == target:
            return True
        if sha in seen:
            continue
        seen.add(sha)
        obj_type, body = _read_object(common, sha)
        if obj_type != "commit":
            raise GitReadError(f"history walk met a {obj_type} object")
        headers = body.split(b"\n\n", 1)[0]
        for match in re.finditer(rb"^parent ([0-9a-f]{40})$", headers, re.MULTILINE):
            frontier.append(match.group(1).decode("ascii"))
    return False


def _semver_key(tag_name: str) -> tuple[int, ...]:
    return tuple(int(part) for part in tag_name[1:].split("."))


def latest_release_error(
    cff_version: str, reachable_release_tags: dict[str, bool]
) -> str | None:
    """PURE adjudicator so the negative arms are testable everywhere.

    ``reachable_release_tags``: tag name -> reachable-from-HEAD. The law: the
    CFF must name exactly the semver-maximum among the REACHABLE release tags.
    A CFF naming an older tag (stale pin) fails; a CFF naming an unreachable
    tag (unrelated or unmerged history) fails; higher tags that are not
    reachable from this HEAD do not raise the bar for this checkout.
    """
    reachable = [name for name, ok in reachable_release_tags.items() if ok]
    if not reachable:
        return "no release tag is reachable from HEAD"
    latest = max(reachable, key=_semver_key)
    want = f"v{cff_version}"
    if want not in reachable_release_tags:
        return f"CITATION.cff names {want}, which is not a release tag"
    if not reachable_release_tags[want]:
        return f"CITATION.cff names {want}, which is not reachable from HEAD"
    if want != latest:
        return (
            f"CITATION.cff names {want} but the latest reachable release tag "
            f"is {latest} — the CFF pin is stale"
        )
    return None


def reachable_release_map(repo: pathlib.Path) -> dict[str, bool]:
    git_dir = _git_dir(repo)
    common = _common_dir(git_dir)
    _object_format_guard(common)
    head = _head_commit(common, git_dir)
    return {
        name: _reachable(common, _peel_to_commit(common, sha), head)
        for name, sha in _release_tags(common).items()
    }


def _read_loose(common: pathlib.Path, sha: str) -> tuple[str, bytes] | None:
    path = common / "objects" / sha[:2] / sha[2:]
    if not path.is_file():
        return None
    raw = zlib.decompress(path.read_bytes())
    header, _, body = raw.partition(b"\x00")
    obj_type, _, size = header.decode("ascii").partition(" ")
    if int(size) != len(body):
        raise GitReadError(f"loose object {sha} size mismatch")
    return obj_type, body


def _varint_size(data: bytes, offset: int) -> tuple[int, int, int]:
    """Pack entry header: type in bits 4-6 of byte 0, size base-128 LE."""
    byte = data[offset]
    obj_type = (byte >> 4) & 0x7
    size = byte & 0x0F
    shift = 4
    offset += 1
    while byte & 0x80:
        byte = data[offset]
        size |= (byte & 0x7F) << shift
        shift += 7
        offset += 1
    return obj_type, size, offset


def _delta_header_size(data: bytes, offset: int) -> tuple[int, int]:
    size = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        size |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return size, offset


def _apply_delta(base: bytes, delta: bytes) -> bytes:
    source_size, pos = _delta_header_size(delta, 0)
    target_size, pos = _delta_header_size(delta, pos)
    if source_size != len(base):
        raise GitReadError("delta source size does not match its base")
    out = bytearray()
    while pos < len(delta):
        opcode = delta[pos]
        pos += 1
        if opcode & 0x80:  # copy from base
            copy_offset = 0
            copy_size = 0
            for bit in range(4):
                if opcode & (1 << bit):
                    copy_offset |= delta[pos] << (8 * bit)
                    pos += 1
            for bit in range(3):
                if opcode & (1 << (4 + bit)):
                    copy_size |= delta[pos] << (8 * bit)
                    pos += 1
            if copy_size == 0:
                copy_size = 0x10000
            out += base[copy_offset : copy_offset + copy_size]
        elif opcode:  # insert literal
            out += delta[pos : pos + opcode]
            pos += opcode
        else:
            raise GitReadError("delta opcode 0 is reserved")
    if len(out) != target_size:
        raise GitReadError("delta produced the wrong target size")
    return bytes(out)


def _pack_lookup(idx_path: pathlib.Path, sha: str) -> int | None:
    """Offset of ``sha`` in the pack this v2 index describes, or None."""
    data = idx_path.read_bytes()
    if data[:4] != b"\xfftOc" or struct.unpack(">I", data[4:8])[0] != 2:
        raise GitReadError(f"{idx_path.name}: only pack index v2 is supported")
    fanout = struct.unpack(">256I", data[8 : 8 + 1024])
    total = fanout[255]
    first = int(sha[:2], 16)
    lo = fanout[first - 1] if first else 0
    hi = fanout[first]
    want = binascii.unhexlify(sha)
    names_at = 8 + 1024
    while lo < hi:
        mid = (lo + hi) // 2
        entry = data[names_at + 20 * mid : names_at + 20 * mid + 20]
        if entry == want:
            offsets_at = names_at + 20 * total + 4 * total
            (offset,) = struct.unpack(
                ">I", data[offsets_at + 4 * mid : offsets_at + 4 * mid + 4]
            )
            if offset & 0x80000000:
                large_at = offsets_at + 4 * total
                index = offset & 0x7FFFFFFF
                (offset,) = struct.unpack(
                    ">Q", data[large_at + 8 * index : large_at + 8 * index + 8]
                )
            return offset
        if entry < want:
            lo = mid + 1
        else:
            hi = mid
    return None


_TYPE_NAMES = {1: "commit", 2: "tree", 3: "blob", 4: "tag"}


def _read_pack_object(pack: bytes, offset: int, common: pathlib.Path) -> tuple[str, bytes]:
    obj_type, _, pos = _varint_size(pack, offset)
    if obj_type in _TYPE_NAMES:
        return _TYPE_NAMES[obj_type], zlib.decompress(pack[pos:])
    if obj_type == 6:  # OFS_DELTA
        byte = pack[pos]
        pos += 1
        base_rel = byte & 0x7F
        while byte & 0x80:
            byte = pack[pos]
            pos += 1
            base_rel = ((base_rel + 1) << 7) | (byte & 0x7F)
        base_type, base = _read_pack_object(pack, offset - base_rel, common)
        return base_type, _apply_delta(base, zlib.decompress(pack[pos:]))
    if obj_type == 7:  # REF_DELTA
        base_sha = binascii.hexlify(pack[pos : pos + 20]).decode("ascii")
        pos += 20
        base_type, base = _read_object(common, base_sha)
        return base_type, _apply_delta(base, zlib.decompress(pack[pos:]))
    raise GitReadError(f"unsupported pack object type {obj_type}")


def _read_object(common: pathlib.Path, sha: str) -> tuple[str, bytes]:
    loose = _read_loose(common, sha)
    if loose is not None:
        return loose
    pack_dir = common / "objects" / "pack"
    if pack_dir.is_dir():
        for idx_path in sorted(pack_dir.glob("*.idx")):
            offset = _pack_lookup(idx_path, sha)
            if offset is not None:
                pack = idx_path.with_suffix(".pack").read_bytes()
                return _read_pack_object(pack, offset, common)
    raise GitReadError(f"object {sha} found neither loose nor in any pack")


def tag_date_utc(repo: pathlib.Path, tag_name: str) -> str:
    """The tag's own date, ISO ``YYYY-MM-DD`` in UTC.

    Annotated tag: the ``tagger`` timestamp of the tag object. Lightweight tag:
    the ``committer`` timestamp of the commit it names. The epoch seconds in
    either line are already UTC; the recorded zone offset is display-only.
    """
    common = _common_dir(_git_dir(repo))
    _object_format_guard(common)
    obj_type, body = _read_object(common, _tag_ref_sha(common, tag_name))
    field = {"tag": "tagger", "commit": "committer"}.get(obj_type)
    if field is None:
        raise GitReadError(f"tag {tag_name!r} points at a {obj_type} object")
    headers = body.split(b"\n\n", 1)[0].decode("utf-8", errors="replace")
    match = re.search(
        rf"^{field} .*> (?P<epoch>\d+) [+-]\d{{4}}$", headers, re.MULTILINE
    )
    if match is None:
        raise GitReadError(f"{obj_type} object for {tag_name!r} has no {field} line")
    stamp = datetime.fromtimestamp(int(match.group("epoch")), tz=timezone.utc)
    return stamp.date().isoformat()


def tag_exists(repo: pathlib.Path, tag_name: str) -> bool:
    # Existence alone is NOT the identity law (see latest_release_error).
    try:
        _tag_ref_sha(_common_dir(_git_dir(repo)), tag_name)
        return True
    except GitReadError:
        return False


# --------------------------------------------------------------------------
# The identity surfaces.
# --------------------------------------------------------------------------


def _pyproject_version() -> str:
    with (REPO / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def _package_version() -> str:
    text = (REPO / "receiver_reliance" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise AssertionError("receiver_reliance/__init__.py has no __version__ line")
    return match.group(1)


def _cff_field(name: str) -> str:
    """A top-level double-quoted scalar from CITATION.cff.

    The stdlib has no YAML reader; the CFF is this repository's own file and
    these three fields are kept as top-level quoted scalars precisely so this
    gate can hold them. Absence fails loudly rather than defaulting.
    """
    text = (REPO / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(rf'^{re.escape(name)}: "([^"]*)"\s*$', text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"CITATION.cff has no top-level quoted {name!r} field")
    return match.group(1)


def _readme_h1() -> str:
    first = (REPO / "README.md").read_text(encoding="utf-8").splitlines()[0]
    if not first.startswith("# "):
        raise AssertionError("README.md does not open with an H1 title")
    return first[2:].strip()


class ReleaseIdentityGate(unittest.TestCase):
    def test_pyproject_version_equals_package_version(self) -> None:
        self.assertEqual(
            _pyproject_version(),
            _package_version(),
            "pyproject [project] version and receiver_reliance.__version__ "
            "must move together; their agreement is enforced here, not in prose",
        )

    def test_readme_h1_equals_cff_title(self) -> None:
        self.assertEqual(
            _readme_h1(),
            _cff_field("title"),
            "one canonical name: README H1 and CITATION.cff title must be "
            "the same string (tickets 01+03 item 1)",
        )

    def test_cff_names_the_latest_reachable_release_tag(self) -> None:
        error = latest_release_error(_cff_field("version"), reachable_release_map(REPO))
        self.assertIsNone(
            error,
            f"{error} — existence is not the bar: a stale CFF naming an older "
            "real tag, and a CFF naming an unreachable tag, both fail here",
        )

    def test_stale_cff_is_rejected(self) -> None:
        error = latest_release_error("1.2", {"v1.2": True, "v1.2.1": True})
        self.assertIsNotNone(error)
        self.assertIn("stale", error)

    def test_unreachable_tag_is_rejected_and_does_not_raise_the_bar(self) -> None:
        self.assertIsNone(
            latest_release_error("1.2.1", {"v1.2.1": True, "v1.3": False}),
            "an unreachable higher tag must not raise the bar for this checkout",
        )
        error = latest_release_error("1.3", {"v1.2.1": True, "v1.3": False})
        self.assertIsNotNone(error)
        self.assertIn("not reachable", error)

    def test_sha256_object_format_fails_closed(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            common = pathlib.Path(tmp)
            (common / "config").write_text(
                "[extensions]\n\tobjectformat = sha256\n", encoding="utf-8"
            )
            with self.assertRaises(GitReadError):
                _object_format_guard(common)

    def test_cff_date_released_is_the_tag_date_utc(self) -> None:
        version = _cff_field("version")
        expected = tag_date_utc(REPO, f"v{version}")
        self.assertEqual(
            _cff_field("date-released"),
            expected,
            f"CITATION.cff date-released must be tag v{version}'s own UTC "
            f"date {expected} — decided semantics: the cut date IS the tag's "
            "timestamp, so stale and premature dates both fail",
        )

    def test_a_cut_tree_pins_cff_to_the_package_version(self) -> None:
        package = _pyproject_version()
        if ".dev" in package:
            self.assertTrue(True)  # a dev tree pins the PREVIOUS cut; arm 3+4 hold it
            return
        self.assertEqual(
            _cff_field("version"),
            package,
            "the tree is a cut (no .devN) so CITATION.cff must already name "
            "this exact version — the CFF pin moves in the tag commit, "
            "nowhere else",
        )


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=1))
