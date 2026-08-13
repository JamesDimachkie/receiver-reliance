# Systems-ready release checklist

No item is inferred from a prior commit or another machine.

## Candidate identity

- [ ] worktree is clean on the intended commit;
- [ ] no forbidden/sealed path or pre-existing committed receipt differs from
      the program base except through an explicitly authorized rebind;
- [ ] `portable/build_manifest.py --check` and `portable/verify_bundle.py` pass;
- [ ] two independent deterministic archive builds have identical bytes;
- [ ] manifest, archive, source commit, and every new evidence receipt are
      cross-pinned.

## Correctness and containment

- [ ] portable preflight has closed READY / REJECTED_INVALID /
      INSUFFICIENT_EVIDENCE behavior and the paired corpus table;
- [ ] independent runtime passes both conformance packs, historical RI1–RI4,
      every new minimized raw witness, authority-pin mutation, and API/CLI
      parity;
- [ ] fresh-context refuter returns NO-NEW-EVIDENCE before the qualifying
      coverage-guided campaign;
- [ ] deterministic coverage-guided campaign executes at least 50,000
      identities with zero divergence and records measured decision-path
      coverage without a completeness claim;
- [ ] sidecar transport rejects pre/mid/post-write poison, stale/duplicate
      sequence and digest, partial/zero write, over-limit output, stderr, EOF,
      timeout, and death, with no replay and complete cleanup;
- [ ] full repository gate, receipt verifier, hygiene verifier, and custody
      checks are green.

## Supported systems

- [ ] the exact committed portable manifest passes on CPython 3.12, 3.13, and
      3.14 on scheduled Linux, macOS, and Windows normative rows;
- [ ] absent or infrastructure-unavailable rows remain visibly distinct from
      PASS and do not substitute for a supported row;
- [ ] local Windows evidence is not presented as Linux/macOS evidence;
- [ ] optional architecture/stress rows remain observation-only unless their
      own evidence bar is explicitly adopted.

## Operations and claims

- [ ] operator runbook, threat model, exit/failure semantics, resource ceilings,
      upgrade, drain, and rollback procedures match executable behavior;
- [ ] public README diff states only receipt-backed bounded properties and keeps
      the outside-implementation invitation honest;
- [ ] no efficacy, security, universal-portability, external-standard, market,
      or independent-confirmation claim appears;
- [ ] James reviews the README/new-generation/workflow diff and separately
      authorizes every push, tag, release, or workflow mutation;
- [ ] after the authorized push, hosted results and remote commit are verified
      before the claim and ledger close.
