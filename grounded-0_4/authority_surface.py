"""Runtime field-authority queries over the canonical 0.4 register.

The JSON register is the only store of per-field authority values.  Public
queries read it afresh, validate that operation selectors are unambiguous,
and return copies of the selected register row.  No field or status value is
duplicated in Python source.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
AUTHORITY_REGISTER_PATH = HERE / "authority_register_0_4.json"


class AuthorityRegisterError(ValueError):
    """The canonical authority register cannot define an unambiguous surface."""


def _nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise AuthorityRegisterError(f"{location} must be a nonempty string")
    return value


def _validate_register(register: Any) -> dict[str, Any]:
    if not isinstance(register, dict):
        raise AuthorityRegisterError("authority register must be a JSON object")
    _nonempty_string(register.get("format_version"), "format_version")
    operations = register.get("operations")
    if not isinstance(operations, list):
        raise AuthorityRegisterError("operations must be an array")

    obligation_ids: set[str] = set()
    operation_handles: set[str] = set()
    for operation_index, operation in enumerate(operations):
        location = f"operations[{operation_index}]"
        if not isinstance(operation, dict):
            raise AuthorityRegisterError(f"{location} must be an object")
        obligation_id = _nonempty_string(
            operation.get("obligation_id"), f"{location}.obligation_id"
        )
        operation_handle = _nonempty_string(
            operation.get("operation_handle"), f"{location}.operation_handle"
        )
        if obligation_id in obligation_ids:
            raise AuthorityRegisterError(f"duplicate obligation_id: {obligation_id}")
        if operation_handle in operation_handles:
            raise AuthorityRegisterError(f"duplicate operation_handle: {operation_handle}")
        if obligation_id in operation_handles or operation_handle in obligation_ids:
            collision = (
                obligation_id if obligation_id in operation_handles else operation_handle
            )
            raise AuthorityRegisterError(
                "cross-namespace operation selector collision: " + collision
            )
        if obligation_id == operation_handle:
            raise AuthorityRegisterError(
                "cross-namespace operation selector collision: " + obligation_id
            )
        obligation_ids.add(obligation_id)
        operation_handles.add(operation_handle)

        fields = operation.get("fields")
        if not isinstance(fields, list):
            raise AuthorityRegisterError(f"{location}.fields must be an array")
        field_names: set[str] = set()
        for field_index, field in enumerate(fields):
            field_location = f"{location}.fields[{field_index}]"
            if not isinstance(field, dict):
                raise AuthorityRegisterError(f"{field_location} must be an object")
            field_name = _nonempty_string(
                field.get("field"), f"{field_location}.field"
            )
            _nonempty_string(field.get("status"), f"{field_location}.status")
            _nonempty_string(field.get("rationale"), f"{field_location}.rationale")
            if field_name in field_names:
                raise AuthorityRegisterError(
                    f"duplicate field in {obligation_id}: {field_name}"
                )
            field_names.add(field_name)
    return register


def read_authority_register(
    path: pathlib.Path | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Read and validate a register, returning its exact bytes and JSON value.

    ``path`` exists for deterministic generation and isolated tests.  Runtime
    authority queries omit it and therefore always use the adjacent canonical
    register.
    """
    source = AUTHORITY_REGISTER_PATH if path is None else pathlib.Path(path)
    try:
        raw = source.read_bytes()
        register = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuthorityRegisterError(
            f"cannot read authority register {source}: {error}"
        ) from error
    return raw, _validate_register(register)


def _surface(operation: dict[str, Any], format_version: str) -> dict[str, Any]:
    return {
        "authority_register_format_version": format_version,
        "obligation_id": operation["obligation_id"],
        "operation_handle": operation["operation_handle"],
        "fields": [
            {
                "field": field["field"],
                "status": field["status"],
                "rationale": field["rationale"],
            }
            for field in operation["fields"]
        ],
    }


def all_operation_authorities(
    register: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return every operation's field-authority surface from one register read."""
    if register is None:
        _raw, register = read_authority_register()
    else:
        register = _validate_register(register)
    format_version = register["format_version"]
    return [_surface(operation, format_version) for operation in register["operations"]]


def authority_for_operation(operation: str) -> dict[str, Any]:
    """Return every required fact field's classification authority.

    ``operation`` may be an exact obligation ID (for example ``OBL-08``) or
    operation handle.  The canonical JSON register is read on every call, so
    this API cannot drift behind the artifact it reports.  Unknown selectors
    raise ``KeyError``; non-string selectors raise ``TypeError``.
    """
    if not isinstance(operation, str):
        raise TypeError("operation must be an obligation ID or operation handle string")
    surfaces = all_operation_authorities()
    matches = [
        surface
        for surface in surfaces
        if operation in (surface["obligation_id"], surface["operation_handle"])
    ]
    if not matches:
        raise KeyError(f"unknown authority operation: {operation}")
    if len(matches) != 1:  # protected by register validation; defense in depth
        raise AuthorityRegisterError(f"ambiguous authority operation: {operation}")
    return matches[0]
