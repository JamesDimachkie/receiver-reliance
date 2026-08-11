# F-LIVE-001 — byte reads were mislabeled as W pause/write partitions

Status: **corrected and freshly refuted**. This was a credible live-harness
coverage defect at discovery; it was not an accepted-implementation
divergence. Found by fresh R-LIVE on 2026-08-10.

## Current adjudication

The correction now expands the complete first-response `W <= 2` domain into
812 acknowledgement-driven trials on each real transport: the unsplit write
and every split `[0,k),[k,812)` for `1 <= k < 812`. Each trial pauses the
reader until the writer reports its completed real prefix write, reads exactly
that prefix, and acknowledges writer resumption before the suffix may be
issued. The corrected schedule has SHA-256
`BB701FCFE56C79FFD15603E8825088325304F9B233C4A003BF4A5E41642A087A`.

A current two-replay run on both `pipe` and `socketpair` reports 812 W
partitions, 812 pauses, 812 resumes, 812 write-boundary acknowledgements, 811
forced short writes, zero unplanned OS short writes, and 812 writer-resume
acknowledgements. Its final acknowledgement transcript has SHA-256
`80B4FA40EC2BEA9EC4EECCC88827C79361CE6E1469A5BCB89164DFC36B2B219A`.
The focused live suite originally closed this finding at 11/11 tests, and
fresh R-LIVE-2 returned no defect. Therefore no live correction or custody
transfer remains open for F-LIVE-001. The terminal suite is 29/29 after the
distinct F-LIVE-002 through F-LIVE-008 corrections.
None of those later corrections changes this finding's W-domain adjudication
or hashes.

The minimized replay and hashes below are retained as discovery-time evidence;
they do not describe the current schedule.

## Minimized schedule at discovery

At discovery, `portability/live/schedules/pause_every_byte.ndjson` had SHA-256
`C719ABA88E8ACBA7DD7481251C967BDC38816D265DFFF283E1C7A9113B9546F9`
and contained only:

```json
{"step":0,"action":"write","bytes_b64":"eAo=","barrier":"request-written"}
{"step":1,"action":"pause","barrier":"reader-paused"}
{"step":2,"action":"resume","barrier":"reader-resumed"}
{"step":3,"action":"read","range":[0,812],"barrier":"each-byte-boundary"}
{"step":4,"action":"close_half","barrier":"input-half-closed"}
```

Observed on both real transports:

```text
actions=[write,pause,resume,read,close_half]
pause_count=1
resume_count=1
read_actions=1
read_bytes=812
backpressure_observed=false
child_events=[]
```

The controller implements the read range as 812 one-byte `read`/`recv` calls.
That proves receiver-side read slicing after bytes may already be buffered. It
does not pause/resume at every first-response byte range and does not force or
observe sender-side write partitions/short writes at every W position.

## Misleading passing evidence at discovery

Two replays reported PASS and byte stability for each transport:

```text
pipe stdout: 812 bytes, SHA-256 0C16B0331892021CED59680FCF730D1EE510EB34B670E400B9935121CD2A11C6
socketpair stdout: 812 bytes, same SHA-256
stderr: empty, SHA-256 E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855
ack SHA-256: DDE5875643FF25692C239B682B505C65161836633507E8364E02827689EC7F79
returncode: 0
byte_boundaries: 812
backpressure_observed: false
```

At discovery, all ten focused tests passed because they asserted
`byte_boundaries == 812`, not actual repeated pause/resume or sender
write-partition coverage. The README's
then-current claim that the compact read range represented W was therefore
unsupported.

The proposed correction at discovery was to give a fresh F-series live author
custody and require each W boundary to become an acknowledgement-driven
schedule state (or to narrow the claimed domain truthfully), followed by a
fresh R-LIVE pass. That correction and refutation are complete, as recorded in
the current adjudication above.
