# F-SANDBOX-022 — a foreign Windows UNC path was accepted as a POSIX source

Status: corrected by fresh F-SANDBOX-22; first correction REFUTED by fresh
refuter R-SANDBOX-22 on two axes, both repaired; re-refutation of the
repaired state required.

`_repository_source_for_host` validated the rendered string instead of the path
dialect. On `Linux` and `Darwin` it rendered `resolved.as_posix()` and required
only a leading `/`. A `PureWindowsPath` renders a UNC root as a POSIX-looking
double-slash spelling, so a foreign Windows object satisfied that test.

The minimized witness is
`PureWindowsPath(r"\\server\share\receiver-reliance")`, which reports
`is_absolute()` true and an `as_posix()` of `//server/share/receiver-reliance`.
Pre-fix, `_repository_source_for_host(witness, "Linux")` and the same call with
`"Darwin"` each returned `//server/share/receiver-reliance` instead of failing
closed, so a foreign path would have been rendered into the `src=` fragment of
a POSIX host's `--mount` plan. That contradicts the docstring guarantee that
platform rendering never pretends a foreign path is resolvable on the current
host, and contradicts F-SANDBOX-021's claim that foreign path dialects are
rejected. `PurePosixPath("//srv/receiver-reliance")` under `Linux` was accepted
on the same rendering path. The Windows branch carried the mirror-image
weakness: it tested only the drive or UNC anchor of `str(resolved)`, never the
dialect of the object.

The correction validates the dialect before rendering. `Linux` and `Darwin`
require a `PurePosixPath` instance and `Windows` requires a `PureWindowsPath`
instance; concrete `PosixPath` and `WindowsPath` qualify by inheritance, so the
current host's real resolved repository identity is unaffected. The POSIX
branch additionally refuses a rendered source beginning with `//`, which is the
implementation-defined POSIX root and the exact laundering shape of the
witness. The prior absolute check, the Windows drive-or-UNC-anchor requirement,
the comma rejection, and the unsupported-host error are unchanged, and every
new rejection is a `RuntimeError` in the function's existing style. One
behavior is strengthened rather than repaired: a `PurePosixPath` on a `Windows`
host already failed closed on the missing drive or UNC anchor and now fails on
the dialect, so the reported reason matches the defect class.

Two regression tests were added.
`test_f_sandbox_022_foreign_path_dialect_witness_fails_closed` binds the
minimized witness under `Linux` and `Darwin`, a Windows drive object under
`Linux`, a POSIX object under `Windows`, and the double-slash root
`PurePosixPath("//srv/receiver-reliance")` under `Linux`, asserting the dialect
and double-slash messages rather than a bare `RuntimeError`.
`test_f_sandbox_022_native_dialects_keep_exact_spellings` holds preservation: a
POSIX absolute source under `Linux`, and Windows drive and UNC sources under
`Windows`, each returned in its exact spelling, with
`intended_repository_source()` still returning this host's resolved native
spelling. Against the pre-fix body the first test fails with three entries —
`RuntimeError not raised` for both witness subtests and a message mismatch on
the Windows drive object — while the second passes before and after, as a
preservation guard should.

No existing test pinned the defective acceptance, so none required correction.
`test_repository_source_rendering_is_platform_exact` already rejected a Windows
drive object under `Linux` and `Darwin`, because that spelling has no leading
slash, but it never exercised a Windows UNC object against a POSIX host and
asserted the UNC spelling only as a valid `Windows` case. It passes unchanged.

## R-SANDBOX-22 refutation rounds

Fresh refutation ran repeated rounds against this correction; every proven
defect was repaired and pinned. Round one:

