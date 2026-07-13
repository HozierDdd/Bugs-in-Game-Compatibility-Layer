# cr_symptom (random_sampling)

对随机抽样兼容报告进行症状标注的数据集，共 33 个分片，由两名标注员各自完成多轮标注。

| 目录/文件 | 说明 |
|-----------|------|
| `unlabel_cr_symptom/` | 未标注的原始分片（part001–033） |
| `labeled_symptom_annotator_1/` | 标注员 1 的标注结果（round_1 / round_2） |
| `labeled_symptom_annotator_2/` | 标注员 2 的标注结果（round_1 / round_2 / enhanced） |
| `Global Tags for Symptom Annotator.json` | 允许使用的症状标签列表（如 Black Screen、Freeze、Launch Failure 等） |
| `label_persentage_count.json` | 各标签的数量与占比统计 |

**标注字段**：在原始 `compatibility_report` 基础上增加 `symptom_summary`（摘要）和 `tags`（症状标签数组）。
