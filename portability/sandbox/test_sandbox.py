#!/usr/bin/env python3
"""Stdlib-only static tests for the portability sandbox specification."""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import expanded_gate  # noqa: E402
import run_sandbox  # noqa: E402


FIXTURE_IMAGE_ID = "sha256:" + "c" * 64
DEFAULT_CLEANUP = object()
FROZEN_WINDOWS_REPOSITORY_SOURCE = (
    r"C:\Users\james\New folder\receiver-reliance-worktrees\portability"
)


def expected_image_tag() -> str:
    dockerfile_sha = run_sandbox.sha256((HERE / "Dockerfile").read_bytes())
    return f"receiver-reliance-portability-sandbox:{dockerfile_sha[:12]}"


def synthetic_pass_receipt() -> dict[str, object]:
    boundary: dict[str, object] = {
        "uid": 65532,
        "gid": 65532,
        "hostname": run_sandbox.EXPECTED_HOSTNAME,
        "environment_hostname": run_sandbox.EXPECTED_HOSTNAME,
        "capabilities": {
            "CapEff": "0000000000000000",
            "CapPrm": "0000000000000000",
            "CapBnd": "0000000000000000",
            "CapAmb": "0000000000000000",
        },
        "no_new_privileges": 1,
        "seccomp_mode": 2,
        "root_read_only": True,
        "repo_read_only": True,
        "tmp": {
            "fs_type": "tmpfs",
            "limit_bytes": 256 * 1024 * 1024,
            "options": ["nodev", "noexec", "nosuid", "rw", "size=262144k"],
        },
        "network_interfaces": ["lo"],
        "environment_names": ["HOME", "LANG", "PATH", "PYTHON_GPG_KEY"],
        "secret_like_environment_names": [],
        "cgroup": {
            "version": 2,
            "cpu_max": "200000 100000",
            "cpu_count": 2.0,
            "memory_max_bytes": 4 * 1024**3,
            "memory_swap_max_bytes": 0,
            "pids_max": 256,
        },
    }
    commands: list[dict[str, object]] = []
    for index, spec in enumerate(expanded_gate.GATES):
        commands.append(
            {
                "gate_id": spec.gate_id,
                "cwd": spec.cwd,
                "argv": list(spec.argv),
                "exit_code": 0,
                "timed_out": False,
                "timeout_seconds": expanded_gate.COMMAND_TIMEOUT_SECONDS,
                "stdout_sha256": f"{index + 1:064x}",
                "stdout_bytes": index + 1,
                "stderr_sha256": run_sandbox.EMPTY_SHA256,
                "stderr_bytes": 0,
                "elapsed_ms": index,
                "resources": {
                    "user_cpu_us": index,
                    "system_cpu_us": index,
                    "voluntary_context_switches": index,
                    "involuntary_context_switches": index,
                    "children_max_rss_kib": index,
                },
                "observed": copy.deepcopy(
                    run_sandbox.EXPECTED_OBSERVED[spec.gate_id]
                ),
            }
        )
    receipt: dict[str, object] = {
        "schema": "receiver-reliance/sandbox-container-receipt-1",
        "treatment_exposed": True,
        "status": "PASS",
        "environment": {
            "os": "Linux",
            "release": "fixture",
            "kernel": "fixture",
            "machine": "x86_64",
            "python_implementation": "CPython",
            "python_version": "3.14.1",
            "python_build": ["main", "fixture"],
            "python_compiler": "fixture",
            "python_executable": "/usr/local/bin/python",
            "python_build_flags": {
                "CONFIG_ARGS": "fixture",
                "Py_DEBUG": 0,
                "Py_GIL_DISABLED": 0,
            },
            "word_size_bits": 64,
            "byte_order": "little",
            "locale_encoding": "UTF-8",
            "filesystem_encoding": "utf-8",
        },
        "boundary": boundary,
        "commands": commands,
        "deterministic_projection_sha256": "0" * 64,
    }
    projection = expanded_gate._stable_projection(boundary, commands)
    receipt["deterministic_projection_sha256"] = run_sandbox.sha256(
        run_sandbox.canonical_bytes(projection)
    )
    return receipt


def encoded_receipt(receipt: dict[str, object]) -> bytes:
    return run_sandbox.canonical_bytes(receipt) + b"\n"


def historical_pass_receipt_before_f015() -> dict[str, object]:
    """Recreate the exact pre-F015 synthetic PASS used by older findings."""

    receipt = synthetic_pass_receipt()
    boundary = receipt["boundary"]
    commands = receipt["commands"]
    if not isinstance(boundary, dict) or not isinstance(commands, list):
        raise AssertionError("synthetic receipt fixture lost expected shape")
    projection = expanded_gate._stable_projection(boundary, commands)
    projected_boundary = projection["boundary"]
    if not isinstance(projected_boundary, dict):
        raise AssertionError("stable projection fixture lost expected shape")
    projected_boundary.pop("hostname")
    projected_boundary.pop("environment_hostname")
    boundary.pop("hostname")
    boundary.pop("environment_hostname")
    receipt["deterministic_projection_sha256"] = run_sandbox.sha256(
        run_sandbox.canonical_bytes(projection)
    )
    return receipt


def reconciled_pass_receipt() -> dict[str, object]:
    """Return a structurally valid PASS bound to current effective Config.Env."""

    receipt = synthetic_pass_receipt()
    boundary = receipt["boundary"]
    commands = receipt["commands"]
    if not isinstance(boundary, dict) or not isinstance(commands, list):
        raise AssertionError("synthetic receipt fixture lost expected shape")
    boundary["environment_names"] = list(run_sandbox.EXPECTED_ENVIRONMENT_NAMES)
    boundary["secret_like_environment_names"] = []
    reproject_receipt(receipt)
    return receipt


def reproject_receipt(receipt: dict[str, object]) -> None:
    boundary = receipt["boundary"]
    commands = receipt["commands"]
    if not isinstance(boundary, dict) or not isinstance(commands, list):
        raise AssertionError("synthetic receipt fixture lost expected shape")
    projection = expanded_gate._stable_projection(boundary, commands)
    receipt["deterministic_projection_sha256"] = run_sandbox.sha256(
        run_sandbox.canonical_bytes(projection)
    )


def valid_docker_inspect(
    repository_source: str | None = None,
) -> dict[str, object]:
    """Return the selected effective config expected from the exact create plan."""

    source = (
        run_sandbox.intended_repository_source()
        if repository_source is None
        else repository_source
    )

    return {
        "Id": "a" * 64,
        "Image": FIXTURE_IMAGE_ID,
        "Path": run_sandbox.EXPECTED_PROCESS_PATH,
        "Args": list(run_sandbox.EXPECTED_PROCESS_ARGS),
        "Config": {
            "Image": expected_image_tag(),
            "Hostname": run_sandbox.EXPECTED_HOSTNAME,
            "NetworkDisabled": False,
            "User": "65532:65532",
            "WorkingDir": "/repo",
            "Entrypoint": list(run_sandbox.EXPECTED_ENTRYPOINT),
            "Cmd": list(run_sandbox.EXPECTED_COMMAND),
            "Env": [
                f"{name}={value}"
                for name, value in run_sandbox.EXPECTED_EFFECTIVE_ENVIRONMENT.items()
            ],
            "Volumes": None,
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "AutoRemove": False,
            "OomKillDisable": False,
            "Init": False,
            "NetworkMode": "none",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges=true"],
            "NanoCpus": 2_000_000_000,
            "Memory": 4 * 1024 * 1024 * 1024,
            "MemorySwap": 4 * 1024 * 1024 * 1024,
            "PidsLimit": 256,
            "ShmSize": 16 * 1024 * 1024,
            "Tmpfs": {
                "/tmp": "rw,noexec,nosuid,nodev,size=268435456,mode=1777"
            },
            "Binds": None,
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": source,
                    "Target": "/repo",
                    "ReadOnly": True,
                    "BindOptions": {
                        "Propagation": (
                            run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION
                        )
                    },
                }
            ],
            "Devices": None,
            "DeviceRequests": None,
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "",
            "UsernsMode": "",
            "PortBindings": {},
            "PublishAllPorts": False,
            "Privileged": False,
            "ReadonlyPaths": [],
            "MaskedPaths": [],
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": source,
                "Destination": "/repo",
                "Mode": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_MODE,
                "RW": False,
                "Propagation": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
            }
        ],
    }


def historical_inspect_before_f013(
    raw: dict[str, object],
) -> dict[str, object]:
    """Remove fields added to the fixture after the preserved F003-F012 replays."""

    historical = copy.deepcopy(raw)
    historical.pop("Mounts", None)
    config = historical["Config"]
    host = historical["HostConfig"]
    if not isinstance(config, dict) or not isinstance(host, dict):
        raise AssertionError("historical inspect fixture lost object shape")
    config["Env"] = ["HOME=/tmp"]
    config.pop("Hostname")
    config.pop("NetworkDisabled")
    for key in ("AutoRemove", "OomKillDisable", "Init"):
        host.pop(key)
    mounts = host["Mounts"]
    if not isinstance(mounts, list) or not isinstance(mounts[0], dict):
        raise AssertionError("historical inspect mount fixture lost object shape")
    mounts[0].pop("Consistency", None)
    mounts[0].pop("BindOptions")
    mounts[0]["Source"] = "/not-recorded"
    return historical


def set_historical_unbound_mount_source(raw: dict[str, object]) -> None:
    """Restore the exact pre-F017 source used by historical witnesses."""

    host = raw["HostConfig"]
    if not isinstance(host, dict):
        raise AssertionError("historical inspect fixture lost HostConfig shape")
    mounts = host["Mounts"]
    if not isinstance(mounts, list) or not isinstance(mounts[0], dict):
        raise AssertionError("historical inspect fixture lost mount shape")
    mounts[0]["Source"] = "/not-recorded"


def remove_selected_mount_source(selected: dict[str, object]) -> None:
    """Project a selected fixture back to its exact pre-F017 shape."""

    mounts = selected["mounts"]
    if not isinstance(mounts, list) or not isinstance(mounts[0], dict):
        raise AssertionError("historical selected fixture lost mount shape")
    mounts[0].pop("source")
    mounts[0].pop("propagation")
    selected.pop("effective_mounts", None)


def remove_request_bind_options(raw: dict[str, object]) -> None:
    """Project a raw fixture back to its exact pre-F019 request shape."""

    host = raw["HostConfig"]
    if not isinstance(host, dict):
        raise AssertionError("historical inspect fixture lost HostConfig shape")
    mounts = host["Mounts"]
    if not isinstance(mounts, list) or not isinstance(mounts[0], dict):
        raise AssertionError("historical inspect fixture lost mount shape")
    mounts[0].pop("BindOptions")


def add_historical_request_consistency(raw: dict[str, object]) -> None:
    """Restore the explicit-empty member present in preserved old witnesses."""

    host = raw["HostConfig"]
    if not isinstance(host, dict):
        raise AssertionError("historical inspect fixture lost HostConfig shape")
    mounts = host["Mounts"]
    if not isinstance(mounts, list) or not isinstance(mounts[0], dict):
        raise AssertionError("historical inspect fixture lost mount shape")
    mounts[0]["Consistency"] = ""


def exercise_host_container_result(
    payload: bytes,
    *,
    container_exit: int = 0,
    raw_inspect: dict[str, object] | None = None,
    image_inspect: dict[str, object] | None = None,
    image_inspect_stdout: bytes | None = None,
    container_inspect_stdout: bytes | None = None,
    created_stdout: bytes | None = None,
    call_trace: list[object] | None = None,
    cleanup_outcome: object = DEFAULT_CLEANUP,
) -> tuple[int, dict[str, object]]:
    completed = run_sandbox.subprocess.CompletedProcess
    docker_version = {
        "Client": {"Version": "fixture", "Os": "windows", "Arch": "amd64"},
        "Server": {"Version": "fixture", "Os": "linux", "Arch": "amd64"},
    }
    calls = [
        completed(
            ["docker", "version"],
            0,
            json.dumps(docker_version).encode("utf-8"),
            b"",
        ),
        completed(["docker", "build"], 0, b"build", b""),
        completed(
            ["docker", "image", "inspect"],
            0,
            image_inspect_stdout
            if image_inspect_stdout is not None
            else json.dumps(
                [
                    image_inspect
                    if image_inspect is not None
                    else {
                        "Id": FIXTURE_IMAGE_ID,
                        "Os": "linux",
                        "Architecture": "amd64",
                    }
                ]
            ).encode("utf-8"),
            b"",
        ),
        completed(
            ["docker", "create"],
            0,
            b"a" * 64 + b"\n" if created_stdout is None else created_stdout,
            b"",
        ),
        completed(
            ["docker", "inspect"],
            0,
            container_inspect_stdout
            if container_inspect_stdout is not None
            else json.dumps(
                [raw_inspect if raw_inspect is not None else valid_docker_inspect()]
            ).encode("utf-8"),
            b"",
        ),
        completed(["docker", "start"], container_exit, payload, b""),
    ]
    calls.append(
        completed(["docker", "rm"], 0, b"", b"")
        if cleanup_outcome is DEFAULT_CLEANUP
        else cleanup_outcome
    )
    emitted: list[dict[str, object]] = []

    def capture(receipt: dict[str, object], _output: Path | None) -> None:
        emitted.append(receipt)

    git_state = {
        "sha": "f" * 40,
        "branch": run_sandbox.EXPECTED_BRANCH,
        "clean": True,
        "status_sha256": "a" * 64,
        "baseline_ancestor": True,
    }
    with (
        mock.patch.object(run_sandbox, "_git_receipt", return_value=git_state),
        mock.patch.object(run_sandbox, "_host_profile", return_value={}),
        mock.patch.object(run_sandbox, "run", side_effect=calls) as mocked_run,
        mock.patch.object(run_sandbox, "_emit", side_effect=capture),
    ):
        exit_code = run_sandbox.main([])
    if call_trace is not None:
        call_trace.extend(mocked_run.call_args_list)
    if len(emitted) != 1:
        raise AssertionError(f"expected one host receipt, observed {len(emitted)}")
    return exit_code, emitted[0]


def exercise_docker_version_probe(
    payload: bytes,
) -> tuple[int, dict[str, object], list[object]]:
    """Run the exact host preflight flow with one untrusted version response."""

    probe = run_sandbox.subprocess.CompletedProcess(
        ["docker", "version"], 0, payload, b""
    )
    git_state = {
        "sha": "f" * 40,
        "branch": run_sandbox.EXPECTED_BRANCH,
        "clean": True,
        "status_sha256": "a" * 64,
        "baseline_ancestor": True,
    }
    emitted: list[dict[str, object]] = []
    with (
        mock.patch.object(run_sandbox, "_git_receipt", return_value=git_state),
        mock.patch.object(run_sandbox, "_host_profile", return_value={}),
        mock.patch.object(run_sandbox, "run", return_value=probe) as mocked_run,
        mock.patch.object(
            run_sandbox,
            "_emit",
            side_effect=lambda receipt, _output: emitted.append(receipt),
        ),
    ):
        exit_code = run_sandbox.main([])
    if len(emitted) != 1:
        raise AssertionError(f"expected one host receipt, observed {len(emitted)}")
    return exit_code, emitted[0], list(mocked_run.call_args_list)


