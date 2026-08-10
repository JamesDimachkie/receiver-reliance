# Deterministic one-shot runner fuzz harness

`fuzz.py` exercises the composed 0.3 stdin/stdout runner in fresh, isolated
local subprocesses. It uses only the Python standard library, an independent
JCS/self-zero recomputation, and the runner's checked-in contract-schema
validator. It never uses the network,
the clock as input data, ambient randomness, or files outside this repository.
The wall clock is consulted only to enforce the requested safety budget.

The recorded default seed is `0x0B10F042` (`random.Random(seed)`). Generated
case bytes, ordering, identifiers, and corpus serialization are deterministic
for a given seed, case count, and strategy selection. Every input is executed
twice. The harness requires:

- no subprocess timeout, abnormal exit, or stderr (the latter would expose an
  uncaught runner failure);
- exactly one strict UTF-8, JCS-canonical response followed by one LF;
- process and response exit codes that agree and lie in `{0,1,2,3}`;
- response validity against the matching composed core or wrapper schema;
- success shape for `ok: true`, or contract protocol-error shape for
  `ok: false`;
- a valid `receipt_sha256` or `response_sha256` self-zero seal;
- at most 16 MiB of output; and
- identical return code, stdout bytes, and stderr bytes across both runs.

## Run it

From the repository root:

```bash
python -B fuzz/fuzz.py --ci-smoke
python -B fuzz/fuzz.py
python -B fuzz/fuzz.py --seed 0x1234 --cases 500 --budget-seconds 120
python -B fuzz/fuzz.py --strategy duplicate_key --strategy huge_integer --cases 20
python -B fuzz/fuzz.py --case 12
```

The generated default is 256 cases with a 300-second hard budget and a
five-second timeout per runner invocation. `--ci-smoke` runs every named
strategy once (31 cases), caps the budget at 45 seconds, and caps each runner
invocation at three seconds. Explicit `--cases`, `--budget-seconds`, and
`--case-timeout-seconds` can make a smaller local smoke; CI mode always keeps
its shorter caps. `--list-strategies` prints the exact strategy names.

The fixed cycle includes schema-derived core and wrapper fixture requests for
both `VALID` and non-`VALID` decisions (exercising successful exits 0 and 1);
required-field deletion, type, closed-object, envelope-binding, and nested-fact
mutations; bounded arbitrary JSON grammar generation; UTF-8 boundary scalar
values; BOM; invalid UTF-8 including surrogate encodings; a lone-surrogate JSON
escape; duplicate keys; nesting past 128; huge integers; NFC key/value traps;
noncanonical whitespace and framing; truncation; bit flips; byte insertion,
deletion, and splicing; scalar roots; and empty input. After the first cycle,
the same strategies consume new deterministic choices from the seeded PRNG.

## Corpus and replay format

Use `--emit-corpus` to save the exact selected inputs, `--replay` to run them,
and `--failures-out` to preserve only failing inputs. Corpus paths are resolved
and required to remain inside the repository boundary.

```bash
python -B fuzz/fuzz.py --ci-smoke --emit-corpus fuzz/smoke.jsonl
python -B fuzz/fuzz.py --replay fuzz/smoke.jsonl
python -B fuzz/fuzz.py --replay fuzz/smoke.jsonl --case 12
```

The corpus is UTF-8 JSON Lines with one LF-terminated object per case. Each
record has `format_version: "RR-FUZZ-CORPUS-0.1"`, `case_id`, `strategy`,
`source`, nullable integer `seed`, integer `index`, `input_base64`, and the
uppercase `input_sha256`. Replay rejects malformed Base64, digest mismatch,
duplicate identifiers, a non-LF final record, more than 100,000 cases, or a
corpus over 64 MiB. Records are self-contained and do not store expected
responses: replay always checks the current runner twice against the same
invariants.

The harness is a deterministic adversarial smoke/campaign tool, not a claim of
exhaustive coverage or a security proof.
