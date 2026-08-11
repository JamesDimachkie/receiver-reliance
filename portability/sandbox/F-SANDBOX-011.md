# F-SANDBOX-011 — container image identity was not bound to the build

Status: corrected by fresh F-SANDBOX-11; awaiting fresh refutation.

The exact mocked host flow let image inspect identify the freshly built image
as `sha256:` plus 64 lowercase `c` characters, while the otherwise hardened
container inspect reported root `Image` as `sha256:` plus 64 lowercase `b`
characters. `Config.Image` retained the expected deterministic tag. The
selected projection discarded both container image fields, so the host started
the container and admitted a complete forged inner PASS receipt.

The canonical container-inspect witness is 1,041 bytes with SHA-256
`6cfaa3b5ab7d0c0370adc53c4321d69d738a65d62334c645d076be70871f0cb0`.
The admitted inner receipt has SHA-256
`eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55`.

Docker Engine exposes root `Image` and `Config.Image` separately in the
container-inspect representation; `Config.Image` is the image reference used
to create the container. The official Engine API documents that field as the
image name/reference used for creation:
<https://docs.docker.com/reference/api/engine/version/v1.46/>.

The correction binds one image chain across build, image inspect, create,
container inspect, and start. Image inspect is queried with the exact
Dockerfile-derived tag and must return one lowercase `sha256:` plus 64-hex ID.
The create command consumes the same tag. Before start, container root `Image`
must equal that inspected ID and `Config.Image` must equal the tag. Both image
and container inspect decoders now reject invalid UTF-8/JSON, duplicate members
at any depth, non-finite numbers, non-array roots, non-object elements, and
zero or multiple results.

Direct and full mocked-flow regressions reproduce the exact witness, prove it
cannot reach `docker start`, and cover missing, null, wrongly typed,
case-mutated, prefix-mutated, digest-mutated, short, long, and different
image-ID/tag forms. The valid neighbor proves the same tag is present in the
build, image-inspect, and create commands, while the inspected image ID is
retained in the host receipt and required by container inspect. Prior
F-SANDBOX-003 through F-SANDBOX-010 controls remain in the complete suite.
