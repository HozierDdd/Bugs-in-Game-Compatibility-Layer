"""Calibration metrics and final summary generation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.utils.datetime_utils import now_utc_iso
from src.utils.json_io import load_json, save_json

from src.cr_characteristics_pipeline import config
from src.cr_characteristics_pipeline.storage import (
    load_jsonl_by_record_id,
    read_jsonl,
    write_jsonl,
)


def evaluate_calibration(
    manual_items: list[dict[str, Any]],
    llm_labels_by_id: dict[str, dict],
) -> dict:
    platform_items: dict[str, list[dict]] = defaultdict(list)
    missing_human: list[str] = []
    missing_llm: list[str] = []

    for item in manual_items:
        record_id = str(item["record_id"])
        try:
            coerce_human_labels(item)
        except ValueError:
            missing_human.append(record_id)
        if record_id not in llm_labels_by_id:
            missing_llm.append(record_id)
        platform_items[str(item["platform"])].append(item)

    platform_reports = {}
    for platform in config.PLATFORMS:
        items = platform_items.get(platform, [])
        platform_reports[platform] = _evaluate_platform(items, llm_labels_by_id)

    gate_passed = (
        not missing_human
        and not missing_llm
        and all(
            platform_reports[p]["field_level_agreement"]
            >= config.FIELD_AGREEMENT_THRESHOLD
            for p in config.PLATFORMS
        )
    )

    return {
        "analysis": "cr_characteristics_prompt_calibration",
        "generated_at": now_utc_iso(),
        "thresholds": {
            "field_level_agreement": config.FIELD_AGREEMENT_THRESHOLD,
        },
        "gate_passed": gate_passed,
        "missing_human_label_record_ids": missing_human,
        "missing_llm_label_record_ids": missing_llm,
        "platforms": platform_reports,
    }


def evaluate_grouped_calibration(
    manual_groups: list[dict[str, Any]],
    llm_labels_by_id: dict[str, dict],
) -> dict:
    completed_groups = [group for group in manual_groups if group["is_complete"]]
    manual_items = [
        item
        for group in completed_groups
        for item in group["items"]
    ]
    report = evaluate_calibration(manual_items, llm_labels_by_id)

    group_reports = []
    for group in manual_groups:
        group_report = {
            "group_id": group["group_id"],
            "platform": group["platform"],
            "group_index": group["group_index"],
            "path": group["path"],
            "is_complete": group["is_complete"],
            "n_records": len(group["items"]),
        }
        if group["is_complete"]:
            group_report["metrics"] = _evaluate_platform(group["items"], llm_labels_by_id)
        group_reports.append(group_report)

    progress = _group_progress(manual_groups)
    all_groups_complete = progress["completed_groups"] == progress["total_groups"]
    report["gate_passed"] = report["gate_passed"] and (
        all_groups_complete or not config.REQUIRE_ALL_CALIBRATION_GROUPS_FOR_GATE
    )
    report["calibration_progress"] = progress
    report["groups"] = group_reports
    return report


def coerce_human_labels(item: dict[str, Any]) -> dict[str, bool]:
    raw = item.get(config.HUMAN_LABELS_FIELD)
    if not isinstance(raw, dict):
        raise ValueError(f"Record {item.get('record_id')} missing human_labels object.")

    labels: dict[str, bool] = {}
    for key in config.CHARACTERISTIC_KEYS:
        labels[key] = _coerce_bool(raw.get(key), item.get("record_id"), key)
    return labels


def has_completed_human_labels(item: dict[str, Any]) -> bool:
    try:
        coerce_human_labels(item)
    except ValueError:
        return False
    return True


def load_completed_manual_items(path: Path | str) -> list[dict[str, Any]]:
    items = load_json(path)
    if not isinstance(items, list):
        raise ValueError(f"Manual labels file must contain a list: {path}")
    for item in items:
        coerce_human_labels(item)
    return items


def _group_progress(manual_groups: list[dict[str, Any]]) -> dict:
    total = len(manual_groups)
    completed = sum(1 for group in manual_groups if group["is_complete"])
    by_platform = {}
    for platform in config.PLATFORMS:
        platform_groups = [g for g in manual_groups if g["platform"] == platform]
        platform_completed = sum(1 for g in platform_groups if g["is_complete"])
        by_platform[platform] = {
            "total_groups": len(platform_groups),
            "completed_groups": platform_completed,
            "total_records": sum(len(g["items"]) for g in platform_groups),
            "completed_records": sum(
                len(g["items"]) for g in platform_groups if g["is_complete"]
            ),
        }
    return {
        "total_groups": total,
        "completed_groups": completed,
        "total_records": sum(len(group["items"]) for group in manual_groups),
        "completed_records": sum(
            len(group["items"]) for group in manual_groups if group["is_complete"]
        ),
        "by_platform": by_platform,
        "require_all_groups_for_gate": config.REQUIRE_ALL_CALIBRATION_GROUPS_FOR_GATE,
    }


def enforce_gate(report_path: Path | str = config.CALIBRATION_REPORT_PATH) -> None:
    report = load_json(report_path)
    if not report.get("gate_passed"):
        raise RuntimeError(
            "Calibration gate did not pass. Update prompts/manual labels and rerun calibrate."
        )


def summarize_final_labels(
    manual_items: list[dict[str, Any]],
    llm_remaining_path: Path | str,
    final_labels_path: Path | str,
    summary_path: Path | str,
) -> dict:
    calibration_ids = {str(item["record_id"]) for item in manual_items}
    final_records: list[dict] = []

    for item in manual_items:
        final_records.append(
            {
                "record_id": item["record_id"],
                "platform": item["platform"],
                "scope": item.get("scope") or config.SCOPE_BY_PLATFORM[item["platform"]],
                "app_id": item.get("app_id") or "",
                "title": item.get("title") or "",
                "created_at": item.get("created_at") or "",
                "source": config.ANNOTATION_SOURCE_HUMAN_CALIBRATION,
                "labels": coerce_human_labels(item),
                "evidence": {key: "" for key in config.CHARACTERISTIC_KEYS},
                "human_notes": item.get(config.HUMAN_NOTES_FIELD) or "",
            }
        )

    for annotation in read_jsonl(llm_remaining_path):
        if str(annotation.get("record_id")) in calibration_ids:
            continue
        final_records.append(annotation)

    write_jsonl(final_records, final_labels_path)
    summary = build_summary(final_records)
    save_json(summary, summary_path)
    return summary


def build_summary(final_records: list[dict]) -> dict:
    by_platform: dict[str, dict] = {}
    for platform in config.PLATFORMS:
        records = [r for r in final_records if r.get("platform") == platform]
        by_platform[platform] = _summarize_platform(records)

    return {
        "analysis": "cr_characteristics_summary",
        "generated_at": now_utc_iso(),
        "n_records": len(final_records),
        "characteristics": config.CHARACTERISTICS,
        "platforms": by_platform,
    }


def load_llm_labels_by_id(path: Path | str) -> dict[str, dict]:
    return load_jsonl_by_record_id(path)


def _evaluate_platform(items: list[dict], llm_labels_by_id: dict[str, dict]) -> dict:
    field_total = 0
    field_matches = 0
    exact_matches = 0
    evaluated_records = 0
    per_key = {
        key: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for key in config.CHARACTERISTIC_KEYS
    }

    for item in items:
        record_id = str(item["record_id"])
        llm = llm_labels_by_id.get(record_id)
        if not llm:
            continue
        try:
            human = coerce_human_labels(item)
        except ValueError:
            continue
        llm_labels = llm.get("labels") or {}
        if not all(isinstance(llm_labels.get(k), bool) for k in config.CHARACTERISTIC_KEYS):
            continue

        evaluated_records += 1
        record_exact = True
        for key in config.CHARACTERISTIC_KEYS:
            h = human[key]
            l = llm_labels[key]
            field_total += 1
            if h == l:
                field_matches += 1
            else:
                record_exact = False

            if h and l:
                per_key[key]["tp"] += 1
            elif not h and l:
                per_key[key]["fp"] += 1
            elif h and not l:
                per_key[key]["fn"] += 1
            else:
                per_key[key]["tn"] += 1

        if record_exact:
            exact_matches += 1

    metrics_by_key = {
        key: _classification_metrics(counts) for key, counts in per_key.items()
    }

    return {
        "n_manual_records": len(items),
        "n_evaluated_records": evaluated_records,
        "field_level_agreement": _ratio(field_matches, field_total),
        "record_level_exact_match": _ratio(exact_matches, evaluated_records),
        "per_characteristic": metrics_by_key,
    }


def _summarize_platform(records: list[dict]) -> dict:
    total = len(records)
    coverage = {}
    for key in config.CHARACTERISTIC_KEYS:
        count = sum(1 for r in records if (r.get("labels") or {}).get(key) is True)
        coverage[key] = {
            "label": config.CHARACTERISTICS[key]["label"],
            "count": count,
            "pct": _ratio(count, total) * 100,
        }
    return {"n_records": total, "coverage": coverage}


def _classification_metrics(counts: dict[str, int]) -> dict[str, float | int]:
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    accuracy = _ratio(tp + tn, tp + fp + fn + tn)
    return {
        **counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
    }


def _coerce_bool(value: Any, record_id: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0"}:
            return False
    raise ValueError(f"Record {record_id} has missing/non-bool human label: {key}")


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, config.ROUND_DIGITS)
