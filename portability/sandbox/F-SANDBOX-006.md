# F-SANDBOX-006 — non-finite Docker metadata prevents receipt emission

Status: corrected by fresh F-SANDBOX-6; awaiting fresh refutation.

The mocked `docker version --format '{{json .}}'` probe exited 0 with empty
stderr and this exact 50-byte stdout value:

```json
{"Server":{"Os":"linux"},"Client":{"Version":NaN}}
```

Its SHA-256 is
`2a02ee19d39d07a6e21ca95a13db17f63c1d7a783f64e978098cf29d765ceb36`.
Python's permissive default JSON decoder admitted `NaN`; the later host
receipt included `client_version=nan`, and canonical emission raised
`ValueError`. No receipt was emitted. The finite-overflow spelling `1e309`
reproduced the same escape with a 52-byte payload whose SHA-256 is
`7d1bedaf4b0f69b5eba100fdb2833c9f51f82bdc19dd8afa81da0d346a36a75b`.

The correction makes the Docker-version decoder finite-only at every nesting
depth. It rejects `NaN`, positive/negative infinity constants, and finite
syntax that overflows to infinity, translating each to `DockerVersionError`.
It also rejects duplicate object members instead of silently collapsing
untrusted metadata. The exact host flow now emits a fully bound canonical
`INFRA_UNAVAILABLE` receipt with exit 2 and the probe stream hashes; image
build and container creation are not reached.

Regressions cover both minimized payloads, nested non-finite values, duplicate
root and nested members, malformed nesting, and finite/string neighbors.
F-SANDBOX-003 through F-SANDBOX-005 remain exercised by the complete suite.
