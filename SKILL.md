---
name: lvsea-skill-router
description: |
  中文本机 Skill 总路由：当用户不知道该用哪个已安装 Skill、多个 Skill 会产生明显不同的效果、一个任务需要多个阶段，或用户要求先给方案再执行时使用。扫描真实可发现的 Skill，按交付物和边界筛选并可用 jev 做语义重排；必要时给出 2–3 个 Skill 组合、效果预期和小样计划，再用 Grilling 式的当前决策前沿提问收敛选择。用户已明确指定 Skill 或要求直接执行时优先遵循用户选择，不替换它。
metadata:
  short-description: 精准选择并串联已安装 Skill
  version: "0.2.0"
---

# lvsea-skill-router

Use this skill as a routing gate, not as a replacement for the selected specialist.
The goal is to load the smallest useful set of Skills and avoid keyword-only matches.

## 触发条件与调用方式

当用户说“帮我选 Skill”“已安装很多技能但不会主动调用”“多个 Skill 描述很像”“请精准调用一个或多个 Skill”“先给我几个制作方向”“让我选方案”或要求先路由再执行时，显式调用 `$lvsea-skill-router`。用户已经指定 `$skill-name` 时，不替换用户选择。

## 中文方案选择模式

本 Skill 不只输出一个 Skill 名称；当候选路线会明显改变交付物或观看/使用效果时，先生成有限的方案卡：

1. 扫描真实 Skill 清单并识别任务的输入、交付物、平台、受众和验收条件。
2. 选择 2–3 条有实质差异的路线，优先给出一个推荐方案；路线可以是一个 Skill，也可以是最多三个阶段的短流水线。
3. 每张方案卡写明 Skill 组合、最终产物、预期效果、适用场景、优点、限制、依赖/权限、预览方式和验收证据。
4. 如果用户没有说“直接执行”，且不同路线确实会改变结果，先等待用户选择；如果用户说“按推荐直接做”，选择推荐方案继续。
5. 如果只有一条明显路线，不为了形式制造选项，直接报告路线并执行。

适用于网页、代码、数据、文章、图像、PPT、视频和其他可交付任务；不要把方案卡限缩为视频制作。

详细模板见 [references/route-cards.md](references/route-cards.md)。

## Grilling 式有限提问

把 `grilling` 的设计树机制用于决策，不把用户当作资料检索器：先自行读取文件、检查环境和扫描 Skill；只有会改变路线、交付物、权限或风险的问题才问。

- 当前轮只问已经具备前置条件的“决策前沿”；相互独立的问题可以同轮提出。
- 每轮最多 3 个问题，默认最多 2 轮；每个问题给出推荐答案和简短理由。
- 用户明确说“直接做”时，使用低风险默认值并记录假设，不把小细节变成确认门。
- 用户明确说“拷问我/压力测试/把方案问透”时，才切换为更深入的完整 Grilling 模式。
- 每轮提问后等待用户回答；不要在没有回答时假装已完成选择。

详细规则见 [references/grilling-dialogue.md](references/grilling-dialogue.md)。

## Workflow

1. **Honor explicit selection first.** If the user names `$skill-name`, a Skill name, or a fixed tool, keep it. Use this router only to check conflicts, missing dependencies, or an additional stage.
2. **Build the real catalog.** Run `scripts/route_request.py --json --cwd <project> "<goal>"`. It scans project, user, Agent, Codex, and enabled plugin roots, deduplicates by Skill name, and includes a bounded body excerpt and boundary evidence. Do not assume that a cloned repository is discoverable.
3. **Use two semantic gates.** Send the emitted `mcp_rerank` payload to the `jev` MCP server's `jev_rerank` tool. Then send the top two to four candidates to `jev_decide` with the three requirements in `mcp_decide_contract` and `escape_hatches: true`. A high relevance score alone is not permission to load a Skill.
4. **Reject broad false positives.** Prefer evidence about the requested deliverable, platform, file type, operation, and acceptance check. Treat shared nouns and trigger words as weak evidence. A Skill Grader score is a risk signal about description/context cost, never proof of functional fit.
5. **Choose one, a short pipeline, or route cards.** Auto-load one Skill only when the final decision supports it, the top probability is at least `0.68`, and the top-to-runner-up margin is at least `0.12`. For distinct stages such as research -> writing -> rendering, load an ordered pipeline capped at three Skills. If the top candidates map to materially different deliverables or visual effects, produce the route cards in the Chinese choice mode before loading heavy downstream Skills. If the margin is lower, ask a focused frontier question instead of guessing. If no local Skill fits, report a `find-skills` handoff; never install automatically.
6. **Load before acting.** Read the chosen Skill's `SKILL.md` from the returned path and follow its boundaries. For a pipeline, read and apply each Skill in order, passing only the needed artifact or evidence between stages. Do not silently substitute a broad general-purpose Skill for a missing specialist.
7. **Report the route.** State the selected Skill(s), why the task evidence matches, the rejected near-match, whether the result came from Jev or the local fallback, any missing dependency, and—when used—the route cards and the user's selected/recommended route. Then proceed with the user's task rather than stopping at the routing report.

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
