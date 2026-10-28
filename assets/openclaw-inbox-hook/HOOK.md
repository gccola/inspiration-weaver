---
name: inspiration-inbox-capture
description: "Capture authorized ~ inspiration messages into the inspiration-weaver local inbox"
metadata:
  { "openclaw": { "emoji": "🪶", "events": ["message:received"], "requires": { "bins": ["node"] } } }
---

# Inspiration inbox capture

Append authorized inbound messages to a local JSONL inbox for the
`inspiration-weaver` skill. This hook observes messages after OpenClaw accepts
them; it does not read an external chat archive and does not send replies.

## Default behavior

- Capture a message when a line starts with `~`, such as `~今天做了一个梦`.
- Remove the leading `~` marker before storing the text.
- Capture ordinary messages only from explicitly allowed channels or
  conversations when `captureAllowedSourcesWithoutTag` is `true`.
- Do not capture ordinary messages from other conversations.
- Optionally support substring tags such as `#灵感` through `triggerTags`.
  The default is empty, so `~` is the only message marker.
- Skip empty text, slash commands, attachment-only messages, oversized text, and
  text that looks like a credential or private key.
- Deduplicate by source message ID and channel/conversation/sender metadata.
- If writing fails, log the error and let the normal conversation continue.

## Install

Review `handler.js` before installing it. Copy this directory to OpenClaw's
managed hook directory, normally `~/.openclaw/hooks/inspiration-inbox-capture/`,
then create the local configuration:

```bash
cp config.example.json config.json
```

Copy the directory before starting or restarting the Gateway. The managed hook
directory is `<stateDir>/hooks/`; use the actual state directory when it has been
customized.

After copying and configuring, restart the Gateway because hook code and
metadata are not watched. Then inspect, enable, and validate the hook:

```bash
openclaw hooks info inspiration-inbox-capture
openclaw hooks enable inspiration-inbox-capture
openclaw hooks check
```

`hooks check` validates registration; it does not prove the handler wrote a
record. Send an authorized test message and verify the actual inbox file.

## Configuration

Copy `config.example.json` to `config.json` in this hook directory. Example:

```json
{
  "triggerPrefixes": ["~"],
  "triggerTags": [],
  "allowedChannelIds": ["YOUR_CHANNEL_ID"],
  "allowedConversationIds": [],
  "allowedSenderIds": ["YOUR_SENDER_ID"],
  "captureAllowedSourcesWithoutTag": true,
  "inboxPath": "",
  "maxTextLength": 50000
}
```

Rules:

- `triggerPrefixes` match only at the start of a line, after optional leading
  whitespace. This prevents ordinary ranges such as `10~20` from triggering
  capture.
- `triggerTags` is an optional substring list for users who also want tags such
  as `#灵感`. Keep it empty when `~` should be the only marker.
- `allowedChannelIds` and `allowedConversationIds` authorize untagged capture
  when `captureAllowedSourcesWithoutTag` is `true`.
- `allowedSenderIds` applies to every capture path. When non-empty, a prefixed
  or tagged message from any other sender is ignored. Set it for shared groups.
- Prefixed messages can be captured outside the allowed-source lists. Do not use
  the marker in public or shared spaces unless that is acceptable.
- Do not guess IDs. Obtain channel, conversation, and sender IDs from the actual
  OpenClaw configuration or event stream.
- Set `inboxPath` to an absolute path only when the Python inbox helper uses the
  same path. An empty value means:
  `~/.openclaw/workspace/memory/inspiration/inbox.jsonl`.
- Restart the Gateway after changing `handler.js`, `HOOK.md`, or loaded hook
  configuration when the deployment does not hot-reload it.

## Verify

Send a test message that starts with `~`, for example:

```text
~今天我做了一个梦，梦见一棵树
```

Then run:

```bash
python "<SKILL_DIR>/scripts/inspiration_inbox.py" list --pending
```

Do not treat automatic collection as active until this test succeeds. The hook
only sees messages received after it is enabled; it cannot backfill conversation
history.