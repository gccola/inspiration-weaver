# 灵感编织器 · inspiration-weaver

把一天里零散的想法、梦境、情绪片段、金句和未完成草稿，整理成保留个人声音的完整句段、文章、梦境解读或故事。

这个仓库首先是一个 **OpenClaw Skill**：配合 OpenClaw Hook 自动收集带 `~` 标记的消息，再由每日定时任务统一成稿。它也可以作为 Codex Skill 手动使用，但 Codex 不是自动收集方案的必要条件。

## 工作方式

```text
OpenClaw 收到的聊天消息
        │
        ▼
Hook：捕获授权来源，或任意一行以 ~ 开头的内容
        │
        ▼
本地 JSONL 收件箱
        │
        ▼
每日 OpenClaw 自动化任务
        │
        ▼
inspiration-weaver：整合、解梦、写作、必要查证
        │
        ▼
发送到用户确认的私密会话
```

你一天中可以随手发送：

```text
~今天我做了一个梦，梦见一棵树
~树叶一直不动，像在等我先开口
~醒来以后我想起小时候院子里那棵树
```

OpenClaw 会把这些片段记录下来；到设定时间后，任务再把它们整理成一篇有标题的短文、梦境解读或故事。

## 能做什么

- **补全句段**：把一句没写完的话补成 1—3 段自然文字。
- **文章优化**：保留原意和个人语域，处理逻辑、结构、节奏与表达。
- **每日灵感整合**：寻找一天碎片中反复出现的意象、情绪和问题。
- **梦境解读**：围绕梦中的画面、动作和情绪做克制解读，不套固定解梦词典，不做临床诊断。
- **故事创作**：以灵感为种子，补出角色欲望、阻力、转折和余韵。
- **必要查证**：只补充会影响成稿的外部事实；无法核实时保留不确定性。

核心边界是：不凭空编造用户经历、人物关系、诊断、引文或来源。

---

## 一、安装 OpenClaw

自动收集依赖一个持续运行的 OpenClaw Gateway。请把 Skill、Hook 和每日任务安装在 **运行 Gateway 的同一台主机** 上。

### 环境要求

- Node.js 24.16+（24.x）或 26.1+；推荐 Node 26。官方安装器会在缺少 Node 时自动安装。
- 一个可用的模型提供方：可在 onboarding 中复用已有 Codex/Claude Code 登录，或配置 API Key。
- Python 3.10+：用于本地灵感收件箱脚本。
- 一个已连接到 OpenClaw 的聊天渠道，例如 Telegram、Discord、Slack 或 WhatsApp。

### Windows

推荐先看 OpenClaw 官方的 Windows Hub：

