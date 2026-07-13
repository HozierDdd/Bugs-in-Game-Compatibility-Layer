# cr_selection

从筛选后的 Issue 中提取兼容报告（Compatibility Report，CR），并进行人工标注的数据集。

| 文件/目录 | 说明 |
|-----------|------|
| `all_report.json` | 全量兼容报告 |
| `random_sampling_report.json` | 随机抽样后的兼容报告 |
| `report_discussion_pair.json` | 报告与后续讨论的配对数据（合并） |
| `cr_symptom(random_sampling)/` | 症状标注数据（标注员 1/2，多轮） |
| `discussion_pair/` | 报告-讨论配对标注数据（多轮） |
| `legacy/` | 历史版本快照 |

**主要字段**：`issue_number`、`issue_title`、`compatibility_report`（报告正文）
