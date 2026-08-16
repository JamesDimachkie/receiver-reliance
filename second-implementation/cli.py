from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr2 import MAX_RAW_BYTES, execute_cli_bytes, execute_wrapper_bytes


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"execute", "execute-wrapper"}:
        return 64
    raw = sys.stdin.buffer.read(MAX_RAW_BYTES + 1)
    if sys.argv[1] == "execute-wrapper":
        code, output = execute_wrapper_bytes(raw)
    else:
        code, output = execute_cli_bytes(raw)
    sys.stdout.buffer.write(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
