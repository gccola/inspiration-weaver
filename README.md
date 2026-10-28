# 灵感编织器 · inspiration-weaver

把零散的想法、梦境、情绪片段、金句和未完成草稿，整理成保留个人声音的完整句段、文章或故事。

这是一个 Codex skill，也可以配合 OpenClaw Hook 自动收集一天中陆续发来的灵感消息，再由定时任务统一整理成稿。

## 能做什么

- **补全句段**：把一句没写完的话补成 1—3 段自然文字。
- **文章优化**：保留原意和个人语域，处理逻辑、结构、节奏与表达。
- **每日灵感整合**：找出一天碎片中反复出现的意象、情绪和问题，写成短文或短章。
- **梦境解读**：围绕梦中的画面、动作和情绪做克制的可能性解读，不套固定解梦词典，不做临床诊断。
- **故事创作**：以灵感为种子，补出角色欲望、阻力、转折和余韵。
- **必要查证**：只补充会影响成稿的外部事实；无法核实时保留不确定性。

核心边界是：不凭空编造用户经历、人物关系、诊断、引文或来源。

## 快速开始

### 1. 安装到 Codex

```bash
git clone https://github.com/gccola/inspiration-weaver.git \
  "$HOME/.codex/skills/inspiration-weaver"
```

Windows PowerShell：

```powershell
git clone https://github.com/gccola/inspiration-weaver.git `
  "$HOME\.codex\skills\inspiration-weaver"
```

重新打开或刷新 Codex 后，skill 会被发现。也可以显式调用：

```text
使用 $inspiration-weaver，把下面的碎片整理成一篇短文：……
```

### 2. 直接提供碎片

最简单的用法就是把当天的原话发进来，不需要先整理：

```text
使用 $inspiration-weaver。

~今天我做了一个梦，梦见一棵树。
~树叶一直不动，像在等我先开口。
~醒来以后我想起小时候院子里那棵树。

请把这些整理成一篇有标题的短文，保留我原来的语气。
```

也可以单独提出需求：

```text
用 $inspiration-weaver 解读这个梦，再写一个可选的梦境散文版本：
我梦见自己走进一片没有边界的空地，中央只有一棵树。
```

```text
用 $inspiration-weaver 优化下面这篇文章。保留我的观点和第一人称，不要改成公众号腔：
……
```

## 自动收集一天的灵感

自动收集属于 **OpenClaw 扩展能力**，不是 Codex skill 自带的后台服务。只把仓库放进 `~/.codex/skills` 不会开启自动收集。

工作方式是：

1. OpenClaw Hook 在收到授权消息时，把内容追加到本地 JSONL 收件箱。
2. OpenClaw 每日定时任务领取当天及之前未处理的素材。
3. 定时任务调用本 skill 的写作规则完成成稿，再把批次标记为已处理。

默认触发方式是**消息任意一行以 `~` 开头**：

```text
~今天我做了一个梦，梦见一棵树
```

写入收件箱前会移除 `~`。`10~20` 或句子中间的 `~` 不会触发。

默认配置：

```json
{
  "triggerPrefixes": ["~"],
  "triggerTags": []
}
```

`triggerTags` 是可选的兼容项。只有仍想接受 `#灵感` 这类旧标记时才需要填写。

完整安装步骤、频道白名单、发送者白名单、每日定时任务和排障说明见：

- [`references/openclaw-daily.md`](references/openclaw-daily.md)
- [`assets/openclaw-inbox-hook/HOOK.md`](assets/openclaw-inbox-hook/HOOK.md)
- [`assets/openclaw-daily-prompt.md`](assets/openclaw-daily-prompt.md)

### 自动收集的最低要求

- OpenClaw Gateway 已安装并保持运行。
- 已明确授权要收集的专用会话、频道或发送者。
- Hook 已安装、启用，并重启过 Gateway。
- 已用一条真实消息验证收件箱确实写入了记录。

Hook 只能观察启用之后经过 OpenClaw 的消息，不能回溯完整历史聊天记录。

## 隐私与安全

- 不要默认收集所有私聊、群聊或频道。
- 在公开群或多人群里使用触发标记前，先确认该消息可能被本地收件箱记录。
- 群聊建议配置 `allowedSenderIds`。
- `config.json`、`*.jsonl` 收件箱和锁文件已加入 `.gitignore`，避免私密内容误上传。
- 不要把密码、密钥、身份证件或他人的隐私资料作为灵感素材发送。
- 成稿应发送到用户确认的私密位置，不应默认发到群聊或公开频道。

## 使用模式

| 需求 | 推荐输入 | 默认交付 |
| --- | --- | --- |
| 补句 | 一句意象或未完成的话 | 1—3 段成稿 |
| 优化文章 | 完整或半完整草稿 | 修改后的全文 |
| 每日整合 | 一天中的多条碎片 | 有标题的短文或短章 |
| 解梦 | 梦境片段和醒来后的感受 | 梦的骨架、可能性解读、现实追问 |
| 故事 | 一个画面或设定 | 完整短篇或场景 |

更细的模式配方见 [`references/modes.md`](references/modes.md)，梦境和故事的结构见 [`references/dream-and-story.md`](references/dream-and-story.md)。

## 仓库结构

```text
inspiration-weaver/
├── SKILL.md                  # Codex skill 入口
├── agents/openai.yaml        # Codex 界面元数据
├── references/               # 模式、梦境/故事、OpenClaw 详细说明
├── assets/                   # 每日任务提示词与 OpenClaw Hook
├── scripts/                  # 本地收件箱读写工具
├── README.md
└── .gitignore
```

## 技术依赖

- **Codex**：使用核心写作能力。
- **Node.js**：仅在启用 OpenClaw Hook 时需要。
- **Python 3.10+**：仅在启用 OpenClaw 自动收集和本地收件箱工具时需要。

## 设计原则

1. 保留用户最有辨识度的原句、比喻和语气。
2. 补全缺口，不替用户发明经历。
3. 外部事实可以查证，私人感受不能代写。
4. 梦的解读使用概率语言，不做诊断。
5. 自动收集只在明确授权、可验证的情况下启用。