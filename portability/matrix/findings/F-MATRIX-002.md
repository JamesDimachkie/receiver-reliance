# F-MATRIX-002 — receipt-supplied command manifest can self-authorize PASS

Status: corrected locally by fresh F-MATRIX-2 before the first authorized
push; awaiting author-separated refutation. No hosted run has occurred.

## Minimized evidence

For any runnable normative entry, start with an otherwise structurally valid
receipt and set:

```json
{"outcome":"PASS","commands_planned":[],"commands":[]}
```

Before correction,
`_receipt_validation_error(row, entry)` returned `None`. A summary containing
that row could therefore exit zero because validation compared only the two
receipt-supplied array lengths. The checked-in command manifest was never
consulted.

## Why this is invalid

Both arrays are attacker- or corruption-controlled artifact data. Their
agreement proves nothing about whether the command sequence declared in
`plan.json` ran. The same trust error permits reordered, substituted,
duplicated, or omitted planned commands when the result array is changed to
match.

## Local correction

- `commands_planned` now stores the stable, checked-in command templates;
  platform-specific interpreter and temporary paths remain in each executed
  command record.
- Summary validation requires exact command identity and order equality with
  `planned_commands(plan, entry)` before accepting any outcome.
- A `PASS` additionally requires executed command IDs in full manifest order;
  divergence receipts require the executed prefix to follow manifest order.
- Regressions cover empty, reordered, substituted, duplicated, and omitted
  command manifests.
