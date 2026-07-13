"""
GitHub issue 数据加载器（流式/生成器实现）。

职责：
- 按文件名顺序扫描 chunks 目录
- 每次 yield 一个 issue 的归一化记录
- 应用时间窗口过滤（GitHub 使用 ISO 8601 字符串）
- 不将所有 chunk 同时加载进内存

时间窗口纳入标准（两者满足其一即纳入）：
  1. created_at 筛选：issue 的首次提交时间落在 [start, end] 内
  2. thread_median 筛选：issue thread 全部帖子（正文 + 评论）时间戳的中位数落在 [start, end] 内
归一化记录中的 inclusion_method 字段记录实际命中的标准
（"created_at" 或 "thread_median"；同时满足时优先标记为 "created_at"）。

重要说明：
    使用 len(comments_data) 而非 issue["comments"] 字段作为评论计数。
    原因：comments 字段是 GitHub API 返回的"已知评论数"，
    而 comments_data 是实际抓取到的评论列表，两者可能因分页截断而不一致。
    以实际观测到的数据为准，保证可重现性。
"""

import json
from pathlib import Path
from typing import Iterator
from src.config import (
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
)
from src.utils.datetime_utils import from_iso8601, in_window, thread_median_in_window


def _normalize_issue(raw: dict) -> dict | None:
    """
    将原始 GitHub issue 归一化为分析用的标准格式。
    缺少必要字段时返回 None。
    """
    try:
        number = raw["number"]
        title = raw.get("title") or ""
        body = raw.get("body") or ""
        state = raw.get("state", "")
        created_at_str = raw["created_at"]
        labels = [lb.get("name", "") for lb in (raw.get("labels") or [])]
        # 使用 comments_data 长度作为真实评论数（见模块文档说明）
        comments_data = raw.get("comments_data") or []
    except (KeyError, TypeError):
        return None

    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "created_at": created_at_str,
        "labels": labels,
        "comments_data": comments_data,
        # inclusion_method 由 iter_github_issues 在 yield 前填充
    }


def iter_github_issues(
    chunks_dir: Path | str = GITHUB_CHUNKS_DIR,
    chunk_glob: str = GITHUB_CHUNK_GLOB,
    start: object = TIME_WINDOW_START,
    end: object = TIME_WINDOW_END,
) -> Iterator[dict]:
    """
    流式生成器：逐 chunk 读取 GitHub issue，yield 归一化后的 issue 记录。

    纳入标准（两者满足其一）：
      1. created_at 落在 [start, end] 内（标记 inclusion_method="created_at"）
      2. thread 全帖时间戳中位数落在 [start, end] 内（标记 inclusion_method="thread_median"）

    Yields:
        归一化的 issue dict（包含 number, title, body, state,
        created_at, labels, comments_data, inclusion_method）
    """
    chunks_dir = Path(chunks_dir)
    chunk_files = sorted(chunks_dir.glob(chunk_glob))

    if not chunk_files:
        raise FileNotFoundError(
            f"在 {chunks_dir} 下未找到匹配 '{chunk_glob}' 的 chunk 文件"
        )

    for chunk_path in chunk_files:
        with open(chunk_path, encoding="utf-8") as f:
            chunk = json.load(f)

        issues = chunk.get("issues") or []
        for raw_issue in issues:
            created_at_str = raw_issue.get("created_at")
            if not created_at_str:
                continue
            try:
                dt = from_iso8601(created_at_str)
            except ValueError:
                continue

            if in_window(dt, start, end):
                inclusion = "created_at"
            elif thread_median_in_window(raw_issue, start, end):
                inclusion = "thread_median"
            else:
                continue

            rec = _normalize_issue(raw_issue)
            if rec is not None:
                rec["inclusion_method"] = inclusion
                yield rec


def count_github_chunks(
    chunks_dir: Path | str = GITHUB_CHUNKS_DIR,
    chunk_glob: str = GITHUB_CHUNK_GLOB,
) -> int:
    """返回 chunk 文件总数，用于日志报告。"""
    return sum(1 for _ in Path(chunks_dir).glob(chunk_glob))
