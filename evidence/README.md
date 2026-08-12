# Evidence bundle — blind completeness review, now externally verifiable

The external review (2026-08-10) correctly observed that two of the four
files the candidate-blind completeness reviewer read were absent from this
repository, making that evidence chain unverifiable from published bytes.
This directory closes that gap. Nothing here is new: these are byte-exact
releases of the exact artifacts already pinned by digest in the shipped
tree.

## Contents

| File | What it is | Verifies against |
|---|---|---|
| `BRIEF.md` | The completeness decision brief — the isolation charter and the two questions the blind reviewer answered. SHA-256 `86DAFEA83ABCB9768D8D0009A687348B5381346453F9A4B279E9C78E1C5C2439`. | Named in the custody confirmation of `supplemental-0_3/BLIND_GATE_VERDICT_0_3.md`. |
| `A1_CAPABILITY_FLOOR_0_1.md` | The frozen Gate 0 capability floor (28 mandatory obligations, source-coverage ledger over public prior art, sealing algebra). | `supplemental-0_3/A1_FLOOR_COUNT_SUPPLEMENTAL_REGISTER_0_1.json` → `gate0_a1_pin`: byte length 23778, raw SHA-256 `3C694ECBD17CCCF3F2E52D0C13F5B03EDBE400D443F1B63E0561A29EB39C7FCE`. |

## Verification recipe

```bash
python - <<'EOF'
import hashlib, json
floor = open("evidence/A1_CAPABILITY_FLOOR_0_1.md", "rb").read()
pin = json.load(open("supplemental-0_3/A1_FLOOR_COUNT_SUPPLEMENTAL_REGISTER_0_1.json"))["gate0_a1_pin"]
print("A1 bytes:", len(floor) == pin["byte_length"])
print("A1 sha256:", hashlib.sha256(floor).hexdigest().upper() == pin["raw_sha256"])
EOF
```

The blind reviewer's other two custody files ship in this repository already:
`supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json` and
`supplemental-0_3/PRIOR_ART_SNAPSHOT_0_3.json`. The review bundle's copies
were compared byte-for-byte against those shipped files on 2026-08-10 and
found identical, so the four-file custody list in the verdict is now fully
resolvable: every file the blind reviewer read is published, and the two
that carry pins verify against them.

## What this does and does not establish

It establishes that the completeness verdict's inputs are exactly these
bytes. It does not upgrade the verdict itself: the reviewer was an isolated
AI context inside the authoring program (disclosed in `ACCEPTANCE.md`), and
completeness remains relative to the pinned prior-art basis, not to all
prior art. Artifacts that remain unpublished are enumerated with reasons in
[../WITHHELD.md](../WITHHELD.md).
