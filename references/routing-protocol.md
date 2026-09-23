# 路由协议

## 1. 先做本地清单

`route_request.py` 是无网络的预筛选器，不能把它的 `local_score` 当成最终答案。它默认扫描：

- 当前项目及其祖先目录中的 `.agents/skills`、`.codex/skills`、`.claude/skills`；
- `CODEX_HOME/skills`、用户级 `.agents/skills` 和 `.claude/skills`；
- Codex 插件缓存中的嵌套 `skills/*/SKILL.md`。

同名 Skill 按项目 > 用户 > 插件优先，避免同一个 Junction 或插件副本被重复计分。`--root` 可用于隔离测试或显式指定其他 Agent 的技能根。

每个候选只保留以下信息：名称、frontmatter 描述、正文首段、边界句、路径、作用域和上下文成本评分。不会把完整 Skill、项目源码、对话记录或密钥发送给 Jev。

## 2. 第一层：jev_rerank

使用脚本输出的 `mcp_rerank` 请求，调用 MCP 服务器 `jev` 的 `jev_rerank`：

```json
{
  "query": "脚本输出的 mcp_rerank.arguments.query",
  "candidates": [
    {"id": "skill-name", "text": "脚本输出的 card"}
  ],
  "top_k": 8
}
```

把排序结果看作语义相关性证据。不要因为某个候选名称与用户用词相同就跳过第二层；也不要因为某个候选的 Grader 等级高就把它当作功能正确。

## 3. 第二层：jev_decide

把 `jev_rerank` 返回的前二至四个候选组成一个有边界的决策。`evidence` 至少包含：

1. 用户要交付的具体文件、页面、数据或操作结果；
2. 当前项目/平台约束；
3. 候选 Skill 的 declared purpose、body evidence 和 boundary evidence；
4. 第一层的概率和 top-to-runner-up margin。

推荐的 `requirements`：

```json
[
  "The selected skill directly supports the requested deliverable, not just the topic.",
  "The selected skill's boundaries do not contradict the user's constraints.",
  "The evidence is strong enough to load automatically; otherwise choose investigate or ask_user."
]
```

`escape_hatches` 必须为 `true`。允许 `ask_user`、`investigate` 或 `none`，因为路由器的职责是避免错误调用，不是强行产出一个名字。

## 4. 判定规则

- **自动加载**：最终决策明确支持某个 Skill，最高概率 `>= 0.68`，且与第二名差距 `>= 0.12`；没有用户明确冲突。
- **需要澄清**：概率或差距不足，或者两个候选分别对应不同交付物。只问一个能区分候选的问题，例如“你要原生 `.pptx`，还是可直接打开的 HTML 页面？”
- **短流水线**：用户明确要求多个不同阶段时，最多选择三个，并给出顺序、输入产物、输出产物和每一阶段的验收点。不要把同一阶段的多个近似 Skill 全部加载。
- **无匹配**：没有候选满足交付物和边界要求时，报告 `find-skills` 交接；不擅自安装。
- **用户指定**：用户显式写出 `$skill-name` 时，优先使用它。只有发现缺失、边界冲突或确实需要前置/后置阶段时才提出补充路由。

## 5. Grader 的用法

本包的 `grade_skill.py` 是离线近似检查，不调用 SEOAgent 云端页面。六个轴对应：

- `resident_footprint`：每条消息都要驻留的描述字符/Token；
- `description_honesty`：是否靠泛化词或重复触发词扩大覆盖面；
- `body_size`：正文相对约 921 词中位数和 2,207 词 p90 的成本；
- `progressive_disclosure`：是否把细节放到 references 或 scripts；
- `factoring`：是否把互不相干的流程塞进一个 Skill；
- `cli_leverage`：是否把稳定、可测试的机械工作下沉到脚本。

低等级只产生 `routing-risk` 警告。修复 Skill 描述应是单独任务，不能在本次路由中静默改写别人的 Skill。

## 6. Codex 现实边界

Skill 不能保证拦截每一个用户消息，也不能凭空让 Codex 自动加载另一个 Skill。最可靠的用法是显式调用 `$lvsea-skill-router`，或在本地 Agent 规则中要求“复杂任务先调用路由器”。本包默认允许隐式发现，但不会自行修改 `AGENTS.md`、Codex 配置、项目 hooks 或安装目录。
