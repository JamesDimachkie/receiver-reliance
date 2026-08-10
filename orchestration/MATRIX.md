# Local CPython interpreter matrix

## Verdict

**PASS.** At integration SHA
`2d4d13a48635f96c9bf24a180de85c3aea48de18`, every distinct, usable local
CPython interpreter satisfying the package floor (`>=3.12`) completed the
eight-command integrated gate exactly once. CPython 3.12.10 and 3.14.5 both
returned top-level exit 0 for every command, with identical asserted counts,
fuzz strategy coverage, and fuzz exit-code distribution. No behavioral
interpreter divergence was observed.

Branch: `sol/w-t2`

Worktree:
`C:\Users\james\New folder\receiver-reliance-worktrees\t2`

The worktree was clean at the integration SHA before discovery and remained
clean after all test commands. This report is the only lane-owned change.

| Discovered CPython | Eligibility | Matrix disposition |
|---|---|---|
| 3.12.10, Windows AMD64 | Eligible (`>=3.12`) | **PASS**, 8/8 top-level commands; 45.733 s summed command time |
| 3.14.5, Windows AMD64 | Eligible (`>=3.12`) | **PASS**, 8/8 top-level commands; 48.318 s summed command time |
| 3.11.15, Windows AMD64 | Ineligible | Skipped: below the repository's `>=3.12` floor |
| 3.13 | Unavailable | Not present; no interpreter installed solely to enlarge the matrix |

## Discovery evidence

The required launcher inventory returned:

```text
$ py -0p
 -V:3.14          C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe
 -V:3.12[-64] *   C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe
 -V:Astral\CPython3.11.15 C:\Users\james\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe
exit=0
```

The required PATH inventory returned:

```text
$ where.exe python
C:\Users\james\AppData\Local\Python\bin\python.exe
C:\Users\james\.cargo\bin\python
C:\Users\james\.cargo\bin\python.cmd
C:\Users\james\AppData\Local\Microsoft\WindowsApps\python.exe
exit=0
```

Direct isolated probes (`-I -B`) established two distinct eligible physical
executables:

| Label | Physical `sys.executable` | Full version | Platform |
|---|---|---|---|
| CPython 3.12 | `C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe` | `3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]` | `Windows-11-10.0.26200-SP0`; AMD64; 64bit |
| CPython 3.14 | `C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe` | `3.14.5 (tags/v3.14.5:5607950, May 10 2026, 10:43:50) [MSC v.1944 64 bit (AMD64)]` | `Windows-11-10.0.26200-SP0`; AMD64; 64bit |

Probe JSON, preserved exactly:

```text
{"architecture": "64bit", "executable": "C:\\Users\\james\\AppData\\Local\\Python\\pythoncore-3.12-64\\python.exe", "implementation": "CPython", "machine": "AMD64", "platform": "Windows-11-10.0.26200-SP0", "version": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]", "version_info": [3, 12, 10, "final", 0]}
{"architecture": "64bit", "executable": "C:\\Users\\james\\AppData\\Local\\Programs\\Python\\Python314\\python.exe", "implementation": "CPython", "machine": "AMD64", "platform": "Windows-11-10.0.26200-SP0", "version": "3.14.5 (tags/v3.14.5:5607950, May 10 2026, 10:43:50) [MSC v.1944 64 bit (AMD64)]", "version_info": [3, 14, 5, "final", 0]}
{"architecture": "64bit", "executable": "C:\\Users\\james\\AppData\\Roaming\\uv\\python\\cpython-3.11.15-windows-x86_64-none\\python.exe", "implementation": "CPython", "machine": "AMD64", "platform": "Windows-10-10.0.26200-SP0", "version": "3.11.15 (main, Jun 23 2026, 15:20:37) [MSC v.1944 64 bit (AMD64)]", "version_info": [3, 11, 15, "final", 0]}
```

