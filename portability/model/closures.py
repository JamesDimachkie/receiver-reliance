"""Named historical closure points pinned inside finite model M.

These are prior accepted/minimized raw-ABI witnesses, not a newly authored
oracle and not future blinded-world material.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawClosure:
    closure_id: str
    source: str
    raw_hex: str
    raw_sha256: str
    expected_code: str
    expected_pointer: str
    expected_response_sha256: str
    mapping: str


RAW_CLOSURES = (
    RawClosure(
        "RI1_UTF16_ASTRAL_BEFORE_BMP",
        "orchestration/refuters/RI1.md",
        "7b22f0908080223a302c22ee8080223a307d0a",
        "898F487E1FFD5284DB606603F67AD297CDDB19D339CE5DDFD570B28D16D74014",
        "ERR_SCHEMA",
        "/format_version",
        "309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF",
        "N=20,D=1,K=0; supplemental lexeme closure because the two ordering-edge keys are not in base A.",
    ),
    RawClosure(
        "RI2_LONE_SURROGATE_SCALAR",
        "orchestration/refuters/RI2.md",
        "225c7564383030220a",
        "B16AF5D32E117E1E4A4132716A6DFB0621BB990D1BFCCE97A9DF73774D0984F3",
        "ERR_JSON",
        "",
        "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2",
        "Exact KEY_B:lone_surrogate scalar plus LF trace in A; N=9,D=0,K=0.",
    ),
    RawClosure(
        "RI2_LONE_SURROGATE_KEY",
        "orchestration/refuters/RI2.md",
        "7b225c7564383030223a307d0a",
        "8BA9AF9592D9FED7D0E9277137B1F224B9BB222AA3E8252C333CA28046140741",
        "ERR_JSON",
        "",
        "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2",
        "Maps to { KEY_B:lone_surrogate : INT_1 } LF; raw 0 is a pinned scalar synonym for A's 1.",
    ),
    RawClosure(
        "RI3_EMPTY_DUPLICATE_NO_LF",
        "orchestration/refuters/RI3.md",
        "7b22223a302c2222",
        "10779FCB480886B954ACEAE3C495771971BAA338F1A8FE55A48EB68965B4D6FD",
        "ERR_DUPLICATE_KEY",
        "",
        "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01",
        "N=8,D=1,K=1; maps to KEY_A/KEY_A_REPEAT incomplete-EOF terminal. Empty key is a supplemental lexeme closure.",
    ),
    RawClosure(
        "RI4_NONEMPTY_DUPLICATE_NO_LF",
        "orchestration/refuters/RI4.md",
        "7b2261223a302c226122",
        "F5EECE3728CC6AFC1FF909758FEF968D8F2EBD0B6F70C5A0B75C6CC47BED4F58",
        "ERR_DUPLICATE_KEY",
        "",
        "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01",
        "Exact KEY_A/KEY_A_REPEAT incomplete-EOF class; raw 0 is a pinned scalar synonym for A's 1.",
    ),
)


TRANSPORT_CLOSURES = (
    {
        "closure_id": "RO1_SHORT_WRITE_ALL_FIRST_RESPONSE_INDICES",
        "source": "orchestration/refuters/RO1.md and RO2.md",
        "claim": "Every positive first-response byte index is an accepted short-write point; no incomplete response is flushed.",
    },
    {
        "closure_id": "RO1_OVERSIZE_BOUNDED_DRAIN_ALIGNMENT",
        "source": "orchestration/refuters/RO1.md and RO2.md",
        "claim": "The actual 16,777,216-byte threshold is crossed incrementally, drained through LF, hashed in full, and the following record remains aligned.",
    },
)
