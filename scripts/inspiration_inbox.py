#!/usr/bin/env python3
"""Local inspiration inbox for message capture and daily compilation."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import secrets
import sys
import time
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
DEFAULT_TIMEZONE = os.environ.get("INSPIRATION_TIMEZONE", "Asia/Shanghai")
DEFAULT_INBOX = Path(
    os.environ.get(
        "INSPIRATION_INBOX",
        "~/.openclaw/workspace/memory/inspiration/inbox.jsonl",
    )
).expanduser()
VALID_STATUSES = {"new", "processing", "compiled", "skipped"}
FALLBACK_OFFSETS = {
    "Asia/Shanghai": timedelta(hours=8),
    "Asia/Taipei": timedelta(hours=8),
    "Asia/Hong_Kong": timedelta(hours=8),
    "Asia/Singapore": timedelta(hours=8),
    "UTC": timedelta(0),
}


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_timezone(name: str) -> tzinfo:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        if name in FALLBACK_OFFSETS:
            return timezone(FALLBACK_OFFSETS[name], name=name)
        local = datetime.now().astimezone().tzinfo
        if local and str(local) == name:
            return local
        raise SystemExit(
            f"无法识别时区 {name!r}；请安装 tzdata，或改用 --timezone Asia/Shanghai。"
        )


def parse_timestamp(value: str | None, default_tz: tzinfo) -> datetime:
    if not value:
        return utc_now()
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"时间戳 {value!r} 无效；请使用 ISO 8601 格式。") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone(timezone.utc)


def resolve_date_filter(value: str | None, tz: tzinfo) -> date | None:
    if not value:
        return None
    today = utc_now().astimezone(tz).date()
    lowered = value.strip().lower()
    if lowered == "today":
        return today
    if lowered == "yesterday":
        return today - timedelta(days=1)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit("--date 只接受 today、yesterday 或 YYYY-MM-DD。") from exc


def local_date(timestamp: str, tz: tzinfo) -> date:
    return parse_timestamp(timestamp, timezone.utc).astimezone(tz).date()


def in_date_range(timestamp: str, selected: date | None, tz: tzinfo) -> bool:
    return selected is None or local_date(timestamp, tz) == selected


def in_date_range_through(timestamp: str, through: date | None, tz: tzinfo) -> bool:
    return through is None or local_date(timestamp, tz) <= through


def make_message_id(args: argparse.Namespace, captured_at: str) -> str:
    if args.id:
        return str(args.id).strip()
    seed = "\x1f".join(
        [
            args.message_id or "",
            args.channel_id or "",
            args.conversation_id or "",
            args.sender_id or "",
            captured_at,
            args.text.strip(),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"msg_{digest}"


def new_batch_id(tz: tzinfo) -> str:
    stamp = utc_now().astimezone(tz).strftime("%Y%m%d-%H%M%S")
    return f"insp-{stamp}-{secrets.token_hex(3)}"


def split_tags(values: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        for item in value.split(","):
            tag = item.strip()
            if tag and tag not in seen:
                result.append(tag)
                seen.add(tag)
    return result


@contextlib.contextmanager
def inbox_lock(inbox_path: Path, timeout: float = 20.0) -> Iterator[None]:
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = inbox_path.with_name(inbox_path.name + ".lock")
    deadline = time.monotonic() + timeout
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, f"{os.getpid()} {time.time()}".encode("ascii"))
            os.close(descriptor)
            descriptor = -1
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > 60:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise SystemExit(f"等待收件箱锁超时：{lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if descriptor != -1:
            try:
                os.close(descriptor)
            except OSError:
                pass
        lock_path.unlink(missing_ok=True)


def read_records(inbox_path: Path) -> list[dict[str, Any]]:
    if not inbox_path.exists():
        return []
    records: list[dict[str, Any]] = []
    with inbox_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"收件箱第 {line_number} 行不是有效 JSON，已跳过。", file=sys.stderr)
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def append_records(inbox_path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )
    with inbox_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def fold_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    messages: dict[str, dict[str, Any]] = {}
    statuses: dict[str, dict[str, Any]] = {}
    for record in records:
        kind = record.get("kind")
        if kind == "message" and record.get("id"):
            messages.setdefault(str(record["id"]), record)
        elif kind == "status" and record.get("id"):
            statuses[str(record["id"])] = record
    folded: dict[str, dict[str, Any]] = {}
    for message_id, message in messages.items():
        item = dict(message)
        status = statuses.get(message_id)
        item["status"] = status.get("status", "new") if status else "new"
        item["batch_id"] = status.get("batch_id") if status else None
        item["status_at"] = status.get("at") if status else None
        item["status_note"] = status.get("note") if status else None
        folded[message_id] = item
    return folded


def add_message(args: argparse.Namespace) -> int:
    text = args.text.strip()
    if not text:
        raise SystemExit("--text 不能为空。")
    default_tz = resolve_timezone(args.timezone)
    captured = parse_timestamp(args.captured_at, default_tz)
    captured_at = iso_utc(captured)
    message_id = make_message_id(args, captured_at)
    if not message_id:
        raise SystemExit("--id 不能为空。")
    tags = split_tags(args.tag)
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "message",
        "id": message_id,
        "captured_at": captured_at,
        "text": text,
        "channel_id": args.channel_id,
        "account_id": args.account_id,
        "conversation_id": args.conversation_id,
        "sender_id": args.sender_id,
        "sender_name": args.sender_name,
        "source_message_id": args.message_id,
        "tags": tags,
    }
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as exc:
            raise SystemExit("--metadata 必须是有效 JSON 对象。") from exc
        if not isinstance(metadata, dict):
            raise SystemExit("--metadata 必须是 JSON 对象。")
        record["metadata"] = metadata
    with inbox_lock(args.inbox):
        folded = fold_records(read_records(args.inbox))
        if message_id in folded:
            print(f"消息已存在：{message_id}")
            return 0
        append_records(args.inbox, [record])
    print(f"已收录：{message_id}")
    return 0


def status_record(
    message_id: str,
    status: str,
    batch_id: str | None,
    note: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "status",
        "id": message_id,
        "status": status,
        "batch_id": batch_id,
        "at": iso_utc(utc_now()),
    }
    if note:
        record["note"] = note
    return record


def select_messages(
    args: argparse.Namespace,
    folded: dict[str, dict[str, Any]],
    tz: tzinfo,
) -> list[dict[str, Any]]:
    selected_date = resolve_date_filter(args.date, tz)
    through_date = resolve_date_filter(getattr(args, "through", None), tz)
    if args.batch:
        selected = [
            item
            for item in folded.values()
            if item.get("status") == "processing" and item.get("batch_id") == args.batch
        ]
    else:
        selected = [item for item in folded.values() if item.get("status") == "new"]
    if through_date is not None:
        selected = [
            item
            for item in selected
            if in_date_range_through(str(item.get("captured_at", "")), through_date, tz)
        ]
    else:
        selected = [
            item
            for item in selected
            if in_date_range(str(item.get("captured_at", "")), selected_date, tz)
        ]
    selected.sort(key=lambda item: str(item.get("captured_at", "")))
    return selected[: args.limit]


def render_markdown(
    messages: list[dict[str, Any]],
    batch_id: str | None,
    tz: tzinfo,
    selected_date: date | None,
    through_date: date | None = None,
) -> str:
    if not messages:
        return (
            '<!-- inspiration-inbox batch_id="" count="0" '
            f'date="{selected_date or ""}" through="{through_date or ""}" -->\n'
            "没有待整理的灵感消息。\n"
        )
    range_label = (
        f"截至 {through_date} 的全部待处理消息"
        if through_date
        else (selected_date or "全部待处理消息")
    )
    lines = [
        f'<!-- inspiration-inbox batch_id="{batch_id}" count="{len(messages)}" '
        f'date="{selected_date or ""}" through="{through_date or ""}" -->',
        f"# 灵感收件箱批次 {batch_id}",
        "",
        f"- 条数：{len(messages)}",
        f"- 时区：{tz}",
        f"- 消息范围：{range_label}",
        "",
    ]
    for index, message in enumerate(messages, 1):
        captured = parse_timestamp(str(message.get("captured_at")), timezone.utc)
        local = captured.astimezone(tz)
        source_parts = [
            str(message.get("channel_id") or "").strip(),
            str(message.get("conversation_id") or "").strip(),
        ]
        source = " / ".join(part for part in source_parts if part) or "未标注来源"
        tags = ", ".join(message.get("tags") or [])
        lines.extend(
            [
                f"## {index}. {local.isoformat(timespec='seconds')} · {source}",
                "",
                f"- 消息 ID：`{message.get('id')}`",
            ]
        )
        if message.get("source_message_id"):
            lines.append(f"- 来源消息 ID：`{message.get('source_message_id')}`")
        if tags:
            lines.append(f"- 标签：{tags}")
        lines.extend(["", str(message.get("text") or "").rstrip(), "", "---", ""])
    return "\n".join(lines)


def export_messages(args: argparse.Namespace) -> int:
    tz = resolve_timezone(args.timezone)
    selected_date = resolve_date_filter(args.date, tz)
    through_date = resolve_date_filter(args.through, tz)
    batch_id: str | None = None
    claimed: list[dict[str, Any]] = []
    with inbox_lock(args.inbox):
        folded = fold_records(read_records(args.inbox))
        if args.batch:
            claimed = select_messages(args, folded, tz)
            batch_id = args.batch if claimed else None
        else:
            candidates = [
                item
                for item in folded.values()
                if item.get("status") == "new"
                and (
                    in_date_range_through(str(item.get("captured_at", "")), through_date, tz)
                    if through_date is not None
                    else in_date_range(str(item.get("captured_at", "")), selected_date, tz)
                )
            ]
            candidates.sort(key=lambda item: str(item.get("captured_at", "")))
            candidates = candidates[: args.limit]
            if candidates:
                batch_id = new_batch_id(tz)
                claim_records = [
                    status_record(str(item["id"]), "processing", batch_id) for item in candidates
                ]
                append_records(args.inbox, claim_records)
                claimed = [
                    {**item, "status": "processing", "batch_id": batch_id}
                    for item in candidates
                ]
    if args.format == "json":
        payload = {
            "batch_id": batch_id,
            "count": len(claimed),
            "timezone": str(tz),
            "date": selected_date.isoformat() if selected_date else None,
            "through": through_date.isoformat() if through_date else None,
            "messages": claimed,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(claimed, batch_id, tz, selected_date, through_date))
    return 0


def list_messages(args: argparse.Namespace) -> int:
    tz = resolve_timezone(args.timezone)
    selected_date = resolve_date_filter(args.date, tz)
    with inbox_lock(args.inbox):
        folded = fold_records(read_records(args.inbox))
    items = list(folded.values())
    if args.pending:
        items = [item for item in items if item.get("status") in {"new", "processing"}]
    if args.status:
        items = [item for item in items if item.get("status") == args.status]
    items = [
        item
        for item in items
        if in_date_range(str(item.get("captured_at", "")), selected_date, tz)
    ]
    items.sort(key=lambda item: str(item.get("captured_at", "")))
    if args.format == "json":
        print(
            json.dumps(
                {
                    "count": len(items),
                    "timezone": str(tz),
                    "date": selected_date.isoformat() if selected_date else None,
                    "messages": items,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not items:
        print("没有符合条件的消息。")
        return 0
    for item in items:
        local = parse_timestamp(str(item["captured_at"]), timezone.utc).astimezone(tz)
        preview = str(item.get("text", "")).replace("\n", " ")[:120]
        print(
            f"[{item.get('status')}] {local.isoformat(timespec='minutes')} "
            f"{item.get('id')} {preview}"
        )
    return 0


def update_batch(args: argparse.Namespace, status: str) -> int:
    with inbox_lock(args.inbox):
        folded = fold_records(read_records(args.inbox))
        selected = [
            item
            for item in folded.values()
            if item.get("status") == "processing" and item.get("batch_id") == args.batch
        ]
        records = [
            status_record(str(item["id"]), status, args.batch, args.note) for item in selected
        ]
        append_records(args.inbox, records)
    print(f"{args.batch}: {len(selected)} 条消息已标记为 {status}。")
    return 0


def recover_stale(args: argparse.Namespace) -> int:
    cutoff = utc_now() - timedelta(hours=args.older_than_hours)
    recovered: list[dict[str, Any]] = []
    with inbox_lock(args.inbox):
        folded = fold_records(read_records(args.inbox))
        for item in folded.values():
            if item.get("status") != "processing" or not item.get("batch_id"):
                continue
            status_at = item.get("status_at")
            if not status_at:
                continue
            try:
                claimed_at = parse_timestamp(str(status_at), timezone.utc)
            except SystemExit:
                continue
            if claimed_at <= cutoff:
                recovered.append(item)
        records = [
            status_record(
                str(item["id"]),
                "new",
                str(item["batch_id"]),
                f"recovered after {args.older_than_hours:g}h processing timeout",
            )
            for item in recovered
        ]
        append_records(args.inbox, records)
    batches = sorted({str(item["batch_id"]) for item in recovered})
    print(f"已释放 {len(recovered)} 条超时消息，涉及 {len(batches)} 个批次。")
    for batch_id in batches:
        print(batch_id)
    return 0


def show_stats(args: argparse.Namespace) -> int:
    tz = resolve_timezone(args.timezone)
    with inbox_lock(args.inbox):
        folded = fold_records(read_records(args.inbox))
    counts: dict[str, int] = {status: 0 for status in VALID_STATUSES}
    by_date: dict[str, int] = {}
    for item in folded.values():
        status = str(item.get("status", "new"))
        counts[status] = counts.get(status, 0) + 1
        day = local_date(str(item.get("captured_at", "")), tz).isoformat()
        by_date[day] = by_date.get(day, 0) + 1
    print(
        json.dumps(
            {
                "inbox": str(args.inbox),
                "total": len(folded),
                "statuses": counts,
                "by_local_date": dict(sorted(by_date.items())),
                "timezone": str(tz),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--inbox",
        type=Path,
        default=DEFAULT_INBOX,
        help=f"JSONL 收件箱路径（默认：{DEFAULT_INBOX}）。",
    )
    common.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"IANA 时区（默认：{DEFAULT_TIMEZONE}）。",
    )

    parser = argparse.ArgumentParser(description="收集零散灵感，并按批次交付给写作流程。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", parents=[common], help="追加一条灵感消息。")
    add.add_argument("--text", required=True)
    add.add_argument("--id")
    add.add_argument("--captured-at")
    add.add_argument("--channel-id")
    add.add_argument("--account-id")
    add.add_argument("--conversation-id")
    add.add_argument("--sender-id")
    add.add_argument("--sender-name")
    add.add_argument("--message-id")
    add.add_argument("--tag", action="append", help="可重复传入；也支持逗号分隔。")
    add.add_argument("--metadata", help="附加 JSON 对象。")
    add.set_defaults(func=add_message)

    export = subparsers.add_parser(
        "export",
        parents=[common],
        help="领取待处理消息，并原子标记为 processing。",
    )
    export.add_argument("--batch", help="重新输出一个已有的 processing 批次。")
    date_filter = export.add_mutually_exclusive_group()
    date_filter.add_argument(
        "--date",
        help="today、yesterday 或 YYYY-MM-DD；只领取该本地日期的消息。",
    )
    date_filter.add_argument(
        "--through",
        help="today、yesterday 或 YYYY-MM-DD；领取截至该本地日期的全部待处理消息。",
    )
    export.add_argument("--limit", type=int, default=500)
    export.add_argument("--format", choices=["markdown", "json"], default="markdown")
    export.set_defaults(func=export_messages)

    listing = subparsers.add_parser("list", parents=[common], help="查询消息。")
    listing.add_argument("--pending", action="store_true")
    listing.add_argument("--status", choices=sorted(VALID_STATUSES))
    listing.add_argument("--date", help="today、yesterday 或 YYYY-MM-DD。")
    listing.add_argument("--format", choices=["markdown", "json"], default="markdown")
    listing.set_defaults(func=list_messages)

    compiled = subparsers.add_parser("mark", parents=[common], help="标记批次状态。")
    compiled.add_argument("--batch", required=True)
    compiled.add_argument(
        "--status",
        choices=["compiled", "skipped", "new"],
        default="compiled",
    )
    compiled.add_argument("--note")
    compiled.set_defaults(func=lambda args: update_batch(args, args.status))

    release = subparsers.add_parser("release", parents=[common], help="生成失败时释放批次。")
    release.add_argument("--batch", required=True)
    release.add_argument("--note", default="generation failed")
    release.set_defaults(func=lambda args: update_batch(args, "new"))

    recover = subparsers.add_parser(
        "recover",
        parents=[common],
        help="把长时间停留在 processing 的批次释放回 new。",
    )
    recover.add_argument("--older-than-hours", type=float, default=12.0)
    recover.set_defaults(func=recover_stale)

    stats = subparsers.add_parser("stats", parents=[common], help="查看收件箱统计。")
    stats.set_defaults(func=show_stats)

    return parser


def main() -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    args.inbox = args.inbox.expanduser()
    if getattr(args, "limit", 1) < 1:
        parser.error("--limit 必须大于 0。")
    if getattr(args, "older_than_hours", 1.0) <= 0:
        parser.error("--older-than-hours 必须大于 0。")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
