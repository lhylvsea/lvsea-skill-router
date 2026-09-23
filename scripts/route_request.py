#!/usr/bin/env python3
"""Build a low-cost shortlist and MCP payload for precise Skill routing.

This script does not call a remote model. It scans local skills, applies a cheap lexical
prefilter, grades description/context cost, and emits the bounded evidence that an Agent
should send to the configured `jev` MCP server for semantic reranking and final decision.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import discover, enrich, expand_task_tokens, json_dump, tokenize  # noqa: E402


def _local_score(goal: str, item: dict[str, Any]) -> tuple[float, dict[str, int]]:
    query = expand_task_tokens(goal)
    name_tokens = tokenize(item["name"].replace("-", " "))
    desc_tokens = tokenize(item.get("description", ""))
    body_tokens = tokenize(item.get("body_excerpt", ""))
    name_hits = len(query & name_tokens)
    desc_hits = len(query & desc_tokens)
    body_hits = len(query & body_tokens)
    raw = 5 * name_hits + 2 * desc_hits + body_hits
    denominator = max(4, len(query) * 2)
    semantic = min(1.0, raw / denominator)
    quality = float(item["quality"]["overall"])
    # Quality breaks ties; it must never replace functional evidence.
    score = min(1.0, semantic * 0.86 + quality * 0.14)
    return round(score, 4), {"name": name_hits, "description": desc_hits, "body": body_hits}


def _card(item: dict[str, Any]) -> str:
    quality = item["quality"]
    boundaries = item.get("boundary_excerpt") or "No explicit boundary detected."
    return "\n".join(
        [
            f"Skill id: {item['name']}",
            f"Declared purpose: {item.get('description') or '(missing description)'}",
            f"Use evidence from body: {item.get('body_excerpt') or '(missing body excerpt)'}",
            f"Boundary evidence: {boundaries}",
            f"Skill Grader: {quality['grade']} overall={quality['overall']}; "
            f"resident_tokens={quality['resident_tokens']}; body_words={quality['body_words']}",
            "Treat the grader as a routing-risk signal, not as proof of task fit.",
        ]
    )


def build_route(goal: str, cwd: str | None = None, roots: list[str] | None = None, top_k: int = 16) -> dict[str, Any]:
    root_specs = [(Path(root), "other") for root in roots] if roots else None
    catalog = [enrich(item) for item in discover(cwd, roots=root_specs)]
    ranked: list[dict[str, Any]] = []
    for item in catalog:
        score, hits = _local_score(goal, item)
        ranked.append({
            "id": item["name"],
            "name": item["name"],
            "path": item["path"],
            "scope": item["scope"],
            "local_score": score,
            "lexical_hits": hits,
            "quality": item["quality"],
            "card": _card(item),
        })
    ranked.sort(key=lambda value: (-value["local_score"], value["id"].lower()))
    shortlist = ranked[: max(2, min(top_k, 24))]
    cards = [{"id": item["id"], "text": item["card"]} for item in shortlist]
    query = (
        f"User task: {goal}\n"
        "Rank only skills that can materially change the deliverable. Reject keyword-only matches. "
        "Prefer a narrow skill with direct evidence over a broad skill with a higher trigger-word overlap. "
        "If no candidate clearly fits, preserve the investigate/none escape hatch in the next decision."
    )
    return {
        "goal": goal,
        "cwd": str(Path(cwd or Path.cwd()).resolve()),
        "catalog_count": len(catalog),
        "shortlist_count": len(shortlist),
        "shortlist": shortlist,
        "mcp_rerank": {
            "server": "jev",
            "tool": "jev_rerank",
            "arguments": {"query": query, "candidates": cards, "top_k": min(8, len(cards))},
        },
        "mcp_decide_contract": {
            "server": "jev",
            "tool": "jev_decide",
            "requirements": [
                "The selected skill directly supports the requested deliverable, not just the topic.",
                "The selected skill's boundaries do not contradict the user's constraints.",
                "The evidence is strong enough to load automatically; otherwise choose investigate or ask_user.",
            ],
            "escape_hatches": True,
        },
        "policy": {
            "auto_load": "Only after semantic rerank plus final decision; require top probability >= 0.68 and margin >= 0.12.",
            "review": "If probability or margin is below the auto threshold, show top two candidates and ask one focused question.",
            "pipeline": "For distinct stages such as research -> write -> render, decide a short ordered pipeline, capped at three skills.",
            "explicit_selection": "If the user names $skill-name or an exact skill, respect it and use the router only for conflict checking.",
            "no_install": "Never install a skill automatically; report a find-skills handoff when no local candidate fits.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a precise Skill routing shortlist and Jev MCP payload.")
    parser.add_argument("goal", nargs="+", help="The user's task or session goal")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--root", action="append", dest="roots", help="Additional skill root; repeatable")
    parser.add_argument("--top-k", type=int, default=16)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_route(" ".join(args.goal), cwd=args.cwd, roots=args.roots, top_k=args.top_k)
    if args.json:
        print(json_dump(result))
        return 0
    print(f"catalog={result['catalog_count']} shortlist={result['shortlist_count']}")
    for item in result["shortlist"][:8]:
        print(f"{item['id']}: local={item['local_score']:.3f} quality={item['quality']['grade']} {item['path']}")
    print("Next: call jev_rerank with the emitted cards, then jev_decide before loading a Skill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
