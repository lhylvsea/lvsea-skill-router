"""Small, dependency-free catalog and grading helpers for lvsea-skill-router."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Iterable

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.S)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+#.-]*|[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+#.-]*")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".cache"}
SCOPE_RANK = {"project": 0, "user": 1, "plugin": 2, "other": 3}

# Common Chinese task signals mapped to the English capability words used by many
# installed Skills. This only improves the cheap local prefilter; Jev still makes
# the semantic decision from the bounded cards.
TASK_ALIASES: dict[str, set[str]] = {
    "修复": {"fix", "debug", "bug", "diagnos", "repair", "error", "regression"},
    "保存": {"save", "persist", "storage", "database", "write", "crud"},
    "校验": {"validation", "validate", "test", "qa", "verify", "check"},
    "回归": {"regression", "test", "verification", "verify"},
    "前端": {"frontend", "web", "ui", "client"},
    "后端": {"backend", "server", "api"},
    "数据库": {"database", "sql", "sqlite", "postgres", "data"},
    "数据": {"data", "analytics", "database", "sql", "chart"},
    "设备": {"equipment", "asset", "manufacturing", "industrial", "dashboard"},
    "网页": {"web", "website", "frontend", "ui"},
    "看板": {"dashboard", "analytics", "visualization", "dataviz"},
    "原生": {"native", "editable"},
    "季度": {"quarterly", "report", "presentation", "slides"},
    "发布": {"publish", "release", "github", "deploy"},
    "安装": {"install", "setup", "configure", "dependency"},
    "技能": {"skill", "agent", "routing", "prompt"},
}


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the flat YAML subset used by SKILL.md front matter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    lines = match.group(1).splitlines()
    result: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        found = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not found:
            index += 1
            continue
        key, value = found.group(1), found.group(2).strip()
        if value in {"", ">", "|", ">-", "|-"}:
            block: list[str] = []
            index += 1
            while index < len(lines) and (lines[index].startswith((" ", "\t")) or not lines[index]):
                block.append(lines[index].strip())
                index += 1
            result[key] = " ".join(part for part in block if part).strip()
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key] = value
        index += 1
    return result


def body_without_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def body_excerpt(text: str, limit: int = 520) -> str:
    """Return useful prose without sending code blocks or headings to a router."""
    body = body_without_frontmatter(text)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        compact = " ".join(paragraph.split())
        if not compact or compact.startswith(("#", "$", "|", "[")):
            continue
        paragraphs.append(compact)
        if sum(len(item) for item in paragraphs) >= limit:
            break
    return " ".join(paragraphs)[:limit].rstrip()


def boundary_excerpt(text: str, limit: int = 300) -> str:
    lines: list[str] = []
    for raw in body_without_frontmatter(text).splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        lowered = line.lower()
        if any(token in lowered for token in ("do not", "not for", "avoid", "only when", "exclude", "不适用", "不要", "仅在")):
            lines.append(line)
        if sum(len(item) for item in lines) >= limit:
            break
    return " ".join(lines)[:limit].rstrip()


def tokenize(text: str) -> set[str]:
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "into", "your", "you", "use", "when",
        "what", "how", "can", "please", "help", "make", "want", "need", "like", "about", "using", "should",
        "will", "的", "了", "和", "是", "我", "你", "请", "帮", "要", "做", "一个", "这个",
    }
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in stop and len(token) > 1}


def expand_task_tokens(text: str) -> set[str]:
    """Add conservative bilingual capability aliases for the lexical prefilter."""
    expanded = tokenize(text)
    for phrase, aliases in TASK_ALIASES.items():
        if phrase in text:
            expanded.update(aliases)
    return expanded


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _skill_files(root: Path) -> Iterable[Path]:
    root = root.expanduser()
    if root.is_file() and root.name.lower() == "skill.md":
        yield root
        return
    if (root / "SKILL.md").is_file():
        yield root / "SKILL.md"
        return
    if not root.is_dir():
        return
    is_plugin_cache = root.name.lower() in {"cache", "plugins"} or "plugins" in {part.lower() for part in root.parts}
    if is_plugin_cache:
        for path in root.rglob("SKILL.md"):
            if not any(part in SKIP_DIRS for part in path.parts):
                yield path
        return
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name not in SKIP_DIRS:
            path = child / "SKILL.md"
            if path.is_file():
                yield path


def default_roots(cwd: str | os.PathLike | None = None) -> list[tuple[Path, str]]:
    current = Path(cwd or os.getcwd()).resolve()
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    roots: list[tuple[Path, str]] = []
    for parent in (current, *current.parents):
        if parent in {home, home.parent, Path(parent.anchor)}:
            break
        for name in (".agents/skills", ".codex/skills", ".claude/skills"):
            roots.append((parent / name, "project"))
    roots.extend(
        [
            (codex_home / "skills", "user"),
            (home / ".agents/skills", "user"),
            (home / ".claude/skills", "user"),
            (codex_home / "plugins/cache", "plugin"),
        ]
    )
    return roots


def _record(path: Path, scope: str, root: Path) -> dict:
    text = _read_text(path)
    if not text:
        return {}
    frontmatter = parse_frontmatter(text)
    name = frontmatter.get("name") or path.parent.name
    description = frontmatter.get("description", "").strip()
    excerpt = body_excerpt(text)
    if len(description) < 60 and excerpt:
        description = f"{description} {excerpt}".strip()
    return {
        "name": name,
        "description": description,
        "frontmatter_description": frontmatter.get("description", "").strip(),
        "body_excerpt": excerpt,
        "boundary_excerpt": boundary_excerpt(text),
        "scope": scope,
        "path": str(path.resolve()),
        "root": str(root.resolve()),
        "text": text,
    }


def discover(cwd: str | os.PathLike | None = None, roots: list[tuple[Path, str]] | None = None) -> list[dict]:
    """Discover skills with project > user > plugin precedence and name deduplication."""
    candidates = roots if roots is not None else default_roots(cwd)
    found: dict[str, tuple[tuple[int, int, str], dict]] = {}
    for position, (root, scope) in enumerate(candidates):
        for path in _skill_files(root):
            item = _record(path, scope, root)
            if not item or not item["name"]:
                continue
            key = item["name"].strip()
            rank = (SCOPE_RANK.get(scope, 3), position, item["path"].lower())
            if key not in found or rank < found[key][0]:
                found[key] = (rank, item)
    return [found[name][1] for name in sorted(found, key=str.lower)]


def _letter(score: float) -> str:
    if score >= 0.86:
        return "A"
    if score >= 0.72:
        return "B"
    if score >= 0.58:
        return "C"
    if score >= 0.40:
        return "D"
    return "F"


def grade_record(record: dict, *, corpus_median: int = 921, corpus_p90: int = 2207) -> dict:
    """Approximate the six public Skill Grader axes without network or signup."""
    description = record.get("frontmatter_description", "") or record.get("description", "")
    body = body_without_frontmatter(record.get("text", ""))
    desc_chars = len(description)
    resident_tokens = max(1, math.ceil(desc_chars / 4))
    body_words = len(WORD_RE.findall(body))
    desc_tokens = list(tokenize(description))
    duplicate_ratio = 0.0 if not desc_tokens else 1.0 - len(set(desc_tokens)) / len(desc_tokens)
    generic_hits = len(re.findall(r"\b(any|all|everything|general|anything|various|万能|任何|全部)\b", description.lower()))
    boundary_hits = len(re.findall(r"\b(use when|do not|not for|only|avoid)\b|适用|不适用|不要|仅在", description.lower()))
    resident = max(0.0, min(1.0, 1.0 - max(0, resident_tokens - 80) / 280))
    honesty = max(0.0, min(1.0, 0.92 - duplicate_ratio * 0.9 - generic_hits * 0.08 + min(boundary_hits, 3) * 0.04))
    if body_words <= corpus_median:
        body_size = 0.92 if body_words >= 80 else 0.78
    elif body_words <= corpus_p90:
        body_size = 0.82
    else:
        body_size = max(0.30, 0.82 - (body_words - corpus_p90) / max(1, corpus_p90 * 2))
    has_refs = bool(re.search(r"references?/|read [^\n]+\.md|\[[^\]]+\]\([^)]*references", body, re.I))
    has_scripts = bool((Path(record.get("path", "")).parent / "scripts").is_dir())
    progressive = min(1.0, 0.66 + (0.16 if has_refs else 0) + (0.12 if has_scripts else 0))
    headings = len(re.findall(r"^#{2,4}\s+", body, re.M))
    factoring = 0.86 if 2 <= headings <= 12 else (0.68 if headings <= 20 else 0.46)
    cli_leverage = min(1.0, 0.54 + (0.28 if has_scripts else 0) + (0.12 if re.search(r"\b(python|node|command|run|script)\b", body, re.I) else 0))
    axes = {
        "resident_footprint": resident,
        "description_honesty": honesty,
        "body_size": body_size,
        "progressive_disclosure": progressive,
        "factoring": factoring,
        "cli_leverage": cli_leverage,
    }
    overall = round(sum(axes.values()) / len(axes), 3)
    return {
        "resident_chars": desc_chars,
        "resident_tokens": resident_tokens,
        "body_words": body_words,
        "axes": {name: {"score": round(score, 3), "grade": _letter(score)} for name, score in axes.items()},
        "overall": overall,
        "grade": _letter(overall),
        "warnings": _warnings(record, resident_tokens, body_words, generic_hits, duplicate_ratio, has_refs),
    }


def _warnings(record: dict, resident_tokens: int, body_words: int, generic_hits: int, duplicate_ratio: float, has_refs: bool) -> list[str]:
    warnings: list[str] = []
    if resident_tokens > 180:
        warnings.append("frontmatter description is expensive in every message")
    if body_words > 2207:
        warnings.append("body is larger than the published-skill p90; move detail to references or scripts")
    if generic_hits:
        warnings.append("description contains broad catch-all language")
    if duplicate_ratio > 0.30:
        warnings.append("description repeats trigger terms")
    if body_words > 921 and not has_refs:
        warnings.append("large body has no obvious progressive-disclosure reference")
    if not record.get("boundary_excerpt"):
        warnings.append("no explicit boundary or exclusion was detected")
    return warnings


def enrich(record: dict, corpus_median: int = 921, corpus_p90: int = 2207) -> dict:
    result = dict(record)
    result.pop("text", None)
    result["quality"] = grade_record(record, corpus_median=corpus_median, corpus_p90=corpus_p90)
    return result


def json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
