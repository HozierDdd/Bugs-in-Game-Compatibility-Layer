"""Prompt rendering for the CR characteristics annotation task."""

import json

from src.cr_characteristics_pipeline import config
from src.cr_characteristics_pipeline.records import CRRecord


def render_messages(record: CRRecord) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": config.SYSTEM_PROMPT},
        {"role": "user", "content": render_user_prompt(record)},
    ]


def render_user_prompt(record: CRRecord) -> str:
    template = config.PROMPT_TEMPLATE_BY_PLATFORM[record.platform]
    return template.format(
        characteristics_json=json.dumps(
            config.CHARACTERISTICS,
            ensure_ascii=False,
            indent=2,
        ),
        record_json=json.dumps(_record_prompt_payload(record), ensure_ascii=False, indent=2),
        record_text=record.text,
    )


def _record_prompt_payload(record: CRRecord) -> dict:
    return {
        "record_id": record.record_id,
        "platform": record.platform,
        "scope": record.scope,
        "app_id": record.app_id,
        "title": record.title,
        "created_at": record.created_at,
        "metadata": record.metadata,
    }

