from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr2 import execute


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "execute":
        return 64
    code, output = execute(sys.stdin.buffer.read())
    sys.stdout.buffer.write(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
