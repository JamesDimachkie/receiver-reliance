# The admission profile — a deployment that narrows its own contract

This directory holds one operator-enabled control: a pre-engine bound that
refuses a request on its byte length before the frozen engine is asked to
classify it. It is off unless an operator turns it on, and turning it on rejects
requests the published contract declares valid. That trade is the subject of
this page. It is not a footnote to the feature; it is the feature's price, and
`HOST_OBLIGATIONS.md` H7 is where the obligation to disclose it lives.

## The law this ships under

**No admission bound can both admit every contract-legal request and bound the
cost of rejecting one.** That is not a limitation of this implementation. It
follows from two measured facts about the published bytes:

| Fact | Value | Where it comes from |
|---|---|---|
| Largest request the published contracts declare legal | **3,392,691 bytes** (`oneOf/27`, OBL-28: three base64 fields at `maxLength: 1048576`) | derived from both contracts by `python -B deployment/derive_admission_numbers.py --extent` |
| Largest request in this artifact's own 372-request fixture corpus | **4,399 bytes** | recomputed by `deployment/test_admission.py` |
| Ratio | **771x** | the same two numbers |

A bound set where the traffic actually lives is three orders of magnitude below
where the contract's ceiling sits. A bound set at the contract ceiling admits a
3.4 MB adversarial request, which is the cost problem restated. There is no
setting that is both.

The second fact rules out the obvious escape. A structural-member count is the
natural "size" proxy, and it is **anti-correlated with cost on exactly the pair
that matters**. Measured on CPython 3.12.10 / Windows 11 `10.0.26200` / AMD64:

| Request | Structural tokens | Cost |
|---|---:|---:|
| Contract-legal OBL-01 at declared caps (`maxItems: 256`, `maxLength: 160`), sealed `ok` | 82,363 | 9.2 ms |
| Adversarial OBL-01 with 17,957 unknown members injected | 18,057 | 566 ms |

The legal request carries four and a half times the tokens and costs sixty times
less, because a comma inside a string literal is a structural token and is
contract-legal. `deployment/test_admission.py::TheProxyIsNotACostControl`
re-measures both sides on every run, so this claim cannot go stale quietly.
`max_structural_members` is therefore offered as a member bound and never as a
cost control, and it cannot be declared without a byte bound beside it.

## Why the engine cannot fix this itself

The frozen 0.2/0.3 error law obliges the engine to prove no `ERR_SCHEMA`
(precedence 80) applies before it may emit `ERR_LIMIT` (precedence 90), and to
select the smallest RFC 6901 pointer among all violations. Both are full
traversals, repeated per `oneOf` branch, so the frozen bytes walk every member
of an attacker-supplied object after it has already failed. The frozen ceiling is
`MAX_INPUT_BYTES = 16,777,216`. Changing any of that means changing bytes the
published evidence is about, which the charter forbids. So the repair cannot
live in the engine, and this is the alternative: decline to ask the question.

The worst cost admitted at a given bound, measured with
`python -B deployment/derive_admission_numbers.py --cost` on the host above,
against a legitimate decision at 3.034 ms:

| Byte bound | Worst of five shapes tried | Cost | Multiple of a legitimate decision |
|---:|---|---:|---:|
| 4,096 | wide `decision_input` | 4.30 ms | 1.4x |
| 8,192 | wide `facts` | 10.99 ms | 3.6x |
| 16,384 | wide `decision_input` | 25.80 ms | 8.5x |
| 32,768 | wide `decision_input` | 56.21 ms | 18.5x |
| 262,144 | wide `facts` | 506.23 ms | 166.8x |

Read that table as a floor, not a ceiling: it is the worst of the five shapes
the script builds, on one host. A shape nobody tried may cost more. The two
wide-object shapes sit within run-to-run noise of each other, so which one wins
a given row is not meaningful; the magnitude is.

## Turning it on

```bash
export RR_ADMISSION_MAX_REQUEST_BYTES=8192      # the only cost control
export RR_ADMISSION_MAX_STRUCTURAL_MEMBERS=4096 # optional, and not a cost control
```

