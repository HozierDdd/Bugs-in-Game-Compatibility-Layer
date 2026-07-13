# discussion_pair

兼容报告与其后续讨论评论的配对标注数据集，共 33 个分片。

| 目录 | 说明 |
|------|------|
| `unlabel_cr_discussion_pair/` | 未标注的配对数据（split_0–32） |
| `labeled_cr_discussion_pair/round_1/` | 第一轮标注结果（annotator_B / annotator_A 两名标注员各自独立标注） |
| `labeled_cr_discussion_pair/round_2/` | 第二轮标注结果（合并后）|

**标注目标**：判断每条讨论评论是否与兼容报告问题直接相关，标注字段 `is_for_the_report`（`"true"` / `"false"`）。

**主要字段**：`issue_number`、`compatibility_report`、`following_discussion`（含 `discussion_body`、`is_for_the_report`）
