"""
Step 3：GitHub 正式讨论量分析。

流式处理所有 GitHub issue chunk，完成：
  1. 线程级别的兼容性报告检测（post 级分类）
  2. 按 appid 聚合游戏级指标
  3. 计算分布统计
  4. 输出线程详情和游戏摘要两个文件
"""

from src.config import (
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    STEP3_OUTPUT,
    STEP3_THREADS_OUTPUT,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
)
from src.loaders.github_loader import iter_github_issues, count_github_chunks
from src.transforms.github_transform import (
    aggregate_threads_by_game,
    compute_appid_rule_breakdown,
    compute_github_distributions,
)
from src.utils.json_io import save_json
from src.utils.datetime_utils import now_utc_iso


def run() -> dict:
    print("[Step 3] GitHub 正式讨论量分析...")

    n_chunks = count_github_chunks()
    print(f"  共 {n_chunks} 个 chunk 文件，开始流式处理...")

    # 流式聚合（生成器传入，不一次性加载）
    issue_iter = iter_github_issues()
    thread_records, game_stats, unresolved_count = aggregate_threads_by_game(issue_iter)

    total_issues = len(thread_records)
    total_reports = sum(t["n_reports_in_thread"] for t in thread_records)
    body_reports = sum(1 for t in thread_records if t["thread_has_body_report"])
    comment_reports = sum(t["n_comment_reports"] for t in thread_records)

    n_created_at    = sum(1 for t in thread_records if t.get("inclusion_method") == "created_at")
    n_thread_median = sum(1 for t in thread_records if t.get("inclusion_method") == "thread_median")

    print(f"  时间窗口内 issue 总数:       {total_issues}")
    print(f"    - created_at 筛选纳入:     {n_created_at}")
    print(f"    - thread_median 筛选纳入:  {n_thread_median}")
    print(f"  无法解析 appid:              {unresolved_count} ({unresolved_count/max(total_issues,1)*100:.1f}%)")
    print(f"  识别为兼容性报告的帖子总数:  {total_reports}")
    print(f"    - issue 正文报告:          {body_reports}")
    print(f"    - 评论中的报告:            {comment_reports}")
    print(f"  覆盖游戏数 (可解析 appid):   {len(game_stats)}")

    # AppID 解析规则分布
    rule_breakdown = compute_appid_rule_breakdown(thread_records)
    print("  AppID 解析规则分布:")
    rule_labels = {
        "parentheses": "规则 1（标题末尾括号）",
        "steam_url":   "规则 2（正文 Steam URL）",
        "standalone":  "规则 3（标题孤立整数）",
        "unresolved":  "无法解析",
    }
    for rule, stats in rule_breakdown.items():
        label = rule_labels.get(rule, rule)
        print(f"    {label}: {stats['n_games']} 个游戏 / {stats['n_issues']} 个 issue")

    # 分布统计
    distributions = compute_github_distributions(game_stats)
    for metric, dist in distributions.items():
        print(f"  {metric} 分布 — 中位数: {dist['median']}, P90: {dist['p90']}, 最大值: {dist['max']}")

    # 游戏列表（按 n_reports_github 降序）
    games_list = sorted(
        game_stats.values(),
        key=lambda g: g["n_reports_github"],
        reverse=True,
    )

    # 线程列表（按 issue number 升序）
    threads_sorted = sorted(thread_records, key=lambda t: t["issue_number"])

    # ── 输出文件 1：游戏级摘要 ──────────────────────────────────────────────
    result = {
        "step": "step3_github",
        "generated_at": now_utc_iso(),
        "time_window": {
            "start": TIME_WINDOW_START.isoformat(),
            "end": TIME_WINDOW_END.isoformat(),
        },
        "github_chunks_dir": str(GITHUB_CHUNKS_DIR),
        "github_chunk_glob": GITHUB_CHUNK_GLOB,
        "summary": {
            "n_chunks": n_chunks,
            "total_issues_in_window": total_issues,
            "inclusion_method_breakdown": {
                "created_at": n_created_at,
                "thread_median": n_thread_median,
            },
            "unresolved_appid_issues": unresolved_count,
            "n_games_with_resolved_appid": len(game_stats),
            "total_compatibility_reports_detected": total_reports,
            "reports_from_issue_body": body_reports,
            "reports_from_comments": comment_reports,
            "appid_rule_breakdown": rule_breakdown,
            "distributions": distributions,
        },
        "games": games_list,
    }

    save_json(result, STEP3_OUTPUT)
    print(f"  → 游戏摘要已保存至: {STEP3_OUTPUT}")

    # ── 输出文件 2：线程详情 ────────────────────────────────────────────────
    threads_output = {
        "step": "step3_github_threads",
        "generated_at": now_utc_iso(),
        "time_window": {
            "start": TIME_WINDOW_START.isoformat(),
            "end": TIME_WINDOW_END.isoformat(),
        },
        "total_threads": len(threads_sorted),
        "threads": threads_sorted,
    }

    save_json(threads_output, STEP3_THREADS_OUTPUT)
    print(f"  → 线程详情已保存至: {STEP3_THREADS_OUTPUT}")

    return result


if __name__ == "__main__":
    run()
