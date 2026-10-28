import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const HOOK_DIR = path.dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = path.join(HOOK_DIR, "config.json");
const DEFAULT_INBOX = path.join(
  os.homedir(),
  ".openclaw",
  "workspace",
  "memory",
  "inspiration",
  "inbox.jsonl",
);
const DEFAULT_CONFIG = {
  triggerPrefixes: ["~"],
  triggerTags: [],
  allowedChannelIds: [],
  allowedConversationIds: [],
  allowedSenderIds: [],
  captureAllowedSourcesWithoutTag: true,
  inboxPath: "",
  maxTextLength: 50000,
};
const SENSITIVE_TEXT =
  /(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S{8,}|\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b)/i;
const COMMAND_TEXT = /^\/[a-zA-Z0-9_-]+(?:\s|$)/;

function expandHome(value) {
  if (value === "~") return os.homedir();
  if (value.startsWith("~/") || value.startsWith("~\\")) {
    return path.join(os.homedir(), value.slice(2));
  }
  return value;
}

function stringArray(value, field) {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error(`${field} must be an array of strings`);
  }
  return value.map((item) => item.trim()).filter(Boolean);
}

async function loadConfig() {
  let loaded = {};
  try {
    const raw = await fs.readFile(CONFIG_PATH, "utf8");
    loaded = JSON.parse(raw.replace(/^\uFEFF/, ""));
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw new Error(`cannot read config.json: ${error.message}`);
    }
  }
  if (!loaded || typeof loaded !== "object" || Array.isArray(loaded)) {
    throw new Error("config.json must contain a JSON object");
  }

  const config = {
    ...DEFAULT_CONFIG,
    ...loaded,
    triggerPrefixes: stringArray(
      loaded.triggerPrefixes ?? DEFAULT_CONFIG.triggerPrefixes,
      "triggerPrefixes",
    ),
    triggerTags: stringArray(loaded.triggerTags ?? DEFAULT_CONFIG.triggerTags, "triggerTags"),
    allowedChannelIds: stringArray(
      loaded.allowedChannelIds ?? DEFAULT_CONFIG.allowedChannelIds,
      "allowedChannelIds",
    ),
    allowedConversationIds: stringArray(
      loaded.allowedConversationIds ?? DEFAULT_CONFIG.allowedConversationIds,
      "allowedConversationIds",
    ),
    allowedSenderIds: stringArray(
      loaded.allowedSenderIds ?? DEFAULT_CONFIG.allowedSenderIds,
      "allowedSenderIds",
    ),
  };
  if (typeof config.captureAllowedSourcesWithoutTag !== "boolean") {
    throw new Error("captureAllowedSourcesWithoutTag must be a boolean");
  }
  if (typeof config.inboxPath !== "string") {
    throw new Error("inboxPath must be a string");
  }
  if (!Number.isInteger(config.maxTextLength) || config.maxTextLength < 1) {
    throw new Error("maxTextLength must be a positive integer");
  }
  config.inboxPath = expandHome(
    config.inboxPath.trim() ||
      process.env.INSPIRATION_INBOX ||
      DEFAULT_INBOX,
  );
  return config;
}

