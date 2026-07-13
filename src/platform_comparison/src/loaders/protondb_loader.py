"""
ProtonDB data loader.

Responsibilities:
- Load raw records from reports_piiremoved.json
- Apply the time-window filter (ProtonDB uses Unix integer-second timestamps)
- Normalize fields and return standardized records
"""

from pathlib import Path
from src.config import PROTONDB_REPORTS_PATH, PROTONDB_TS_START, PROTONDB_TS_END
from src.utils.json_io import load_json


def _normalize_record(raw: dict) -> dict | None:
    """
    Normalize a raw ProtonDB record into the standard format used for analysis.
    Returns None when a required field is missing (skipped by the caller).
    """
    try:
        app_id = str(raw["app"]["steam"]["appId"])
        title = raw["app"].get("title", "")
        verdict = raw["responses"].get("verdict", "")
        timestamp = raw["timestamp"]
    except (KeyError, TypeError):
        return None

    return {
        "app_id": app_id,
        "title": title,
        "verdict": verdict,
        "timestamp": timestamp,
    }


def load_protondb_records(
    path: Path | str = PROTONDB_REPORTS_PATH,
    ts_start: float = PROTONDB_TS_START,
    ts_end: float = PROTONDB_TS_END,
) -> tuple[list[dict], int, int]:
    """
    Load and filter ProtonDB reports.

    Returns:
        (records, total_raw, filtered_count)
        records        — list of normalized records within the time window
        total_raw      — total number of raw records
        filtered_count — number of records excluded by the time filter
    """
    raw_data = load_json(path)
    total_raw = len(raw_data)

    records = []
    filtered_count = 0

    for raw in raw_data:
        ts = raw.get("timestamp")
        if ts is None or not (ts_start <= ts <= ts_end):
            filtered_count += 1
            continue
        rec = _normalize_record(raw)
        if rec is None:
            filtered_count += 1
            continue
        records.append(rec)

    return records, total_raw, filtered_count
