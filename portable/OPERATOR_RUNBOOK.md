# Operator runbook

## Deployment shape

Deploy the extracted bundle as a read-only directory owned by the service
account. Run it as an unprivileged local process behind the host application's
process supervisor. The default long-lived boundary is anonymous stdin/stdout;
the bundle opens no network listener and needs no shell, database, secret, or
writable repository.

Do not copy individual Python files between versions. A deployment unit is the
complete manifest-bound directory.

## Admission and startup

From the extracted root, using the exact interpreter that will run the service:

```text
python -B portable/verify_bundle.py
python -B portable/gate.py --manifest-only
python -B portable/gate.py
```

All three commands must exit 0. A digest, length, path, authority-pin, import,
or regression failure blocks startup. Never regenerate `MANIFEST.json` on the
target host; regeneration creates a different candidate, not a repair.

Start the sidecar only after admission. Configure the supervisor to provide
binary pipes, close stdin during shutdown, wait a bounded grace period, and
then terminate the process if it does not exit. Do not automatically replay an
in-flight request after timeout, EOF, protocol poison, or child death. The host
must reconcile the request by its own idempotency/effect policy before retrying.

## Health and readiness

- **Artifact health:** `portable/verify_bundle.py` exits 0.
- **Runtime readiness:** the sidecar completes its versioned transport
  handshake and accepts a known non-effecting probe supplied by the adopter.
- **Operational readiness:** the process is alive, stderr remains empty for the
  engine channel, and the supervisor has no unresolved in-flight request.

Process liveness alone is not readiness. A response is accepted only when its
transport version, sequence, and complete request-byte digest match the active
request.

## Failure handling

| Failure | Required host action |
|---|---|
| bundle verification or authority-pin failure | keep instance out of service; restore an authenticated complete bundle |
| preflight `REJECTED_INVALID` | record a detected host-evidence defect; do not invoke the engine |
| preflight `INSUFFICIENT_EVIDENCE` | abstain and obtain the missing native observation; do not count it as pass or detection |
| sidecar malformed/stale/duplicate/unbound output | poison and terminate that session; do not reuse queued bytes |
| timeout, EOF, broken pipe, or child death | terminate/reap; reconcile externally; never automatic replay |
| deterministic conformance divergence | remove the candidate from service and roll back the entire bundle |

## Resource containment

Run one bounded request at a time per sidecar process. Enforce the contract's
input/output ceilings before allocation, a host request deadline, and an
external memory/CPU/process limit appropriate to the deployment. The artifact
does not choose an operator's service-level objective. Optional process census
telemetry is diagnostic only and may not become a portability precondition.

## Observability

Keep engine stdout dedicated to protocol bytes. Capture supervisor lifecycle
events separately with at least: bundle manifest seal, runtime version, process
identifier, transport sequence, request digest, terminal state, elapsed time,
and whether any response was admitted. Never log raw requests by default; they
may contain host data. The artifact itself has no credential or telemetry
export channel.

## Upgrade and rollback

1. Stage the new bundle in a new read-only directory.
2. Authenticate its source commit/release, then run the admission commands.
3. Run the supported hosted matrix on that exact commit.
4. Drain old sidecars; do not move in-flight requests between processes.
5. Switch new traffic to the new directory.
6. Retain the previous authenticated bundle until the observation window ends.

Rollback is an atomic switch to the previous complete bundle plus fresh
sidecar processes. There is no artifact-owned persistent state or migration to
reverse. Host nonce/effect state remains the host's responsibility.