The PATH `python.exe`, Cargo `python.cmd`, and WindowsApps `python.exe` shims
were also probed and each resolved `sys.executable` to the same physical
CPython 3.12.10 path above, so they were not counted as additional
interpreters. The launcher's Astral CPython 3.11.15 runtime was usable but
excluded because it is below the declared `>=3.12` floor. No CPython 3.13
runtime was installed. `py help install` showed Python installation manager
26.3 can install runtimes noninteractively, but no runtime was added merely to
enlarge the already representative 3.12/3.14 matrix; PATH was not changed.
During discovery, the launcher also reported that its installation manager
had updated itself to 26.3. That launcher self-update was the only reported
tooling-state change; it did not add a CPython runtime.

## Exact commands

The two conformance commands used working directory
`C:\Users\james\New folder\receiver-reliance-worktrees\t2\baseline-run`.
The other six commands used the worktree root.

CPython 3.12.10:

```text
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B implementation-output-0.2/run_conformance_0_2.py
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B implementation-output-0.3/run_conformance_0_3.py --suite all
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B grounded-0_4/test_grounded_0_4.py
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B grounded-0_4/lint_contract.py --gate
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B grounded-0_4/test_lint_gate.py
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B grounded-0_4/test_properties.py
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B proof/test_proof_harness.py
"C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe" -B fuzz/fuzz.py --ci-smoke
```

CPython 3.14.5:

```text
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B implementation-output-0.2/run_conformance_0_2.py
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B implementation-output-0.3/run_conformance_0_3.py --suite all
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B grounded-0_4/test_grounded_0_4.py
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B grounded-0_4/lint_contract.py --gate
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B grounded-0_4/test_lint_gate.py
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B grounded-0_4/test_properties.py
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B proof/test_proof_harness.py
"C:\Users\james\AppData\Local\Programs\Python\Python314\python.exe" -B fuzz/fuzz.py --ci-smoke
```

Both the P2 meta-test and P3 fuzz harness spawn nested processes with
`sys.executable`; the explicit parent invocation therefore kept all nested
work on the target physical interpreter.

## CPython 3.12.10 results

| Gate | Exit | Elapsed | Exact output summary |
|---|---:|---:|---|
| Frozen 0.2 | 0 | 16.055 s | `semantic=112`, `competence=370`, `wrapper_arms=224`, `negative=10`, `metamorphic=4`, `error_law=80`, `failures=0` (800 checks); stderr empty |
| Composed 0.3 `--suite all` | 0 | 17.900 s | suite 0.2: `total=800 failures=0`; suite 0.3: `competence=53`, `metamorphic=8`, `negative=10`, `semantic=12`, `wrapper_arms=24`, `total=107 failures=0`; stderr empty |
| Grounded regression | 0 | 1.424 s | `grounded-0.4 regression: checks=504 failures=0`; stderr empty |
| Lint `--gate` | 0 | 0.154 s | authority ledger `{'inert_disclosed': 10, 'inert_registered_debt': 14, 'presence_only': 64, 'semantic': 111} of 199 required fields`; `lint: 0 findings`; stderr empty |
| P2 lint meta-test | 0 | 2.067 s | 7/7 checks passed: baseline accepted at nested exit 0 and all six controlled mutations rejected at nested exit 1; `failures=0`; stderr empty |
| P4 properties | 0 | 0.154 s | seed `0x5EED8785`; cases `jcs_idempotence=128`, `parse_profile_agreement=129`, `pointer_roundtrip=128`, `precedence_short_circuit=3`, `self_zero_seal=96`, `strict_equal=96`, `utf16_member_order=65`; `checks=2296 failures=0`; stderr empty |
| P6 proof harness | 0 | 0.761 s | `Ran 7 tests in 0.516s`; `OK`; stdout empty; normal `unittest` progress on stderr |
| P3 fuzz `--ci-smoke` | 0 | 7.218 s | `verdict=PASS cases=31/31 seed=0x000000000B10F042 source=generated failures=0 budget_exhausted=false`; every one of 31 named strategies ran once; `exit_counts={"0":2,"1":2,"2":27}`; stderr empty |

