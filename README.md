# lvsea-skill-router

一个面向 Codex、Claude Code 和其他 Agent 工作流的个人 Skill 路由器。它解决的不是“再安装一个大而全的 Skill”，而是：当本机有几十到上百个 Skill 时，先判断当前任务真正需要哪个 Skill，再把最小、最匹配的一组 Skill 交给智能体使用。

## 为什么做这个整合

[lomeshdutta/skill-router](https://github.com/lomeshdutta/skill-router) 提供了很有价值的第一层机制：扫描已安装 Skill，用 TypeSafe Jev 对任务与 Skill 做语义排序，并在没有匹配项时转交 `find-skills`。它的局限是最终输入仍然主要依赖 Skill 描述；描述写得宽泛、堆满触发词时，错误候选可能仍排在第一位。

[SEOAgent Skill Grader](https://seoagent.com/skill-grader) 提供了另一条重要视角：Skill 的描述每条消息都会占用上下文，正文过长、职责过多、没有渐进披露或没有把机械工作下沉到脚本，都会降低整体触发质量。这个项目把公开页面描述的六个轴做成了本地、无网络、无注册的近似评分：驻留 footprint、描述诚实度、正文体量、渐进披露、职责拆分和 CLI leverage。

本项目不把 Grader 分数冒充“功能相关性”。最终采用两道门：

```text
真实 Skill 清单
    -> 本地低成本预筛选 + 描述/上下文成本评分
    -> jev_rerank 语义重排
    -> jev_decide 检查交付物、边界、负证据和逃生选项
    -> 加载一个 Skill / 三步以内流水线 / 询问一个澄清问题 / 不加载
```

## 最短用法

先显式调用本 Skill：

```text
$lvsea-skill-router
请判断当前任务应该调用哪些已安装 Skill，完成后继续执行任务。
```

在本包目录运行本地预筛选：

```powershell
py -3.12 scripts/route_request.py --cwd C:\path\to\project --json "把季度数据做成可编辑的 PowerPoint 汇报并检查文字越界"
```

脚本不会替你调用远程模型，而是输出一个有界的 `jev_rerank` MCP 请求。然后让当前 Agent 调用已配置的 `jev` MCP：

1. 调用 `jev_rerank` 对 shortlist 排名；
2. 取前 2 至 4 个候选调用 `jev_decide`；
3. 只有概率至少 `0.68` 且与第二名差距至少 `0.12`，并且交付物与边界都匹配时，才加载 Skill；
4. 低于阈值时只问一个能区分候选的问题，不要硬猜。

## 常用命令

```powershell
# 扫描 Codex、Agent、项目和插件中的可发现 Skill
py -3.12 scripts/scan_skills.py --cwd C:\path\to\project --json

# 对全部发现的 Skill 做六轴上下文成本检查
py -3.12 scripts/grade_skill.py --all --cwd C:\path\to\project --json

# 为一个具体任务生成 shortlist 和 Jev MCP 请求
py -3.12 scripts/route_request.py --cwd C:\path\to\project --json "用户任务"

# 验证发布包结构、中文说明、脚本语法和公开文件中的密钥模式
py -3.12 scripts/validate_package.py .
```

## 四个实际场景

### 场景 1：原生 PPT 与 HTML 页面不要混淆

用户说“把季度数据做成一页可以展示的材料”。路由器不会只看“展示”这个词就选择 PPT Skill，而会把交付物问题带进二次决策：原生 `.pptx`、可直接打开的 HTML，还是图片。答案不清楚时先问一个问题。

### 场景 2：制造业设备管理系统

用户要求“读取设备和产量数据，设计工业科技蓝的设备管理看板并输出可运行页面”。路由器可以选择数据分析 Skill + 前端 Skill 的短流水线，并把“真实数据、可运行页面、桌面/移动验收”作为要求，而不是误选只会做静态图表的 Skill。

### 场景 3：本地 Web 保存链路修复

用户要求“修复保存失败，检查前端请求、后端校验、数据库写入和真实记录回归”。候选中可能同时有前端设计、后端架构、调试和测试 Skill。路由器把“保存链路和代表性记录回归”作为交付物证据，避免仅因“页面”一词就把设计 Skill 排第一。

### 场景 4：创建并发布新的 Skill

用户要求“创建中文 Skill，补充四个场景，运行验收并发布 GitHub”。路由器会优先考虑 Skill 创建/发布专用 Skill，并把 GitHub 发布和机器验收视为后续阶段；不会因为正文里出现“文档”就只加载普通写作 Skill。

## 发现范围与去重

默认扫描当前项目及祖先目录中的 `.agents/skills`、`.codex/skills`、`.claude/skills`，以及用户级 `CODEX_HOME/skills`、`~/.agents/skills`、`~/.claude/skills` 和 Codex 插件缓存。相同名称按“项目 > 用户 > 插件”优先，避免 Junction、复制安装和插件缓存造成重复候选。

如果使用其他 Agent，可通过 `--root` 显式指定其技能目录：

```powershell
py -3.12 scripts/route_request.py --root D:\agent\skills --json "任务"
```

## 安全与边界

- 默认只把任务摘要、Skill 名称、短描述、正文首段、边界句和评分发送给 Jev，不发送完整项目源码、完整对话、凭据或 API Key。
- `jev` MCP 不可用时，脚本仍可输出本地 shortlist，但必须标记为 `fallback`，不能把关键词重合说成语义置信度。
- 不自动安装、不自动修改其他 Skill、不自动修改 `AGENTS.md` 或 Codex 配置。
- 用户明确指定 `$skill-name` 时，以用户选择为准；路由器只做冲突检查或补充阶段建议。
- Skill Grader 评分是维护信号，不是任务匹配结论。一个功能很准确但描述过长的 Skill 可能得分不高，应该提示维护，而不是直接排除。
- 低置信度时宁可询问，也不要为了“必须选一个”加载错误 Skill。

## 本地验证

本包只使用 Python 标准库：

```powershell
py -3.12 -m unittest discover -s tests -p "test_*.py"
py -3.12 scripts/validate_package.py .
```

这两个检查能证明包结构、路由 payload、去重、质量警告和离线 fallback 可运行；它们不能替代 Jev 真实调用、下游 Skill 的实际产物质量或人工确认。

## 许可证

MIT。上游 `skill-router` 的实现与许可证请以其原仓库为准；本项目是面向 Codex/Windows 多根目录和二次 Grader 门的独立实现，不复制上游内部源码。