class SandboxSpecTests(unittest.TestCase):
    def test_dockerfile_pins_manifest_digest_and_numeric_user(self) -> None:
        text = (HERE / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn(
            "python:3.14.1-slim-bookworm@sha256:"
            "5d17fc066275d26bb2ffe05bc89367dc665310200b5f4cfa8b294e97dc679bff",
            text,
        )
        self.assertIn("USER 65532:65532", text)
        self.assertIn(
            'ENTRYPOINT ["python", "-B", '
            '"/repo/portability/sandbox/expanded_gate.py"]',
            text,
        )
        self.assertIn("CMD []", text)

    def test_create_plan_contains_required_hardening(self) -> None:
        args = run_sandbox.docker_create_args("fixture:image")
        joined = "\n".join(args)
        for value in (
            "--read-only",
            "none",
            "ALL",
            "no-new-privileges=true",
            "65532:65532",
            "2.0",
            "4g",
            "256",
            "/tmp:rw,noexec,nosuid,nodev,size=268435456,mode=1777",
            "dst=/repo,readonly",
        ):
            self.assertIn(value, joined)
        self.assertNotIn("--env-file", args)
        self.assertNotIn("--privileged", args)
        self.assertEqual(args.count("--hostname"), 1)
        self.assertEqual(
            args[args.index("--hostname") + 1], run_sandbox.EXPECTED_HOSTNAME
        )
        self.assertEqual(
            args.count(f"HOSTNAME={run_sandbox.EXPECTED_HOSTNAME}"), 1
        )

    def test_only_repo_is_bound(self) -> None:
        args = run_sandbox.docker_create_args("fixture:image")
        self.assertEqual(args.count("--mount"), 1)
        mount = args[args.index("--mount") + 1]
        self.assertIn("dst=/repo", mount)
        self.assertIn(",readonly,", mount)
        self.assertTrue(mount.endswith(",bind-propagation=rprivate"))
        self.assertEqual(args[-1], "fixture:image")

    def test_repository_source_is_one_host_resolved_exact_identity(self) -> None:
        source = run_sandbox.intended_repository_source()
        resolved = run_sandbox.REPO.resolve(strict=True)
        expected = (
            str(resolved)
            if run_sandbox.platform.system() == "Windows"
            else resolved.as_posix()
        )
        self.assertEqual(source, expected)
        self.assertTrue(resolved.is_absolute())
        self.assertNotIn(",", source)

        image = "fixture:image"
        plan = run_sandbox._plan(image)
        self.assertEqual(plan["expected_repository_mount"]["source"], source)
        self.assertEqual(
            plan["expected_repository_mount"]["source_sha256"],
            run_sandbox.sha256(source.encode("utf-8")),
        )
        self.assertEqual(
            plan["expected_repository_mount"]["comparison"],
            run_sandbox.MOUNT_SOURCE_COMPARISON,
        )
        self.assertEqual(
            plan["expected_repository_mount"]["request"],
            {
                "type": "bind",
                "target": "/repo",
                "read_only": True,
                "consistency": {
                    "mode": "default",
                    "inspect_member": "omitted",
                },
                "propagation": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
            },
        )
        self.assertEqual(
            plan["expected_repository_mount"]["effective"],
            {
                "type": "bind",
                "destination": "/repo",
                "mode": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_MODE,
                "read_write": False,
                "propagation": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
            },
        )
        mount_arg = plan["create"][plan["create"].index("--mount") + 1]
        self.assertEqual(
            mount_arg,
            (
                f"type=bind,src={source},dst=/repo,readonly,"
                "bind-propagation=rprivate"
            ),
        )

    def test_repository_source_rendering_is_platform_exact(self) -> None:
        cases = (
            (
                "Windows",
                PureWindowsPath(FROZEN_WINDOWS_REPOSITORY_SOURCE),
                FROZEN_WINDOWS_REPOSITORY_SOURCE,
            ),
            (
                "Windows",
                PureWindowsPath(r"\\server\share\receiver-reliance"),
                r"\\server\share\receiver-reliance",
            ),
            (
                "Linux",
                PurePosixPath(
                    "/home/runner/work/receiver-reliance/receiver-reliance"
                ),
                "/home/runner/work/receiver-reliance/receiver-reliance",
            ),
            (
                "Darwin",
                PurePosixPath(
                    "/Users/runner/work/receiver-reliance/receiver-reliance"
                ),
                "/Users/runner/work/receiver-reliance/receiver-reliance",
            ),
        )
        for host_os, resolved, expected in cases:
            with self.subTest(host_os=host_os, expected=expected):
                self.assertEqual(
                    run_sandbox._repository_source_for_host(resolved, host_os),
                    expected,
                )

        invalid = (
            ("Linux", PureWindowsPath(FROZEN_WINDOWS_REPOSITORY_SOURCE)),
            ("Darwin", PureWindowsPath(FROZEN_WINDOWS_REPOSITORY_SOURCE)),
            ("Windows", PurePosixPath("/home/runner/repository")),
            ("Plan9", PurePosixPath("/srv/repository")),
            ("Linux", PurePosixPath("relative/repository")),
            ("Linux", PurePosixPath("/srv/repository,alternate")),
        )
        for host_os, resolved in invalid:
            with self.subTest(host_os=host_os, invalid=str(resolved)):
                with self.assertRaises(RuntimeError):
                    run_sandbox._repository_source_for_host(resolved, host_os)

    def test_f_sandbox_022_foreign_path_dialect_witness_fails_closed(
        self,
    ) -> None:
        witness = PureWindowsPath(r"\\server\share\receiver-reliance")
        self.assertTrue(witness.is_absolute())
        self.assertEqual(witness.as_posix(), "//server/share/receiver-reliance")

        for host_os in ("Linux", "Darwin"):
            with self.subTest(host_os=host_os, dialect="windows-unc"):
                with self.assertRaisesRegex(
                    RuntimeError, "not a POSIX path dialect"
                ):
                    run_sandbox._repository_source_for_host(witness, host_os)

        with self.assertRaisesRegex(RuntimeError, "not a POSIX path dialect"):
            run_sandbox._repository_source_for_host(
                PureWindowsPath("C:/x/receiver-reliance"), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "not a Windows path dialect"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/receiver-reliance"), "Windows"
            )
        with self.assertRaisesRegex(RuntimeError, "double-slash root"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("//srv/receiver-reliance"), "Linux"
            )

    def test_f_sandbox_022_native_dialects_keep_exact_spellings(self) -> None:
        cases = (
            (
                "Linux",
                PurePosixPath("/srv/receiver-reliance"),
                "/srv/receiver-reliance",
            ),
            (
                "Windows",
                PureWindowsPath(r"C:\x\receiver-reliance"),
                r"C:\x\receiver-reliance",
            ),
            (
                "Windows",
                PureWindowsPath(r"\\server\share\rr"),
                r"\\server\share\rr",
            ),
        )
        for host_os, resolved, expected in cases:
            with self.subTest(host_os=host_os, expected=expected):
                self.assertEqual(
                    run_sandbox._repository_source_for_host(resolved, host_os),
                    expected,
                )

        # The concrete resolved object must still satisfy the dialect gate by
        # inheritance, so this host's real repository identity is unchanged.
        resolved_here = run_sandbox.REPO.resolve(strict=True)
        expected_here = (
            str(resolved_here)
            if run_sandbox.platform.system() == "Windows"
            else resolved_here.as_posix()
        )
        self.assertEqual(
            run_sandbox.intended_repository_source(), expected_here
        )

    def test_f_sandbox_022_unc_anatomy_and_mount_metachars_fail_closed(
        self,
    ) -> None:
        # R-SANDBOX-22 witnesses. CPython 3.14 treats any leading double
        # backslash as absolute, so a bare or shareless UNC introducer must be
        # rejected by explicit anatomy on 3.14 and by the absolute check on
        # 3.12 — either way a RuntimeError from a declared gate.
        anatomy = "(did not resolve absolutely|server and a share)"
        for spelling in (
            "//",
            r"\\",
            r"\\server",
            r"\\server\\",
            "\\\\s\\ ",
            r"\\s\\x",
            "\\\\ \\share",
            "\\\\?\\UNC\\s\\ ",
            "\\\\?\\UNC\\ \\share",
            r"\\?\UNC\s\\x",
            r"\\?\UNC",
            r"\\?\UNC\s",
        ):
            with self.subTest(spelling=spelling):
                with self.assertRaisesRegex(RuntimeError, anatomy):
                    run_sandbox._repository_source_for_host(
                        PureWindowsPath(spelling), "Windows"
                    )

        # Complete UNC anatomy still renders exactly, including the
        # extended-length and device forms whose "server" is ? or . .  A
        # share-root path renders drive plus root, hence the trailing
        # separator on the first expectation.
        for spelling, expected in (
            (r"\\server\share", "\\\\server\\share\\"),
            (r"\\?\C:\x\receiver-reliance", r"\\?\C:\x\receiver-reliance"),
            (
                r"\\?\UNC\server\share\receiver-reliance",
                r"\\?\UNC\server\share\receiver-reliance",
            ),
            (
                r"\\?\unc\server\share\receiver-reliance",
                r"\\?\unc\server\share\receiver-reliance",
            ),
        ):
            with self.subTest(spelling=spelling):
                self.assertEqual(
                    run_sandbox._repository_source_for_host(
                        PureWindowsPath(spelling), "Windows"
                    ),
                    expected,
                )

        # A double quote in an otherwise native source would make Docker's
        # strict CSV --mount value unparseable; it fails closed here instead,
        # on both branches, exactly like the comma guard.
        with self.assertRaisesRegex(RuntimeError, "double quote"):
            run_sandbox._repository_source_for_host(
                PurePosixPath('/srv/a"b'), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "double quote"):
            run_sandbox._repository_source_for_host(
                PureWindowsPath('C:\\a"b\\receiver-reliance'), "Windows"
            )
        with self.assertRaisesRegex(RuntimeError, "comma"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a,b"), "Linux"
            )

        # Docker splits --mount on CSV records, cannot receive argv NUL, and
        # trims field values with Go's TrimSpace, so a NUL, a line feed, or
        # edge whitespace can never form a usable plan.  Spellings Docker's
        # actual grammar preserves stay legal: interior whitespace, a lone
        # interior carriage return, and the information separators
        # U+001C..U+001F that only Python considers whitespace.
        with self.assertRaisesRegex(RuntimeError, "UTF-8 encodable"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a\udcff"), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "NUL byte"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a\x00b"), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "newline"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a\nb"), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "trailing whitespace"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a "), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "trailing whitespace"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a\r"), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "trailing whitespace"):
            run_sandbox._repository_source_for_host(
                PurePosixPath("/srv/a\xa0"), "Linux"
            )
        with self.assertRaisesRegex(RuntimeError, "trailing whitespace"):
            run_sandbox._repository_source_for_host(
                PureWindowsPath("C:\\x \\"), "Windows"
            )
        for preserved in ("/srv/a b", "/srv/a\rb", "/srv/a\x1c", "/srv/café"):
            with self.subTest(preserved=preserved):
                self.assertEqual(
                    run_sandbox._repository_source_for_host(
                        PurePosixPath(preserved), "Linux"
                    ),
                    preserved,
                )

    def test_active_source_binding_is_platform_independent(self) -> None:
        cases = (
            ("Windows", FROZEN_WINDOWS_REPOSITORY_SOURCE),
            (
                "Linux",
                "/home/runner/work/receiver-reliance/receiver-reliance",
            ),
            (
                "Darwin",
                "/Users/runner/work/receiver-reliance/receiver-reliance",
            ),
        )
        payload = encoded_receipt(reconciled_pass_receipt())
        for host_os, source in cases:
            with self.subTest(host_os=host_os, source=source):
                raw = valid_docker_inspect(source)
                selected = run_sandbox._selected_inspect(raw)
                run_sandbox._assert_inspect(
                    selected,
                    "a" * 64,
                    FIXTURE_IMAGE_ID,
                    expected_image_tag(),
                    source,
                )
                create_args = run_sandbox.docker_create_args(
                    "fixture:image", source
                )
                mount_arg = create_args[create_args.index("--mount") + 1]
                self.assertIn(f"src={source}", mount_arg)

                with (
                    mock.patch.object(
                        run_sandbox,
                        "intended_repository_source",
                        return_value=source,
                    ),
                    mock.patch.object(
                        run_sandbox.platform,
                        "system",
                        return_value=host_os,
                    ),
                ):
                    trace: list[object] = []
                    exit_code, receipt = exercise_host_container_result(
                        payload,
                        raw_inspect=raw,
                        call_trace=trace,
                    )
                self.assertEqual(exit_code, 0)
                self.assertEqual(receipt["status"], "PASS")
                self.assertEqual(
                    receipt["plan"]["expected_repository_mount"]["host_os"],
                    host_os,
                )
                self.assertIn(
                    ["docker", "start", "--attach", "a" * 64],
                    [call.args[0] for call in trace],
                )

                forged = copy.deepcopy(selected)
                forged["effective_mounts"][0]["source"] = source + "-forged"
                with self.assertRaisesRegex(RuntimeError, "effective_mounts"):
                    run_sandbox._assert_inspect(
                        forged,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                        source,
                    )

    def test_inspect_projection_reads_structured_mount(self) -> None:
        raw = valid_docker_inspect()
        selected = run_sandbox._selected_inspect(raw)
        run_sandbox._assert_inspect(
            selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
        )
        self.assertEqual(
            selected["mounts"][0]["source"],
            run_sandbox.intended_repository_source(),
        )
        self.assertEqual(
            selected["mounts"][0]["propagation"],
            run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
        )
        self.assertEqual(
            selected["effective_mounts"],
            [
                {
                    "type": "bind",
                    "source": run_sandbox.intended_repository_source(),
                    "destination": "/repo",
                    "mode": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_MODE,
                    "read_write": False,
                    "propagation": run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
                }
            ],
        )
        self.assertEqual(selected["container_id"], "a" * 64)
        self.assertEqual(selected["image_id"], FIXTURE_IMAGE_ID)
        self.assertEqual(selected["image_tag"], expected_image_tag())
        self.assertEqual(selected["entrypoint"], run_sandbox.EXPECTED_ENTRYPOINT)
        self.assertEqual(selected["command"], run_sandbox.EXPECTED_COMMAND)
        self.assertEqual(selected["process_path"], run_sandbox.EXPECTED_PROCESS_PATH)
        self.assertEqual(selected["process_args"], run_sandbox.EXPECTED_PROCESS_ARGS)
        self.assertEqual(selected["hostname"], run_sandbox.EXPECTED_HOSTNAME)
        self.assertEqual(
            selected["environment_hostname"], run_sandbox.EXPECTED_HOSTNAME
        )

    def test_f_sandbox_020_native_omitted_consistency_reaches_start(self) -> None:
        raw = valid_docker_inspect()
        host = raw["HostConfig"]
        self.assertIsInstance(host, dict)
        mounts = host["Mounts"]
        self.assertIsInstance(mounts, list)
        self.assertIsInstance(mounts[0], dict)
        self.assertNotIn("Consistency", mounts[0])

        selected = run_sandbox._selected_inspect(raw)
        run_sandbox._assert_inspect(
            selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
        )
        self.assertEqual(selected["mounts"][0]["consistency"], "default")
        self.assertEqual(
            selected["mounts"][0]["source"],
            run_sandbox.intended_repository_source(),
        )
        self.assertEqual(
            selected["mounts"][0]["propagation"],
            run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
        )

        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            encoded_receipt(reconciled_pass_receipt()),
            raw_inspect=raw,
            call_trace=trace,
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 0)
        self.assertEqual(receipt["status"], "PASS")
        self.assertIn("inner_receipt", receipt)
        self.assertIn(["docker", "start", "--attach", "a" * 64], argv)

    def test_f_sandbox_020_frozen_windows_custody_witness(self) -> None:
        raw = valid_docker_inspect(FROZEN_WINDOWS_REPOSITORY_SOURCE)
        host = raw["HostConfig"]
        self.assertIsInstance(host, dict)
        mounts = host["Mounts"]
        self.assertIsInstance(mounts, list)
        self.assertIsInstance(mounts[0], dict)
        self.assertEqual(
            mounts[0]["Source"], FROZEN_WINDOWS_REPOSITORY_SOURCE
        )
        self.assertNotIn("Consistency", mounts[0])

        mount_fragment = run_sandbox.canonical_bytes(mounts[0])
        self.assertEqual(len(mount_fragment), 171)
        self.assertEqual(
            run_sandbox.sha256(mount_fragment),
            "2f7ff46e5f4f59082d6b0445969bd56bbf2f79c2609b245a171e58da8b0a85e9",
        )
        inspect_witness = run_sandbox.canonical_bytes(raw)
        self.assertEqual(len(inspect_witness), 1733)
        self.assertEqual(
            run_sandbox.sha256(inspect_witness),
            "d1e6e191beb0a144fbc45cb99215f365dc8a7d2769b49927fbc54fc188dff1a1",
        )

    def test_request_consistency_member_is_rejected_direct_and_full_flow(
        self,
    ) -> None:
        payload = encoded_receipt(reconciled_pass_receipt())
        mutations: dict[str, object] = {
            "explicit_empty": "",
            "default_string": "default",
            "delegated": "delegated",
            "null": None,
            "boolean": False,
            "integer": 0,
            "array": [],
            "object": {},
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                host = raw["HostConfig"]
                self.assertIsInstance(host, dict)
                mounts = host["Mounts"]
                self.assertIsInstance(mounts, list)
                self.assertIsInstance(mounts[0], dict)
                mounts[0]["Consistency"] = mutation

                with self.assertRaises(run_sandbox.DockerInspectError):
                    run_sandbox._selected_inspect(raw)

                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64],
                    [call.args[0] for call in trace],
                )

    def test_f_sandbox_017_exact_forged_source_witness_fails_closed(self) -> None:
        raw = valid_docker_inspect()
        host = raw["HostConfig"]
        self.assertIsInstance(host, dict)
        mounts = host["Mounts"]
        self.assertIsInstance(mounts, list)
        self.assertIsInstance(mounts[0], dict)
        mounts[0]["Source"] = r"C:\arbitrary\forged-repository"
        historical_raw = valid_docker_inspect(FROZEN_WINDOWS_REPOSITORY_SOURCE)
        historical_host = historical_raw["HostConfig"]
        self.assertIsInstance(historical_host, dict)
        historical_mounts = historical_host["Mounts"]
        self.assertIsInstance(historical_mounts, list)
        self.assertIsInstance(historical_mounts[0], dict)
        historical_mounts[0]["Source"] = r"C:\arbitrary\forged-repository"
        historical_raw.pop("Mounts")
        remove_request_bind_options(historical_raw)
        add_historical_request_consistency(historical_raw)
        witness = run_sandbox.canonical_bytes(historical_raw)
        self.assertEqual(len(witness), 1492)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "a4a8cd02f444da1c5b038e9525f447938415a5144765af6b6ab0d7957bd77a1c",
        )

        selected = run_sandbox._selected_inspect(raw)
        with self.assertRaisesRegex(RuntimeError, "mounts"):
            run_sandbox._assert_inspect(
                selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
            )

        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            encoded_receipt(reconciled_pass_receipt()),
            raw_inspect=raw,
            call_trace=trace,
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertNotIn("inner_receipt", receipt)
        self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)
        self.assertNotIn(
            r"C:\arbitrary\forged-repository",
            json.dumps(receipt, sort_keys=True),
        )

    def test_f_sandbox_018_exact_effective_source_witness_fails_closed(
        self,
    ) -> None:
        forged_source = r"C:\arbitrary\effective-forged-repository"
        raw = valid_docker_inspect()
        effective_mounts = raw["Mounts"]
        self.assertIsInstance(effective_mounts, list)
        self.assertIsInstance(effective_mounts[0], dict)
        effective_mounts[0]["Source"] = forged_source

        historical_raw = valid_docker_inspect(FROZEN_WINDOWS_REPOSITORY_SOURCE)
        historical_effective_mounts = historical_raw["Mounts"]
        self.assertIsInstance(historical_effective_mounts, list)
        self.assertIsInstance(historical_effective_mounts[0], dict)
        historical_effective_mounts[0]["Source"] = forged_source
        remove_request_bind_options(historical_raw)
        add_historical_request_consistency(historical_raw)
        witness = run_sandbox.canonical_bytes(historical_raw)
        self.assertEqual(len(witness), 1681)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "377617a476f6122efb35562eea09b5f2736a642767c2703a98b419d481842031",
        )
        forged_source_sha = run_sandbox.sha256(forged_source.encode("utf-8"))
        self.assertEqual(
            forged_source_sha,
            "200a92799147453fd469ad4af756403847655dbf950fe19116bda0bfc1113acf",
        )

        selected = run_sandbox._selected_inspect(raw)
        with self.assertRaisesRegex(RuntimeError, "effective_mounts"):
            run_sandbox._assert_inspect(
                selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
            )

        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            encoded_receipt(reconciled_pass_receipt()),
            raw_inspect=raw,
            call_trace=trace,
        )
        argv = [call.args[0] for call in trace]
        encoded_host_receipt = json.dumps(receipt, sort_keys=True)
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertIn("effective_mounts", str(receipt["detail"]))
        self.assertIn(forged_source_sha, encoded_host_receipt)
        self.assertNotIn(forged_source, encoded_host_receipt)
        self.assertNotIn("inner_receipt", receipt)
        self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)

    def test_f_sandbox_019_exact_request_propagation_witness_fails_closed(
        self,
    ) -> None:
        raw = valid_docker_inspect()
        host = raw["HostConfig"]
        self.assertIsInstance(host, dict)
        mounts = host["Mounts"]
        self.assertIsInstance(mounts, list)
        self.assertIsInstance(mounts[0], dict)
        bind_options = mounts[0]["BindOptions"]
        self.assertIsInstance(bind_options, dict)
        bind_options["Propagation"] = "rshared"

        historical_raw = valid_docker_inspect(FROZEN_WINDOWS_REPOSITORY_SOURCE)
        historical_host = historical_raw["HostConfig"]
        self.assertIsInstance(historical_host, dict)
        historical_mounts = historical_host["Mounts"]
        self.assertIsInstance(historical_mounts, list)
        self.assertIsInstance(historical_mounts[0], dict)
        historical_bind_options = historical_mounts[0]["BindOptions"]
        self.assertIsInstance(historical_bind_options, dict)
        historical_bind_options["Propagation"] = "rshared"
        add_historical_request_consistency(historical_raw)
        witness = run_sandbox.canonical_bytes(historical_raw)
        self.assertEqual(len(witness), 1749)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "6b1f90d64e2f5fe6beca5b66f30b1c041b76fcb2c5ae5720fbb04468896b62b7",
        )
        fragment = run_sandbox.canonical_bytes(bind_options)
        self.assertEqual(fragment, b'{"Propagation":"rshared"}')
        self.assertEqual(
            run_sandbox.sha256(fragment),
            "a2b186f42ef8c0d06df1bb375622bec37b9df5f52aa94bba40d88b97c4c2a3cb",
        )

        selected = run_sandbox._selected_inspect(raw)
        self.assertEqual(
            selected["effective_mounts"][0]["propagation"],
            run_sandbox.EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
        )
        with self.assertRaisesRegex(RuntimeError, "mounts"):
            run_sandbox._assert_inspect(
                selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
            )

        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            encoded_receipt(reconciled_pass_receipt()),
            raw_inspect=raw,
            call_trace=trace,
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertIn("mounts", str(receipt["detail"]))
        self.assertNotIn("inner_receipt", receipt)
        self.assertNotIn(
            ["docker", "start", "--attach", "a" * 64],
            [call.args[0] for call in trace],
        )

    def test_request_bind_options_schema_fails_direct_and_full_flow(
        self,
    ) -> None:
        missing = object()
        mutations: dict[str, object] = {
            "bind_options_missing": missing,
            "bind_options_null": None,
            "bind_options_string": "rprivate",
            "bind_options_array": ["rprivate"],
            "bind_options_empty": {},
            "propagation_null": {"Propagation": None},
            "propagation_boolean": {"Propagation": False},
            "propagation_integer": {"Propagation": 0},
            "propagation_empty": {"Propagation": ""},
            "propagation_private": {"Propagation": "private"},
            "propagation_rshared": {"Propagation": "rshared"},
            "non_recursive_false": {
                "Propagation": "rprivate",
                "NonRecursive": False,
            },
            "non_recursive_true": {
                "Propagation": "rprivate",
                "NonRecursive": True,
            },
            "create_mountpoint_false": {
                "Propagation": "rprivate",
                "CreateMountpoint": False,
            },
            "create_mountpoint_true": {
                "Propagation": "rprivate",
                "CreateMountpoint": True,
            },
            "read_only_non_recursive_false": {
                "Propagation": "rprivate",
                "ReadOnlyNonRecursive": False,
            },
            "read_only_non_recursive_true": {
                "Propagation": "rprivate",
                "ReadOnlyNonRecursive": True,
            },
            "read_only_force_recursive_false": {
                "Propagation": "rprivate",
                "ReadOnlyForceRecursive": False,
            },
            "read_only_force_recursive_true": {
                "Propagation": "rprivate",
                "ReadOnlyForceRecursive": True,
            },
            "unrecognized": {
                "Propagation": "rprivate",
                "RecursiveReadOnly": False,
            },
        }
        payload = encoded_receipt(reconciled_pass_receipt())
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                host = raw["HostConfig"]
                self.assertIsInstance(host, dict)
                mounts = host["Mounts"]
                self.assertIsInstance(mounts, list)
                self.assertIsInstance(mounts[0], dict)
                if mutation is missing:
                    mounts[0].pop("BindOptions")
                else:
                    mounts[0]["BindOptions"] = mutation

                with self.assertRaises(
                    (run_sandbox.DockerInspectError, RuntimeError)
                ):
                    selected = run_sandbox._selected_inspect(raw)
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )

                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64],
                    [call.args[0] for call in trace],
                )

    def test_effective_mount_schema_and_values_fail_direct_and_full_flow(
        self,
    ) -> None:
        source = run_sandbox.intended_repository_source()
        separator = "\\" if run_sandbox.platform.system() == "Windows" else "/"
        missing = object()
        payload = encoded_receipt(reconciled_pass_receipt())

        def mutate_root(
            raw: dict[str, object], field: str, value: object
        ) -> None:
            mounts = raw["Mounts"]
            if not isinstance(mounts, list) or not isinstance(mounts[0], dict):
                raise AssertionError("effective mount fixture lost object shape")
            if value is missing:
                mounts[0].pop(field)
            else:
                mounts[0][field] = value

        source_mutations: dict[str, object] = {
            "source_missing": missing,
            "source_null": None,
            "source_boolean": False,
            "source_integer": 7,
            "source_array": [source],
            "source_empty": "",
            "source_relative": "relative-repository",
            "source_alternate_separator": (
                source.replace("\\", "/")
                if "\\" in source
                else source.replace("/", "//", 1)
            ),
            "source_traversal": source
            + separator
            + ".."
            + separator
            + "forged-repository",
            "source_case": source.swapcase(),
            "source_other": r"C:\arbitrary\effective-forged-repository",
        }
        field_mutations: dict[str, tuple[str, object]] = {
            "type_missing": ("Type", missing),
            "type_null": ("Type", None),
            "type_volume": ("Type", "volume"),
            "destination_missing": ("Destination", missing),
            "destination_null": ("Destination", None),
            "destination_other": ("Destination", "/other"),
            "destination_trailing_slash": ("Destination", "/repo/"),
            "mode_missing": ("Mode", missing),
            "mode_null": ("Mode", None),
            "mode_empty": ("Mode", ""),
            "mode_rw": ("Mode", "rw"),
            "rw_missing": ("RW", missing),
            "rw_null": ("RW", None),
            "rw_string_false": ("RW", "false"),
            "rw_integer_zero": ("RW", 0),
            "rw_true": ("RW", True),
            "propagation_missing": ("Propagation", missing),
            "propagation_null": ("Propagation", None),
            "propagation_empty": ("Propagation", ""),
            "propagation_private": ("Propagation", "private"),
        }
        mutations = {
            **{name: ("Source", value) for name, value in source_mutations.items()},
            **field_mutations,
        }
        for name, (field, value) in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                mutate_root(raw, field, value)
                with self.assertRaises(
                    (run_sandbox.DockerInspectError, RuntimeError)
                ):
                    selected = run_sandbox._selected_inspect(raw)
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )
                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64],
                    [call.args[0] for call in trace],
                )

        top_level_mutations: dict[str, object] = {
            "root_missing": missing,
            "root_null": None,
            "root_object": {},
            "root_empty": [],
            "root_element_string": ["mount"],
        }
        for name, mutation in top_level_mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                if mutation is missing:
                    raw.pop("Mounts")
                else:
                    raw["Mounts"] = mutation
                with self.assertRaises(
                    (run_sandbox.DockerInspectError, RuntimeError)
                ):
                    selected = run_sandbox._selected_inspect(raw)
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )
                trace = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64],
                    [call.args[0] for call in trace],
                )

        for name in ("extra_mount", "extra_member"):
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                mounts = raw["Mounts"]
                self.assertIsInstance(mounts, list)
                self.assertIsInstance(mounts[0], dict)
                if name == "extra_mount":
                    mounts.append(copy.deepcopy(mounts[0]))
                    mounts[1]["Destination"] = "/other"
                else:
                    mounts[0]["Unbound"] = "value"
                with self.assertRaises(
                    (run_sandbox.DockerInspectError, RuntimeError)
                ):
                    selected = run_sandbox._selected_inspect(raw)
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )
                trace = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64],
                    [call.args[0] for call in trace],
                )

    def test_repository_source_mutations_fail_direct_and_full_flow(self) -> None:
        source = run_sandbox.intended_repository_source()
        separator = "\\" if run_sandbox.platform.system() == "Windows" else "/"
        case_mutation = source.swapcase()
        self.assertNotEqual(case_mutation, source)
        missing = object()
        mutations: dict[str, object] = {
            "missing": missing,
            "null": None,
            "boolean": False,
            "integer": 7,
            "array": [source],
            "empty": "",
            "lone_surrogate": "\ud800",
            "relative": "relative-repository",
            "alternate_separator": (
                source.replace("\\", "/")
                if "\\" in source
                else source.replace("/", "//", 1)
            ),
            "traversal": source + separator + ".." + separator + "forged-repository",
            "case": case_mutation,
            "other": r"C:\arbitrary\forged-repository",
        }
        payload = encoded_receipt(reconciled_pass_receipt())
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                host = raw["HostConfig"]
                self.assertIsInstance(host, dict)
                mounts = host["Mounts"]
                self.assertIsInstance(mounts, list)
                self.assertIsInstance(mounts[0], dict)
                if mutation is missing:
                    mounts[0].pop("Source")
                else:
                    mounts[0]["Source"] = mutation
                with self.assertRaises(
                    (run_sandbox.DockerInspectError, RuntimeError)
                ):
                    selected = run_sandbox._selected_inspect(raw)
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )

                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64], argv
                )

        extra = valid_docker_inspect()
        extra_host = extra["HostConfig"]
        self.assertIsInstance(extra_host, dict)
        extra_mounts = extra_host["Mounts"]
        self.assertIsInstance(extra_mounts, list)
        extra_mounts.append(copy.deepcopy(extra_mounts[0]))
        extra_mounts[1]["Target"] = "/other"
        selected = run_sandbox._selected_inspect(extra)
        with self.assertRaisesRegex(RuntimeError, "mounts"):
            run_sandbox._assert_inspect(
                selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
            )
        trace = []
        exit_code, receipt = exercise_host_container_result(
            payload, raw_inspect=extra, call_trace=trace
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertNotIn(
            ["docker", "start", "--attach", "a" * 64],
            [call.args[0] for call in trace],
        )

    def test_f_sandbox_015_exact_hostname_witnesses_fail_closed(self) -> None:
        missing = valid_docker_inspect()
        missing_config = missing["Config"]
        self.assertIsInstance(missing_config, dict)
        missing_config.pop("Hostname")
        set_historical_unbound_mount_source(missing)
        historical_missing = copy.deepcopy(missing)
        historical_missing.pop("Mounts")
        remove_request_bind_options(historical_missing)
        add_historical_request_consistency(historical_missing)
        missing_witness = run_sandbox.canonical_bytes(historical_missing)
        self.assertEqual(len(missing_witness), 1449)
        self.assertEqual(
            run_sandbox.sha256(missing_witness),
            "5ea68d807d00e0b2f368124b09bc6d14b23d303fb84b11331a3b220590944c14",
        )

        wrong = valid_docker_inspect()
        wrong_config = wrong["Config"]
        self.assertIsInstance(wrong_config, dict)
        wrong_config["Hostname"] = "evil-host"
        set_historical_unbound_mount_source(wrong)
        historical_wrong = copy.deepcopy(wrong)
        historical_wrong.pop("Mounts")
        remove_request_bind_options(historical_wrong)
        add_historical_request_consistency(historical_wrong)
        wrong_witness = run_sandbox.canonical_bytes(historical_wrong)
        self.assertEqual(len(wrong_witness), 1472)
        self.assertEqual(
            run_sandbox.sha256(wrong_witness),
            "c2e2f2be8315f61bd835cc500283ab1f41cbbb6733699cf669a41112af35ad27",
        )

        for name, raw in (("missing", missing), ("wrong", wrong)):
            with self.subTest(name=name):
                selected = run_sandbox._selected_inspect(raw)
                with self.assertRaisesRegex(RuntimeError, "hostname"):
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )
                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    encoded_receipt(reconciled_pass_receipt()),
                    raw_inspect=raw,
                    call_trace=trace,
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn("hostname", str(receipt["detail"]))
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64], argv
                )

    def test_hostname_shapes_case_whitespace_and_values_fail_before_start(
        self,
    ) -> None:
        missing = object()
        mutations: dict[str, object] = {
            "missing": missing,
            "null": None,
            "boolean": False,
            "integer": 7,
            "array": [run_sandbox.EXPECTED_HOSTNAME],
            "object": {"value": run_sandbox.EXPECTED_HOSTNAME},
            "empty": "",
            "case": "RR-SANDBOX",
            "leading_whitespace": " rr-sandbox",
            "trailing_whitespace": "rr-sandbox ",
            "evil": "evil-host",
        }
        payload = encoded_receipt(reconciled_pass_receipt())
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                config = raw["Config"]
                self.assertIsInstance(config, dict)
                if mutation is missing:
                    config.pop("Hostname")
                else:
                    config["Hostname"] = mutation
                selected = run_sandbox._selected_inspect(raw)
                with self.assertRaisesRegex(RuntimeError, "hostname"):
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )

                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn("hostname", str(receipt["detail"]))
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64], argv
                )

    def test_f_sandbox_014_exact_secret_environment_witness_fails_closed(
        self,
    ) -> None:
        raw = valid_docker_inspect()
        config = raw["Config"]
        self.assertIsInstance(config, dict)
        config["Env"] = ["SECRET_TOKEN=forged"]
        historical_raw = copy.deepcopy(raw)
        historical_config = historical_raw["Config"]
        self.assertIsInstance(historical_config, dict)
        historical_config.pop("Hostname")
        set_historical_unbound_mount_source(historical_raw)
        historical_raw.pop("Mounts")
        remove_request_bind_options(historical_raw)
        add_historical_request_consistency(historical_raw)
        raw_witness = run_sandbox.canonical_bytes(historical_raw)
        self.assertEqual(len(raw_witness), 1147)
        self.assertEqual(
            run_sandbox.sha256(raw_witness),
            "2f832130d910bd8341577fde2f77619056e3dc282209d3004f17edb4d5bbb3a4",
        )

        historical_selected = run_sandbox._selected_inspect(
            valid_docker_inspect()
        )
        historical_selected["environment_names"] = ["SECRET_TOKEN"]
        historical_selected.pop("hostname")
        historical_selected.pop("environment_hostname")
        remove_selected_mount_source(historical_selected)
        selected_witness = run_sandbox.canonical_bytes(historical_selected)
        self.assertEqual(len(selected_witness), 1224)
        self.assertEqual(
            run_sandbox.sha256(selected_witness),
            "dda5a3271fe0b8a30b0514357e157615d2e5da54bae54f5c53181a2dc453cd7e",
        )
        with self.assertRaisesRegex(
            run_sandbox.DockerInspectError, "deterministic allowlist"
        ):
            run_sandbox._selected_inspect(raw)

        forged = encoded_receipt(historical_pass_receipt_before_f015())
        self.assertEqual(
            run_sandbox.sha256(forged),
            "eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55",
        )
        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            forged, raw_inspect=raw, call_trace=trace
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertNotIn("inner_receipt", receipt)
        self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)
        self.assertNotIn("forged", json.dumps(receipt, sort_keys=True))

    def test_environment_allowlist_rejects_every_shape_and_content_mutation(
        self,
    ) -> None:
        valid_environment = [
            f"{name}={value}"
            for name, value in run_sandbox.EXPECTED_EFFECTIVE_ENVIRONMENT.items()
        ]
        missing = object()
        mutations: dict[str, object] = {
            "missing_member": missing,
            "null": None,
            "string_container": "HOME=/tmp",
            "object_container": {"HOME": "/tmp"},
            "integer_entry": valid_environment[:-1] + [7],
            "boolean_entry": valid_environment[:-1] + [False],
            "object_entry": valid_environment[:-1] + [{"TZ": "UTC"}],
            "missing_equals": valid_environment[:-1] + ["TZ"],
            "empty_name": valid_environment[:-1] + ["=UTC"],
            "invalid_name": valid_environment[:-1] + ["BAD-NAME=UTC"],
            "digit_initial_name": valid_environment[:-1] + ["1TZ=UTC"],
            "duplicate_name": valid_environment + ["HOME=/tmp"],
            "missing_allowlisted": valid_environment[:-1],
            "extra_benign": valid_environment + ["EXTRA_FLAG=1"],
            "extra_secret": valid_environment + ["SECRET_TOKEN=forged"],
            "wrong_value": [
                "HOME=forged" if item.startswith("HOME=") else item
                for item in valid_environment
            ],
        }
        forged = encoded_receipt(historical_pass_receipt_before_f015())
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                config = raw["Config"]
                self.assertIsInstance(config, dict)
                if mutation is missing:
                    config.pop("Env")
                else:
                    config["Env"] = mutation
                with self.assertRaises(run_sandbox.DockerInspectError):
                    run_sandbox._selected_inspect(raw)

                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    forged, raw_inspect=raw, call_trace=trace
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn("inner_receipt", receipt)
                self.assertNotIn(
                    ["docker", "start", "--attach", "a" * 64], argv
                )
                self.assertNotIn("forged", json.dumps(receipt, sort_keys=True))

    def test_inner_environment_is_reconciled_to_inspected_names(self) -> None:
        effective = run_sandbox._selected_inspect(valid_docker_inspect())
        valid = reconciled_pass_receipt()
        run_sandbox._reconcile_inner_environment(valid, effective)
        self.assertEqual(
            effective["environment_names"],
            run_sandbox.EXPECTED_ENVIRONMENT_NAMES,
        )
        self.assertNotIn("environment_values", effective)
        self.assertEqual(
            effective["environment_hostname"], run_sandbox.EXPECTED_HOSTNAME
        )

        selected_mutation = copy.deepcopy(effective)
        selected_mutation["environment_names"] = ["SECRET_TOKEN"]
        with self.assertRaisesRegex(RuntimeError, "environment_names"):
            run_sandbox._assert_inspect(
                selected_mutation,
                "a" * 64,
                FIXTURE_IMAGE_ID,
                expected_image_tag(),
            )

        mutations = {
            "missing": run_sandbox.EXPECTED_ENVIRONMENT_NAMES[:-1],
            "extra_benign": sorted(
                run_sandbox.EXPECTED_ENVIRONMENT_NAMES + ["EXTRA_FLAG"]
            ),
        }
        for name, environment_names in mutations.items():
            with self.subTest(name=name):
                receipt = reconciled_pass_receipt()
                boundary = receipt["boundary"]
                self.assertIsInstance(boundary, dict)
                boundary["environment_names"] = environment_names
                reproject_receipt(receipt)
                with self.assertRaisesRegex(
                    run_sandbox.InnerReceiptError, "inspected Config.Env names"
                ):
                    run_sandbox._reconcile_inner_environment(receipt, effective)

                exit_code, host_receipt = exercise_host_container_result(
                    encoded_receipt(receipt)
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    host_receipt["status"], "INVALID_CONTAINER_RECEIPT"
                )
                self.assertNotIn("inner_receipt", host_receipt)

    def test_inner_secret_and_malformed_name_claims_fail_before_pass(self) -> None:
        mutations: dict[str, tuple[object, object]] = {
            "secret_name": (
                sorted(run_sandbox.EXPECTED_ENVIRONMENT_NAMES + ["SECRET_TOKEN"]),
                [],
            ),
            "claimed_secret": (
                list(run_sandbox.EXPECTED_ENVIRONMENT_NAMES),
                ["HOME"],
            ),
            "duplicate": (
                sorted(run_sandbox.EXPECTED_ENVIRONMENT_NAMES)
                + [run_sandbox.EXPECTED_ENVIRONMENT_NAMES[-1]],
                [],
            ),
            "malformed_type": (list(run_sandbox.EXPECTED_ENVIRONMENT_NAMES) + [7], []),
        }
        for name, (environment_names, secret_names) in mutations.items():
            with self.subTest(name=name):
                receipt = reconciled_pass_receipt()
                boundary = receipt["boundary"]
                self.assertIsInstance(boundary, dict)
                boundary["environment_names"] = environment_names
                boundary["secret_like_environment_names"] = secret_names
                reproject_receipt(receipt)
                payload = encoded_receipt(receipt)
                with self.assertRaises(run_sandbox.InnerReceiptError):
                    run_sandbox.validate_inner_receipt(payload)
                exit_code, host_receipt = exercise_host_container_result(payload)
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    host_receipt["status"], "INVALID_CONTAINER_RECEIPT"
                )
                self.assertNotIn("inner_receipt", host_receipt)

    def test_f_sandbox_013_exact_string_false_mount_witness_fails_closed(
        self,
    ) -> None:
        historical = historical_inspect_before_f013(valid_docker_inspect())
        historical_config = historical["Config"]
        historical_host = historical["HostConfig"]
        self.assertIsInstance(historical_config, dict)
        self.assertIsInstance(historical_host, dict)
        historical_mounts = historical_host["Mounts"]
        self.assertIsInstance(historical_mounts, list)
        historical_mount = historical_mounts[0]
        self.assertIsInstance(historical_mount, dict)
        historical_mount["ReadOnly"] = "false"
        witness = run_sandbox.canonical_bytes(historical)
        self.assertEqual(len(witness), 1044)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "de64a3f9033843d5f746a99211bc8e2934bf57973de1d0a9b93c5dd1bb4883e8",
        )

        forged = encoded_receipt(historical_pass_receipt_before_f015())
        self.assertEqual(
            run_sandbox.sha256(forged),
            "eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55",
        )
        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            forged, raw_inspect=historical, call_trace=trace
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertNotIn("inner_receipt", receipt)
        self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)

    def test_security_boolean_mutations_fail_direct_and_full_host_flow(self) -> None:
        missing = object()
        fields: dict[str, tuple[tuple[object, ...], bool]] = {
            "mount_read_only": (
                ("HostConfig", "Mounts", 0, "ReadOnly"),
                True,
            ),
            "readonly_rootfs": (("HostConfig", "ReadonlyRootfs"), True),
            "network_disabled": (("Config", "NetworkDisabled"), False),
            "auto_remove": (("HostConfig", "AutoRemove"), False),
            "oom_kill_disable": (("HostConfig", "OomKillDisable"), False),
            "init": (("HostConfig", "Init"), False),
            "publish_all_ports": (("HostConfig", "PublishAllPorts"), False),
            "privileged": (("HostConfig", "Privileged"), False),
        }

        def mutate(
            raw: dict[str, object], path: tuple[object, ...], value: object
        ) -> None:
            parent: object = raw
            for part in path[:-1]:
                if isinstance(part, int):
                    self.assertIsInstance(parent, list)
                    parent = parent[part]
                else:
                    self.assertIsInstance(parent, dict)
                    parent = parent[part]
            final = path[-1]
            self.assertIsInstance(parent, dict)
            self.assertIsInstance(final, str)
            if value is missing:
                parent.pop(final)
            else:
                parent[final] = value

        for field, (path, expected) in fields.items():
            invalid_values = {
                "missing": missing,
                "null": None,
                "string_false": "false",
                "integer_zero": 0,
                "integer_one": 1,
                "opposite_boolean": not expected,
            }
            for mutation_name, invalid in invalid_values.items():
                with self.subTest(field=field, mutation=mutation_name):
                    raw = valid_docker_inspect()
                    mutate(raw, path, invalid)
                    with self.assertRaises(
                        (run_sandbox.DockerInspectError, RuntimeError)
                    ):
                        selected = run_sandbox._selected_inspect(raw)
                        run_sandbox._assert_inspect(
                            selected,
                            "a" * 64,
                            FIXTURE_IMAGE_ID,
                            expected_image_tag(),
                        )

                    trace: list[object] = []
                    exit_code, receipt = exercise_host_container_result(
                        encoded_receipt(synthetic_pass_receipt()),
                        raw_inspect=raw,
                        call_trace=trace,
                    )
                    argv = [call.args[0] for call in trace]
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                    self.assertNotIn("inner_receipt", receipt)
                    self.assertNotIn(
                        ["docker", "start", "--attach", "a" * 64], argv
                    )

    def test_f_sandbox_010_exact_container_identity_witness_fails_closed(self) -> None:
        created_id = "a" * 64
        raw = valid_docker_inspect()
        raw["Id"] = "b" * 64
        historical_raw = historical_inspect_before_f013(raw)
        historical_raw.pop("Image")
        historical_config = historical_raw["Config"]
        self.assertIsInstance(historical_config, dict)
        historical_config.pop("Image")
        witness = run_sandbox.canonical_bytes(historical_raw)
        self.assertEqual(len(witness), 898)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "dbd52a5cd753d37069fd33525ae3899a758c6fd3c9420eb4dccef8118a008f8f",
        )

        selected = run_sandbox._selected_inspect(raw)
        with self.assertRaisesRegex(RuntimeError, "container_id"):
            run_sandbox._assert_inspect(
                selected, created_id, FIXTURE_IMAGE_ID, expected_image_tag()
            )

        payload = encoded_receipt(historical_pass_receipt_before_f015())
        self.assertEqual(
            run_sandbox.sha256(payload),
            "eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55",
        )
        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            payload,
            created_stdout=created_id.encode("ascii"),
            raw_inspect=raw,
            call_trace=trace,
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertIn("container_id", str(receipt["detail"]))
        self.assertNotIn("inner_receipt", receipt)
        self.assertIn(["docker", "inspect", created_id], argv)
        self.assertNotIn(["docker", "start", "--attach", created_id], argv)
        self.assertIn(["docker", "rm", "--force", created_id], argv)

    def test_inspected_container_id_mutations_fail_direct_and_host_flow(self) -> None:
        created_id = "a" * 64
        mutations: dict[str, tuple[object, bool]] = {
            "missing": (None, True),
            "null": (None, False),
            "list": ([created_id], False),
            "integer": (1, False),
            "case": ("A" * 64, False),
            "prefix": ("sha256:" + created_id, False),
            "short": ("a" * 63, False),
            "long": ("a" * 65, False),
            "leading_whitespace": (" " + created_id, False),
            "trailing_whitespace": (created_id + " ", False),
            "linefeed": (created_id + "\n", False),
            "different": ("b" * 64, False),
        }
        payload = encoded_receipt(historical_pass_receipt_before_f015())
        for name, (value, remove) in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                if remove:
                    raw.pop("Id")
                else:
                    raw["Id"] = value
                selected = run_sandbox._selected_inspect(raw)
                with self.assertRaisesRegex(RuntimeError, "container_id"):
                    run_sandbox._assert_inspect(
                        selected, created_id, FIXTURE_IMAGE_ID, expected_image_tag()
                    )

                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload,
                    created_stdout=created_id.encode("ascii"),
                    raw_inspect=raw,
                    call_trace=trace,
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn("container_id", str(receipt["detail"]))
                self.assertIn(["docker", "inspect", created_id], argv)
                self.assertNotIn(
                    ["docker", "start", "--attach", created_id], argv
                )
                self.assertIn(["docker", "rm", "--force", created_id], argv)

    def test_f_sandbox_011_exact_image_substitution_witness_fails_closed(
        self,
    ) -> None:
        raw = valid_docker_inspect()
        raw["Image"] = "sha256:" + "b" * 64
        witness = run_sandbox.canonical_bytes(historical_inspect_before_f013(raw))
        self.assertEqual(len(witness), 1041)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "6cfaa3b5ab7d0c0370adc53c4321d69d738a65d62334c645d076be70871f0cb0",
        )

        selected = run_sandbox._selected_inspect(raw)
        with self.assertRaisesRegex(RuntimeError, "image_id"):
            run_sandbox._assert_inspect(
                selected,
                "a" * 64,
                FIXTURE_IMAGE_ID,
                expected_image_tag(),
            )

        payload = encoded_receipt(historical_pass_receipt_before_f015())
        self.assertEqual(
            run_sandbox.sha256(payload),
            "eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55",
        )
        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            payload, raw_inspect=raw, call_trace=trace
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertIn("image_id", str(receipt["detail"]))
        self.assertNotIn("inner_receipt", receipt)
        self.assertIn(["docker", "build", "--pull", "--network=none"], [a[:4] for a in argv])
        self.assertIn(["docker", "image", "inspect", expected_image_tag()], argv)
        self.assertIn(["docker", "inspect", "a" * 64], argv)
        self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)
        self.assertIn(["docker", "rm", "--force", "a" * 64], argv)

    def test_container_image_id_and_tag_mutations_fail_before_start(self) -> None:
        mutations: dict[str, tuple[str, object, bool]] = {
            "image_id_missing": ("Image", None, True),
            "image_id_null": ("Image", None, False),
            "image_id_list": ("Image", [FIXTURE_IMAGE_ID], False),
            "image_id_integer": ("Image", 1, False),
            "image_id_case_prefix": ("Image", "SHA256:" + "c" * 64, False),
            "image_id_case_digest": ("Image", "sha256:" + "C" * 64, False),
            "image_id_wrong_prefix": ("Image", "sha512:" + "c" * 64, False),
            "image_id_short": ("Image", "sha256:" + "c" * 63, False),
            "image_id_long": ("Image", "sha256:" + "c" * 65, False),
            "image_id_different": ("Image", "sha256:" + "b" * 64, False),
            "image_tag_missing": ("Config.Image", None, True),
            "image_tag_null": ("Config.Image", None, False),
            "image_tag_list": ("Config.Image", [expected_image_tag()], False),
            "image_tag_integer": ("Config.Image", 1, False),
            "image_tag_case": ("Config.Image", expected_image_tag().upper(), False),
            "image_tag_prefix": (
                "Config.Image",
                "other-sandbox:" + expected_image_tag().rsplit(":", 1)[1],
                False,
            ),
            "image_tag_digest": (
                "Config.Image",
                expected_image_tag()[:-1] + "0",
                False,
            ),
            "image_tag_different": (
                "Config.Image",
                "receiver-reliance-portability-sandbox:" + "f" * 12,
                False,
            ),
        }
        payload = encoded_receipt(historical_pass_receipt_before_f015())
        for name, (field, value, remove) in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                if field == "Image":
                    target = raw
                    key = "Image"
                    expected_detail = "image_id"
                else:
                    target = raw["Config"]
                    self.assertIsInstance(target, dict)
                    key = "Image"
                    expected_detail = "image_tag"
                if remove:
                    target.pop(key)
                else:
                    target[key] = value
                selected = run_sandbox._selected_inspect(raw)
                with self.assertRaisesRegex(RuntimeError, expected_detail):
                    run_sandbox._assert_inspect(
                        selected,
                        "a" * 64,
                        FIXTURE_IMAGE_ID,
                        expected_image_tag(),
                    )
                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw, call_trace=trace
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn(expected_detail, str(receipt["detail"]))
                self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)

    def test_image_inspect_identity_and_tag_shapes_are_strict(self) -> None:
        valid = {
            "Id": FIXTURE_IMAGE_ID,
            "Os": "linux",
            "Architecture": "amd64",
        }
        parsed = run_sandbox._validated_image_inspect(
            json.dumps([valid]).encode("utf-8"), expected_image_tag()
        )
        self.assertEqual(parsed["id"], FIXTURE_IMAGE_ID)
        self.assertEqual(parsed["tag"], expected_image_tag())

        id_mutations: dict[str, object] = {
            "missing": None,
            "null": None,
            "list": [FIXTURE_IMAGE_ID],
            "integer": 1,
            "case_prefix": "SHA256:" + "c" * 64,
            "case_digest": "sha256:" + "C" * 64,
            "wrong_prefix": "sha512:" + "c" * 64,
            "short": "sha256:" + "c" * 63,
            "long": "sha256:" + "c" * 65,
        }
        for name, value in id_mutations.items():
            with self.subTest(image_id=name):
                mutated = dict(valid)
                if name == "missing":
                    mutated.pop("Id")
                else:
                    mutated["Id"] = value
                with self.assertRaisesRegex(run_sandbox.DockerInspectError, "Id"):
                    run_sandbox._validated_image_inspect(
                        json.dumps([mutated]).encode("utf-8"), expected_image_tag()
                    )

        invalid_tags: list[object] = [
            None,
            [expected_image_tag()],
            expected_image_tag().upper(),
            "sha256:" + "c" * 64,
            "receiver-reliance-portability-sandbox:" + "c" * 11,
            "receiver-reliance-portability-sandbox:" + "C" * 12,
        ]
        valid_payload = json.dumps([valid]).encode("utf-8")
        for tag in invalid_tags:
            with self.subTest(image_tag=tag):
                with self.assertRaisesRegex(
                    run_sandbox.DockerInspectError, "image tag"
                ):
                    run_sandbox._validated_image_inspect(
                        valid_payload, tag  # type: ignore[arg-type]
                    )

    def test_inspect_json_is_duplicate_free_finite_and_single_object(self) -> None:
        malformed = {
            "object_root": b"{}",
            "empty_array": b"[]",
            "two_objects": b"[{},{}]",
            "nonobject_item": b"[null]",
            "invalid_utf8": b"[\xff]",
            "duplicate_root_member": b'[{"Id":"a","Id":"b"}]',
            "duplicate_nested_member": b'[{"Config":{"Image":"a","Image":"b"}}]',
            "nan": b'[{"x":NaN}]',
            "overflow": b'[{"x":1e309}]',
        }
        for name, value in malformed.items():
            with self.subTest(name=name):
                with self.assertRaises(run_sandbox.DockerInspectError):
                    run_sandbox._parse_docker_inspect(value, "fixture inspect")

        forged = encoded_receipt(synthetic_pass_receipt())
        for name, value in {
            "image_duplicate": b'[{"Id":"sha256:'
            + b"c" * 64
            + b'","Id":"sha256:'
            + b"b" * 64
            + b'","Os":"linux","Architecture":"amd64"}]',
            "image_nonfinite": b'[{"Id":"sha256:'
            + b"c" * 64
            + b'","Os":"linux","Architecture":"amd64","x":NaN}]',
        }.items():
            with self.subTest(host_image=name):
                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    forged, image_inspect_stdout=value, call_trace=trace
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertNotIn(["docker", "create"], [a[:2] for a in argv])

        container_duplicate = run_sandbox.canonical_bytes([valid_docker_inspect()])
        marker = b'"Image":"' + FIXTURE_IMAGE_ID.encode("ascii") + b'",'
        container_duplicate = container_duplicate.replace(marker, marker + marker, 1)
        trace = []
        exit_code, receipt = exercise_host_container_result(
            forged,
            container_inspect_stdout=container_duplicate,
            call_trace=trace,
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertNotIn(["docker", "start", "--attach", "a" * 64], argv)

    def test_create_container_id_output_is_strict_before_handle_binding(self) -> None:
        created_id = b"a" * 64
        for valid in (created_id, created_id + b"\n", created_id + b"\r\n"):
            with self.subTest(valid=valid[-2:]):
                self.assertEqual(
                    run_sandbox._created_container_id(valid), "a" * 64
                )

        invalid = {
            "missing": b"",
            "null": b"null",
            "case": b"A" * 64,
            "prefix": b"sha256:" + created_id,
            "short": b"a" * 63,
            "long": b"a" * 65,
            "leading_whitespace": b" " + created_id,
            "trailing_whitespace": created_id + b" ",
            "tab": created_id + b"\t",
            "double_linefeed": created_id + b"\n\n",
            "carriage_return_only": created_id + b"\r",
            "different_shape": b"g" * 64,
        }
        payload = encoded_receipt(synthetic_pass_receipt())
        for name, raw_output in invalid.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, "invalid container id output"):
                    run_sandbox._created_container_id(raw_output)
                trace: list[object] = []
                exit_code, receipt = exercise_host_container_result(
                    payload,
                    created_stdout=raw_output,
                    call_trace=trace,
                )
                argv = [call.args[0] for call in trace]
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn("invalid container id output", str(receipt["detail"]))
                self.assertFalse(any(args[:2] == ["docker", "inspect"] for args in argv))
                self.assertFalse(any(args[:2] == ["docker", "start"] for args in argv))
                self.assertFalse(any(args[:2] == ["docker", "rm"] for args in argv))

    def test_container_handle_is_identical_across_inspect_start_and_remove(self) -> None:
        created_id = "a" * 64
        trace: list[object] = []
        exit_code, receipt = exercise_host_container_result(
            encoded_receipt(reconciled_pass_receipt()),
            created_stdout=created_id.encode("ascii"),
            call_trace=trace,
        )
        argv = [call.args[0] for call in trace]
        self.assertEqual(exit_code, 0)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["effective_config"]["container_id"], created_id)
        self.assertEqual(receipt["image"]["id"], FIXTURE_IMAGE_ID)
        self.assertEqual(
            receipt["effective_config"]["image_id"], FIXTURE_IMAGE_ID
        )
        self.assertEqual(
            receipt["effective_config"]["image_tag"], expected_image_tag()
        )
        self.assertIn(["docker", "inspect", created_id], argv)
        self.assertIn(["docker", "start", "--attach", created_id], argv)
        self.assertIn(["docker", "rm", "--force", created_id], argv)
        self.assertEqual(receipt["cleanup"]["status"], "SUCCESS")
        self.assertEqual(receipt["cleanup"]["primary_status"], "PASS")

    def test_cleanup_boundary_classifies_all_direct_outcomes(self) -> None:
        container_id = "a" * 64
        completed = run_sandbox.subprocess.CompletedProcess
        timeout = run_sandbox.subprocess.TimeoutExpired(
            ["docker", "rm", "--force", container_id],
            run_sandbox.CLEANUP_TIMEOUT_SECONDS,
            output=b"timeout-out",
            stderr=b"timeout-error",
        )
        cases = {
            "success": (
                completed(["docker", "rm"], 0, b"removed", b""),
                "SUCCESS",
                None,
            ),
            "timeout": (timeout, "FAILURE", "TIMEOUT"),
            "launch": (OSError("fixture launch failure"), "FAILURE", "LAUNCH_FAILURE"),
            "nonzero": (
                completed(["docker", "rm"], 17, b"", b"remove failed"),
                "FAILURE",
                "NONZERO_EXIT",
            ),
            "malformed_result": (object(), "FAILURE", "MALFORMED_RESULT"),
            "malformed_stream": (
                completed(["docker", "rm"], 0, "not-bytes", b""),
                "FAILURE",
                "MALFORMED_RESULT",
            ),
            "call_exception": (
                ValueError("fixture malformed exception"),
                "FAILURE",
                "CALL_EXCEPTION",
            ),
        }
        for name, (outcome, expected_status, expected_kind) in cases.items():
            with self.subTest(name=name):
                with mock.patch.object(run_sandbox, "run", side_effect=[outcome]):
                    cleanup = run_sandbox._cleanup_container(container_id)
                self.assertEqual(cleanup["status"], expected_status)
                self.assertEqual(cleanup.get("failure_kind"), expected_kind)
                self.assertEqual(cleanup["container_removed"], name == "success")
                self.assertEqual(
                    json.loads(run_sandbox.canonical_bytes(cleanup)), cleanup
                )

        with mock.patch.object(run_sandbox, "run") as mocked_run:
            cleanup = run_sandbox._cleanup_container(None)
        mocked_run.assert_not_called()
        self.assertEqual(cleanup["status"], "NOT_REQUIRED")
        self.assertFalse(cleanup["attempted"])

    def test_cleanup_failures_emit_one_receipt_and_override_primary_pass(self) -> None:
        container_id = "a" * 64
        completed = run_sandbox.subprocess.CompletedProcess
        timeout = run_sandbox.subprocess.TimeoutExpired(
            ["docker", "rm", "--force", container_id],
            run_sandbox.CLEANUP_TIMEOUT_SECONDS,
            output=b"partial cleanup output",
            stderr=b"cleanup timeout",
        )
        cases = {
            "timeout": (timeout, "TIMEOUT"),
            "launch": (OSError("fixture launch failure"), "LAUNCH_FAILURE"),
            "nonzero": (
                completed(["docker", "rm"], 23, b"", b"fixture remove failure"),
                "NONZERO_EXIT",
            ),
        }
        payload = encoded_receipt(reconciled_pass_receipt())
        for name, (outcome, expected_kind) in cases.items():
            with self.subTest(name=name):
                exit_code, receipt = exercise_host_container_result(
                    payload, cleanup_outcome=outcome
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "CLEANUP_FAILURE")
                self.assertEqual(receipt["cleanup"]["status"], "FAILURE")
                self.assertEqual(receipt["cleanup"]["failure_kind"], expected_kind)
                self.assertEqual(receipt["cleanup"]["primary_status"], "PASS")
                self.assertEqual(receipt["cleanup"]["primary_exit_code"], 0)
                self.assertIn("inner_receipt", receipt)
                self.assertEqual(
                    json.loads(run_sandbox.canonical_bytes(receipt)), receipt
                )

    def test_primary_failure_and_cleanup_failure_are_both_retained(self) -> None:
        timeout = run_sandbox.subprocess.TimeoutExpired(
            ["docker", "rm", "--force", "a" * 64],
            run_sandbox.CLEANUP_TIMEOUT_SECONDS,
            output=b"",
            stderr=b"cleanup timeout",
        )
        exit_code, receipt = exercise_host_container_result(
            b'{"status":"PASS"}\n', cleanup_outcome=timeout
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "INVALID_CONTAINER_RECEIPT")
        self.assertIn("schema mismatch", receipt["detail"])
        self.assertEqual(receipt["cleanup"]["status"], "FAILURE")
        self.assertEqual(receipt["cleanup"]["failure_kind"], "TIMEOUT")
        self.assertEqual(
            receipt["cleanup"]["primary_status"], "INVALID_CONTAINER_RECEIPT"
        )
        self.assertEqual(receipt["cleanup"]["primary_exit_code"], 1)

    def test_no_container_cleanup_is_explicit_and_does_not_invoke_remove(self) -> None:
        completed = run_sandbox.subprocess.CompletedProcess
        docker_version = {
            "Client": {"Version": "fixture", "Os": "windows", "Arch": "amd64"},
            "Server": {"Version": "fixture", "Os": "linux", "Arch": "amd64"},
        }
        calls = [
            completed(
                ["docker", "version"],
                0,
                json.dumps(docker_version).encode("utf-8"),
                b"",
            ),
            completed(["docker", "build"], 0, b"build", b""),
            completed(["docker", "image", "inspect"], 17, b"", b"not found"),
        ]
        emitted: list[dict[str, object]] = []
        git_state = {
            "sha": "f" * 40,
            "branch": run_sandbox.EXPECTED_BRANCH,
            "clean": True,
            "status_sha256": "a" * 64,
            "baseline_ancestor": True,
        }
        with (
            mock.patch.object(run_sandbox, "_git_receipt", return_value=git_state),
            mock.patch.object(run_sandbox, "_host_profile", return_value={}),
            mock.patch.object(run_sandbox, "run", side_effect=calls) as mocked_run,
            mock.patch.object(
                run_sandbox,
                "_emit",
                side_effect=lambda receipt, _output: emitted.append(receipt),
            ),
        ):
            exit_code = run_sandbox.main([])
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(emitted), 1)
        receipt = emitted[0]
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertEqual(receipt["cleanup"]["status"], "NOT_REQUIRED")
        self.assertEqual(receipt["cleanup"]["primary_status"], "SANDBOX_SETUP_FAILURE")
        argv = [call.args[0] for call in mocked_run.call_args_list]
        self.assertFalse(any(args[:2] == ["docker", "rm"] for args in argv))

    def test_f_sandbox_009_exact_process_witness_fails_closed(self) -> None:
        raw = valid_docker_inspect()
        raw["Path"] = "/bin/sh"
        raw["Args"] = ["-c", "emit-forged-pass"]
        historical_raw = historical_inspect_before_f013(raw)
        historical_raw.pop("Id")
        historical_raw.pop("Image")
        historical_config = historical_raw["Config"]
        self.assertIsInstance(historical_config, dict)
        historical_config.pop("Image")
        witness = run_sandbox.canonical_bytes(historical_raw)
        self.assertEqual(len(witness), 801)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "78abdfa49c34795b091889d09af270edf4511d79e1d0858f5b6c0682387f4786",
        )

        selected = run_sandbox._selected_inspect(raw)
        with self.assertRaisesRegex(RuntimeError, "process_(path|args)"):
            run_sandbox._assert_inspect(
                selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
            )

        payload = encoded_receipt(historical_pass_receipt_before_f015())
        self.assertEqual(
            run_sandbox.sha256(payload),
            "eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55",
        )
        exit_code, receipt = exercise_host_container_result(
            payload, raw_inspect=raw
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertRegex(str(receipt["detail"]), "process_(path|args)")
        self.assertNotIn("inner_receipt", receipt)

    def test_process_path_and_args_mutations_fail_direct_and_host_flow(self) -> None:
        mutations: dict[str, tuple[str, object, bool]] = {
            "path_missing": ("Path", None, True),
            "path_null": ("Path", None, False),
            "path_list": ("Path", ["python"], False),
            "path_case": ("Path", "Python", False),
            "path_absolute": ("Path", "/usr/local/bin/python", False),
            "path_extra": ("Path", "python ", False),
            "args_missing": ("Args", None, True),
            "args_null": ("Args", None, False),
            "args_string": (
                "Args",
                "-B /repo/portability/sandbox/expanded_gate.py",
                False,
            ),
            "args_extra": (
                "Args",
                list(run_sandbox.EXPECTED_PROCESS_ARGS) + ["unexpected"],
                False,
            ),
            "args_order": (
                "Args",
                list(reversed(run_sandbox.EXPECTED_PROCESS_ARGS)),
                False,
            ),
            "args_flag_case": (
                "Args",
                ["-b", "/repo/portability/sandbox/expanded_gate.py"],
                False,
            ),
            "args_path_case": (
                "Args",
                ["-B", "/repo/portability/sandbox/Expanded_Gate.py"],
                False,
            ),
            "args_path_mutation": (
                "Args",
                ["-B", "/repo/portability/sandbox/expanded-gate.py"],
                False,
            ),
            "args_flag_missing": (
                "Args",
                ["/repo/portability/sandbox/expanded_gate.py"],
                False,
            ),
            "args_wrong_element_type": (
                "Args",
                ["-B", {"path": "/repo/portability/sandbox/expanded_gate.py"}],
                False,
            ),
        }
        payload = encoded_receipt(synthetic_pass_receipt())
        for name, (field, value, remove) in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                if remove:
                    raw.pop(field)
                else:
                    raw[field] = value
                selected = run_sandbox._selected_inspect(raw)
                expected_detail = "process_path" if field == "Path" else "process_args"
                with self.assertRaisesRegex(RuntimeError, expected_detail):
                    run_sandbox._assert_inspect(
                        selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
                    )

                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn(expected_detail, str(receipt["detail"]))
                self.assertNotIn("inner_receipt", receipt)

    def test_f_sandbox_008_exact_entrypoint_witness_fails_closed(self) -> None:
        raw = valid_docker_inspect()
        config = raw["Config"]
        self.assertIsInstance(config, dict)
        config["Entrypoint"] = ["/bin/sh", "-c", "emit-forged-pass"]
        selected = run_sandbox._selected_inspect(raw)

        legacy_selected = dict(selected)
        legacy_selected.pop("process_path")
        legacy_selected.pop("process_args")
        legacy_selected.pop("command")
        legacy_selected.pop("container_id")
        legacy_selected.pop("image_id")
        legacy_selected.pop("image_tag")
        legacy_selected.pop("network_disabled")
        legacy_selected.pop("auto_remove")
        legacy_selected.pop("oom_kill_disable")
        legacy_selected.pop("init_process")
        legacy_selected.pop("hostname")
        legacy_selected.pop("environment_hostname")
        remove_selected_mount_source(legacy_selected)
        legacy_selected["environment_names"] = ["HOME"]
        witness = run_sandbox.canonical_bytes(legacy_selected)
        self.assertEqual(len(witness), 764)
        self.assertEqual(
            run_sandbox.sha256(witness),
            "3b00ca00e9cb36c69a5f566b840f8e2ff7300f16d3b1a4d33734220d3b044972",
        )
        with self.assertRaisesRegex(RuntimeError, "entrypoint"):
            run_sandbox._assert_inspect(
                selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
            )

        payload = encoded_receipt(historical_pass_receipt_before_f015())
        self.assertEqual(
            run_sandbox.sha256(payload),
            "eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55",
        )
        exit_code, receipt = exercise_host_container_result(
            payload, raw_inspect=raw
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
        self.assertIn("entrypoint", receipt["detail"])
        self.assertNotIn("inner_receipt", receipt)

    def test_entrypoint_and_command_shape_mutations_fail_direct_and_host_flow(
        self,
    ) -> None:
        mutations: dict[str, tuple[str, object, bool]] = {
            "entrypoint_shell": (
                "Entrypoint",
                ["/bin/sh", "-c", "emit-forged-pass"],
                False,
            ),
            "entrypoint_string": (
                "Entrypoint",
                "python -B /repo/portability/sandbox/expanded_gate.py",
                False,
            ),
            "entrypoint_extra": (
                "Entrypoint",
                list(run_sandbox.EXPECTED_ENTRYPOINT) + ["unexpected"],
                False,
            ),
            "entrypoint_missing": ("Entrypoint", None, True),
            "entrypoint_wrong_type": ("Entrypoint", {"argv": "python"}, False),
            "command_inherited": ("Cmd", ["python3"], False),
            "command_string": ("Cmd", "python3", False),
            "command_extra": ("Cmd", ["unexpected"], False),
            "command_missing": ("Cmd", None, True),
            "command_wrong_type": ("Cmd", {"argv": []}, False),
        }
        payload = encoded_receipt(synthetic_pass_receipt())
        for name, (field, value, remove) in mutations.items():
            with self.subTest(name=name):
                raw = valid_docker_inspect()
                config = raw["Config"]
                self.assertIsInstance(config, dict)
                if remove:
                    config.pop(field)
                else:
                    config[field] = value
                selected = run_sandbox._selected_inspect(raw)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "entrypoint" if field == "Entrypoint" else "command",
                ):
                    run_sandbox._assert_inspect(
                        selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
                    )

                exit_code, receipt = exercise_host_container_result(
                    payload, raw_inspect=raw
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(receipt["status"], "SANDBOX_SETUP_FAILURE")
                self.assertIn(
                    "entrypoint" if field == "Entrypoint" else "command",
                    receipt["detail"],
                )
                self.assertNotIn("inner_receipt", receipt)

    def test_dockerfile_create_plan_and_inspect_share_one_execution_contract(
        self,
    ) -> None:
        dockerfile = (HERE / "Dockerfile").read_text(encoding="utf-8")
        expected_entrypoint = json.dumps(run_sandbox.EXPECTED_ENTRYPOINT)
        self.assertIn(f"ENTRYPOINT {expected_entrypoint}", dockerfile)
        self.assertIn(
            f"CMD {json.dumps(run_sandbox.EXPECTED_COMMAND)}", dockerfile
        )
        for name in sorted(run_sandbox.DOCKERFILE_ENVIRONMENT_NAMES):
            self.assertIn(
                f"{name}={run_sandbox.EXPECTED_EFFECTIVE_ENVIRONMENT[name]}",
                dockerfile,
            )

        image = "fixture:image"
        plan = run_sandbox._plan(image)
        self.assertEqual(
            set(run_sandbox.EXPECTED_EFFECTIVE_ENVIRONMENT),
            run_sandbox.PINNED_BASE_ENVIRONMENT_NAMES
            | run_sandbox.CREATE_ENVIRONMENT_NAMES,
        )
        create = plan["create"]
        create_environment: dict[str, str] = {}
        for index, item in enumerate(create):
            if item == "--env":
                name, value = create[index + 1].split("=", 1)
                self.assertNotIn(name, create_environment)
                create_environment[name] = value
        self.assertEqual(
            create_environment,
            {
                name: run_sandbox.EXPECTED_EFFECTIVE_ENVIRONMENT[name]
                for name in run_sandbox.CREATE_ENVIRONMENT_NAMES
            },
        )
        self.assertEqual(plan["create"][-1], image)
        self.assertEqual(plan["create"].count(image), 1)
        self.assertEqual(
            plan["expected_image"],
            {
                "tag": image,
                "container_config_image": image,
                "container_root_image": "docker-image-inspect.Id",
            },
        )
        self.assertEqual(
            plan["expected_execution"],
            {
                "entrypoint": run_sandbox.EXPECTED_ENTRYPOINT,
                "command": run_sandbox.EXPECTED_COMMAND,
                "path": run_sandbox.EXPECTED_PROCESS_PATH,
                "args": run_sandbox.EXPECTED_PROCESS_ARGS,
            },
        )
        self.assertEqual(
            plan["expected_hostname"],
            {
                "config": run_sandbox.EXPECTED_HOSTNAME,
                "environment": run_sandbox.EXPECTED_HOSTNAME,
                "kernel_nodename": run_sandbox.EXPECTED_HOSTNAME,
            },
        )
        self.assertEqual(
            plan["expected_environment_names"],
            run_sandbox.EXPECTED_ENVIRONMENT_NAMES,
        )

        selected = run_sandbox._selected_inspect(valid_docker_inspect())
        self.assertEqual(selected["entrypoint"], run_sandbox.EXPECTED_ENTRYPOINT)
        self.assertEqual(selected["command"], run_sandbox.EXPECTED_COMMAND)
        self.assertEqual(selected["process_path"], run_sandbox.EXPECTED_PROCESS_PATH)
        self.assertEqual(selected["process_args"], run_sandbox.EXPECTED_PROCESS_ARGS)
        self.assertEqual(selected["hostname"], run_sandbox.EXPECTED_HOSTNAME)
        self.assertEqual(
            selected["environment_hostname"], run_sandbox.EXPECTED_HOSTNAME
        )
        self.assertEqual(
            selected["environment_names"], run_sandbox.EXPECTED_ENVIRONMENT_NAMES
        )
        run_sandbox._assert_inspect(
            selected, "a" * 64, FIXTURE_IMAGE_ID, expected_image_tag()
        )

    def test_gate_has_exact_expanded_command_count(self) -> None:
        self.assertEqual(len(expanded_gate.GATES), 11)
        self.assertEqual(len({gate.gate_id for gate in expanded_gate.GATES}), 11)

    def test_core_validator_sums_800(self) -> None:
        counts = {
            "semantic": 112,
            "competence": 370,
            "wrapper_arms": 224,
            "negative": 10,
            "metamorphic": 4,
            "error_law": 80,
        }
        output = f"mode=in-process counts={json.dumps(counts)} failures=0\n".encode()
        observed = expanded_gate.validate_gate_output("core_800", output, b"")
        self.assertEqual(observed["total"], 800)

    def test_core_validator_rejects_wrong_total(self) -> None:
        output = b'mode=in-process counts={"semantic":799} failures=0\n'
        with self.assertRaises(expanded_gate.GateFailure):
            expanded_gate.validate_gate_output("core_800", output, b"")

    def test_composed_validator_requires_both_suites(self) -> None:
        output = (
            b'mode=in-process suite=0.2 counts={"all":800} total=800 failures=0\n'
            b'mode=in-process suite=0.3 counts={"all":107} total=107 failures=0\n'
        )
        observed = expanded_gate.validate_gate_output(
            "composed_800_107", output, b""
        )
        self.assertEqual(observed["0.2"]["total"], 800)
        self.assertEqual(observed["0.3"]["total"], 107)

    def test_fuzz_validator_requires_31_of_31(self) -> None:
        output = (
            b"rr-fuzz: verdict=PASS cases=31/31 seed=fixture source=generated "
            b"failures=0 budget_exhausted=false\n"
        )
        observed = expanded_gate.validate_gate_output("fuzz_31", output, b"")
        self.assertEqual(observed["completed"], 31)

    def test_canonical_receipt_encoding_is_stable(self) -> None:
        left = run_sandbox.canonical_bytes({"b": 2, "a": 1})
        right = run_sandbox.canonical_bytes({"a": 1, "b": 2})
        self.assertEqual(left, right)
        self.assertEqual(left, b'{"a":1,"b":2}')

    def test_valid_synthetic_pass_receipt_is_accepted(self) -> None:
        receipt = reconciled_pass_receipt()
        validated = run_sandbox.validate_inner_receipt(encoded_receipt(receipt))
        self.assertEqual(validated, receipt)

        completed = run_sandbox.subprocess.CompletedProcess(
            ["docker", "start"], 0, encoded_receipt(receipt), b""
        )
        self.assertEqual(run_sandbox.validate_container_pass(completed), receipt)
        exit_code, host_receipt = exercise_host_container_result(
            encoded_receipt(receipt)
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(host_receipt["status"], "PASS")
        self.assertEqual(host_receipt["inner_receipt"], receipt)

    def test_evidence_free_and_malformed_pass_receipts_fail_closed(self) -> None:
        invalid_payloads = {
            "evidence_free": b'{"status":"PASS"}\n',
            "not_canonical": b'{ "status": "PASS" }\n',
            "duplicate_member": b'{"status":"PASS","status":"PASS"}\n',
            "not_json": b"PASS\n",
        }
        for name, payload in invalid_payloads.items():
            with self.subTest(name=name):
                with self.assertRaises(run_sandbox.InnerReceiptError):
                    run_sandbox.validate_inner_receipt(payload)

        exit_code, host_receipt = exercise_host_container_result(
            b'{"status":"PASS"}\n'
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(host_receipt["status"], "INVALID_CONTAINER_RECEIPT")

    def test_non_finite_numbers_are_receipt_errors_at_any_depth(self) -> None:
        invalid_payloads = {
            "positive_overflow": b'{"status":"PASS","x":1e309}\n',
            "negative_overflow_nested": b'{"status":"PASS","x":[{"y":-1e309}]}\n',
            "nan_constant": b'{"status":"PASS","x":NaN}\n',
            "positive_infinity_constant": b'{"status":"PASS","x":Infinity}\n',
            "negative_infinity_constant": b'{"status":"PASS","x":-Infinity}\n',
        }
        for name, payload in invalid_payloads.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    run_sandbox.InnerReceiptError, "non-finite JSON number"
                ):
                    run_sandbox.validate_inner_receipt(payload)

    def test_overflow_and_malformed_numbers_fail_as_invalid_host_receipts(self) -> None:
        payloads = {
            "overflow": b'{"status":"PASS","x":1e309}\n',
            "nested_overflow": b'{"status":"PASS","x":{"y":-1e309}}\n',
            "malformed_exponent": b'{"status":"PASS","x":1e}\n',
        }
        for name, payload in payloads.items():
            with self.subTest(name=name):
                exit_code, host_receipt = exercise_host_container_result(payload)
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    host_receipt["status"], "INVALID_CONTAINER_RECEIPT"
                )

    def test_finite_float_neighbor_and_canonicalization_errors_are_bounded(self) -> None:
        self.assertEqual(run_sandbox._parse_json_float("1e308"), 1e308)
        self.assertEqual(run_sandbox._parse_json_float("2.0"), 2.0)
        for error in (ValueError("fixture value"), TypeError("fixture type")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(
                    run_sandbox, "canonical_bytes", side_effect=error
                ):
                    with self.assertRaisesRegex(
                        run_sandbox.InnerReceiptError,
                        "receipt cannot be canonicalized",
                    ):
                        run_sandbox.validate_inner_receipt(b"{}\n")

    def test_missing_treatment_and_boundary_evidence_fail_closed(self) -> None:
        mutations: dict[str, tuple[object, object]] = {
            "treatment": ("treatment_exposed", False),
            "boundary": ("boundary", None),
        }
        for name, (key, value) in mutations.items():
            with self.subTest(name=name):
                receipt = synthetic_pass_receipt()
                if value is None:
                    del receipt[str(key)]
                else:
                    receipt[str(key)] = value
                with self.assertRaises(run_sandbox.InnerReceiptError):
                    run_sandbox.validate_inner_receipt(encoded_receipt(receipt))

        boundary_mutations = {
            "writable_root": ("root_read_only", False),
            "network": ("network_interfaces", ["eth0", "lo"]),
            "secret": ("environment_names", ["API_TOKEN", "HOME"]),
        }
        for name, (key, value) in boundary_mutations.items():
            with self.subTest(name=name):
                receipt = synthetic_pass_receipt()
                boundary = receipt["boundary"]
                self.assertIsInstance(boundary, dict)
                boundary[key] = value
                with self.assertRaises(run_sandbox.InnerReceiptError):
                    run_sandbox.validate_inner_receipt(encoded_receipt(receipt))

    def test_inner_hostname_evidence_rejects_missing_types_case_and_whitespace(
        self,
    ) -> None:
        missing = object()
        mutations: dict[str, object] = {
            "missing": missing,
            "null": None,
            "boolean": False,
            "integer": 7,
            "array": [run_sandbox.EXPECTED_HOSTNAME],
            "object": {"value": run_sandbox.EXPECTED_HOSTNAME},
            "empty": "",
            "case": "RR-SANDBOX",
            "leading_whitespace": " rr-sandbox",
            "trailing_whitespace": "rr-sandbox ",
            "evil": "evil-host",
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                receipt = reconciled_pass_receipt()
                boundary = receipt["boundary"]
                self.assertIsInstance(boundary, dict)
                if mutation is missing:
                    boundary.pop("hostname")
                else:
                    boundary["hostname"] = mutation
                if mutation is not missing:
                    reproject_receipt(receipt)
                payload = encoded_receipt(receipt)
                with self.assertRaisesRegex(
                    run_sandbox.InnerReceiptError,
                    "boundary|hostname",
                ):
                    run_sandbox.validate_inner_receipt(payload)

                exit_code, host_receipt = exercise_host_container_result(payload)
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    host_receipt["status"], "INVALID_CONTAINER_RECEIPT"
                )
                self.assertNotIn("inner_receipt", host_receipt)

    def test_expanded_gate_observes_exact_kernel_and_process_hostname(self) -> None:
        mounts = {
            "/": {"mount_options": ["ro"]},
            "/repo": {"mount_options": ["ro"]},
            "/tmp": {
                "fs_type": "tmpfs",
                "mount_options": ["rw", "noexec", "nosuid", "nodev"],
                "super_options": [],
            },
        }
        status = {
            "CapEff": "0",
            "CapPrm": "0",
            "CapBnd": "0",
            "CapAmb": "0",
            "NoNewPrivs": "1",
            "Seccomp": "2",
        }
        cgroup = {
            "version": 2,
            "cpu_max": "200000 100000",
            "cpu_count": 2.0,
            "memory_max_bytes": 4 * 1024**3,
            "memory_swap_max_bytes": 0,
            "pids_max": 256,
        }

        def observe(
            nodename: str,
            environment_hostname: str | None = run_sandbox.EXPECTED_HOSTNAME,
        ) -> dict[str, object]:
            process_environment = {"HOME": "/tmp"}
            if environment_hostname is not None:
                process_environment["HOSTNAME"] = environment_hostname
            with (
                mock.patch.object(expanded_gate.platform, "system", return_value="Linux"),
                mock.patch.object(expanded_gate.os, "geteuid", return_value=65532, create=True),
                mock.patch.object(expanded_gate.os, "getegid", return_value=65532, create=True),
                mock.patch.object(
                    expanded_gate.os,
                    "uname",
                    return_value=mock.Mock(nodename=nodename),
                    create=True,
                ),
                mock.patch.object(expanded_gate, "_status_fields", return_value=status),
                mock.patch.object(expanded_gate, "_mount_table", return_value=mounts),
                mock.patch.object(
                    expanded_gate.Path,
                    "iterdir",
                    return_value=[expanded_gate.Path("/sys/class/net/lo")],
                ),
                mock.patch.object(
                    expanded_gate,
                    "_tmpfs_size",
                    return_value=expanded_gate.TMPFS_LIMIT_BYTES,
                ),
                mock.patch.object(expanded_gate, "_check_cgroup", return_value=cgroup),
                mock.patch.dict(
                    expanded_gate.os.environ,
                    process_environment,
                    clear=True,
                ),
            ):
                return expanded_gate.verify_boundary()

        observed = observe(run_sandbox.EXPECTED_HOSTNAME)
        self.assertEqual(observed["hostname"], run_sandbox.EXPECTED_HOSTNAME)
        self.assertEqual(
            observed["environment_hostname"], run_sandbox.EXPECTED_HOSTNAME
        )
        with self.assertRaisesRegex(expanded_gate.BoundaryFailure, "kernel nodename"):
            observe("evil-host")
        for name, value in {
            "missing": None,
            "case": "RR-SANDBOX",
            "leading_whitespace": " rr-sandbox",
            "trailing_whitespace": "rr-sandbox ",
            "evil": "evil-host",
        }.items():
            with self.subTest(process_hostname=name):
                with self.assertRaisesRegex(
                    expanded_gate.BoundaryFailure, "process HOSTNAME"
                ):
                    observe(run_sandbox.EXPECTED_HOSTNAME, value)

    def test_f_sandbox_016_inner_environment_hostname_fails_closed(self) -> None:
        missing = object()
        mutations: dict[str, object] = {
            "missing": missing,
            "null": None,
            "boolean": False,
            "integer": 7,
            "array": [run_sandbox.EXPECTED_HOSTNAME],
            "object": {"value": run_sandbox.EXPECTED_HOSTNAME},
            "empty": "",
            "case": "RR-SANDBOX",
            "leading_whitespace": " rr-sandbox",
            "trailing_whitespace": "rr-sandbox ",
            "evil": "evil-host",
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                receipt = reconciled_pass_receipt()
                boundary = receipt["boundary"]
                self.assertIsInstance(boundary, dict)
                if mutation is missing:
                    boundary.pop("environment_hostname")
                else:
                    boundary["environment_hostname"] = mutation
                    reproject_receipt(receipt)
                payload = encoded_receipt(receipt)
                with self.assertRaisesRegex(
                    run_sandbox.InnerReceiptError,
                    "boundary|environment_hostname",
                ):
                    run_sandbox.validate_inner_receipt(payload)

                exit_code, host_receipt = exercise_host_container_result(payload)
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    host_receipt["status"], "INVALID_CONTAINER_RECEIPT"
                )
                self.assertNotIn("inner_receipt", host_receipt)

    def test_f_sandbox_016_host_reconciles_process_and_config_hostname(
        self,
    ) -> None:
        valid = reconciled_pass_receipt()
        effective = run_sandbox._selected_inspect(valid_docker_inspect())
        run_sandbox._reconcile_inner_environment(valid, effective)

        for field in ("hostname", "environment_hostname"):
            for name, mutation in {
                "missing": None,
                "null": None,
                "boolean": False,
                "integer": 7,
                "case": "RR-SANDBOX",
                "leading_whitespace": " rr-sandbox",
                "trailing_whitespace": "rr-sandbox ",
                "evil": "evil-host",
            }.items():
                with self.subTest(field=field, mutation=name):
                    mutated = copy.deepcopy(effective)
                    if name == "missing":
                        mutated.pop(field)
                    else:
                        mutated[field] = mutation
                    with self.assertRaisesRegex(
                        run_sandbox.InnerReceiptError,
                        "environment_hostname",
                    ):
                        run_sandbox._reconcile_inner_environment(valid, mutated)

    def test_wrong_command_count_identity_exit_and_counts_fail_closed(self) -> None:
        cases = (
            "command_count",
            "identity",
            "exit",
            "observed_count",
        )
        for name in cases:
            with self.subTest(name=name):
                receipt = synthetic_pass_receipt()
                commands = receipt["commands"]
                self.assertIsInstance(commands, list)
                if name == "command_count":
                    commands.pop()
                elif name == "identity":
                    commands[0]["argv"] = ["python", "dishonest.py"]
                elif name == "exit":
                    commands[0]["exit_code"] = 9
                else:
                    commands[5]["observed"]["checks"] = 2295
                with self.assertRaises(run_sandbox.InnerReceiptError):
                    run_sandbox.validate_inner_receipt(encoded_receipt(receipt))

    def test_missing_hash_resource_and_wrong_projection_fail_closed(self) -> None:
        cases = ("hash", "resource", "projection")
        for name in cases:
            with self.subTest(name=name):
                receipt = synthetic_pass_receipt()
                commands = receipt["commands"]
                self.assertIsInstance(commands, list)
                if name == "hash":
                    del commands[0]["stdout_sha256"]
                elif name == "resource":
                    del commands[0]["resources"]["children_max_rss_kib"]
                else:
                    receipt["deterministic_projection_sha256"] = "f" * 64
                with self.assertRaises(run_sandbox.InnerReceiptError):
                    run_sandbox.validate_inner_receipt(encoded_receipt(receipt))

    def test_zero_byte_stream_digest_mismatch_fails_direct_and_host_validation(self) -> None:
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream):
                receipt = synthetic_pass_receipt()
                commands = receipt["commands"]
                self.assertIsInstance(commands, list)
                commands[0][f"{stream}_bytes"] = 0
                commands[0][f"{stream}_sha256"] = "0" * 63 + "1"
                payload = encoded_receipt(receipt)

                with self.assertRaisesRegex(
                    run_sandbox.InnerReceiptError,
                    rf"commands\[0\]\.{stream}_sha256.*SHA-256\(empty\)",
                ):
                    run_sandbox.validate_inner_receipt(payload)

                exit_code, host_receipt = exercise_host_container_result(payload)
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    host_receipt["status"], "INVALID_CONTAINER_RECEIPT"
                )
                self.assertIn(
                    f"commands[0].{stream}_sha256", host_receipt["detail"]
                )

    def test_f_sandbox_007_exact_witness_is_rejected(self) -> None:
        receipt = historical_pass_receipt_before_f015()
        commands = receipt["commands"]
        self.assertIsInstance(commands, list)
        for index, command in enumerate(commands):
            command["stderr_sha256"] = f"{index + 101:064x}"
        commands[0]["stdout_bytes"] = 0
        commands[0]["stdout_sha256"] = "0" * 63 + "1"
        payload = encoded_receipt(receipt)

        self.assertEqual(len(payload), 7561)
        self.assertEqual(
            run_sandbox.sha256(payload),
            "4433ea1bb53c148d391f680322a3fe2ed597505c5d97bf7edae034dc6d6574fb",
        )
        with self.assertRaises(run_sandbox.InnerReceiptError):
            run_sandbox.validate_inner_receipt(payload)

    def test_nonzero_stream_byte_neighbors_remain_structurally_valid(self) -> None:
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream):
                receipt = reconciled_pass_receipt()
                commands = receipt["commands"]
                self.assertIsInstance(commands, list)
                commands[0][f"{stream}_bytes"] = 1
                commands[0][f"{stream}_sha256"] = "1" * 64
                payload = encoded_receipt(receipt)

                self.assertEqual(
                    run_sandbox.validate_inner_receipt(payload), receipt
                )
                exit_code, host_receipt = exercise_host_container_result(payload)
                self.assertEqual(exit_code, 0)
                self.assertEqual(host_receipt["status"], "PASS")

    def test_nonzero_container_exit_cannot_promote_valid_inner_pass(self) -> None:
        receipt = synthetic_pass_receipt()
        completed = run_sandbox.subprocess.CompletedProcess(
            ["docker", "start"], 17, encoded_receipt(receipt), b""
        )
        with self.assertRaises(run_sandbox.InnerReceiptError):
            run_sandbox.validate_container_pass(completed)

    def test_git_receipt_records_valid_negative_ancestry(self) -> None:
        completed = run_sandbox.subprocess.CompletedProcess
        results = [
            completed(["git"], 0, b"f" * 40 + b"\n", b""),
            completed(["git"], 0, b"fixture-branch\n", b""),
            completed(["git"], 0, b"?? fixture\n", b""),
            completed(["git"], 1, b"", b""),
        ]
        with mock.patch.object(run_sandbox, "run", side_effect=results):
            receipt = run_sandbox._git_receipt()
        self.assertFalse(receipt["clean"])
        self.assertFalse(receipt["baseline_ancestor"])

    def test_cli_unavailable_receipt_is_fully_bound_and_exits_two(self) -> None:
        git_state = {
            "sha": "f" * 40,
            "branch": "fixture-branch",
            "clean": False,
            "status_sha256": "a" * 64,
            "baseline_ancestor": True,
        }
        host = {"os": "FixtureOS", "machine": "fixture-arch"}
        emitted: list[dict[str, object]] = []

        def capture(receipt: dict[str, object], _output: Path | None) -> None:
            emitted.append(receipt)

        with (
            mock.patch.object(run_sandbox, "_git_receipt", return_value=git_state),
            mock.patch.object(run_sandbox, "_host_profile", return_value=host),
            mock.patch.object(
                run_sandbox, "run", side_effect=FileNotFoundError("fixture")
            ),
            mock.patch.object(run_sandbox, "_emit", side_effect=capture),
        ):
            exit_code = run_sandbox.main([])

        self.assertEqual(exit_code, 2)
        self.assertEqual(len(emitted), 1)
        receipt = emitted[0]
        self.assertEqual(receipt["status"], "INFRA_UNAVAILABLE")
        self.assertIs(receipt["git"], git_state)
        self.assertIs(receipt["host"], host)
        self.assertEqual(
            receipt["image"]["dockerfile_sha256"],
            run_sandbox.sha256((HERE / "Dockerfile").read_bytes()),
        )
        self.assertEqual(receipt["plan"]["build"][0:2], ["docker", "build"])
        self.assertEqual(receipt["plan"]["create"][0:2], ["docker", "create"])

    def test_daemon_unavailable_receipt_binds_probe_evidence(self) -> None:
        probe = run_sandbox.subprocess.CompletedProcess(
            ["docker", "version"], 1, b"fixture-out", b"fixture-error"
        )
        receipt = run_sandbox._infra_receipt(
            "Docker daemon unavailable",
            git_state={"sha": "f" * 40},
            host={"os": "FixtureOS"},
            image={"tag": "fixture:image", "dockerfile_sha256": "d" * 64},
            plan={
                "build": ["docker", "build"],
                "create": ["docker", "create"],
            },
            probe=probe,
        )
        self.assertEqual(receipt["probe"]["exit_code"], 1)
        self.assertEqual(
            receipt["probe"]["stdout_sha256"],
            run_sandbox.sha256(b"fixture-out"),
        )
        self.assertEqual(
            receipt["probe"]["stderr_sha256"],
            run_sandbox.sha256(b"fixture-error"),
        )

    def test_nonobject_and_malformed_version_probes_are_bound_infra(self) -> None:
        payloads = {
            "finding_list": b"[]",
            "null": b"null",
            "string": b'"fixture"',
            "number": b"7",
            "malformed": b"{",
            "invalid_utf8": b"\xff",
        }
        self.assertEqual(
            run_sandbox.sha256(payloads["finding_list"]),
            "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        )
        for name, payload in payloads.items():
            with self.subTest(name=name):
                probe = run_sandbox.subprocess.CompletedProcess(
                    ["docker", "version"], 0, payload, b""
                )
                git_state = {
                    "sha": "f" * 40,
                    "branch": run_sandbox.EXPECTED_BRANCH,
                    "clean": True,
                    "status_sha256": "a" * 64,
                    "baseline_ancestor": True,
                }
                host = {"os": "FixtureOS", "machine": "fixture-arch"}
                emitted: list[dict[str, object]] = []

                with (
                    mock.patch.object(
                        run_sandbox, "_git_receipt", return_value=git_state
                    ),
                    mock.patch.object(
                        run_sandbox, "_host_profile", return_value=host
                    ),
                    mock.patch.object(
                        run_sandbox, "run", return_value=probe
                    ) as mocked_run,
                    mock.patch.object(
                        run_sandbox,
                        "_emit",
                        side_effect=lambda receipt, _output: emitted.append(receipt),
                    ),
                ):
                    exit_code = run_sandbox.main([])

                self.assertEqual(exit_code, 2)
                mocked_run.assert_called_once_with(
                    ["docker", "version", "--format", "{{json .}}"], timeout=20
                )
                self.assertEqual(len(emitted), 1)
                receipt = emitted[0]
                self.assertEqual(receipt["status"], "INFRA_UNAVAILABLE")
                self.assertTrue(receipt["treatment_exposed"])
                self.assertIs(receipt["git"], git_state)
                self.assertIs(receipt["host"], host)
                self.assertEqual(receipt["plan"]["build"][0:2], ["docker", "build"])
                self.assertEqual(receipt["plan"]["create"][0:2], ["docker", "create"])
                self.assertEqual(receipt["probe"]["exit_code"], 0)
                self.assertEqual(
                    receipt["probe"]["stdout_sha256"],
                    run_sandbox.sha256(payload),
                )
                encoded = run_sandbox.canonical_bytes(receipt) + b"\n"
                self.assertEqual(json.loads(encoded), receipt)

    def test_nonfinite_docker_version_probes_are_bound_infra_before_build(self) -> None:
        payloads = {
            "nan": (
                b'{"Server":{"Os":"linux"},"Client":{"Version":NaN}}',
                "2a02ee19d39d07a6e21ca95a13db17f63c1d7a783f64e978098cf29d765ceb36",
            ),
            "overflow": (
                b'{"Server":{"Os":"linux"},"Client":{"Version":1e309}}',
                "7d1bedaf4b0f69b5eba100fdb2833c9f51f82bdc19dd8afa81da0d346a36a75b",
            ),
            "nested_negative_infinity": (
                b'{"Server":{"Os":"linux","Nested":[-Infinity]},"Client":{}}',
                None,
            ),
        }
        self.assertEqual(len(payloads["nan"][0]), 50)
        self.assertEqual(len(payloads["overflow"][0]), 52)
        for name, (payload, expected_hash) in payloads.items():
            with self.subTest(name=name):
                if expected_hash is not None:
                    self.assertEqual(run_sandbox.sha256(payload), expected_hash)
                exit_code, receipt, calls = exercise_docker_version_probe(payload)
                self.assertEqual(exit_code, 2)
                self.assertEqual(receipt["status"], "INFRA_UNAVAILABLE")
                self.assertTrue(receipt["treatment_exposed"])
                self.assertIn("non-finite JSON number", receipt["detail"])
                self.assertEqual(
                    receipt["probe"]["stdout_sha256"],
                    run_sandbox.sha256(payload),
                )
                self.assertEqual(len(calls), 1)
                self.assertEqual(
                    calls[0].args[0],
                    ["docker", "version", "--format", "{{json .}}"],
                )
                self.assertFalse(
                    any(call.args[0][0:2] == ["docker", "build"] for call in calls)
                )
                self.assertEqual(
                    json.loads(run_sandbox.canonical_bytes(receipt)), receipt
                )

    def test_duplicate_and_malformed_docker_objects_stop_before_build(self) -> None:
        payloads = {
            "duplicate_root": (
                b'{"Server":{"Os":"linux"},"Client":{},"Client":{}}'
            ),
            "duplicate_nested": (
                b'{"Server":{"Os":"linux"},"Client":{"Version":"a","Version":"b"}}'
            ),
            "malformed_nested": (
                b'{"Server":{"Os":"linux"},"Client":{"Version":"fixture"}'
            ),
        }
        for name, payload in payloads.items():
            with self.subTest(name=name):
                exit_code, receipt, calls = exercise_docker_version_probe(payload)
                self.assertEqual(exit_code, 2)
                self.assertEqual(receipt["status"], "INFRA_UNAVAILABLE")
                self.assertEqual(
                    receipt["probe"]["stdout_sha256"],
                    run_sandbox.sha256(payload),
                )
                self.assertEqual(len(calls), 1)
                self.assertEqual(
                    json.loads(run_sandbox.canonical_bytes(receipt)), receipt
                )

    def test_finite_and_string_docker_version_neighbors_remain_valid(self) -> None:
        payloads = (
            b'{"Server":{"Os":"LiNuX","Load":1e308},"Client":{"Version":"fixture"}}',
            b'{"Server":{"Os":"linux"},"Client":{"Version":1.7976931348623157e308}}',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                version = run_sandbox._parse_docker_version(payload)
                self.assertEqual(version["Server"]["Os"].casefold(), "linux")
                self.assertTrue(
                    isinstance(version["Client"]["Version"], (str, float))
                )
                self.assertEqual(
                    json.loads(run_sandbox.canonical_bytes(version)), version
                )

    def test_missing_and_wrong_server_shapes_are_bound_infra(self) -> None:
        client = {"Version": "fixture", "Os": "windows", "Arch": "amd64"}
        server = {"Version": "fixture", "Os": "linux", "Arch": "amd64"}
        payloads = {
            "missing_server": {"Client": client},
            "server_null": {"Client": client, "Server": None},
            "server_string": {"Client": client, "Server": "linux"},
            "server_number": {"Client": client, "Server": 7},
            "server_array": {"Client": client, "Server": []},
            "os_missing": {"Client": client, "Server": {}},
            "os_null": {"Client": client, "Server": {"Os": None}},
            "os_number": {"Client": client, "Server": {"Os": 7}},
            "os_array": {"Client": client, "Server": {"Os": []}},
            "os_object": {"Client": client, "Server": {"Os": {}}},
            "client_missing": {"Server": server},
            "client_null": {"Client": None, "Server": server},
            "client_number": {"Client": 7, "Server": server},
            "client_array": {"Client": [], "Server": server},
        }
        for name, version in payloads.items():
            with self.subTest(name=name):
                payload = json.dumps(version).encode("utf-8")
                probe = run_sandbox.subprocess.CompletedProcess(
                    ["docker", "version"], 0, payload, b""
                )
                emitted: list[dict[str, object]] = []
                git_state = {
                    "sha": "f" * 40,
                    "branch": run_sandbox.EXPECTED_BRANCH,
                    "clean": True,
                    "status_sha256": "a" * 64,
                    "baseline_ancestor": True,
                }
                with (
                    mock.patch.object(
                        run_sandbox, "_git_receipt", return_value=git_state
                    ),
                    mock.patch.object(run_sandbox, "_host_profile", return_value={}),
                    mock.patch.object(run_sandbox, "run", return_value=probe),
                    mock.patch.object(
                        run_sandbox,
                        "_emit",
                        side_effect=lambda receipt, _output: emitted.append(receipt),
                    ),
                ):
                    exit_code = run_sandbox.main([])

                self.assertEqual(exit_code, 2)
                self.assertEqual(len(emitted), 1)
                receipt = emitted[0]
                self.assertEqual(receipt["status"], "INFRA_UNAVAILABLE")
                self.assertEqual(
                    receipt["probe"]["stdout_sha256"],
                    run_sandbox.sha256(payload),
                )
                self.assertEqual(
                    json.loads(run_sandbox.canonical_bytes(receipt)), receipt
                )

    def test_non_linux_server_is_fully_bound_infra_unavailable_before_build(self) -> None:
        git_state = {
            "sha": "f" * 40,
            "branch": run_sandbox.EXPECTED_BRANCH,
            "clean": True,
            "status_sha256": "a" * 64,
            "baseline_ancestor": True,
        }
        host = {"os": "FixtureOS", "machine": "fixture-arch"}
        version_payload = {
            "Client": {"Version": "fixture", "Os": "windows", "Arch": "amd64"},
            "Server": {"Version": "fixture", "Os": "windows", "Arch": "amd64"},
        }
        probe = run_sandbox.subprocess.CompletedProcess(
            ["docker", "version"],
            0,
            json.dumps(version_payload).encode("utf-8"),
            b"",
        )
        emitted: list[dict[str, object]] = []

        def capture(receipt: dict[str, object], _output: Path | None) -> None:
            emitted.append(receipt)

        with (
            mock.patch.object(run_sandbox, "_git_receipt", return_value=git_state),
            mock.patch.object(run_sandbox, "_host_profile", return_value=host),
            mock.patch.object(run_sandbox, "run", return_value=probe) as mocked_run,
            mock.patch.object(run_sandbox, "_emit", side_effect=capture),
        ):
            exit_code = run_sandbox.main([])

        self.assertEqual(exit_code, 2)
        mocked_run.assert_called_once_with(
            ["docker", "version", "--format", "{{json .}}"], timeout=20
        )
        self.assertEqual(len(emitted), 1)
        receipt = emitted[0]
        self.assertEqual(receipt["status"], "INFRA_UNAVAILABLE")
        self.assertIn("Server.Os='windows'", receipt["detail"])
        self.assertIs(receipt["git"], git_state)
        self.assertIs(receipt["host"], host)
        self.assertEqual(
            receipt["image"]["dockerfile_sha256"],
            run_sandbox.sha256((HERE / "Dockerfile").read_bytes()),
        )
        self.assertEqual(receipt["plan"]["build"][0:2], ["docker", "build"])
        self.assertEqual(receipt["plan"]["create"][0:2], ["docker", "create"])
        self.assertEqual(receipt["probe"]["exit_code"], 0)

    def test_case_normalized_linux_server_reaches_build(self) -> None:
        git_state = {
            "sha": "f" * 40,
            "branch": run_sandbox.EXPECTED_BRANCH,
            "clean": True,
            "status_sha256": "a" * 64,
            "baseline_ancestor": True,
        }
        version_payload = {
            "Client": {"Version": "fixture", "Os": "windows", "Arch": "amd64"},
            "Server": {"Version": "fixture", "Os": "LiNuX", "Arch": "amd64"},
        }
        probe = run_sandbox.subprocess.CompletedProcess(
            ["docker", "version"],
            0,
            json.dumps(version_payload).encode("utf-8"),
            b"",
        )
        build_failure = run_sandbox.subprocess.CompletedProcess(
            ["docker", "build"], 1, b"", b"fixture build failure"
        )

        with (
            mock.patch.object(run_sandbox, "_git_receipt", return_value=git_state),
            mock.patch.object(run_sandbox, "_host_profile", return_value={}),
            mock.patch.object(
                run_sandbox, "run", side_effect=[probe, build_failure]
            ) as mocked_run,
            mock.patch.object(run_sandbox, "_emit"),
        ):
            exit_code = run_sandbox.main([])

        self.assertEqual(exit_code, 1)
        calls = mocked_run.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].args[0][0:2], ["docker", "build"])
        self.assertFalse(
            any(call.args[0][0:2] == ["docker", "create"] for call in calls)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
