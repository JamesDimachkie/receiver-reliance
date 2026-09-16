"""The public seam shared by the three arms.

``architecture.public_seam``: each callable accepts exactly two positional
arguments -- ``canonical_common_bytes`` and ``canonical_module_state_bytes`` --
and returns exact built-in bytes.

``diagnostic_authority.parser_totality`` fixes the shape of this module: an outer
exact-type gate that computes only ``type(x) is bytes`` and never invokes
candidate hooks, then a region from which every BaseException is caught and
answered with the registered INTERNAL result.  The handler itself uses only
literal constants, ``type``, SHA-256 and byte concatenation.

Nothing here reaches the filesystem, the network, a subprocess, a dynamic import
or a reflection import: ``architecture.candidate_runtime_forbidden``.
"""

from . import admission
from . import decision
from . import faults as fault_mod
from . import schema
from . import vocab


class Semantics:
    """What an arm supplies to the seam.

    ``evaluate(common_value, state_value)`` returns ``(code, semantic_evidence)``
    and is reached only after both documents have fully passed CLOSED_SCHEMA.
    """

    __slots__ = ("entrypoint", "evaluate")

    def __init__(self, entrypoint, evaluate):
        self.entrypoint = entrypoint
        self.evaluate = evaluate


def decide(semantics, canonical_common_bytes, canonical_module_state_bytes):
    """Run one decision and return its exact bytes."""
    # architecture.public_seam / call_atom_encoding.law: the exact-type gate uses
    # type(x) is bytes and invokes no hook on either argument.
    common_is_bytes = type(canonical_common_bytes) is bytes
    state_is_bytes = type(canonical_module_state_bytes) is bytes
    entrypoint = semantics.entrypoint
    module = vocab.MODULE_BY_ENTRYPOINT[entrypoint]

    if not (common_is_bytes and state_is_bytes):
        return decision.build(
            entrypoint,
            None,
            "PYTHON_TYPE",
            "ARGUMENT_TYPE",
            "",
            0,
            module,
            None,
            "NONE",
        )

    try:
        return _decide(
            semantics,
            module,
            canonical_common_bytes,
            canonical_module_state_bytes,
        )
    except BaseException:  # diagnostic_authority.parser_totality
        return _internal(
            entrypoint, canonical_common_bytes, canonical_module_state_bytes
        )


def _internal(entrypoint, common_bytes, state_bytes):
    """``diagnostic_authority.internal_exception_result``, verbatim."""
    digest_bytes = decision.input_digest_bytes(entrypoint, common_bytes, state_bytes)
    return decision.build(
        entrypoint,
        digest_bytes,
        "INTERNAL",
        "BOUNDARY_EXCEPTION",
        "",
        0,
        "PUBLIC_BOUNDARY",
        None,
        "NONE",
    )


def _decide(semantics, module, common_bytes, state_bytes):
    entrypoint = semantics.entrypoint
    state_document = vocab.STATE_DOCUMENT_BY_ENTRYPOINT[entrypoint]
    digest_bytes = decision.input_digest_bytes(entrypoint, common_bytes, state_bytes)

    common = admission.admit(common_bytes, "COMMON")
    state = admission.admit(state_bytes, state_document)
    found = list(common.faults) + list(state.faults)

    common_schema_passed = False
    if common.parsed and not common.faults:
        before = len(found)
        schema.validate(common.value, "COMMON", found)
        common_schema_passed = len(found) == before
    if state.parsed and not state.faults:
        schema.validate(state.value, state_document, found)

    selected = fault_mod.select(found)
    if selected is not None:
        remediation = decision.resolve_remediation(
            "DEFER", common_schema_passed, common.value
        )
        return decision.build(
            entrypoint,
            digest_bytes,
            selected.stage,
            selected.code,
            selected.pointer,
            selected.occurrence,
            module,
            None,
            remediation,
        )

    code, semantic_evidence = semantics.evaluate(common.value, state.value)
    disposition = vocab.PUBLIC_RESULTS[code][0]
    remediation = decision.resolve_remediation(disposition, True, common.value)
    return decision.build(
        entrypoint,
        digest_bytes,
        "MODULE_SEMANTICS",
        code,
        "",
        0,
        module,
        semantic_evidence,
        remediation,
    )