- [OpenClaw Windows Hub](https://github.com/openclaw/openclaw-windows-node/releases/latest)
- [Windows 安装说明](https://docs.openclaw.ai/platforms/windows)

也可以在 PowerShell 中安装：

```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

### macOS / Linux

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

### 完成 onboarding

安装器通常会自动进入 onboarding。选择 Quick start 或 Custom setup，完成模型和基础配置。之后可以运行：

```bash
openclaw configure
```

把 Gateway 安装成后台服务并检查状态：

```bash
openclaw gateway install
openclaw gateway status
openclaw dashboard
```

如果 onboarding 中的 Gateway 仍在前台运行，先按 `Ctrl+C` 停止，再安装后台服务。

连接聊天渠道：

```bash
openclaw channels add
openclaw channels list
```

具体渠道参数以 `openclaw channels add --help` 和官方渠道文档为准。

---

## 二、安装 inspiration-weaver Skill

直接从 GitHub 安装：

```bash
openclaw skills install git:gccola/inspiration-weaver@main
```

也可以先克隆仓库，再从本地目录安装：

```bash
git clone https://github.com/gccola/inspiration-weaver.git
openclaw skills install ./inspiration-weaver --as inspiration-weaver
```

PowerShell 中将最后一行改为：

```powershell
openclaw skills install .\inspiration-weaver --as inspiration-weaver
```

只给当前 agent workspace 安装时使用默认行为；让本机所有 agent 共用时加 `--global`：

```bash
openclaw skills install git:gccola/inspiration-weaver@main --global
```

验证：

```bash
openclaw skills list --verbose
openclaw skills info inspiration-weaver
openclaw skills check
```

默认工作区安装位置通常是：

```text
~/.openclaw/workspace/skills/inspiration-weaver
```

全局安装位置通常是：

```text
~/.openclaw/skills/inspiration-weaver
```

如果自定义过 agent workspace，请以 `openclaw skills info inspiration-weaver` 显示的实际路径为准。下文把这个目录记为 `SKILL_DIR`。

> OpenClaw 和 Codex 的技能目录彼此独立。只把仓库放进 `~/.codex/skills` 不会让 OpenClaw 自动收集消息，也不会创建每日任务。

---

## 三、安装自动收集 Hook

Hook 源码位于：

```text
<SKILL_DIR>/assets/openclaw-inbox-hook
```

它监听 OpenClaw 收到的消息，把符合条件的内容追加到本地 JSONL 收件箱，不回复消息，也不会主动读取历史聊天。

### Windows PowerShell

```powershell
$skillDir = Join-Path $HOME ".openclaw\workspace\skills\inspiration-weaver"
$hookSource = Join-Path $skillDir "assets\openclaw-inbox-hook"
$hookTarget = Join-Path $HOME ".openclaw\hooks\inspiration-inbox-capture"

New-Item -ItemType Directory -Force -Path $hookTarget | Out-Null
Copy-Item -Path (Join-Path $hookSource "*") -Destination $hookTarget -Recurse -Force

$configPath = Join-Path $hookTarget "config.json"
if (-not (Test-Path $configPath)) {
  Copy-Item (Join-Path $hookTarget "config.example.json") $configPath
}
```

### macOS / Linux

```bash
SKILL_DIR="$HOME/.openclaw/workspace/skills/inspiration-weaver"
HOOK_DIR="$HOME/.openclaw/hooks/inspiration-inbox-capture"

mkdir -p "$HOOK_DIR"
cp -R "$SKILL_DIR/assets/openclaw-inbox-hook/." "$HOOK_DIR/"
[ -f "$HOOK_DIR/config.json" ] || \
  cp "$HOOK_DIR/config.example.json" "$HOOK_DIR/config.json"
```

安装前请审阅 `handler.js` 和 `HOOK.md`。这是会在本机运行的 Hook 代码，只应安装你信任的版本。

Hook 是复制到 managed hooks 目录的独立副本。以后更新 Skill 中的 Hook 源码后，需要重新复制并重启 Gateway；Skill 安装本身不会同步 Hook 配置。

---

## 四、配置触发标记与来源

编辑：

```text
~/.openclaw/hooks/inspiration-inbox-capture/config.json
```

基础配置：

```json
{
  "triggerPrefixes": ["~"],
  "triggerTags": [],
  "allowedChannelIds": [],
  "allowedConversationIds": [],
  "allowedSenderIds": [],
  "captureAllowedSourcesWithoutTag": true,
  "inboxPath": "",
  "maxTextLength": 50000
}
```

默认行为：

- 任意消息行以 `~` 开头时捕获，例如 `~今天我做了一个梦`。
- `~` 前允许空格；写入收件箱前会移除 `~`。
- `10~20` 或句子中间的 `~` 不会触发。
- 默认不捕获普通消息，因为没有配置任何允许来源。
- `triggerTags` 默认为空。只有仍想兼容 `#灵感` 等旧标记时才填写，例如 `["#灵感"]`。
- 默认收件箱路径是 `~/.openclaw/workspace/memory/inspiration/inbox.jsonl`。
- `inboxPath` 留空时使用默认路径；如果填写自定义绝对路径，Python 命令也必须使用同一路径。

### 捕获专用会话中不带 `~` 的消息

先确认来源 ID：

```bash
openclaw channels list
openclaw channels resolve --channel <provider> "<channel-or-user-name>"
```

然后在 `config.json` 中填写对应的 `allowedChannelIds` 或 `allowedConversationIds`，并保持：

```json
"captureAllowedSourcesWithoutTag": true
```

不要猜频道 ID、会话 ID 或发送者 ID。不同渠道的 ID 和 target 格式不同，应以 `channels list`、`channels resolve` 或真实测试记录为准。

### 群聊与隐私

`allowedSenderIds` 会作用于所有捕获路径，包括带 `~` 的消息。在群聊中务必配置发送者白名单：

```json
"allowedSenderIds": ["YOUR_SENDER_ID"]
```

带 `~` 的消息可以绕过频道/会话白名单，因此不要在公开群或多人频道随意使用该标记，除非你接受它被记录到本地收件箱。

Hook 还会跳过斜杠命令、空文本、超长文本和看起来像密钥或密码的内容。但这只是启发式保护，不能替代权限隔离。

---

## 五、启用 Hook 并用真实消息验证

先检查 Hook 是否被发现：

```bash
openclaw hooks list --verbose
openclaw hooks info inspiration-inbox-capture
```

启用 Hook：

```bash
openclaw hooks enable inspiration-inbox-capture
```

Hook 代码和元数据不会被自动监视；安装、复制或修改 Hook 后，重启 Gateway：

```bash
openclaw gateway restart
openclaw hooks check
```

`hooks check` 只能证明注册和可用性，不能证明消息真的写入了收件箱。发送一条真实测试消息：

```text
~今天我做了一个梦，梦见一棵树
```

然后检查收件箱：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" stats
python "<SKILL_DIR>/scripts/inspiration_inbox.py" list --pending
```

只有看到真实测试记录后，才说明捕获链路已经工作。

Hook 只能观察启用之后、实际经过 OpenClaw 的消息，不能回溯完整聊天历史。没有接入 OpenClaw 的微信、手机通知或其他应用消息也不会被自动收集。

---

## 六、创建每日自动整理任务

每日任务会先领取收件箱中的待处理素材，再按 `inspiration-weaver` 的规则成稿。任务运行和 Skill/Hook 必须位于同一台 Gateway 主机。

### PowerShell

```powershell
$skillDir = Join-Path $HOME ".openclaw\workspace\skills\inspiration-weaver"
$prompt = (Get-Content -Raw -Encoding UTF8 `
  (Join-Path $skillDir "assets\openclaw-daily-prompt.md")).Replace("<SKILL_DIR>", $skillDir)

openclaw automations create "30 22 * * *" $prompt `
  --name "每日灵感编织" `
  --tz "Asia/Shanghai" `
  --session isolated `
  --announce `
  --channel "<CHANNEL>" `
  --to "<TARGET>"
```

### macOS / Linux

```bash
SKILL_DIR="$HOME/.openclaw/workspace/skills/inspiration-weaver"
PROMPT="$(cat "$SKILL_DIR/assets/openclaw-daily-prompt.md")"
PROMPT="${PROMPT//<SKILL_DIR>/$SKILL_DIR}"

openclaw automations create "30 22 * * *" "$PROMPT" \
  --name "每日灵感编织" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --announce \
  --channel "<CHANNEL>" \
  --to "<TARGET>"
```

参数说明：

- `30 22 * * *` 表示每天 22:30；可以按自己的作息调整。
- `--tz "Asia/Shanghai"` 指定任务时区。
- `--session isolated` 让任务在独立会话中运行，不依赖创建时的聊天上下文。
- `--channel` 和 `--to` 必须是已确认、能接收私密成稿的渠道目标。不同渠道格式不同，不要猜。
- 任务保存的是创建时的提示词副本。以后修改 `assets/openclaw-daily-prompt.md` 不会自动更新任务，需要重新执行 `openclaw automations edit <jobId> --message "<NEW_PROMPT>"`。

创建后查看任务和 ID：

```bash
openclaw automations list --all
openclaw automations show <jobId>
```

立即手动跑一次，不必等到设定时间：

```bash
openclaw automations run <jobId> --wait
openclaw automations runs <jobId> --limit 20
```

如果任务执行成功，收件箱批次会标记为 `compiled`；失败时会释放批次，下一次任务可以重试。任务为空时最终回复 `NO_REPLY`，不会发送空洞总结。

---

## 七、端到端验收

建议按这个顺序验收一次：

1. 发送一条真实的 `~` 测试消息。
2. 用 `inspiration_inbox.py list --pending` 确认消息已经入库。
3. 用 `openclaw automations run <jobId> --wait` 手动执行每日任务。
4. 确认收到成稿，并检查 `inspiration_inbox.py stats` 中的状态变化。
5. 等到下一次计划时间，确认定时调度本身也正常。

常用收件箱命令：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" stats
python "<SKILL_DIR>/scripts/inspiration_inbox.py" list --pending
python "<SKILL_DIR>/scripts/inspiration_inbox.py" export --through today --format markdown
python "<SKILL_DIR>/scripts/inspiration_inbox.py" recover --older-than-hours 12
python "<SKILL_DIR>/scripts/inspiration_inbox.py" mark --batch "<BATCH_ID>" --status compiled
python "<SKILL_DIR>/scripts/inspiration_inbox.py" release --batch "<BATCH_ID>" --note "daily compilation failed"
```

---

## 八、排障

### `openclaw` 命令找不到

重新打开终端，并检查 Node 和 OpenClaw：

```bash
node --version
openclaw --version
```

如果刚完成安装，通常是 PATH 尚未刷新。

### Gateway 不在运行

```bash
openclaw status
openclaw gateway status
openclaw gateway restart
openclaw logs --follow
openclaw doctor
```

### Skill 没有被识别

```bash
openclaw skills list --verbose
openclaw skills info inspiration-weaver
openclaw skills check
```

检查安装位置是否为当前 agent workspace，以及 `SKILL.md` 是否存在。

### Hook 没有捕获消息

依次检查：

```bash
openclaw hooks list --verbose
openclaw hooks info inspiration-inbox-capture
openclaw hooks check
```

然后确认：

- Hook 已启用，并且复制或修改后重启过 Gateway。
- 消息确实经过当前 OpenClaw Gateway。
- 触发标记在行首，或来源 ID 已加入允许列表。
- `allowedSenderIds` 没有误排除自己的发送者 ID。
- `handler.js` 和 Python 命令使用同一个 `inboxPath`。
- 消息没有被斜杠命令、疑似密钥、空文本或超长文本规则跳过。

### 定时任务不执行

```bash
openclaw automations status
openclaw automations list --all
openclaw automations runs <jobId> --limit 20
openclaw automations show <jobId>
openclaw logs --follow
openclaw doctor
```

同时检查任务是否启用、时区是否正确、Gateway 是否常驻，以及 `--channel` / `--to` 是否能接收消息。

### 批次长期停在 `processing`

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" recover --older-than-hours 1
```

---

## 九、隐私与安全

- 默认只捕获带 `~` 的消息；不要默认打开“收集所有私聊”。
- 专用会话必须明确授权；群聊必须配置 `allowedSenderIds`。
- Hook 只在本地记录，不会回复消息，也不会读取完整历史。
- `config.json`、`*.jsonl` 收件箱和锁文件已加入 `.gitignore`，避免私密内容误上传。
- 不要在灵感素材里发送密码、密钥、身份证件或他人的隐私资料。
- 外部查证应尽量使用最小必要查询，不要把整段私密原文转发到额外第三方服务。
- 成稿只发送到用户确认的私密渠道，不要默认发到群聊或公开频道。
- 安装、启用和验证都应在 Gateway 主机完成；不要声称自动收集已经上线，除非真实测试成功。

---

## 十、手动使用

### 在 OpenClaw 中

直接给 OpenClaw 发消息即可：

```text
使用 inspiration-weaver skill，把下面的碎片整理成一篇有标题的短文。
保留我的语气，不要写成公众号腔。

~今天我做了一个梦，梦见一棵树。
~树叶一直不动，像在等我先开口。
~醒来以后我想起小时候院子里那棵树。
```

也可以单独提出任务：

```text
用 inspiration-weaver 解读这个梦，再附一个可选的梦境散文版本：
我梦见自己走进一片没有边界的空地，中央只有一棵树。
```

```text
用 inspiration-weaver 优化下面这篇文章。保留观点和第一人称，不要扩写成鸡汤：
……
```

### 使用模式

| 需求 | 推荐输入 | 默认交付 |
| --- | --- | --- |
| 补句 | 一句意象或未完成的话 | 1—3 段成稿 |
| 优化文章 | 完整或半完整草稿 | 修改后的全文 |
| 每日整合 | 一天中的多条碎片 | 有标题的短文或短章 |
| 解梦 | 梦境片段和醒来后的感受 | 梦的骨架、可能性解读、现实追问 |
| 故事 | 一个画面或设定 | 完整短篇或场景 |

更细的写作规则见：

- [`references/modes.md`](references/modes.md)
- [`references/dream-and-story.md`](references/dream-and-story.md)
- [`references/openclaw-daily.md`](references/openclaw-daily.md)

---

## 可选：在 Codex 中手动使用

本仓库同时保留了 Codex Skill 元数据。你可以在 Codex 中手动调用它，但这条路径 **不会开启 OpenClaw 自动收集**。

克隆到 Codex 技能目录：

```bash
git clone https://github.com/gccola/inspiration-weaver.git \
  "$HOME/.codex/skills/inspiration-weaver"
```

Windows PowerShell：

```powershell
git clone https://github.com/gccola/inspiration-weaver.git `
  "$HOME\.codex\skills\inspiration-weaver"
```

刷新或重新打开 Codex 后，显式调用：

```text
使用 $inspiration-weaver，把下面的碎片整理成一篇短文：……
```

如果你只需要 OpenClaw 的自动收集和每日成稿，不需要执行这一节。

---

## 仓库结构

```text
inspiration-weaver/
├── SKILL.md                         # Skill 入口
├── agents/openai.yaml               # Codex 界面元数据
├── assets/
│   ├── openclaw-daily-prompt.md     # 每日自动化提示词
│   └── openclaw-inbox-hook/         # OpenClaw 消息捕获 Hook
├── references/
│   ├── modes.md
│   ├── dream-and-story.md
│   └── openclaw-daily.md            # OpenClaw 详细部署与排障
├── scripts/
│   └── inspiration_inbox.py         # 本地收件箱工具
├── README.md
└── .gitignore
```

## 技术依赖

- **OpenClaw**：Gateway、Skill、Hook 和每日自动化。
- **Node.js**：OpenClaw 与 Hook 运行环境。
- **Python 3.10+**：本地收件箱工具。
- **Git**：仅在使用 Git 安装 Skill 时需要。

## 设计原则

1. 保留用户最有辨识度的原句、比喻和语气。
2. 补全缺口，不替用户发明经历。
3. 外部事实可以查证，私人感受不能代写。
4. 梦的解读使用概率语言，不做诊断。
5. 自动收集只在明确授权、可验证的情况下启用。

## 官方资料

本 README 的 OpenClaw 命令与路径按 2026-10-28 的官方文档和 OpenClaw `v2026.10.8` 核对：

- [OpenClaw 文档](https://docs.openclaw.ai/)
- [Getting started](https://docs.openclaw.ai/start/getting-started)
- [Install](https://docs.openclaw.ai/install)
- [Skills CLI](https://docs.openclaw.ai/cli/skills)
- [Hooks CLI](https://docs.openclaw.ai/cli/hooks)
- [Hooks configuration](https://docs.openclaw.ai/automation/hooks/configuration)
- [Automation jobs](https://docs.openclaw.ai/automation/cron-jobs/managing-jobs)
- [Channels CLI](https://docs.openclaw.ai/cli/channels)

OpenClaw 的版本、命令和渠道参数可能继续变化；遇到差异时以你本机 `openclaw --help` 和官方文档为准。