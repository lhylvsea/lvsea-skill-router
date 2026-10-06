#!/usr/bin/env python3
"""Print a compact catalog of discoverable Codex/Agent skills."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import discover, enrich, json_dump  # noqa: E402


def main() -> int:
    # Windows PowerShell often exposes a legacy GBK stdout. Skill descriptions
    # may contain emoji or other Unicode; keep the JSON inventory usable without
    # requiring every caller to remember `-X utf8`.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Scan installed SKILL.md files.")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--root", action="append", dest="roots", help="Additional skill root; repeatable")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    roots = [(Path(root), "other") for root in args.roots] if args.roots else None
    catalog = [enrich(item) for item in discover(args.cwd, roots=roots)]
    if args.json:
        print(json_dump({"count": len(catalog), "skills": catalog}))
    else:
        print(f"skills={len(catalog)}")
        for item in catalog:
            quality = item["quality"]
            print(f"{item['name']:<32} {item['scope']:<7} {quality['grade']} {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