function eventDate(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
  if (typeof value === "number") {
    const milliseconds = value < 1e12 ? value * 1000 : value;
    const parsed = new Date(milliseconds);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  return new Date();
}

function isoUtc(value) {
  return value
    .toISOString()
    .replace(/\.\d{3}Z$/, "Z");
}

function stringValue(value) {
  return value === undefined || value === null ? "" : String(value);
}

function stableMessageId(context, capturedAt, text) {
  const sourceMessageId = stringValue(context.messageId);
  const seed = sourceMessageId
    ? [
        sourceMessageId,
        stringValue(context.channelId),
        stringValue(context.conversationId),
        stringValue(context.metadata?.senderId ?? context.from),
      ].join("\x1f")
    : [
        stringValue(context.channelId),
        stringValue(context.conversationId),
        stringValue(context.metadata?.senderId ?? context.from),
        capturedAt,
        text,
      ].join("\x1f");
  return `msg_${createHash("sha256").update(seed, "utf8").digest("hex").slice(0, 24)}`;
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function acquireLock(lockPath, timeoutMs) {
  await fs.mkdir(path.dirname(lockPath), { recursive: true });
  const token = `${process.pid} ${Date.now()} ${randomUUID()}`;
  const deadline = Date.now() + timeoutMs;
  while (true) {
    try {
      const handle = await fs.open(lockPath, "wx", 0o600);
      try {
        await handle.writeFile(token, "utf8");
      } finally {
        await handle.close();
      }
      return async () => {
        try {
          const current = await fs.readFile(lockPath, "utf8");
          if (current === token) await fs.rm(lockPath, { force: true });
        } catch (error) {
          if (error?.code !== "ENOENT") throw error;
        }
      };
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      try {
        const stat = await fs.stat(lockPath);
        if (Date.now() - stat.mtimeMs > 60000) {
          await fs.rm(lockPath, { force: true });
          continue;
        }
      } catch (statError) {
        if (statError?.code === "ENOENT") continue;
        throw statError;
      }
      if (Date.now() >= deadline) throw new Error(`lock timeout: ${lockPath}`);
      await sleep(50);
    }
  }
}

async function hasMessageId(inboxPath, messageId) {
  try {
    const input = createReadStream(inboxPath, { encoding: "utf8" });
    const lines = createInterface({ input, crlfDelay: Infinity });
    for await (const line of lines) {
      if (!line.trim()) continue;
      try {
        const record = JSON.parse(line);
        if (record?.kind === "message" && record?.id === messageId) return true;
      } catch {
        // A damaged line must not block capture of new material.
      }
    }
    return false;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function appendRecord(inboxPath, record) {
  await fs.mkdir(path.dirname(inboxPath), { recursive: true });
  const handle = await fs.open(inboxPath, "a", 0o600);
  try {
    await handle.writeFile(`${JSON.stringify(record)}\n`, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
}

function matchedTags(text, triggerTags) {
  const lowered = text.toLocaleLowerCase();
  return triggerTags
    .filter((tag) => lowered.includes(tag.toLocaleLowerCase()))
    .map((tag) => tag.replace(/^#+/, "").trim())
    .filter(Boolean);
}

function matchedPrefixes(text, triggerPrefixes) {
  const lines = text.split(/\r?\n/);
  return triggerPrefixes.filter((prefix) =>
    lines.some((line) => line.trimStart().startsWith(prefix)),
  );
}

function stripTriggerPrefixes(text, triggerPrefixes) {
  return text
    .split(/\r?\n/)
    .map((line) => {
      const indent = line.match(/^\s*/)?.[0] ?? "";
      const body = line.slice(indent.length);
      const prefix = triggerPrefixes.find((item) => body.startsWith(item));
      if (!prefix) return line;
      return indent + body.slice(prefix.length).replace(/^[ \t]+/, "");
    })
    .join("\n");
}

function isAllowedSource(context, config) {
  const channelId = stringValue(context.channelId);
  const conversationId = stringValue(context.conversationId);
  return (
    (channelId && config.allowedChannelIds.includes(channelId)) ||
    (conversationId && config.allowedConversationIds.includes(conversationId))
  );
}

function isAllowedSender(context, config) {
  if (config.allowedSenderIds.length === 0) return true;
  const senderId = stringValue(context.metadata?.senderId ?? context.from);
  return Boolean(senderId) && config.allowedSenderIds.includes(senderId);
}

export default async function handler(event) {
  try {
    if (event?.type !== "message" || event?.action !== "received") return;
    const context = event.context ?? {};
    const text = stringValue(context.content ?? context.body).trim();
    if (!text || COMMAND_TEXT.test(text)) return;

    const config = await loadConfig();
    if (text.length > config.maxTextLength) {
      console.error(`[inspiration-inbox] skipped oversized message (${text.length} chars)`);
      return;
    }
    if (SENSITIVE_TEXT.test(text)) {
      console.error("[inspiration-inbox] skipped message that looks sensitive");
      return;
    }
    if (!isAllowedSender(context, config)) return;

    const tags = matchedTags(text, config.triggerTags);
    const prefixes = matchedPrefixes(text, config.triggerPrefixes);
    const sourceAllowed =
      config.captureAllowedSourcesWithoutTag && isAllowedSource(context, config);
    if (tags.length === 0 && prefixes.length === 0 && !sourceAllowed) return;

    const storedText = stripTriggerPrefixes(text, config.triggerPrefixes).trim();
    if (!storedText) return;

    const capturedAt = isoUtc(eventDate(context.timestamp ?? event.timestamp));
    const messageId = stableMessageId(context, capturedAt, text);
    const inboxPath = path.resolve(config.inboxPath);
    const release = await acquireLock(`${inboxPath}.lock`, 5000);
    try {
      if (await hasMessageId(inboxPath, messageId)) return;
      const metadata = context.metadata ?? {};
      const record = {
        schema_version: 1,
        kind: "message",
        id: messageId,
        captured_at: capturedAt,
        text: storedText,
        channel_id: context.channelId ?? null,
        account_id: context.accountId ?? null,
        conversation_id: context.conversationId ?? null,
        sender_id: metadata.senderId ?? context.from ?? null,
        sender_name: metadata.senderName ?? null,
        source_message_id: context.messageId ?? null,
        tags: [...new Set(tags.length ? tags : ["灵感"])],
        metadata: {
          provider: metadata.provider ?? null,
          surface: metadata.surface ?? null,
          channel_name: metadata.channelName ?? null,
          topic_name: metadata.topicName ?? null,
          thread_id: metadata.threadId ?? null,
          guild_id: metadata.guildId ?? null,
          sender_username: metadata.senderUsername ?? null,
        },
      };
      await appendRecord(inboxPath, record);
      console.log(`[inspiration-inbox] captured ${messageId}`);
    } finally {
      await release();
    }
  } catch (error) {
    console.error(`[inspiration-inbox] capture failed: ${error?.message ?? error}`);
  }
}