```python
import admission

BOUND = admission.from_environment()   # None when nothing is declared

refusal, envelope = admission.decide_audited_admitted(request_bytes, BOUND)
if refusal is not None:
    log_refusal(refusal)               # no decision was made
else:
    handle(envelope)                   # the ordinary audited envelope
```

With both variables unset, `from_environment()` returns None and
`decide_audited_admitted(raw, None)` forwards `raw` to
`receiver_reliance.decide_audited` untouched — the same object, every input
type, including the Python-object route. That is the same shape
`portability/pinned_tools.py` uses for `RR_TOOL_DIR`: the unset default is
byte-identical to the artifact without the module, so no receipt digest, custody
hash, or published count moves when it lands. Hardening is something an operator
turns on, not a migration the artifact performs.

A malformed declaration raises rather than degrading to None. An operator who
declared a bound and silently got none would be holding a control that is not in
the decision path, which is the defect class `ADOPTION.md` A5 records twice.

## What a refusal is, and is not

A refusal is a plain `RR-ADMISSION-REFUSAL-1` object. It carries
`admitted: false`, `decision_made: false`, the digest of the declared bound, and
a SHA-256 over **the prefix it actually read** with that prefix's length — the
`rr_batch` `ERR_BATCH_RECORD_LIMIT` law, which forbids claiming a digest of a
request you may not have received in full.

| A refusal proves | A refusal does not prove |
|---|---|
| This deployment declined to evaluate these bytes, under a bound whose digest it names | Anything about the request's validity. No decision was made and no class was assigned |
| The prefix it read hashes to the recorded value | That the whole request hashes to anything. Beyond the bound it was never read |
| Whether the request also exceeded the frozen ceiling (`exceeds_frozen_ceiling`) | That the engine would have refused it. When that flag is false, the contract may well declare the request valid |

It is not an audited envelope: `receiver_reliance.verify_audit_seal` returns
`False` for it, it carries no `ERR_` code, no `exit_code`, no `audit_sha256` and
no `sealed_response`, and its `format_version` names no generation of the wire
law. `deployment/test_admission.py::RefusalIsNotEvidence` pins each of those.

## What this does not do

- **It does not bound the cost of a request it admits.** It bounds input size.
  Cost at a fixed size is whatever the worst shape at that size costs, and the
  table above is a measured floor for that, not a proof.
- **It is not a security boundary.** `TRUST_MODEL.md` and `README.md` disclaim
  security claims for every surface in this repository, and this one adds none.
  It reduces the work an oversized request can buy; it does not authenticate,
  authorize, rate-limit, or defend a host.
- **It is not part of the supported surface.** `README.md` defines that as what
  `grounded-0_4/test_public_surface.py` pins, and this module is pinned by its
  own suite instead. It changes nothing about the audited envelope, the wire
  law, or any published count.
- **It does not make the engine cheaper.** The frozen bytes are unchanged and
  every admitted request costs exactly what it always cost.
- **It does not gate the object route.** `decide_audited(obj)` is an in-process
  convenience, is not wire bytes, and is not gated here (H7).
- **It never widens.** The gated route takes `bytes` exactly; `bytearray` and
  `memoryview` raise, because `decide_audited` sends both down the object path
  and refuses them as `ERR_JSON`. A gate that admitted what the ungated route
  rejects would not be a narrowing.

## Re-verification

```bash
python -B deployment/test_admission.py                              # 25 tests
python -B deployment/derive_admission_numbers.py --extent --check   # contract extent vs the module constants
python -B deployment/derive_admission_numbers.py --cost             # re-measure the table on your host
```

Both commands now run on every normative cell of the hosted matrix, as
`admission-profile-tests` and `admission-extent-check` in
`portability/matrix/plan.json`. That addition was the designed
evidence-regeneration event `ERRATA.md` E12 and E14 describe, not an inline
edit: the committed hosted receipts predate both rows, so
`portability/verify_receipts.py` declares them in `HOSTED_ERA_ABSENT_COMMANDS`
and those receipts keep replaying against the 17-command manifest their own run
executed. The suite is still not in the eleven-command charter gate, which pins
its command set inside a byte-committed receipt of its own, and `--cost`
measures on your host, so it stays hand-run.
