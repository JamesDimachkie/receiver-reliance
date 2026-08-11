"""Independent receiver-reliance portability oracle."""

from .oracle import (
    Classification,
    FixtureOracle,
    OutsideFixture,
    classify_record,
    error_response,
    jcs_bytes,
    jcs_dumps,
    relation_concurrency_vs_isolated,
    relation_deterministic_replay,
    relation_input_partition_invariance,
    relation_oversize_drain_next_record,
    relation_physical_line_equality,
    relation_request_sequence_permutation,
    self_zero_digest,
    utf16_sort_key,
)

__all__ = [
    "Classification",
    "FixtureOracle",
    "OutsideFixture",
    "classify_record",
    "error_response",
    "jcs_bytes",
    "jcs_dumps",
    "relation_concurrency_vs_isolated",
    "relation_deterministic_replay",
    "relation_input_partition_invariance",
    "relation_oversize_drain_next_record",
    "relation_physical_line_equality",
    "relation_request_sequence_permutation",
    "self_zero_digest",
    "utf16_sort_key",
]
