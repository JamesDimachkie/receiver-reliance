# F-ORACLE-013 — host decimal-conversion cap escapes the classifier

Status before correction: credible independent-oracle portability defect;
accepted implementation unchanged. Found by fresh refuter R-ORACLE-12 at
frozen closure 48 on 2026-08-10.

## Frozen closure replay

```text
raw construction: ASCII `1` repeated 5,000 times, then LF
raw length:       5,001
raw SHA-256:      3D980BE60158306FF0525F4803AC3F409B2967720FA56D6B006B75B26EEFA8ED
schedule:         isolated invocation; no transport schedule
```

The record is strict UTF-8, exactly LF-framed, canonical JSON, and far above
the safe-integer maximum. The frozen result is therefore `ERR_NUMBER` at the
empty root pointer:

```text
exit: 2
stderr: empty
stdout length: 348
stdout SHA-256: DD26E054DFC5F888F85E0C0323249B392F859292D047B923DB6343FF4E66C66F
```

The oracle instead raised an uncaught `ValueError` when
`JNumber.valid_safe_integer` called `int()` on the 5,000-digit lexeme. On the
observed CPython host, `sys.get_int_max_str_digits()` was 4,300. That ambient
denial-of-service guard is not a frozen contract limit and must not alter the
raw-ABI result.

## Host-boundary minimization

```text
raw construction: ASCII `1` repeated 4,301 times, without LF
raw length:       4,301
raw SHA-256:      8AFECECF38E8946DF9CFF0BB388B1F2909AAA9F595A91450A1C0D69407C3EC36
expected:         ERR_JSON, empty pointer, exit 2, empty stderr
expected stdout:  338 bytes, SHA-256 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
oracle before:    uncaught ValueError
```

The otherwise identical 4,300-digit neighbor agreed, pinning the first digit
at which that host setting leaked. The 4,301-digit witness is minimal with
respect to the ambient conversion boundary, while the 5,000-digit frozen
closure pins the required number-error result with correct LF framing.

## Narrow correction

F-ORACLE-13 replaces regular-expression tail slicing plus decimal `int(str)`
conversion with a direct JSON-number scanner and lexical safe-integer
comparison. Raw `JNumber` canonicalization retains its already parsed lexeme;
programmatic safe integers use a bounded manual decimal emitter. Thus no raw
numeric lexeme crosses the host conversion cap, while invalid-number lexemes
remain stable long enough for framing or surrounding canonical-byte defects to
win at their earlier precedence.

Regressions cover 4,300/4,301/5,000 digits, the exact 16,777,216-byte physical
record limit, positive and negative safe-integer neighbors, signs, leading
zeroes, fractions, exponents, nested and escaped-key pointers, surrounding
noncanonical JSON, and multiple temporary `sys.set_int_max_str_digits()`
settings. Allocation remains proportional to the already bounded physical
record; no accepted implementation or forbidden source was read or executed.

