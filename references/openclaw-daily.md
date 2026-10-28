# OpenClaw 每日自动收集与整理

这条流程分两层：

1. **Hook 捕获**：OpenClaw 每收到一条消息，只把明确授权来源或带行首触发前缀的文字追加到本地 JSONL 收件箱。
2. **每日定时任务**：领取收件箱批次，按 `inspiration-weaver` 的规则写成完整文字，成功后标记为 `compiled`。

OpenClaw 与 Codex 的技能目录彼此独立。把本 skill 放进 `~/.codex/skills` 不会自动让 OpenClaw 看到；需要在 OpenClaw 所在主机单独安装 skill、Hook 和定时任务。

## 前置条件

- OpenClaw Gateway 已安装并保持运行。
- OpenClaw 所在主机可运行 Python 3.10+ 和 Node.js。
- 用户已确认要收集的专用会话/频道，以及每日成稿的发送目标。
- 不要把“收集所有私聊”作为默认配置；默认只用行首 `~` 标记，或用户明确指定的来源。

## 一、安装 skill

把整个 `inspiration-weaver` 目录放到 OpenClaw 可访问的主机，然后执行：

```bash
openclaw skills install "<inspiration-weaver 的绝对路径>"
```

只为当前工作区安装时省略额外参数；让本机所有 agent 可见时加 `--global`：

```bash
openclaw skills install "<inspiration-weaver 的绝对路径>" --global
```

常见安装位置：

- 工作区安装：`~/.openclaw/workspace/skills/inspiration-weaver`
- 全局安装：`~/.openclaw/skills/inspiration-weaver`

实际路径以 OpenClaw 的安装结果为准。后文把这个目录记为 `SKILL_DIR`。

## 二、安装 Hook

Hook 位于：

```text
<SKILL_DIR>/assets/openclaw-inbox-hook
```

在 Windows PowerShell 中，可复制到 OpenClaw 的 managed hook 目录：

```powershell
$skillDir = Join-Path $HOME ".openclaw\workspace\skills\inspiration-weaver"
$hookSource = Join-Path $skillDir "assets\openclaw-inbox-hook"
$hookTarget = Join-Path $HOME ".openclaw\hooks\inspiration-inbox-capture"

New-Item -ItemType Directory -Force -Path $hookTarget | Out-Null
Copy-Item -Path (Join-Path $hookSource "*") -Destination $hookTarget -Recurse -Force
Copy-Item -Path (Join-Path $hookTarget "config.example.json") -Destination (Join-Path $hookTarget "config.json") -Force
```

Linux/macOS 对应做法：

```bash
mkdir -p ~/.openclaw/hooks/inspiration-inbox-capture
cp -R "$SKILL_DIR/assets/openclaw-inbox-hook/." ~/.openclaw/hooks/inspiration-inbox-capture/
cp ~/.openclaw/hooks/inspiration-inbox-capture/config.example.json \
  ~/.openclaw/hooks/inspiration-inbox-capture/config.json
```

安装前先检查 `handler.js` 和 `HOOK.md`。这是本地运行的代码，只应安装自己审阅过的版本。

### 配置来源

编辑 Hook 目录中的 `config.json`。默认模板：

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

> 已部署旧版 Hook 的用户：必须编辑现有 `config.json`，加入 `"triggerPrefixes": ["~"]`，并清空默认 `"triggerTags"`，然后重启 Gateway。只更新 skill 目录不会修改 Hook 的 `config.json`。

规则：

- 消息中任意一行以 `~` 开头时会进入收件箱；`~` 前允许空格，写入收件箱前会移除该前缀。`10~20` 这类普通范围不会触发。
- `triggerTags` 是可选的子串匹配兼容项，例如仍想接受 `#灵感` 时填写 `["#灵感"]`；若只使用 `~`，保持空数组。
- `allowedChannelIds` / `allowedConversationIds` 中的来源，可以在没有 `~` 时也被捕获；只有 `captureAllowedSourcesWithoutTag` 为 `true` 时生效。
- 群聊或多人频道建议同时填写 `allowedSenderIds`。该列表非空时，即使消息带 `~` 或可选标签，也只捕获列表中发送者的消息。
- 不要猜频道 ID、会话 ID 或发送者 ID；从 OpenClaw 的现有频道配置或实际事件中确认。
- `inboxPath` 留空时使用 `~/.openclaw/workspace/memory/inspiration/inbox.jsonl`。如果改成绝对路径，Python 命令必须使用同一个路径。
- Hook 只处理启用之后 OpenClaw 实际接收并派发的消息，不能读取完整历史聊天记录。

### 启用并验证

```bash
openclaw hooks info inspiration-inbox-capture
openclaw hooks enable inspiration-inbox-capture
```

