# OpenClaw 每日自动收集与整理

本流程把 OpenClaw 收到的零散消息收集到本地，再由每日任务统一整理成文章、梦境解读或故事。

```text
消息 → Hook 捕获 → 本地 JSONL 收件箱 → 每日自动化 → inspiration-weaver 成稿
```

命令与路径按 **OpenClaw 2026.10.8 官方文档** 核对，核对于 2026-10-28。OpenClaw 更新较快，遇到差异时以本机 `openclaw --help` 和官方文档为准。

> 本文是部署说明，不表示任何一台机器已经完成实际部署或联调。只有真实测试消息进入收件箱、每日任务成功产出成稿后，才能说这条链路已经工作。

## 适用边界

- 所有 OpenClaw CLI 操作都应在**运行 Gateway 的同一台主机**执行，尤其是 `hooks enable`、Hook 配置和自动化任务。
- OpenClaw 与 Codex 的技能目录彼此独立。把 Skill 放进 `~/.codex/skills` 不会开启 OpenClaw 自动收集。
- Hook 只观察启用之后、实际经过 OpenClaw Gateway 的消息，不能回溯历史聊天。
- 没有接入 OpenClaw 的微信消息、手机通知或其他应用内容不会被自动收集。
- 默认只捕获带行首 `~` 的消息；不要默认收集全部私聊或群聊。

## 前置条件

- OpenClaw Gateway 已安装并可持续运行。
- 已配置模型提供方，并能正常对话。
- 已连接至少一个聊天渠道。
- 主机可运行 Node.js 和 Python 3.10+。
- 已确认成稿要发送到哪个私密会话或频道。

Node.js 要求为 24.16+（24.x）或 26.1+，推荐 Node 26。官方安装器通常会自动处理 Node。

---

## 一、安装和检查 OpenClaw

Windows PowerShell：

```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

macOS / Linux：

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

安装器通常会启动 onboarding。完成后安装后台 Gateway 服务：

```bash
openclaw gateway install
openclaw gateway status
openclaw dashboard
```

如果 onboarding 中的 Gateway 仍在前台运行，先按 `Ctrl+C` 停止。

连接渠道：

```bash
openclaw channels add
openclaw channels list
```

如果稍后需要补配置：

```bash
openclaw configure
```

---

## 二、安装 Skill

优先使用官方 Git 安装语法：

```bash
openclaw skills install git:gccola/inspiration-weaver@main
```

本地目录安装：

```bash
openclaw skills install ./inspiration-weaver --as inspiration-weaver
```

Windows PowerShell：

```powershell
openclaw skills install .\inspiration-weaver --as inspiration-weaver
```

全局安装时加 `--global`：

```bash
openclaw skills install git:gccola/inspiration-weaver@main --global
```

验证：

```bash
openclaw skills list --verbose
openclaw skills info inspiration-weaver
openclaw skills check
```

常见安装位置：

- 当前 workspace：`~/.openclaw/workspace/skills/inspiration-weaver`
- 全局：`~/.openclaw/skills/inspiration-weaver`

如果自定义过 workspace，必须使用 `openclaw skills info inspiration-weaver` 显示的实际路径。后文记为 `SKILL_DIR`。

Git 和本地目录安装不走 `openclaw skills update` 的托管更新；更新时重新安装并处理覆盖提示。

---

## 三、安装 Hook

Hook 源码：

```text
<SKILL_DIR>/assets/openclaw-inbox-hook
```

managed hook 默认目录：

```text
~/.openclaw/hooks/inspiration-inbox-capture
```

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

不要用 `config.example.json` 覆盖已有的 `config.json`，否则会丢失之前确认过的来源白名单和收件箱路径。

Hook 是复制到 managed hooks 目录的独立副本。更新 Skill 中的 Hook 源码后，需要重新复制并重启 Gateway。

安装前审阅 `handler.js` 和 `HOOK.md`。这是本地运行的代码，只应安装已审阅的版本。

---

## 四、配置触发标记和来源

编辑：

```text
~/.openclaw/hooks/inspiration-inbox-capture/config.json
```

默认模板：

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

规则：

- 任意消息行以 `~` 开头时捕获，例如 `~今天做了一个梦`。
- `~` 前允许空格；保存前会移除该前缀。
- `10~20` 或句子中间的 `~` 不会触发。
- `triggerTags` 默认空数组。若仍想兼容 `#灵感`，可填 `["#灵感"]`。
- `allowedChannelIds` / `allowedConversationIds` 指定可捕获的普通消息来源；只有 `captureAllowedSourcesWithoutTag` 为 `true` 时生效。
- 带 `~` 的消息可以绕过频道/会话白名单，因此公开群不要随意使用该标记。
- `allowedSenderIds` 对所有捕获路径生效。群聊中必须配置，且不要误排除自己的发送者 ID。
- `inboxPath` 留空时使用 `~/.openclaw/workspace/memory/inspiration/inbox.jsonl`。如果改成绝对路径，Python 命令必须使用同一路径。

查找渠道、会话或发送者 ID：

```bash
openclaw channels list
openclaw channels resolve --channel <provider> "<name-or-target>"
```

不同渠道的参数和 target 格式不同。不要猜 ID；也可以先发送一条真实测试消息，再从实际写入的 JSONL 记录中确认 `channel_id`、`conversation_id` 和 `sender_id`。

---

## 五、启用 Hook

检查发现和状态：

```bash
openclaw hooks list --verbose
openclaw hooks info inspiration-inbox-capture
```

启用：

```bash
openclaw hooks enable inspiration-inbox-capture
```

Hook 代码和元数据不会被自动监视；复制、修改 Hook 或配置后重启 Gateway：

```bash
openclaw gateway restart
openclaw hooks check
```

