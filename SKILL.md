---
name: lvsea-skill-router
description: 仅在用户显式调用或明确要求路由时使用的通用 Skill 入口：扫描实际可发现的 Skill，调用可用 Jev MCP 进行语义重排和最终决策，选择单个 Skill 或不超过三个阶段的短流水线；保留用户指定项。默认高置信度时继续，也支持先展示候选、证据和 provider 状态后等待确认。不扫描普通任务、不自动安装，不把本地回退说成 Jev 概率。
metadata:
  short-description: 统一 Skill 路由与可选确认门
---

# lvsea-skill-router

Use this skill as a routing gate, not as a replacement for the selected specialist.
The goal is to load the smallest useful set of Skills and avoid keyword-only matches.

## 触发条件与模式

- 普通任务不自动扫描 Skill、不自动调用 Jev。用户显式调用 `$lvsea-skill-router` / `@lvsea-skill-router`，或明确要求先选 Skill、检查 Skill 冲突、安排多阶段路由时，才运行本 Skill。
- 默认是“路由后继续”：完成 `jev_rerank` 与 `jev_decide` 后，只有满足下方阈值和边界条件才加载 Skill 并继续用户任务。
- 用户说“先展示候选，等我确认”“先不要执行”或同义表达时，进入“确认后继续”模式：先 rerank，展示结果并停止；收到明确的“继续”后，再对同一批候选调用 `jev_decide`，不重跑扫描或 rerank。
- 旧名 `$lvsea-jev-gate` 不保证能被不同 Agent 解析为本 Skill；跨智能体请统一显式调用 `$lvsea-skill-router`，并用“先展示候选并等我确认”进入确认模式。
- 用户明确指定 `$skill-name`、Skill 名称或固定工具时保留其选择；本 Skill 只检查冲突、缺失依赖或确有必要的额外阶段，不得用候选覆盖用户选择。
- `$codex-jev-gate` 是可选的独立 Codex Skill，不是本路由器的依赖；本路由器内置确认流程，在没有该 Skill 的其他智能体中仍可工作。用户显式指定它时必须保留该选择；若目标 Agent 没有安装，则报告不可用，不得静默替换。

## 统一路由流程

1. 读取用户原始目标、明确指定的 Skill、工作目录和确认模式，不擅自扩展任务。
2. 运行 `scripts/route_request.py --json --cwd <project> "<goal>"`。脚本扫描真实可发现的项目、用户、Agent、Codex 和插件 Skill，按名称去重并生成有界候选；路由器自身不作为下游候选。
3. 仅将脚本输出的有限 `mcp_rerank` 数据发送给已配置 `jev` MCP 的 `jev_rerank`。优先依据交付物、平台、文件类型、操作和验收证据，弱化单纯关键词重合；Grader 仅代表描述与上下文成本风险，不代表功能匹配。
4. 在确认模式下，展示第一名、第二名、`Δ`、命中证据和 provider 状态，然后询问：**“是否继续？回复‘继续’后我才执行；回复‘停止’则结束。”** 随即停止。确认前不得调用 `jev_decide`、读取候选 Skill 的完整说明或执行实际任务；允许的外部调用仅限本次有界 `jev_rerank`。
5. 收到明确“继续”后（默认模式则在 rerank 后），把前二至四个候选和 `mcp_decide_contract` 交给 `jev_decide`，设置 `escape_hatches: true`。复用本轮扫描和 rerank 结果，不重复发起相同调用。
6. 仅在最终决策明确支持、最高概率至少 `0.68`、领先第二名至少 `0.12` 且交付物与边界吻合时，读取所选 `SKILL.md` 并按其规则执行。不同阶段组成的流水线最多三个 Skill，并标明顺序及阶段验收点。
7. 概率或差距不足、交付物不明、候选边界冲突或 Jev 建议 `ask_user` / `investigate` / `none` 时，不猜测加载；只问一个能区分候选的问题，或报告 `find-skills` 交接。绝不自动安装。
8. 报告所选 Skill、匹配证据、排除的近似候选、Jev 或 fallback 来源、置信度与差值、缺失依赖，然后按模式继续或停止。

## 概率、Provider 与隐私边界

- 只有 `jev_rerank` 返回可验证的概率字段时才能报告真实概率；若返回候选但没有概率，明确写“本轮没有可验证概率”。本地 `local_score` / shortlist 是回退证据，不得改名为 Jev 概率或语义置信度。
- Jev 不可用时报告未验证原因和本地回退；不自动加载未被用户明确指定的 Skill。确认模式仍需先等待“继续”；回退候选接近时先询问。
- 首选已配置的 `jev` MCP，不直接调用外部 API。只发送有界 Skill 名称、描述、短正文摘录、边界证据和任务摘要；不得发送密钥、凭据、完整私有源码、完整对话或无关项目数据。
- `scripts/grade_skill.py --all` 是六轴上下文成本近似检查，只用于发现描述噪声或打破平局，不代表任务功能匹配。

## 本地命令

```text
py -3.12 scripts/scan_skills.py --json --cwd <project>
py -3.12 scripts/grade_skill.py --all --cwd <project> --json
py -3.12 scripts/route_request.py --cwd <project> --json "<user task>"
```

详细 MCP 请求契约、确认模式、阈值和 Windows 发现范围见 [references/routing-protocol.md](references/routing-protocol.md)。