- **Interpreter-divergent bare-UNC acceptance.** CPython 3.14 delegates
  `PureWindowsPath.is_absolute()` to `ntpath.isabs()`, which treats any
  leading double backslash as absolute, and reports a bare `\\` introducer
  as a drive. `_repository_source_for_host(PureWindowsPath("//"),
  "Windows")` therefore returned the meaningless two-backslash string on
  3.14.5 while 3.12.10 rejected it. The Windows branch now validates UNC
  anatomy explicitly: a double-backslash source must name both a server
  and a share, so bare (`\\`) and shareless (`\\server`, `\\server\`)
  introducers fail closed on every supported interpreter, while complete
  shares, `\\?\`-extended, and device forms keep their exact spellings.
- **Quote-poisoned mount plans.** An accepted native source containing a
  double quote (e.g. `PurePosixPath('/srv/a"b')`) rendered into a
  `--mount` value that Docker's strict Go CSV reader rejects
  (`bare " in non-quoted-field`), producing an unusable plan instead of a
  fail-closed error. A double-quote rejection now sits beside the
  existing comma rejection, applied after either platform branch.

Round two proved the first anatomy check too weak and the mount-metachar
guard incomplete, all repaired:

- **Component-level UNC anatomy.** `strip("\\")` let a whitespace-only
  share (`\\s\ `), an empty share component with descendants (`\\s\\x`),
  and a whitespace-only server (`\\ \share`) through. The anchor's first
  two components are now taken from `source[2:].split("\\")` and each must
  be non-whitespace; interior spaces in real server or share names remain
  legal.
- **Whitespace and newline mount values.** Docker splits `--mount` on CSV
  records and trims each field value, rejecting a value whose trimmed
  spelling differs. An accepted source with a trailing space
  (`/srv/a `) or a newline (`/srv/a\nb`) therefore produced an unusable
  plan. Newlines and leading/trailing whitespace now fail closed beside
  the comma and quote guards; interior whitespace is preserved exactly.

Round three proved the component anatomy blind to the extended-UNC
namespace and the metachar policy both incomplete and over-broad, all
repaired:

- **Extended-UNC anatomy.** `\\?\UNC\s\ ` validated the namespace prefix
  (`?`, `UNC`) instead of the real components, accepting a whitespace-only
  real share; `\\?\UNC\ \share` and `\\?\UNC\s\\x` passed the same way.
  When the anchor's first two components are `?` or `.` followed by
  case-insensitive `UNC`, the validated server and share now come from the
  two components after that prefix. The `\\?\C:\...` extended-drive and
  device forms are unaffected.
- **NUL.** An embedded NUL survived every guard yet no operating-system
  argv can carry it (`ValueError: embedded null character` before Docker
  even parses); it now fails closed first.
- **Over-rejection repaired.** A lone interior carriage return is ordinary
  field data under Go's CSV grammar and legal in POSIX filenames, and the
  information separators U+001C..U+001F are whitespace to Python but not
  to Go's `TrimSpace`. The newline guard now rejects only line feeds, and
  the edge check tests the first and last character with Python's
  `isspace()` minus those four separators — matching Docker's actual
  trimming instead of Python's broader character policy. Edge carriage
  returns and edge NBSP still fail closed (both runtimes trim them).

Round four proved one remaining representability axis, repaired:

- **Surrogate-escaped sources.** A real POSIX filename with non-UTF-8
  bytes reaches Python as `surrogateescape` text (e.g.
  `/srv/a\udcff`); the renderer returned it, after which strict UTF-8
  plan hashing raises `UnicodeEncodeError` and Go's JSON would coerce the
  bytes to U+FFFD, silently changing the mount identity. The source must
  now encode to strict UTF-8 or it fails closed
  (`...not strictly UTF-8 encodable`), while ordinary non-ASCII UTF-8
  spellings such as `/srv/café` are preserved exactly.

`test_f_sandbox_022_unc_anatomy_and_mount_metachars_fail_closed` pins all
of it: twelve malformed UNC spellings (message-bound to the anatomy or
absolute gate, since 3.12 and 3.14 reject at different declared gates),
four complete-anatomy preservations including lowercase `\\?\unc\` (a
share-root path renders drive plus root, hence its trailing separator),
the surrogate, NUL, double-quote, comma, line-feed, and edge-whitespace
rejections (trailing space, CR, and NBSP) across both branches, and exact
preservation of interior space, interior CR, trailing U+001C, and
non-ASCII UTF-8.

Post-fix `python -B portability/sandbox/test_sandbox.py` runs 76 tests with
no failures on CPython 3.12.10 and on CPython 3.14.5; the pre-fix count was
73 on both, and the first correction's count was 75. Local Docker remains
`INFRA_UNAVAILABLE`, so this correction rests on static checks and no
hosted Linux daemon evidence exists.
