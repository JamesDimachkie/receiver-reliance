"""Shape mappers: native agent-stack objects -> RR native evidence + fact profile.

One module per exchanged shape. Each mapper declares, per obligation, the native
precondition under which it maps (HOST_OBLIGATIONS H4) and abstains otherwise.
Fabricating a fact value is forbidden in every mapper.

Implemented:
  ``mcp_tool_result``  MCP ``CallToolResult`` -> REF family / OBL-02.

Specified, not implemented (see ``DESIGN.md``):
  Microsoft Agent Framework message/state objects; A2A-style agent messages.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from .mcp_tool_result import Mapping, map_tool_result  # noqa: E402

__all__ = ["Mapping", "map_tool_result"]