Sum of measured command elapsed times: **45.733 seconds**.

## CPython 3.14.5 results

| Gate | Exit | Elapsed | Exact output summary |
|---|---:|---:|---|
| Frozen 0.2 | 0 | 19.318 s | `semantic=112`, `competence=370`, `wrapper_arms=224`, `negative=10`, `metamorphic=4`, `error_law=80`, `failures=0` (800 checks); stderr empty |
| Composed 0.3 `--suite all` | 0 | 17.824 s | suite 0.2: `total=800 failures=0`; suite 0.3: `competence=53`, `metamorphic=8`, `negative=10`, `semantic=12`, `wrapper_arms=24`, `total=107 failures=0`; stderr empty |
| Grounded regression | 0 | 1.239 s | `grounded-0.4 regression: checks=504 failures=0`; stderr empty |
| Lint `--gate` | 0 | 0.120 s | authority ledger `{'inert_disclosed': 10, 'inert_registered_debt': 14, 'presence_only': 64, 'semantic': 111} of 199 required fields`; `lint: 0 findings`; stderr empty |
| P2 lint meta-test | 0 | 2.071 s | 7/7 checks passed: baseline accepted at nested exit 0 and all six controlled mutations rejected at nested exit 1; `failures=0`; stderr empty |
| P4 properties | 0 | 0.161 s | seed `0x5EED8785`; cases `jcs_idempotence=128`, `parse_profile_agreement=129`, `pointer_roundtrip=128`, `precedence_short_circuit=3`, `self_zero_seal=96`, `strict_equal=96`, `utf16_member_order=65`; `checks=2296 failures=0`; stderr empty |
| P6 proof harness | 0 | 1.241 s | `Ran 7 tests in 0.801s`; `OK`; stdout empty; normal `unittest` progress on stderr |
| P3 fuzz `--ci-smoke` | 0 | 6.344 s | `verdict=PASS cases=31/31 seed=0x000000000B10F042 source=generated failures=0 budget_exhausted=false`; every one of 31 named strategies ran once; `exit_counts={"0":2,"1":2,"2":27}`; stderr empty |

Sum of measured command elapsed times: **48.318 seconds**.

## Divergences

No result divergence was found:

- all 16 top-level processes exited 0;
- every asserted check, suite, case, strategy, and exit-distribution count was
  identical between 3.12.10 and 3.14.5; and
- stdout/stderr placement was identical, including `unittest`'s expected P6
  progress on stderr.

Elapsed times differed. CPython 3.14.5 took 48.318 seconds across the eight
commands versus 45.733 seconds for CPython 3.12.10. These are single cold
runs under an uncontrolled desktop workload, so the timing difference is
evidence of run duration only, not a performance conclusion.

## Residual risks and limitations

- This is a local Windows 11, AMD64 matrix. It does not cover Linux, macOS,
  ARM64, PyPy, debug builds, prereleases, or CPython 3.13 (not installed).
- Per the stop rule, each eligible interpreter received one full run and no
  retries. The absence of repeated timing samples limits performance
  interpretation but not the deterministic pass/fail evidence.
- The required P3 run was the 31-case deterministic CI smoke, not the
  256-case default campaign or a coverage-guided/exhaustive fuzz campaign.
- The conformance commands used the specified in-process modes. The sealed
  ABI `--subprocess` mode was not part of this gate, and the separately pinned
  `baseline-run/toolchain/python.exe` is not present in this checkout.
- The P6 harness used only the committed synthetic corpus and temporary
  directories. `proof/extract_corpus.py` was not run, and no workspace-derived
  corpus was read or regenerated.
- This lane is treatment-exposed by reading the repository. It must not author
  regenerated research worlds, an oracle, gold outputs, or a renderer for a
  future blinded experiment.
