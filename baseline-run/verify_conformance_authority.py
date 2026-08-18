#!/usr/bin/env python3
"""Authenticate what the frozen conformance surface declares but never checks.

    python -B baseline-run/verify_conformance_authority.py

Four scan findings all land inside ``baseline-run/implementation-output-*``,
whose bytes are frozen: they are the accepted implementation and its recorded
evidence, and the campaign law is additive guards and dispositions rather than
edits.  So this program sits outside that boundary and checks, from current
bytes, the four things those files declare on trust:

``csf_9237eb71`` -- the manifest emitters write ``check_counts``, ``failures: 0``
and ``result: "PASS"`` as literals and never invoke the conformance harness, so a
changed or broken implementation can still be hashed into freshly generated
PASS-shaped artifacts.  This program EXECUTES both suites and requires the
declared numbers to equal the observed ones.  That is the check the emitters
skip; it does not make the emitters safe to trust on their own, and the
disposition says so.

``csf_56621d97`` -- the implementation manifests enumerate source only, while
``-B`` suppresses bytecode WRITES and not READS.  Timestamp- and size-matching
``__pycache__`` bytecode can therefore execute in place of a manifested source
without either manifest digest changing.  This program compiles each manifested
source and requires any cached bytecode that CPython would accept to contain
exactly that code object.

``csf_a68931d8`` -- the runners load the supplemental fixture packs and base
success on replay failures without ever comparing the packs' own
``authority_pins`` against the bytes in play.  This program compares all of them,
and two rows genuinely disagree: both packs pin a contract and matrix digest from
an earlier generation.  Neither side can move, so the divergence is declared
below and enforced, which is strictly better than being unnoticed.

``csf_b7bc7ed8`` -- ``--subprocess`` launches ``baseline-run/toolchain/python.exe``
directly, with the download-and-hash step documented in the RUNBOOK and no digest
check at invocation.  This program refuses to report the subprocess mode as
available unless a toolchain is present AND digest-verified, and reports its
absence explicitly rather than silently.

Summary line, machine-parseable::

    conformance-authority: checks=<n> failures=<n> declared_divergences=<n>

Exit 0 only when every check passes.  Stdlib-only; writes nothing.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import marshal
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent

MANIFESTS = {
    "0.2": HERE / "implementation-output-0.2" / "B1_IMPLEMENTATION_MANIFEST_0_2.json",
    "0.3": HERE / "implementation-output-0.3" / "B1_IMPLEMENTATION_MANIFEST_0_3.json",
}
TREES = {
    "0.2": HERE / "implementation-output-0.2",
    "0.3": HERE / "implementation-output-0.3",
}
RUNNERS = {
    "0.2": ("implementation-output-0.2/run_conformance_0_2.py",),
    "0.3": ("implementation-output-0.3/run_conformance_0_3.py", "--suite", "all"),
}
# The literals the emitters write without executing anything.  Held against a
# live run below; a mismatch is the finding firing, not a pin to refresh.
DECLARED_0_2 = {
    "semantic": 112,
    "competence": 370,
    "wrapper_arms": 224,
    "negative": 10,
    "metamorphic": 4,
    "error_law": 80,
}
DECLARED_0_3_SUPPLEMENTAL = {
    "semantic": 12,
    "competence": 53,
    "wrapper_arms": 24,
    "negative": 10,
    "metamorphic": 8,
}
SUPPLEMENTAL_PACKS = (
    REPO / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
    REPO / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
)
CONTROL = {
    "contract_raw_sha256": REPO / "supplemental-0_3" / "control" / "B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json",
    "matrix_raw_sha256": REPO / "supplemental-0_3" / "control" / "B1_COMPOSED_CAPABILITY_MATRIX_0_3.json",
    "packet_raw_sha256": REPO / "access" / "SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json",
    "projection_raw_sha256": REPO / "access" / "A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json",
}
# csf_a68931d8, declared.  Both supplemental packs pin a contract and matrix
# digest that the current sealed control bytes do not have.  Neither side can be
# corrected: the packs and the control JSONs are both frozen sealed bytes, and the
# packs' digests are pinned in turn by the implementation manifest, the portable
# manifest and the WP5 receipts.  The pins date from an earlier draft of the
# supplemental generation.  What matters is that the divergence is now named and
# enforced -- these exact values, and no others -- so a THIRD value appearing on
# either side fails instead of passing unexamined.
DECLARED_PACK_PIN_DIVERGENCES = {
    "contract_raw_sha256": (
        "0FA31FD99546A2CEDA697F9D3CAC9269991EEE63072EEF15ADAA1419B8D291E2",
        "6B2CAD02DDE7388D63D66E4863E5233CFBD1DC413575D9D260DB9799C7023A12",
    ),
    "matrix_raw_sha256": (
        "5A750006C6FE8307DD3B1768EDC3ED1F6A852B698705FEE352D9D056274F59D3",
        "B369777E51B2A64DC2C304C5949F38E13956353B496BABA8B6E488451F8C5B98",
    ),
}
TOOLCHAIN = HERE / "toolchain"


class Verifier:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.checks += 1
        if not condition:
            self.failures.append(f"{name}{': ' + detail if detail else ''}")
            print(f"FAIL {name} {detail}".rstrip(), file=sys.stderr)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _observed_counts(generation: str) -> tuple[dict[str, int], int, str]:
    """Execute a conformance runner and read its own summary line."""
    argv = [sys.executable, "-B", *RUNNERS[generation]]
    completed = subprocess.run(
        argv,
        cwd=HERE,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1800,
        check=False,
    )
    text = completed.stdout.decode("utf-8", "strict")
    counts: dict[str, int] = {}
    failures = 0
    wanted = "suite=0.3" if generation == "0.3" else "mode=in-process"
    for line in text.splitlines():
        if not line.startswith("mode=in-process") or wanted not in line:
            continue
        start = line.index("counts=") + len("counts=")
        end = line.index("}", start) + 1
        counts = json.loads(line[start:end])
        failures = int(line.rsplit("failures=", 1)[1].split()[0])
    return counts, failures, text


def verify_emitted_evidence_matches_a_real_run(v: Verifier) -> None:
    for generation, declared in (
        ("0.2", DECLARED_0_2),
        ("0.3", DECLARED_0_3_SUPPLEMENTAL),
    ):
        counts, failures, text = _observed_counts(generation)
        v.check(
            f"executed.{generation}.summary_present",
            bool(counts),
            f"no in-process summary line in {len(text)} bytes of output",
        )
        if not counts:
            continue
        v.check(
            f"executed.{generation}.declared_counts_are_observed",
            counts == declared,
            f"declared={declared} observed={counts}",
        )
        v.check(f"executed.{generation}.declared_zero_failures", failures == 0, str(failures))


def verify_no_bytecode_shadows_a_manifested_source(v: Verifier) -> None:
    for generation, manifest_path in MANIFESTS.items():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tree = TREES[generation]
        files = manifest["files"]
        v.check(f"manifest.{generation}.enumerates_files", bool(files))
        for entry in sorted(files, key=lambda item: item["relative_path"]):
            relative = entry["relative_path"]
            source = REPO / "baseline-run" / pathlib.PurePosixPath(relative)
            if source.suffix != ".py" or not source.is_file():
                continue
            raw = source.read_bytes()
            # The manifest digest must still describe the source before any
            # question about bytecode shadowing it is meaningful.
            v.check(
                f"manifest.{generation}.{source.name}.raw_sha256",
                _sha256(raw) == entry["raw_sha256"]
                and len(raw) == entry["byte_length"],
            )
            fresh = importlib.util.cache_from_source(str(source))
            cached = pathlib.Path(fresh)
            if not cached.is_file():
                v.check(f"bytecode.{generation}.{source.name}.absent", True)
                continue
            # CPython accepts a timestamp pyc when its recorded mtime and size
            # match the source, so that is exactly when shadowing is possible.
            header = cached.read_bytes()[:16]
            stat = source.stat()
            accepted = (
                len(header) == 16
                and int.from_bytes(header[8:12], "little") == int(stat.st_mtime) & 0xFFFFFFFF
                and int.from_bytes(header[12:16], "little") == stat.st_size & 0xFFFFFFFF
            )
            if not accepted:
                v.check(f"bytecode.{generation}.{source.name}.stale_and_ignored", True)
                continue
            # Round-trip both sides through marshal so the comparison is over
            # code objects rather than over a marshal version or writer's flags.
            try:
                cached_code = marshal.dumps(marshal.loads(cached.read_bytes()[16:]))
            except (EOFError, ValueError, TypeError):
                cached_code = None
            fresh_code = marshal.dumps(
                marshal.loads(
                    marshal.dumps(compile(raw, str(source), "exec", dont_inherit=True))
                )
            )
            v.check(
                f"bytecode.{generation}.{source.name}.matches_manifested_source",
                cached_code == fresh_code,
                "importable bytecode does not compile from the manifested source; "
                f"remove {cached} and re-run",
            )


def verify_supplemental_pack_authority(v: Verifier) -> int:
    current = {name: _sha256(path.read_bytes()) for name, path in CONTROL.items()}
    declared_divergences = 0
    for pack_path in SUPPLEMENTAL_PACKS:
        raw = pack_path.read_bytes()
        pack = json.loads(raw.decode("utf-8"))
        label = pack_path.name
        v.check(f"pack.{label}.self_seal_shape", len(pack["pack_sha256"]) == 64)
        pins = pack["authority_pins"]
        for name, expected in sorted(current.items()):
            if name not in pins:
                continue
            pinned = pins[name]
            divergence = DECLARED_PACK_PIN_DIVERGENCES.get(name)
            if divergence is None or pinned == expected:
                v.check(
                    f"pack.{label}.{name}.binds_current_control",
                    pinned == expected,
                    f"pinned={pinned} current={expected}",
                )
                continue
            recorded_pin, recorded_current = divergence
            v.check(
                f"pack.{label}.{name}.declared_divergence",
                pinned == recorded_pin and expected == recorded_current,
                f"pinned={pinned} current={expected} "
                f"declared=({recorded_pin}, {recorded_current})",
            )
            declared_divergences += 1
        # Cardinality the runners never assert: a pack can be emptied and the
        # printed counts fall while failures stays empty and exit stays zero.
        for count_field, array_field in (
            ("entry_count", "entries"),
            ("arm_count", "pairs"),
            ("pair_count", "pairs"),
            ("negative_case_count", "negative_cases"),
            ("metamorphic_case_count", "metamorphic_cases"),
        ):
            if count_field not in pack or array_field not in pack:
                continue
            declared = pack[count_field]
            actual = len(pack[array_field])
            if count_field == "arm_count":
                # Arms are two configurations per pair, per the pack's own law.
                actual *= len(pack["configuration_counts"])
            v.check(
                f"pack.{label}.{count_field}_matches_{array_field}",
                declared == actual,
                f"declared={declared} actual={actual}",
            )
    return declared_divergences


def verify_subprocess_toolchain(v: Verifier) -> None:
    manifest = next(TOOLCHAIN.glob("*MANIFEST*"), None) if TOOLCHAIN.is_dir() else None
    if not TOOLCHAIN.is_dir():
        # Absence is the honest, checkable state: the subprocess mode cannot run
        # here at all, so no unverified binary can be launched.  Reported rather
        # than skipped.
        v.check("toolchain.absent_so_subprocess_mode_unavailable", True)
        print(
            "toolchain: absent; --subprocess conformance is unavailable at these "
            "bytes and no repository-local interpreter can be launched"
        )
        return
    v.check(
        "toolchain.present_requires_a_manifest",
        manifest is not None,
        "a toolchain directory without a digest manifest must not be executed",
    )
    if manifest is None:
        return
    declared = json.loads(manifest.read_text(encoding="utf-8"))
    entries = declared.get("files") or declared
    for relative, expected in sorted(entries.items()):
        candidate = TOOLCHAIN / pathlib.PurePosixPath(relative)
        digest = expected if isinstance(expected, str) else expected.get("sha256", "")
        v.check(
            f"toolchain.{relative}.digest",
            candidate.is_file() and _sha256(candidate.read_bytes()) == digest.upper(),
        )


def main() -> int:
    v = Verifier()
    verify_emitted_evidence_matches_a_real_run(v)
    verify_no_bytecode_shadows_a_manifested_source(v)
    declared = verify_supplemental_pack_authority(v)
    verify_subprocess_toolchain(v)
    print(
        f"conformance-authority: checks={v.checks} failures={len(v.failures)} "
        f"declared_divergences={declared}"
    )
    return 1 if v.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