`hooks check` 只验证注册和可用性，不验证实际写入。必须发送真实测试消息：

```text
~今天我做了一个梦，梦见一棵树
```

然后检查：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" stats
python "<SKILL_DIR>/scripts/inspiration_inbox.py" list --pending
```

看到真实记录才说明捕获链路可用。

---

## 六、创建每日自动化任务

每日任务提示词位于：

```text
<SKILL_DIR>/assets/openclaw-daily-prompt.md
```

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

说明：

- `30 22 * * *` 是每天 22:30，可以调整。
- `--session isolated` 让任务独立执行，不依赖创建时的聊天上下文。
- `--announce` 要求把最终成稿投递到指定会话。
- `--channel` 和 `--to` 必须是用户确认、能接收私密成稿的目标，且必须与已连接渠道匹配。
- 任务保存的是创建时的提示词副本。修改资产文件后不会自动更新任务；需要执行：

```bash
openclaw automations edit <jobId> --message "<NEW_PROMPT>"
```

查看任务：

```bash
openclaw automations list --all
openclaw automations show <jobId>
```

立即手动运行：

```bash
openclaw automations run <jobId> --wait
openclaw automations runs <jobId> --limit 20
```

其他管理命令：

```bash
openclaw automations status
openclaw automations enable <jobId>
openclaw automations remove <jobId>
```

---

## 七、任务如何保护和推进素材

提示词会要求任务：

1. 用 `recover --older-than-hours 12` 释放超时批次。
2. 用 `export --through today --format markdown` 领取截至今天的全部积压素材。
3. 从输出读取 `batch_id` 和 `count`；无素材时只回复 `NO_REPLY`。
4. 按 Skill 规则写成完整文章、短章、梦境解读或故事。
5. 成功后执行 `mark --status compiled`；失败时执行 `release`。

相关命令：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" export --through today --format markdown
python "<SKILL_DIR>/scripts/inspiration_inbox.py" mark --batch "<BATCH_ID>" --status compiled
python "<SKILL_DIR>/scripts/inspiration_inbox.py" release --batch "<BATCH_ID>" --note "daily compilation failed"
python "<SKILL_DIR>/scripts/inspiration_inbox.py" recover --older-than-hours 12
```

`export --through today` 不只领取当天，也会补上之前漏掉或失败后释放的积压素材。批次完成前不会误标为 `compiled`；生成失败必须释放，避免永久卡在 `processing`。

---

## 八、端到端验收

按以下顺序做一次完整测试：

1. 发送一条真实的 `~` 消息。
2. 运行 `list --pending`，确认收件箱有记录。
3. 运行 `openclaw automations run <jobId> --wait`。
4. 确认私密会话收到成稿。
5. 运行 `stats`，确认批次状态变为 `compiled`。
6. 检查 `openclaw automations runs <jobId> --limit 20` 没有执行或投递错误。
7. 等到下一次计划时间，确认定时调度本身正常。

自动化任务和 Hook 必须在同一台 Gateway 主机；如果使用远程 Gateway，请在该主机执行安装和文件操作。

---

## 九、排障

### 命令或 Gateway

```bash
openclaw status
openclaw gateway status
openclaw gateway restart
openclaw logs --follow
openclaw doctor
```

### Skill

```bash
openclaw skills list --verbose
openclaw skills info inspiration-weaver
openclaw skills check
```

检查 `SKILL.md` 是否存在、安装目录是否为当前 workspace，以及是否误装到了 `~/.codex/skills`。

### Hook

```bash
openclaw hooks list --verbose
openclaw hooks info inspiration-inbox-capture
openclaw hooks check
```

如果消息没有入库，检查：

- Hook 是否已 `enable`。
- 复制或修改后是否重启过 Gateway。
- 消息是否真的经过当前 Gateway。
- `~` 是否在行首，或来源 ID 是否已配置。
- `allowedSenderIds` 是否排除了发送者。
- Hook 和 Python 是否指向同一个 `inboxPath`。
- 消息是否因斜杠命令、疑似密钥、空文本或超长文本被跳过。

### 自动化

```bash
openclaw automations status
openclaw automations list --all
openclaw automations show <jobId>
openclaw automations runs <jobId> --limit 20
openclaw logs --follow
openclaw doctor
```

检查 Gateway 是否常驻、任务是否启用、时区是否正确，以及投递渠道是否可用。

批次卡住时：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" recover --older-than-hours 1
```

---

## 十、隐私与安全

- 默认只用 `~` 触发，不要捕获所有私聊。
- 专用来源必须明确授权；群聊必须配置 `allowedSenderIds`。
- 带 `~` 的消息仍可能绕过来源白名单，不要公开群中随意使用。
- Hook 只在本地追加 JSONL，不主动回复，不读取历史。
- 敏感信息检测只是启发式规则，不能替代权限隔离。
- 不要在素材中发送密码、密钥、身份证件或他人的隐私资料。
- 外部查证使用最小必要查询，不要把私密原文转发到第三方服务。
- 成稿只发送到用户确认的私密渠道。
- 在真实测试成功前，不要宣称自动捕获或定时任务已经上线。

## 官方资料

- [OpenClaw Getting started](https://docs.openclaw.ai/start/getting-started)
- [OpenClaw Install](https://docs.openclaw.ai/install)
- [Skills CLI](https://docs.openclaw.ai/cli/skills)
- [Hooks CLI](https://docs.openclaw.ai/cli/hooks)
- [Hooks configuration](https://docs.openclaw.ai/automation/hooks/configuration)
- [Automation jobs](https://docs.openclaw.ai/automation/cron-jobs/managing-jobs)
- [Channels CLI](https://docs.openclaw.ai/cli/channels)