# F-PORTABLE-002 — gate summaries accepted contradictory child output

Status: fixed in hardening wave W4. Deep-scan finding
`csf_9ef46cbea002b12d86653e73`.

## Evidence

Most gate decisions searched decoded output for a success substring. The raw
boundary lane parsed only the final JSON line. A zero-exit child could emit
failure evidence, invalid UTF-8, or an earlier contradictory record and still
place an accepted marker at the end.

## Repair

Every lane now has a closed output grammar. Script summaries must be one exact
UTF-8 line, unittest lanes must have one matching success trailer and no
failure trailer, and unexpected stderr is rejected. The raw-boundary lane
requires exactly one duplicate-free JSON line with `PASS`, zero divergences,
no first divergence, and a positive executed-case count. Output is size
bounded before decoding; malformed UTF-8, NUL, bare CR, extra lines, duplicate
members, trailing text, and contradictory evidence all fail the gate.
