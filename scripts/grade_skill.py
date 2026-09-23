#!/usr/bin/env python3
"""Run the local, deterministic six-axis Skill Grader approximation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import _record, discover, enrich, json_dump  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade a SKILL.md or every discovered skill.")
    parser.add_argument("path", nargs="?", help="Skill directory or SKILL.md; omit with --all")
    parser.add_argument("--all", action="store_true", help="Grade the discovered catalog")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.all:
        result = [enrich(item) for item in discover(args.cwd)]
    elif args.path:
        path = Path(args.path)
        skill_md = path if path.name.lower() == "skill.md" else path / "SKILL.md"
        if not skill_md.is_file():
            parser.error(f"SKILL.md not found: {skill_md}")
        item = _record(skill_md, "explicit", skill_md.parent)
        result = [enrich(item)]
    else:
        parser.error("pass a skill path or --all")
    if args.json:
        print(json_dump(result))
    else:
        for item in result:
            quality = item["quality"]
            print(f"{item['name']}: {quality['grade']} ({quality['overall']})")
            for warning in quality["warnings"]:
                print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
