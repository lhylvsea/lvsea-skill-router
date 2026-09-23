#!/usr/bin/env python3
"""Structural and secret-safety checks for the published Skill package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import parse_frontmatter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.path).resolve()
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    skill_path = root / "SKILL.md"
    readme = root / "README.md"
    usage = root / "USAGE.zh-CN.md"
    agents = root / "agents" / "openai.yaml"
    skill_text = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
    fm = parse_frontmatter(skill_text)
    check("skill_exists", skill_path.is_file(), str(skill_path))
    check("skill_name", fm.get("name") == "lvsea-skill-router", fm.get("name", "missing"))
    check("description_discriminating", 80 <= len(fm.get("description", "")) <= 700, str(len(fm.get("description", ""))))
    check("readme_exists", readme.is_file(), str(readme))
    check("chinese_usage_exists", usage.is_file(), str(usage))
    check("openai_metadata_exists", agents.is_file(), str(agents))
    readme_text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    usage_text = usage.read_text(encoding="utf-8") if usage.is_file() else ""
    combined = readme_text + "\n" + usage_text
    check("four_scenarios", len(re.findall(r"场景\s*[1-4一二三四]", combined)) >= 4, "at least four scenario labels")
    check("four_usage_examples", len(re.findall(r"lvsea-skill-router|route_request\.py", combined)) >= 4, "usage references")
    check("boundary_notes", any(token in combined for token in ("边界", "不会自动安装", "不替代")), "Chinese boundary text")
    check("no_secret_pattern", not re.search(r"(?:apikey_|sk-[A-Za-z0-9]|TYPESAFE_API_KEY\s*=\s*[\"'][^$\n]{8,})", combined + "\n" + skill_text), "public files")
    check("no_scaffold_placeholders", not re.search(r"TODO|TBD|Your skill description|Replace this", skill_text + combined, re.I), "no unfinished scaffold")
    for script in sorted((root / "scripts").glob("*.py")) if (root / "scripts").is_dir() else []:
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
            passed, detail = True, "compile ok"
        except SyntaxError as error:
            passed, detail = False, str(error)
        check(f"compile:{script.name}", passed, detail)

    failed = [item for item in checks if not item["passed"]]
    output = {"status": "PASS" if not failed else "FAIL", "failedCount": len(failed), "checks": checks}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
