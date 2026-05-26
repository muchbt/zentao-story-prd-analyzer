# 阶段六实施计划：需求点拆分与逐点追溯

**日期**: 2026-05-26
**状态**: 执行中

---

## 实施顺序（依赖链）

```
1. analysis_result.py  (RequirementPoint 模型 + 解析/校验/汇总)
   ↓
2. prompts.py  (Feature prompt 更新)
   ↓
3. analyzer.py  (集成 RP 逻辑)
   ↓
4. document_generator.py  (PRD 表格)
   ↓
5. summary_report.py  (索引字段)
   ↓
6. debug_bundle.py  (保存 RP)
   ↓
7. main.py  (主流程集成 + stdout JSON)
   ↓
8. test_main_phase6.py  (新测试)
   ↓
9. 更新既有测试 → 全量运行确认通过
```

---

## 任务 1：`analysis_result.py` — 新增 RequirementPoint 数据模型及解析/校验/汇总逻辑

**文件**: `zentao_analyzer/analysis_result.py`

1. 新增 `RequirementPoint` 数据类：
   - `id: str` (RP-001, RP-002…)
   - `description: str`
   - `status: str` (完成/部分完成/未完成/无法判断)
   - `reason: str`
   - `gaps: List[str]`
   - `evidence: List[EvidenceLocation]`
   - `_original_status: str` (校验前原始值，仅 Debug Bundle 用)
   - `_correction_reason: str` (修正原因，仅 Debug Bundle 用)

2. 在 `AnalysisResult` 新增字段：
   - `requirement_points: List[RequirementPoint]`
   - `analysis_status: str` (空或 `"requirement_points_unavailable"`)

3. 新增 `RequirementPointStatus` 常量: `COMPLETED = "完成"`, `PARTIALLY_COMPLETED = "部分完成"`, `NOT_COMPLETED = "未完成"`, `INDETERMINATE = "无法判断"`

4. 新增 `parse_requirement_points(data)` — 从 LLM JSON 的 `requirement_points` 数组解析为 `List[RequirementPoint]`，为每个分配运行内 ID (RP-001, RP-002…)

5. 新增 `validate_requirement_points(rps)` — 校验：
   - 数组非空、每个 RP 必要字段存在
   - `status` 值合法
   - 状态-缺口合约：`未完成`/`部分完成` 必须有非空 `gaps`；`完成`/`无法判断` 的 `gaps` 必须为空
   - 不允许完全重复的 `description`
   - 返回 `(valid_rps_or_None, failure_reason)`

6. 新增 `compute_item_conclusion(rps) -> str` — 按设计文档 §4 汇总规则

7. 新增 `compute_item_gaps(rps) -> List[str]` — 聚合逐点 `gaps`，每条附加 RP ID

8. 新增 `compute_item_confidence(rps, has_fallback_evidence, has_invalid_evidence) -> str`

9. 新增 `aggregate_evidence_from_rps(rps) -> List[EvidenceLocation]` — 去重聚合各点有效证据

10. 新增 `validate_rp_evidence_locations(rps, repo_path)` — 逐点校验证据位置

11. 新增 `correct_invalidated_rps(rps, rp_validation_issues)` — 修正校验失败的 RP 为 `无法判断`

---

## 任务 2：`prompts.py` — 更新 Feature Agent 提示模板

**文件**: `zentao_analyzer/prompts.py`

1. Feature prompt JSON Schema 替换为包含 `requirement_points` 数组的新 schema
2. 明确告知 Agent 不再返回顶层 `conclusion`、`gaps`、`confidence`、`evidence`
3. Defect prompt 完全不动
4. 保留 `_COMMON_SCHEMA` 供 Defect prompt 继续使用

---

## 任务 3：`analyzer.py` — 集成需求点解析、校验、修正、汇总

**文件**: `zentao_analyzer/analyzer.py`

1. Feature Item 分析流程改为使用需求点汇总
2. Defect Item 分析流程完全不变
3. 新增 `_analyze_feature()` 内部函数处理 Feature Item 专属逻辑
4. Feature Item 顶层 conclusion/gaps/confidence/evidence 由 RP 汇总生成
5. 证据校验逻辑对 Feature Item 改用 `validate_rp_evidence_locations`

---

## 任务 4：`document_generator.py` — PRD 新增需求点完成情况表格

**文件**: `zentao_analyzer/document_generator.py`

1. 新增 `_render_requirement_points_table(analysis)`
2. 在 `## 实现完成度` 之后、`## 关键代码证据` 之前插入 `## 需求点完成情况`
3. `## 差异与缺口` 每条缺口前加 RP ID 前缀
4. Feature Item 的 `## 关键代码证据` 展示去重后的可定位证据
5. Defect Item PRD 不变

---

## 任务 5：`summary_report.py` — 新增需求点索引字段

**文件**: `zentao_analyzer/summary_report.py`

1. `build_summary_item` 新增 `requirement_points` 参数
2. Feature Item 增加三个索引字段：`requirement_point_count`、`requirement_point_status_counts`、`has_unconfirmed_requirement_points`
3. `requirement_points_unavailable` 时输出对应的索引值

---

## 任务 6：`debug_bundle.py` — 保存需求点完整结构

**文件**: `zentao_analyzer/debug_bundle.py`

1. 新增 `write_requirement_points(self, item_id, rps)` 方法
2. 保存完整需求点结构到 `requirement_points/{item_id}.json`

---

## 任务 7：`main.py` — 集成需求点到主流程和 stdout JSON

**文件**: `zentao_analyzer/main.py`

1. Feature Item 从 result 获取 `requirement_points` 和 `analysis_status`
2. 最终 stdout JSON 增加 `requirement_points` 和 `analysis_status` 字段
3. Debug Bundle 写入需求点数据
4. `requirement_points_unavailable` 时 exit code 1

---

## 任务 8：测试文件 `test_main_phase6.py`

覆盖场景：
1. Feature Item 返回完整 requirement_points → 顶层结论由汇总计算
2. Feature Item 无 requirement_points → analysis_status = "requirement_points_unavailable"
3. RP 状态-缺口合约校验失败 → requirement_points_unavailable
4. RP 证据位置校验失败 → 该点修正为 无法判断
5. 全部完成 → 结论 完成，confidence 高
6. 混合状态 → 结论 部分完成
7. 全部 无法判断 → 结论 无法判断，confidence 低
8. PRD 包含需求点完成情况表格
9. Summary 包含 requirement_point_count 等字段
10. Defect Item 不受影响
11. 顶层 gaps 带 RP ID 前缀
12. 顶层 evidence 由 RP 聚合去重
13. 重复 description → invalid_requirement_point_schema
14. 同一证据位置支持多个需求点

---

## 不在本次实施范围内

- Code Side、Analysis Scope、Responsibility Hint、Candidate Location — 阶段七
- Defect Item 需求点拆分 — 设计明确排除
- 补充需求内容 (Supplemental Requirement Context) — 已废弃