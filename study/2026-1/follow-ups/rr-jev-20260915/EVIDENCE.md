# Evidence supplement

Start with [ADDENDUM.md](ADDENDUM.md). The two `rr-jev-*` directories retain the
original scientific files byte-for-byte. `rr-source/` supplies the 59 RR source
files bound by both experiment freezes, plus the repository license. Source
identity is tied to bytes, not to the older worktree's Git HEAD.

`MANIFEST.json` records each supplied file's SHA-256 and length, both freezes,
and each source file's comparison with the original published archive. It
excludes itself to avoid a self-referential hash. The separately distributed
`SHA256SUMS.txt` binds the supplement archive and its manifest. Checksums detect
changes; they do not authenticate the experiment or establish scientific truth.

Run with Python 3.10 or later, from any directory:

```text
python -B /path/to/rr-jev-20260915/verify.py
```

This uses only the standard library, without network access or credentials. It
checks the manifest, both freezes, the recorded request and response bank, model
identifiers, semantic gate, headline totals and release-decision parity. It does
not call TypeSafe or rerun the RR engine. The original author-separated audits
contain the fuller receipt/presentation checks; this packaging verifier is not
another independent replication.

The original collection scripts are archival provenance. They retain historical
absolute Windows paths and are not a portable, one-command live rerun. The raw
full VitaminC test file is not included; the selected rows are included. The
protocol records the upstream revision and full-file hash. Changing paths or
collecting new model responses would be a new run, not a reproduction of these
frozen inference outcomes.

The five omitted local operational files are `credential.ps1`,
`authentication-block.json`, `credential-verification.json`,
`CREDENTIAL-AMENDMENT.md`, and `CREDENTIAL-REVIEW.md` from the VitaminC folder.
The report's credential discussion remains historical; these files and any
stored credential are outside the scientific supplement. Its rejected discovery
request preceded all judgment POSTs; scientific selection, thresholds and
collection budget were unchanged.

The supplement is separate from the published study DOI
[10.5281/zenodo.22492561](https://doi.org/10.5281/zenodo.22492561)
and the software concept DOI
[10.5281/zenodo.22035952](https://doi.org/10.5281/zenodo.22035952).
No existing DOI metadata or archive is replaced by this update.
