from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from route_request import build_route  # noqa: E402
from skilllib import discover, grade_record, parse_frontmatter  # noqa: E402


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_skill(self, name: str, description: str, body: str = "") -> None:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8"
        )

    def test_frontmatter_block_scalar(self) -> None:
        parsed = parse_frontmatter("---\nname: demo\ndescription: >\n  one line\n  two line\n---\n")
        self.assertEqual(parsed, {"name": "demo", "description": "one line two line"})

    def test_discover_deduplicates_by_name(self) -> None:
        project = self.root / "project" / ".agents" / "skills"
        user = self.root / "user" / "skills"
        project_skill = project / "same"
        user_skill = user / "same"
        project_skill.mkdir(parents=True)
        user_skill.mkdir(parents=True)
        (project_skill / "SKILL.md").write_text("---\nname: same\ndescription: project\n---\n", encoding="utf-8")
        (user_skill / "SKILL.md").write_text("---\nname: same\ndescription: user\n---\n", encoding="utf-8")
        found = discover(roots=[(project, "project"), (user, "user")])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["scope"], "project")

    def test_grader_flags_broad_resident_description(self) -> None:
        broad = {
            "name": "broad",
            "frontmatter_description": "A general skill for everything: any project, all tasks, and various work.",
            "description": "A general skill for everything: any project, all tasks, and various work.",
            "text": "---\nname: broad\ndescription: general\n---\n\n" + ("long body text " * 2400),
            "path": str(self.root / "broad" / "SKILL.md"),
            "boundary_excerpt": "",
        }
        grade = grade_record(broad)
        self.assertIn(grade["grade"], {"C", "D", "F"})
        self.assertTrue(grade["warnings"])

    def test_route_shortlist_contains_narrow_deliverable_skill(self) -> None:
        self._write_skill(
            "pptx",
            "Create or edit native PowerPoint slide decks from source material, with editable layouts and verification.",
            "Use when the requested deliverable is a .pptx file. Do not use for plain prose.",
        )
        self._write_skill(
            "article",
            "Write and edit long-form articles and prose for publication.",
            "Use for articles, not native presentation files.",
        )
        route = build_route("把季度数据做成可编辑的 PowerPoint 汇报", roots=[str(self.root)], top_k=2)
        names = [item["name"] for item in route["shortlist"]]
        self.assertIn("pptx", names)
        self.assertEqual(route["mcp_rerank"]["server"], "jev")
        payload = route["mcp_rerank"]["arguments"]
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertTrue(all("Boundary evidence" in item["text"] for item in payload["candidates"]))

    def test_route_output_is_json_serializable(self) -> None:
        self._write_skill("one", "A focused skill for one task.", "Use when the task matches.")
        result = build_route("one task", roots=[str(self.root)])
        json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
