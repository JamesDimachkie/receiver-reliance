# External validation record — additive, post-close (2026-08-10)

`FINAL_REPORT.md` closed before any push and correctly said, at close time,
that nothing had been pushed and Linux/macOS were untested. Both statements
are now stale; per convergence doctrine this record adds the later evidence
with timestamps instead of rewriting the closed report.

## What happened after close

1. **Branch push (operator-authorized).** `sol/rr-continuation-20260810`
   was pushed to `https://github.com/JimGHTB12/receiver-reliance.git` at
   exact SHA `4e788d21e882a30bdda2aec3f780537161f81644` so hosted and
   cloud validation could run against public bytes. `main` is untouched
   (still `cc6f365`).
2. **GitHub-hosted conformance** — run
   `https://github.com/JimGHTB12/receiver-reliance/actions/runs/31428624244`
   completed successfully at that SHA on `ubuntu-latest`, `macos-latest`,
   and `windows-latest` with CPython 3.12, running the two-step committed
   workflow: frozen 0.2 suite (800/0) and composed suite (800/0 + 107/0).
   Scope note: this is the first real Linux/macOS conformance evidence,
   but it is the two-suite workflow only — not the expanded gate — and the
   jobs persisted no runtime/architecture receipts beyond the job labels.
3. **Codex Cloud bounded stress (read-only task)** — task
   `task_e_6a7a37f505e48323b48e763594b5a37e` independently verified the
   same SHA and a clean tree, ran the full expanded gate under a Linux
   container with CPython 3.14.4, and reported all suites green at pinned
   counts, batch gate 2,160/0 (ratio 1.160576, peak 16,853,409 bytes),
   single-pass equivalence 1,142/0 (ratio 0.998985), plus a deterministic
   256-case double-execution run (seed `0xA11CE8785`), zero failures, no
   credible divergence, clean tree after. Bounded evidence: one container,
   one architecture, no live backpressure, no finite exhaustive model.
4. **Codex Security usefulness assessment** — assessed the PROPOSED next
   work, not a vulnerability. Conclusion: contribution potential is real
   but rides on independent oracles, precisely bounded exhaustive models,
   real transport backpressure, bounded concurrency, and minimized
   findings — not additional undifferentiated fuzz volume. That priority
   order governs the portability session's charter.
5. **Local re-verification (Fable convergence, this record's author).**
   The full expanded gate was rerun at the same SHA on Windows AMD64 /
   CPython 3.12.10 on 2026-08-10: 800/0; 800/0 + 107/0; 504/0; lint 0
   findings; lint meta 7/0; properties 2,296/0; adversarial 6,497/0;
   proof harness 7/7; fuzz smoke 31/31; batch 2,160/0 (perf on);
   single-pass equivalence green (benchmark median ratio 1.008,
   observational). Protected-path diff vs `cc6f365`: zero.

## Standing claim discipline

None of the above establishes efficacy, novelty, security, fuzzing
completeness, external-standard conformance, or universal portability.
The proof evidence tier remains `internal held-out`. The defensible form
for anything the next session adds stays: independent validation found no
divergence within the stated environments and bounds, with everything
outside the model reported as outside the model.