用本机 OpenClaw 服务管理器重启 Gateway；Hook 文件和元数据修改后不会被自动监视。重启后执行：

```bash
openclaw hooks check
```

然后实际发送一条测试消息：

```text
~今天我做了一个梦，梦见一棵树
```

如果测试的是已授权的专用会话，也可以发送不带 `~` 的消息。检查收件箱：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" list --pending
```

在真实测试记录出现之前，不要宣称自动收集已经生效。

## 三、创建每日任务

先读取并复制：

```text
<SKILL_DIR>/assets/openclaw-daily-prompt.md
```

把其中所有 `<SKILL_DIR>` 替换为实际绝对路径。这个提示词会要求定时 agent：

1. 先用 `recover` 释放超时批次。
2. 再用 `export --through today --format markdown` 领取截至今天的全部积压素材。
3. 根据 `batch_id` 判断是否有内容；为空时只回复 `NO_REPLY`。
4. 写成完整文章、短章、梦境解读或故事。
5. 成功后执行 `mark --status compiled`；失败时执行 `release`。

在 PowerShell 中可以这样创建任务：

```powershell
$skillDir = Join-Path $HOME ".openclaw\workspace\skills\inspiration-weaver"
$prompt = (Get-Content -Raw -Encoding UTF8 (Join-Path $skillDir "assets\openclaw-daily-prompt.md")).Replace("<SKILL_DIR>", $skillDir)

openclaw automations create "30 22 * * *" $prompt `
  --name "每日灵感编织" `
  --tz "Asia/Shanghai" `
  --session isolated `
  --announce `
  --channel "<用户确认的渠道>" `
  --to "<用户确认的私有目标>"
```

说明：

- `30 22 * * *` 表示每天 22:30，按 `--tz` 指定的时区运行；可以改成用户习惯的时间。
- `--session isolated` 让任务在没有聊天历史的情况下按提示词独立执行。最终回复必须直接是交付物。
- `--channel` 和 `--to` 必须由用户确认，且应优先使用私聊或只有用户自己的频道。不同渠道的 target 格式不同，按本机 OpenClaw 文档填写。
- 任务保存的是创建时的提示词副本；以后修改资产文件不会自动更新任务，需要 `openclaw automations edit <jobId> --message "..."`。
- Gateway 必须常驻，否则到点不会执行。

## 四、每日任务如何保护和推进素材

- 收件箱为空时返回 `NO_REPLY`，OpenClaw 会把它视为有意的静默，不发送空总结。
- 处理中的批次如果因为崩溃而卡住，下一次任务会先运行 `recover --older-than-hours 12`。
- `export --through today` 不只处理今天，还会补上之前漏掉或失败后释放的积压素材。
- 成稿失败时必须 `release`；不能把未完成的批次误标为 `compiled`。
- 生成时可以做必要的外部事实查证，但不要把私密原文复制到额外的第三方搜索、群聊或转发服务。查不到就保留不确定性。
- 素材中的 `#故事` 和 `#解梦` 可作为体裁提示；没有提示时默认整合成有标题的完整短篇或一组短章。

## 五、隐私边界

- 默认不要捕获全部私聊、全部群聊或所有频道。
- 专用来源必须明确授权；群聊还应配置 `allowedSenderIds`。
- 带 `~` 或可选标签的消息仍可能来自未列入白名单的来源，因此公开群里不要使用这些标记或标签，除非接受它被收集。
- Hook 只是本地记录，不会主动回复消息，也不会读取历史记录。
- 敏感信息过滤只是启发式保护，不能替代权限隔离；不要在灵感消息里发送密码、密钥或他人的隐私资料。
- 发送成稿的目标必须是用户确认的私密位置，不能默认发到群聊或公开频道。

## 六、排障

检查收件箱状态：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" stats
python "<SKILL_DIR>/scripts/inspiration_inbox.py" list --pending
```

收件箱有内容但 Hook 没有新增记录时，依次检查：

1. `openclaw hooks check` 是否通过，Hook 是否已启用。
2. 修改 `handler.js` 或 `HOOK.md` 后是否重启了 Gateway。
3. `config.json` 的频道/会话/发送者 ID 是否正确。
4. 消息是否被斜杠命令、疑似密钥或超长文本规则跳过。
5. Hook 和 Python 是否指向同一个 `inboxPath`。

定时任务不执行时，检查 Gateway 是否运行、任务是否启用、时区是否正确，以及任务发送目标是否有效。批次长期停在 `processing` 时，可手动运行：

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" recover --older-than-hours 1
```

如果当前主机没有 `openclaw` 命令，只能先完成 skill 和资产制作，不能声称 Hook 或每日任务已经上线。