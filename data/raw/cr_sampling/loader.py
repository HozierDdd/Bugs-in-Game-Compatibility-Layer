"""
读取 cr_selection 下的 [legacy]random_sampling_reports.json，
并为每条记录添加 pair_found 键（bool，初始为空 None）。
"""
from pathlib import Path
from typing import Any, List, Dict, Optional, Union, Tuple

import json


def find_root_directory() -> Path:
    """定位项目根目录（包含 data 的上级目录）。"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "data").is_dir():
            return parent
    return Path(__file__).resolve().parent.parent


def load_random_sampling_reports_with_pair_found(
    file_path: Optional[Union[Path, str]] = None,
) -> List[Dict[str, Any]]:
    """
    读取 [legacy]random_sampling_reports.json，为每条记录添加 "pair_found" 键（bool，初始为空 None）。

    Args:
        file_path: JSON 文件路径。若为 None，则使用默认路径：
                   {项目根}/data/cr_selection/[legacy]random_sampling_reports.json

    Returns:
        每条记录均包含 "pair_found" 键的列表；该键初始为 None（表示空/未设置）。
    """
    if file_path is None:
        root = find_root_directory()
        file_path = root / "data" / "cr_selection" / "[legacy]random_sampling_reports.json"
    else:
        file_path = Path(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        item["pair_found"] = None  # 空，后续可设为 True/False
        item["symptom"] = ""
        item["cause"] = ""

    return data


def load_report_discussion_pair_split(
    file_path: Optional[Union[Path, str]] = None,
    save: bool = False,
    num_splits: int = 33,
) -> Tuple[List[Dict[str, Any]], ...]:
    """
    加载 report_discussion_pair.json，将数组等分为指定数量的 split 并返回。

    Args:
        file_path: JSON 文件路径。若为 None，则使用默认路径：
                   {项目根}/data/cr_selection/report_discussion_pair.json
        save: 若为 True，将各 split 分别存为同目录下的
              report_discussion_pair_split_0.json、report_discussion_pair_split_1.json、... 。
        num_splits: 等分数量，默认为 2。

    Returns:
        长度为 num_splits 的元组，每个元素为一份等分后的列表。无法整除时前若干份多一个元素。
    """
    if file_path is None:
        root = find_root_directory()
        file_path = root / "data" / "cr_selection" / "report_discussion_pair.json"
    else:
        file_path = Path(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    n, k = len(data), num_splits
    # 前 n % k 份每份多 1 个，其余每份 base 个
    base, remainder = n // k, n % k
    sizes = [base + (1 if i < remainder else 0) for i in range(k)]
    splits = []
    start = 0
    for size in sizes:
        splits.append(data[start : start + size])
        start += size

    if save:
        base_dir = file_path.parent
        base_dir.mkdir(parents=True, exist_ok=True)
        for i, part in enumerate(splits):
            with open(base_dir / f"report_discussion_pair_split_{i}.json", "w", encoding="utf-8") as f:
                json.dump(part, f, ensure_ascii=False, indent=2)

    return tuple(splits)


if __name__ == "__main__":
    # data = load_random_sampling_reports_with_pair_found()
    # root_dir = find_root_directory()
    # print(f"已加载 {len(data)} 条记录，每条均含 pair_found 键（当前为 None）")
    # random_sampling_reports_path = root_dir / "data/cr_selection" / "[legacy]random_sampling_reports_with_marker.json"
    # try:
    #     random_sampling_reports_path.parent.mkdir(parents=True, exist_ok=True)
    #     with open(random_sampling_reports_path, 'w', encoding='utf-8') as f:
    #         json.dump(data, f, ensure_ascii=False, indent=2)
    # except Exception as e:
    #     raise OSError(f"Failed to write file {random_sampling_reports_path}: {e}")

    data = load_report_discussion_pair_split(save=True)
