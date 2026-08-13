# Author-separated second implementation

`rr2.py` is a standard-library-only interpreter of the public 0.2 and 0.3
contracts. Its raw ABI is a bounded, iterative total wire machine: JSON
containers, JCS serialization, and NFC traversal use explicit stacks, and
unbounded number tokens are classified lexically before any host integer
conversion. It does not import or inspect either frozen implementation.

Run one semantic request through the raw ABI:

```powershell
python -B second-implementation/cli.py execute < request.json
```

Run the author-separated fixture and regression gate:

```powershell
python -B second-implementation/test_cross.py
```

Run the deterministic raw-totality black-box preflight (deep containers and
host numeric-conversion boundaries):

```powershell
python -B second-implementation/bounded_preflight.py
```

The runtime authenticates the supplemental contract by its externally
accepted raw SHA-256, then derives and verifies the declared byte length plus
raw SHA-256 for the primary contract, sanitized packet, and shared projection
before their JSON is parsed or admitted to reference resolution. All four
same-length authority mutations fail closed.

Verify receipt bindings, the standard-library import closure, and the exact
four-file runtime authority read set:

```powershell
python -B second-implementation/verify_artifacts.py
```

Receipted commands add `-I -B -X pycache_prefix=<unique-empty-temp-root>`.
Every child CLI probe receives its own system-temporary prefix and fails if a
bytecode artifact appears.

The coverage campaign is gated on a fresh-context refuter returning no new
evidence. Its small steering smoke requires schema, classification, dispatch,
and predicate helper coverage, and records rejection of an `_execute`-only
falsifier, but is not a house-scale campaign receipt.
