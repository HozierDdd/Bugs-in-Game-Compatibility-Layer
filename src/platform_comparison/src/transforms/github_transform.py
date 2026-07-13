"""
GitHub issue 数据聚合层。

核心设计说明：
────────────────────────────────────────────────────────────────────────────
分类单元为 POST 级别，而非线程级别。

原因：
    GitHub issue tracker 中，一个线程（issue）可能包含：
      - issue 正文：通常是第一个报告人的兼容性报告
      - 多条评论：其中部分是后续用户补充的新报告，
        其余是讨论、确认、建议等跟帖

    如果以线程为单位仅统计"是否有报告"，则会低估 GitHub 的报告密度；
    如果把所有评论都算作报告，则会高估。
    因此以每条帖子（正文/评论）为独立分类单元，更接近真实情况。

线程级指标计算逻辑：
    thread_has_issue_body_report = classify_post(issue.body).is_report
    n_comment_reports            = 统计 comments_data 中被分类为报告的帖子数
    n_reports_in_thread          = int(thread_has_issue_body_report) + n_comment_reports
    n_comments_in_thread         = len(comments_data) - n_comment_reports
        （即"真正的讨论评论数" = 总评论数 - 其中属于报告的评论数）
    注意：issue 正文本身不计入 comments_in_thread。
────────────────────────────────────────────────────────────────────────────
"""

from collections import defaultdict
from typing import Iterator
from src.parsers.appid_extractor import extract_appid
from src.parsers.compatibility_report_classifier import classify_post
from src.config import UNRESOLVED_APPID, STATS_ROUND_DIGITS
from src.utils.stats import compute_distribution_stats


def process_issue_thread(issue: dict) -> dict:
    """
    处理单个 GitHub issue 线程，返回线程级分析结果。

    Args:
        issue: 归一化的 issue 记录（来自 github_loader）

    Returns:
        {
            "issue_number":              int,
            "resolved_appid":            str,   # 或 UNRESOLVED_APPID
            "appid_rule":                str,
            "title":                     str,
            "created_at":                str,
            "state":                     str,
            "thread_has_body_report":    bool,
            "n_comment_reports":         int,
            "n_reports_in_thread":       int,
            "n_comments_in_thread":      int,   # 排除报告后的纯讨论评论数
            "n_comments_total":          int,   # len(comments_data) 真实观测值
        }
    """
    title = issue["title"]
    body = issue["body"]
    comments_data = issue["comments_data"]

    # 提取 appid
    appid, appid_rule = extract_appid(title, body)

    # 判断 issue 正文是否为兼容性报告（确定性规则：含 "# Compatibility Report"）
    has_body_report = classify_post(body)["is_compatibility_report"]

    # 逐条分类评论
    n_comment_reports = 0
    for comment in comments_data:
        comment_body = comment.get("body") or ""
        if classify_post(comment_body)["is_compatibility_report"]:
            n_comment_reports += 1

    n_total_comments = len(comments_data)
    n_reports_in_thread = int(has_body_report) + n_comment_reports
    # 讨论评论数 = 总评论数 - 其中属于报告的评论数（issue 正文不计入）
    n_comments_in_thread = n_total_comments - n_comment_reports

    return {
        "issue_number": issue["number"],
        "resolved_appid": appid,
        "appid_rule": appid_rule,
        "title": title,
        "created_at": issue["created_at"],
        "state": issue["state"],
        "inclusion_method": issue.get("inclusion_method", "created_at"),
        "thread_has_body_report": has_body_report,
        "n_comment_reports": n_comment_reports,
        "n_reports_in_thread": n_reports_in_thread,
        "n_comments_in_thread": n_comments_in_thread,
        "n_comments_total": n_total_comments,
    }


def aggregate_threads_by_game(
    issue_iter: Iterator[dict],
) -> tuple[list[dict], dict[str, dict], int]:
    """
    流式处理所有 GitHub issue，完成线程级分析后按 appid 聚合。

    Args:
        issue_iter: iter_github_issues() 生成的 issue 迭代器

    Returns:
        (thread_records, game_stats, unresolved_count)

        thread_records — 所有线程的详细分析结果列表
        game_stats     — appid -> 游戏级聚合指标
        unresolved_count — 无法提取 appid 的 issue 数量
    """
    thread_records: list[dict] = []
    # appid -> {n_issues, n_reports, n_comments, title（首次见到的标题）}
    game_buckets: dict[str, dict] = defaultdict(lambda: {
        "n_issues_github": 0,
        "n_reports_github": 0,
        "n_comments_github": 0,
        "game_title_github": "",
    })
    unresolved_count = 0

    for issue in issue_iter:
        thread = process_issue_thread(issue)
        thread_records.append(thread)

        appid = thread["resolved_appid"]
        if appid == UNRESOLVED_APPID:
            unresolved_count += 1
            continue

        bucket = game_buckets[appid]
        bucket["n_issues_github"] += 1
        bucket["n_reports_github"] += thread["n_reports_in_thread"]
        bucket["n_comments_github"] += thread["n_comments_in_thread"]
        # 保留首次见到的标题（最早 issue 的标题）
        if not bucket["game_title_github"] and thread["title"]:
            bucket["game_title_github"] = thread["title"]

    # 转为普通 dict，并补充 app_id 字段
    game_stats: dict[str, dict] = {}
    for appid, bucket in game_buckets.items():
        game_stats[appid] = {"app_id": appid, **bucket}

    return thread_records, game_stats, unresolved_count


def compute_appid_rule_breakdown(thread_records: list[dict]) -> dict:
    """
    按 AppID 解析规则统计各规则覆盖的游戏数和 issue 数。

    一个游戏可能被多条规则覆盖（若其不同 issue 使用了不同规则），
    因此各规则游戏数之和可能超过总游戏数。

    Returns:
        {rule_name: {"n_games": int, "n_issues": int}, ...}
        固定顺序：parentheses → steam_url → standalone → unresolved
    """
    rule_game_sets: dict[str, set] = defaultdict(set)
    rule_issue_counts: dict[str, int] = defaultdict(int)

    for thread in thread_records:
        rule = thread["appid_rule"]
        appid = thread["resolved_appid"]
        rule_issue_counts[rule] += 1
        if appid != UNRESOLVED_APPID:
            rule_game_sets[rule].add(appid)

    all_rules = ["parentheses", "steam_url", "standalone", "unresolved"]
    return {
        rule: {
            "n_games": len(rule_game_sets.get(rule, set())),
            "n_issues": rule_issue_counts.get(rule, 0),
        }
        for rule in all_rules
    }


def compute_github_distributions(game_stats: dict[str, dict]) -> dict:
    """
    计算 GitHub 游戏级指标的分布统计（issues、reports、comments 各一组）。
    """
    games = list(game_stats.values())
    return {
        "n_issues_github": compute_distribution_stats(
            [g["n_issues_github"] for g in games], STATS_ROUND_DIGITS
        ),
        "n_reports_github": compute_distribution_stats(
            [g["n_reports_github"] for g in games], STATS_ROUND_DIGITS
        ),
        "n_comments_github": compute_distribution_stats(
            [g["n_comments_github"] for g in games], STATS_ROUND_DIGITS
        ),
    }
