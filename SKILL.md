---
name: lvsea-skill-router
description: >
  精确路由 Codex/Agent 已安装的 Skill：当技能很多、智能体没有主动调用、多个 Skill 描述重叠或一个任务需要多个阶段时使用。先扫描实际可发现的 SKILL.md，再用本地六轴上下文成本评分过滤宽泛描述，调用已配置的 jev MCP 做语义重排和二次决策，只有证据充分且置信度与排名差距达标才加载一个或多个 Skill；用户已明确指定 Skill 时不替换它。
metadata:
  short-description: 精准选择并串联已安装 Skill
---

# lvsea-skill-router

Use this skill as a routing gate, not as a replacement for the selected specialist.
The goal is to load the smallest useful set of Skills and avoid keyword-only matches.

## Workflow

1. **Honor explicit selection first.** If the user names `$skill-name`, a Skill name, or a fixed tool, keep it. Use this router only to check conflicts, missing dependencies, or an additional stage.
2. **Build the real catalog.** Run `scripts/route_request.py --json --cwd <project> "<goal>"`. It scans project, user, Agent, Codex, and enabled plugin roots, deduplicates by Skill name, and includes a bounded body excerpt and boundary evidence. Do not assume that a cloned repository is discoverable.
3. **Use two semantic gates.** Send the emitted `mcp_rerank` payload to the `jev` MCP server's `jev_rerank` tool. Then send the top two to four candidates to `jev_decide` with the three requirements in `mcp_decide_contract` and `escape_hatches: true`. A high relevance score alone is not permission to load a Skill.
4. **Reject broad false positives.** Prefer evidence about the requested deliverable, platform, file type, operation, and acceptance check. Treat shared nouns and trigger words as weak evidence. A Skill Grader score is a risk signal about description/context cost, never proof of functional fit.
5. **Choose one, a short pipeline, or none.** Auto-load one Skill only when the final decision supports it, the top probability is at least `0.68`, and the top-to-runner-up margin is at least `0.12`. For distinct stages such as research -> writing -> rendering, load an ordered pipeline capped at three Skills. If the margin is lower, ask one focused question instead of guessing. If no local Skill fits, report a `find-skills` handoff; never install automatically.
6. **Load before acting.** Read the chosen Skill's `SKILL.md` from the returned path and follow its boundaries. For a pipeline, read and apply each Skill in order, passing only the needed artifact or evidence between stages. Do not silently substitute a broad general-purpose Skill for a missing specialist.
7. **Report the route.** State the selected Skill(s), why the task evidence matches, the rejected near-match, whether the result came from Jev or the local fallback, and any missing dependency. Then proceed with the user's task rather than stopping at the routing report.

## Provider and privacy boundary

- The preferred semantic provider is the configured MCP server `jev`, not a direct API call from this Skill.
- If `jev_rerank` or `jev_decide` is unavailable, the scripts may produce a deterministic shortlist, but label it `fallback` and do not present it as semantic confidence. Ask the user when the shortlist is ambiguous.
- Send only bounded Skill metadata, descriptions, body excerpts, boundary lines, and the task summary. Never send secrets, API keys, credentials, full private source files, transcripts, or unrelated project data.
- `scripts/grade_skill.py --all` implements the local approximation of the six public Skill Grader axes: resident footprint, description honesty, body size, progressive disclosure, factoring, and CLI leverage. Use it to repair noisy Skills or break ties, not to decide task fit.

## Useful commands

```text
py -3.12 scripts/scan_skills.py --json --cwd <project>
py -3.12 scripts/grade_skill.py --all --cwd <project> --json
py -3.12 scripts/route_request.py --cwd <project> --json "<user task>"
```

For the full MCP request contract, thresholds, and Windows discovery details, read [references/routing-protocol.md](references/routing-protocol.md).
