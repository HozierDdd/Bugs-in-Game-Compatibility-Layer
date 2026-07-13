"""Record extraction and rendering for ProtonDB and issue tracker CRs."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from src.loaders.github_loader import iter_github_issues
from src.parsers.appid_extractor import extract_appid
from src.parsers.compatibility_report_classifier import classify_post
from src.utils.datetime_utils import from_unix_timestamp
from src.utils.json_io import load_json

from src.cr_characteristics_pipeline import config


_HTML_COMMENT_RE = re.compile(config.HTML_COMMENT_PATTERN, re.DOTALL)


@dataclass(frozen=True)
class CRRecord:
    """A single compatibility report ready for manual or LLM annotation."""

    record_id: str
    platform: str
    scope: str
    source_index: int
    app_id: str
    title: str
    created_at: str
    text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_manual_template_item(self) -> dict[str, Any]:
        item = self.to_dict()
        item[config.HUMAN_LABELS_FIELD] = {
            key: None for key in config.CHARACTERISTIC_KEYS
        }
        item[config.HUMAN_NOTES_FIELD] = ""
        return item


def record_from_template_item(item: dict[str, Any]) -> CRRecord:
    return CRRecord(
        record_id=str(item["record_id"]),
        platform=str(item["platform"]),
        scope=str(item.get("scope") or config.SCOPE_BY_PLATFORM[str(item["platform"])]),
        source_index=int(item.get("source_index") or 0),
        app_id=str(item.get("app_id") or ""),
        title=str(item.get("title") or ""),
        created_at=str(item.get("created_at") or ""),
        text=str(item.get("text") or ""),
        metadata=dict(item.get("metadata") or {}),
    )


def iter_records(platform: str) -> Iterable[CRRecord]:
    if platform == config.PLATFORM_PROTONDB:
        yield from iter_protondb_records()
        return
    if platform == config.PLATFORM_ISSUE_TRACKER:
        yield from iter_issue_tracker_records()
        return
    raise ValueError(f"Unknown platform: {platform}")


def load_records(platform: str) -> list[CRRecord]:
    return list(iter_records(platform))


def iter_all_records() -> Iterable[CRRecord]:
    for platform in config.PLATFORMS:
        yield from iter_records(platform)


def iter_protondb_records() -> Iterable[CRRecord]:
    raw_records = load_json(config.PROTONDB_INPUT_PATH)
    source_index = 0
    for raw_index, raw in enumerate(raw_records):
        ts = raw.get("timestamp")
        if ts is None or not (
            config.PROTONDB_TIMESTAMP_START <= ts <= config.PROTONDB_TIMESTAMP_END
        ):
            continue

        try:
            app_id = str(raw["app"]["steam"]["appId"])
        except (KeyError, TypeError):
            continue

        title = str((raw.get("app") or {}).get("title") or "")
        created_at = from_unix_timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
        metadata = {
            "raw_index": raw_index,
            "timestamp": ts,
            "source_path": str(config.PROTONDB_INPUT_PATH),
        }
        text = _truncate_text(render_protondb_record(raw))
        yield CRRecord(
            record_id=f"{config.PLATFORM_PROTONDB}:{raw_index}",
            platform=config.PLATFORM_PROTONDB,
            scope=config.SCOPE_BY_PLATFORM[config.PLATFORM_PROTONDB],
            source_index=source_index,
            app_id=app_id,
            title=title,
            created_at=created_at,
            text=text,
            metadata=metadata,
        )
        source_index += 1


def iter_issue_tracker_records() -> Iterable[CRRecord]:
    source_index = 0
    for issue in iter_github_issues(
        chunks_dir=config.ISSUE_TRACKER_CHUNKS_DIR,
        chunk_glob=config.ISSUE_TRACKER_CHUNK_GLOB,
    ):
        title = issue.get("title") or ""
        body = issue.get("body") or ""
        app_id, appid_rule = extract_appid(title, body)

        if classify_post(body)["is_compatibility_report"]:
            clean_body = clean_issue_tracker_text(body)
            yield CRRecord(
                record_id=f"{config.PLATFORM_ISSUE_TRACKER}:{issue['number']}:body",
                platform=config.PLATFORM_ISSUE_TRACKER,
                scope=config.SCOPE_BY_PLATFORM[config.PLATFORM_ISSUE_TRACKER],
                source_index=source_index,
                app_id=app_id,
                title=title,
                created_at=str(issue.get("created_at") or ""),
                text=_truncate_text(clean_body),
                metadata={
                    "issue_number": issue["number"],
                    "issue_title": title,
                    "issue_state": issue.get("state") or "",
                    "post_kind": config.ISSUE_TRACKER_POST_KINDS["issue_body"],
                    "appid_rule": appid_rule,
                    "inclusion_method": issue.get("inclusion_method") or "",
                },
            )
            source_index += 1

        for comment_index, comment in enumerate(issue.get("comments_data") or []):
            comment_body = comment.get("body") or ""
            if not classify_post(comment_body)["is_compatibility_report"]:
                continue
            comment_id = comment.get("id", comment_index)
            clean_body = clean_issue_tracker_text(comment_body)
            yield CRRecord(
                record_id=(
                    f"{config.PLATFORM_ISSUE_TRACKER}:"
                    f"{issue['number']}:comment:{comment_id}"
                ),
                platform=config.PLATFORM_ISSUE_TRACKER,
                scope=config.SCOPE_BY_PLATFORM[config.PLATFORM_ISSUE_TRACKER],
                source_index=source_index,
                app_id=app_id,
                title=title,
                created_at=str(comment.get("created_at") or ""),
                text=_truncate_text(clean_body),
                metadata={
                    "issue_number": issue["number"],
                    "issue_title": title,
                    "issue_state": issue.get("state") or "",
                    "post_kind": config.ISSUE_TRACKER_POST_KINDS["comment"],
                    "comment_id": comment_id,
                    "comment_html_url": comment.get("html_url") or "",
                    "appid_rule": appid_rule,
                    "inclusion_method": issue.get("inclusion_method") or "",
                },
            )
            source_index += 1


def render_protondb_record(raw: dict[str, Any]) -> str:
    app = raw.get("app") or {}
    steam = app.get("steam") or {}
    lines = [
        "[metadata]",
        f"app.steam.appId: {steam.get('appId', config.EMPTY_FIELD_PLACEHOLDER)}",
        f"app.title: {app.get('title', config.EMPTY_FIELD_PLACEHOLDER)}",
        f"timestamp: {raw.get('timestamp', config.EMPTY_FIELD_PLACEHOLDER)}",
    ]

    system_info = raw.get("systemInfo") or {}
    lines.append("")
    lines.append("[systemInfo]")
    lines.extend(_render_mapping(system_info))

    responses = raw.get("responses") or {}
    lines.append("")
    lines.append("[responses]")
    lines.extend(_render_mapping(responses))

    return "\n".join(line for line in lines if line is not None)


def clean_issue_tracker_text(text: str) -> str:
    return _HTML_COMMENT_RE.sub("", text or "").strip()


def _render_mapping(data: dict[str, Any], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for key in sorted(data):
        value = data[key]
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            lines.extend(_render_mapping(value, full_key))
        elif isinstance(value, list):
            if value:
                lines.append(f"{full_key}: {value}")
        elif value is not None and str(value).strip():
            lines.append(f"{full_key}: {value}")
    return lines


def _truncate_text(text: str) -> str:
    if len(text) <= config.RECORD_TEXT_MAX_CHARS:
        return text
    suffix = "\n\n[TRUNCATED]"
    return text[: config.RECORD_TEXT_MAX_CHARS - len(suffix)] + suffix

