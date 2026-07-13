"""Primary entry for the CR characteristics annotation pipeline."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

from src.utils.datetime_utils import now_utc_iso
from src.utils.json_io import load_json, save_json

from src.cr_characteristics_pipeline import config
from src.cr_characteristics_pipeline.annotator import annotate_records
from src.cr_characteristics_pipeline.evaluation import (
    enforce_gate,
    evaluate_grouped_calibration,
    has_completed_human_labels,
    load_llm_labels_by_id,
    summarize_final_labels,
)
from src.cr_characteristics_pipeline.llm_client import MockLLMClient, OpenAICompatibleClient
from src.cr_characteristics_pipeline.records import (
    CRRecord,
    iter_all_records,
    load_records,
    record_from_template_item,
)


def prepare_manual() -> dict:
    run_id, sample_path, template_path, groups_dir = _new_prepare_manual_paths()
    all_items: list[dict] = []
    manual_groups: list[dict] = []
    counts: dict[str, int] = {}
    for platform in config.PLATFORMS:
        records = load_records(platform)
        counts[platform] = len(records)
        sampled = _sample_records(records, platform)
        sampled_items = [record.to_manual_template_item() for record in sampled]
        all_items.extend(sampled_items)
        manual_groups.extend(
            _write_manual_groups(run_id, platform, sampled_items, groups_dir)
        )

    output = {
        "generated_at": now_utc_iso(),
        "run_id": run_id,
        "random_seed": config.RANDOM_SEED,
        "sample_size_per_platform": config.CALIBRATION_SAMPLE_SIZE_PER_PLATFORM,
        "group_size": config.CALIBRATION_GROUP_SIZE,
        "available_records": counts,
        "record_ids": [item["record_id"] for item in all_items],
        "calibration_sample_path": str(sample_path),
        "manual_labels_template_path": str(template_path),
        "manual_label_groups_dir": str(groups_dir),
        "manual_groups": manual_groups,
    }
    save_json(output, sample_path)
    save_json(all_items, template_path)
    save_json(output, config.LATEST_PREPARE_MANUAL_OUTPUT_PATH)

    print(f"[OK] calibration sample -> {sample_path}")
    print(f"[OK] legacy combined manual template -> {template_path}")
    print(f"[OK] grouped manual templates -> {groups_dir}")
    print(f"[OK] latest prepare-manual pointer -> {config.LATEST_PREPARE_MANUAL_OUTPUT_PATH}")
    return output


def calibrate(manual_labels_path: Path, *, mock: bool = False, force: bool = False) -> dict:
    manual_groups = _manual_groups()
    completed_groups = [group for group in manual_groups if group["is_complete"]]
    manual_items = [
        item
        for group in completed_groups
        for item in group["items"]
    ]
    records = [record_from_template_item(item) for item in manual_items]
    client = _make_client(mock)
    annotation_stats = annotate_records(
        records,
        config.LLM_CALIBRATION_LABELS_PATH,
        client,
        force=force,
    )
    llm_labels = load_llm_labels_by_id(config.LLM_CALIBRATION_LABELS_PATH)
    report = evaluate_grouped_calibration(manual_groups, llm_labels)
    report["annotation_stats"] = annotation_stats
    report["manual_labels_path"] = str(manual_labels_path)
    report["manual_group_paths"] = [group["path"] for group in manual_groups]
    report["llm_labels_path"] = str(config.LLM_CALIBRATION_LABELS_PATH)
    save_json(report, config.CALIBRATION_REPORT_PATH)

    print(f"[OK] calibration report -> {config.CALIBRATION_REPORT_PATH}")
    progress = report["calibration_progress"]
    print(
        "     completed_groups="
        f"{progress['completed_groups']}/{progress['total_groups']}, "
        f"completed_records={progress['completed_records']}/{progress['total_records']}"
    )
    print(f"     gate_passed={report['gate_passed']}")
    for platform, platform_report in report["platforms"].items():
        print(
            f"     {platform}: field_agreement="
            f"{platform_report['field_level_agreement']:.4f}, "
            f"exact_match={platform_report['record_level_exact_match']:.4f}"
        )
    return report


def label_remaining(
    manual_labels_path: Path,
    *,
    mock: bool = False,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    enforce_gate(config.CALIBRATION_REPORT_PATH)
    manual_items = _completed_manual_items_for_all_groups()
    calibration_ids = {str(item["record_id"]) for item in manual_items}
    client = _make_client(mock)
    stats = annotate_records(
        iter_all_records(),
        config.LLM_REMAINING_LABELS_PATH,
        client,
        exclude_record_ids=calibration_ids,
        force=force,
        limit=limit,
    )
    print(f"[OK] remaining labels -> {config.LLM_REMAINING_LABELS_PATH}")
    return stats


def summarize(manual_labels_path: Path) -> dict:
    manual_items = _completed_manual_items_for_all_groups()
    summary = summarize_final_labels(
        manual_items,
        config.LLM_REMAINING_LABELS_PATH,
        config.FINAL_LABELS_PATH,
        config.SUMMARY_OUTPUT_PATH,
    )
    print(f"[OK] final labels -> {config.FINAL_LABELS_PATH}")
    print(f"[OK] summary -> {config.SUMMARY_OUTPUT_PATH}")
    return summary


def main() -> None:
    stage = config.PIPELINE_RUN_STAGE
    if stage == "prepare_manual":
        prepare_manual()
    elif stage == "calibrate":
        calibrate(
            _manual_labels_path(),
            mock=config.CALIBRATE_USE_MOCK_LLM,
            force=config.CALIBRATE_FORCE,
        )
    elif stage == "label_remaining":
        label_remaining(
            _manual_labels_path(),
            mock=config.LABEL_REMAINING_USE_MOCK_LLM,
            force=config.LABEL_REMAINING_FORCE,
            limit=config.LABEL_REMAINING_LIMIT,
        )
    elif stage == "summarize":
        summarize(_manual_labels_path())
    else:
        raise ValueError(f"Unknown PIPELINE_RUN_STAGE: {stage!r}")


def _sample_records(records: list[CRRecord], platform: str) -> list[CRRecord]:
    n = config.CALIBRATION_SAMPLE_SIZE_PER_PLATFORM
    if len(records) < n and config.REQUIRE_FULL_CALIBRATION_SAMPLE_SIZE:
        raise ValueError(
            f"Platform {platform} has only {len(records)} records; need {n}."
        )
    sample_size = min(n, len(records))
    rng = random.Random(f"{config.RANDOM_SEED}:{platform}")
    return rng.sample(records, sample_size)


def _make_client(mock: bool):
    if mock:
        return MockLLMClient()
    return OpenAICompatibleClient()


def _new_prepare_manual_paths() -> tuple[str, Path, Path, Path]:
    base_run_id = config.PREPARE_MANUAL_RUN_ID or datetime.now(
        tz=timezone.utc
    ).strftime(config.PREPARE_MANUAL_RUN_ID_FORMAT)
    run_id = base_run_id
    counter = 2
    while True:
        sample_path = config.PIPELINE_OUTPUT_DIR / (
            config.CALIBRATION_SAMPLE_FILENAME_TEMPLATE.format(run_id=run_id)
        )
        template_path = config.PIPELINE_OUTPUT_DIR / (
            config.MANUAL_LABELS_TEMPLATE_FILENAME_TEMPLATE.format(run_id=run_id)
        )
        groups_dir = config.PIPELINE_OUTPUT_DIR / (
            config.MANUAL_LABEL_GROUPS_DIR_TEMPLATE.format(run_id=run_id)
        )
        if not sample_path.exists() and not template_path.exists() and not groups_dir.exists():
            return run_id, sample_path, template_path, groups_dir
        run_id = f"{base_run_id}_{counter}"
        counter += 1


def _manual_labels_path() -> Path:
    if config.MANUAL_LABELS_PATH is not None:
        return Path(config.MANUAL_LABELS_PATH)
    if not config.LATEST_PREPARE_MANUAL_OUTPUT_PATH.exists():
        if config.MANUAL_LABELS_TEMPLATE_PATH.exists():
            return config.MANUAL_LABELS_TEMPLATE_PATH
        raise FileNotFoundError(
            f"Neither {config.LATEST_PREPARE_MANUAL_OUTPUT_PATH} nor "
            f"{config.MANUAL_LABELS_TEMPLATE_PATH} exists. Run prepare_manual first."
        )
    latest = load_json(config.LATEST_PREPARE_MANUAL_OUTPUT_PATH)
    path = latest.get("manual_labels_template_path")
    if not path:
        raise ValueError(
            f"{config.LATEST_PREPARE_MANUAL_OUTPUT_PATH} does not contain "
            "manual_labels_template_path."
        )
    return Path(path)


def _manual_groups() -> list[dict]:
    if config.MANUAL_LABELS_PATH is not None:
        path = Path(config.MANUAL_LABELS_PATH)
        if path.is_dir():
            return _load_group_files(sorted(path.glob("*.json")))
        items = load_json(path)
        if not isinstance(items, list):
            raise ValueError(f"Manual labels file must contain a list: {path}")
        is_complete = bool(items) and all(has_completed_human_labels(item) for item in items)
        first = items[0] if items else {}
        return [
            {
                "group_id": str(first.get("calibration_group_id") or "manual_labels"),
                "platform": str(first.get("platform") or "mixed"),
                "group_index": int(first.get("calibration_group_index") or 1),
                "path": str(path),
                "is_complete": is_complete,
                "items": items,
            }
        ]

    latest = _latest_prepare_manual_outputs()
    groups = latest.get("manual_groups") or []
    if groups:
        paths = [Path(group["path"]) for group in groups]
        return _load_group_files(paths)
    return _manual_groups_from_legacy_template()


def _write_manual_groups(
    run_id: str,
    platform: str,
    items: list[dict],
    groups_dir: Path,
) -> list[dict]:
    groups_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for group_index, group_items in enumerate(
        _split_items(items, config.CALIBRATION_GROUP_SIZE),
        start=1,
    ):
        group_id = config.CALIBRATION_GROUP_ID_TEMPLATE.format(
            platform=platform,
            group_index=group_index,
        )
        for position, item in enumerate(group_items, start=1):
            item["calibration_run_id"] = run_id
            item["calibration_group_id"] = group_id
            item["calibration_group_index"] = group_index
            item["calibration_group_position"] = position
        group_path = groups_dir / config.MANUAL_LABEL_GROUP_FILENAME_TEMPLATE.format(
            platform=platform,
            group_index=group_index,
        )
        save_json(group_items, group_path)
        groups.append(
            {
                "group_id": group_id,
                "platform": platform,
                "group_index": group_index,
                "path": str(group_path),
                "n_records": len(group_items),
            }
        )
    return groups


def _load_group_files(paths: list[Path]) -> list[dict]:
    groups = []
    for path in paths:
        items = load_json(path)
        if not isinstance(items, list):
            raise ValueError(f"Manual group file must contain a list: {path}")
        first = items[0] if items else {}
        group_id = first.get("calibration_group_id") or path.stem
        platform = first.get("platform") or "unknown"
        group_index = int(first.get("calibration_group_index") or len(groups) + 1)
        is_complete = bool(items) and all(has_completed_human_labels(item) for item in items)
        groups.append(
            {
                "group_id": str(group_id),
                "platform": str(platform),
                "group_index": group_index,
                "path": str(path),
                "is_complete": is_complete,
                "items": items,
            }
        )
    return groups


def _manual_groups_from_legacy_template() -> list[dict]:
    path = _manual_labels_path()
    items = load_json(path)
    if not isinstance(items, list):
        raise ValueError(f"Manual labels file must contain a list: {path}")
    platform_groups: list[dict] = []
    for platform in config.PLATFORMS:
        platform_items = [item for item in items if item.get("platform") == platform]
        for group_index, group_items in enumerate(
            _split_items(platform_items, config.CALIBRATION_GROUP_SIZE),
            start=1,
        ):
            is_complete = bool(group_items) and all(
                has_completed_human_labels(item) for item in group_items
            )
            platform_groups.append(
                {
                    "group_id": config.CALIBRATION_GROUP_ID_TEMPLATE.format(
                        platform=platform,
                        group_index=group_index,
                    ),
                    "platform": platform,
                    "group_index": group_index,
                    "path": str(path),
                    "is_complete": is_complete,
                    "items": group_items,
                }
            )
    return platform_groups


def _completed_manual_items_for_all_groups() -> list[dict]:
    groups = _manual_groups()
    incomplete = [group["group_id"] for group in groups if not group["is_complete"]]
    if incomplete:
        raise RuntimeError(
            "All calibration groups must be manually labeled before this stage. "
            f"Incomplete groups: {incomplete}"
        )
    return [item for group in groups for item in group["items"]]


def _latest_prepare_manual_outputs() -> dict:
    if not config.LATEST_PREPARE_MANUAL_OUTPUT_PATH.exists():
        raise FileNotFoundError(
            f"{config.LATEST_PREPARE_MANUAL_OUTPUT_PATH} does not exist. "
            "Run prepare_manual first."
        )
    return load_json(config.LATEST_PREPARE_MANUAL_OUTPUT_PATH)


def _split_items(items: list[dict], group_size: int) -> list[list[dict]]:
    if group_size <= 0:
        raise ValueError("CALIBRATION_GROUP_SIZE must be positive.")
    return [items[i : i + group_size] for i in range(0, len(items), group_size)]


if __name__ == "__main__":
    main()
