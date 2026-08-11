# F-MATRIX-011 — new workflow pinned actions to the deprecated Node20 runtime

Status: **RESOLVED locally.** Correction retained and covered by two
consecutive 44/44 focused passes. No hosted run has occurred. This lane is
treatment-exposed.

## Evidence

The proposed workflow pinned these otherwise immutable commits:

```text
actions/checkout@11d5960a326750d5838078e36cf38b85af677262
actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
```

Each commit's official `action.yml` declares `runs.using: node20`. GitHub's
official Node20 deprecation notice says hosted runners began defaulting to
Node24 on 2026-06-16 and that Node20 will be removed later in fall 2026:

<https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/>

That makes the new workflow time-bounded before its first run. The existing
`actions/setup-python` v6 commit already declares Node24 and did not need an
unrelated version chase.

## Local correction

The workflow now uses exact official release commits whose own manifests
declare `runs.using: node24`:

- checkout v7.0.1:
  `3d3c42e5aac5ba805825da76410c181273ba90b1`
- upload-artifact v7.0.1:
  `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
- download-artifact v8.0.1:
  `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`

Primary release and manifest evidence:

- <https://github.com/actions/checkout/releases/tag/v7.0.1>
- <https://raw.githubusercontent.com/actions/checkout/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml>
- <https://github.com/actions/upload-artifact/releases/tag/v7.0.1>
- <https://raw.githubusercontent.com/actions/upload-artifact/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a/action.yml>
- <https://github.com/actions/download-artifact/releases/tag/v8.0.1>
- <https://raw.githubusercontent.com/actions/download-artifact/3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c/action.yml>

The used inputs remain present in the new manifests: checkout retains
`persist-credentials`; upload retains `name`, `path`, `if-no-files-found`, and
`retention-days`; download retains `pattern`, `path`, and `merge-multiple`.
Every runner scheduled by this workflow is GitHub-hosted. The Node24
incompatibility with macOS 13.4 and older does not affect the plan because the
retired `macos-13` rows remain unscheduled evidence-only rows.

## Regression boundary

The workflow test now requires the exact four-action commit set, not merely a
40-hex shape. This prevents a stale but syntactically pinned runtime from
passing local validation. Hosted execution is still required to prove the
actions operate together on the requested runners.
