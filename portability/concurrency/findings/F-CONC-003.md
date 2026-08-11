# F-CONC-003 — semantic/physical comparator layer mismatch

Status: adjudicated harness defect; not an accepted-code divergence.

R-CONC-3 stopped `RR-CONCURRENCY-LADDER-2` at library mode, `P=1`, request
index 0. The preserved receipt is
`receipts/normative-clean-oracle-attempt2.json` (raw SHA-256
`1DEB0148450A0F430DAB8668CB11FC9F3AD4FF56CC5D809AF2348CC20DBE9797`).
Its minimized request SHA-256 is
`50DE63075B898F16D5C733F6FF3726B3029E22ACF4E41040784D6971873CE04A`.

The v2 harness compared unlike layers:

- expected SHA-256
  `9580542F7FB69CCADFA63B4EA34A5D5363C4D5EC35FDA88E46135DEC9EA85780`
  was the clean oracle's canonical `PCB-RUNNER-RESPONSE-0.2` record; while
- actual SHA-256
  `57DC76AFCF4F3C97150BABAAE525D94F0C624B978A59C13E53DAA7F17B023D06`
  was the accepted batch surface's canonical `B1-AUDITED-DECISION-0.4`
  envelope containing that record under `sealed_response`.

The bytes therefore differed by required envelope structure, not by semantic
result. The correction separates two obligations:

1. compare concurrent physical bytes with cached one-record isolated accepted
   `rr_batch.py` bytes, with an explicit non-semantic provenance statement;
2. independently parse and canonical-validate each actual audited 0.4 line,
   project `sealed_response` through clean-room JCS+LF, and compare it exactly
   with `FixtureOracle.expected_record(raw)`.

The v2 receipt remains stopped evidence. It cannot support either a CUT
divergence claim or the corrected concurrency claim.
