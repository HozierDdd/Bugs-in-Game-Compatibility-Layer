"""LLM annotation, schema validation, and resumable JSONL writing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Iterator

from src.utils.datetime_utils import now_utc_iso

from src.cr_characteristics_pipeline import config
from src.cr_characteristics_pipeline.llm_client import ChatClient
from src.cr_characteristics_pipeline.prompts import render_messages
from src.cr_characteristics_pipeline.records import CRRecord
from src.cr_characteristics_pipeline.storage import (
    append_jsonl,
    load_jsonl_record_ids,
    save_failed_record,
)


def annotate_record(record: CRRecord, client: ChatClient) -> dict:
    messages = render_messages(record)
    content = client.complete_json(messages)
    parsed = parse_llm_response(content)
    labels, evidence = normalize_llm_labels(parsed)
    prompt_hash = hashlib.sha256(
        json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "record_id": record.record_id,
        "platform": record.platform,
        "scope": record.scope,
        "app_id": record.app_id,
        "title": record.title,
        "created_at": record.created_at,
        "source": config.ANNOTATION_SOURCE_LLM,
        "labels": labels,
        "evidence": evidence,
        "llm_notes": str(parsed.get("notes") or ""),
        "llm_metadata": {
            "generated_at": now_utc_iso(),
            "prompt_hash": prompt_hash,
        },
    }


def annotate_records(
    records: Iterable[CRRecord],
    output_path: Path,
    client: ChatClient,
    *,
    exclude_record_ids: set[str] | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    output_path = Path(output_path)
    if force and output_path.exists():
        output_path.unlink()

    done_ids = load_jsonl_record_ids(output_path)
    exclude_record_ids = exclude_record_ids or set()

    attempted = 0
    written = 0
    skipped = 0
    failed = 0

    for batch in _batched(records, config.ANNOTATION_BATCH_SIZE):
        for record in batch:
            if record.record_id in exclude_record_ids:
                skipped += 1
                continue
            if record.record_id in done_ids:
                skipped += 1
                continue
            if limit is not None and written >= limit:
                return _annotation_stats(attempted, written, skipped, failed, output_path)

            attempted += 1
            try:
                annotation = annotate_record(record, client)
            except Exception as exc:
                failed += 1
                save_failed_record(
                    {
                        "record_id": record.record_id,
                        "platform": record.platform,
                        "failed_at": now_utc_iso(),
                        "error": repr(exc),
                    },
                    config.FAILED_RECORDS_PATH,
                )
                continue

            append_jsonl(annotation, output_path)
            done_ids.add(record.record_id)
            written += 1

            if written % config.ANNOTATION_PROGRESS_INTERVAL == 0:
                print(f"  annotated {written} records -> {output_path}")

    return _annotation_stats(attempted, written, skipped, failed, output_path)


def _annotation_stats(
    attempted: int,
    written: int,
    skipped: int,
    failed: int,
    output_path: Path,
) -> dict:
    return {
        "attempted": attempted,
        "written": written,
        "skipped": skipped,
        "failed": failed,
        "output_path": str(output_path),
    }


def _batched(records: Iterable[CRRecord], batch_size: int) -> Iterator[list[CRRecord]]:
    batch: list[CRRecord] = []
    for record in records:
        batch.append(record)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def parse_llm_response(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(content[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object.")
    return parsed


def normalize_llm_labels(parsed: dict) -> tuple[dict[str, bool], dict[str, str]]:
    raw_labels = parsed.get("labels")
    if not isinstance(raw_labels, dict):
        raise ValueError("LLM response missing object field: labels")

    labels: dict[str, bool] = {}
    evidence: dict[str, str] = {}
    for key in config.CHARACTERISTIC_KEYS:
        value = raw_labels.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"Label {key!r} must be an object.")
        present = value.get(config.LABEL_PRESENT_FIELD)
        if not isinstance(present, bool):
            raise ValueError(f"Label {key!r}.present must be a boolean.")
        ev = value.get(config.LABEL_EVIDENCE_FIELD) or ""
        if not isinstance(ev, str):
            raise ValueError(f"Label {key!r}.evidence must be a string.")
        if not present:
            ev = ""
        labels[key] = present
        evidence[key] = ev[: config.EVIDENCE_MAX_CHARS]

    extra = set(raw_labels) - set(config.CHARACTERISTIC_KEYS)
    if extra:
        raise ValueError(f"LLM response has unknown label keys: {sorted(extra)}")

    return labels, evidence
