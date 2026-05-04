import unittest
import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin")
os.environ.setdefault("LLM_API_KEY", "test-key")

from teaching_eval.report_markdown import sync_report_markdown
from teaching_eval.scoring_controller import apply_scoring_rules


class ScoringConsistencyTests(unittest.TestCase):
    def test_adjusted_score_uses_total_once_not_llm_adjusted(self):
        result = apply_scoring_rules(
            llm_score_general=30,
            llm_score_specific=37,
            llm_score_total=67,
            llm_adjusted_score=64,
            tci={"total": 90, "consistency_level": "高度一致"},
            issues=[{"severity": "major"}],
        )

        self.assertEqual(result["score_total"], 67)
        self.assertEqual(result["buffer_deduction"], 3)
        self.assertEqual(result["adjusted_score"], 64)
        self.assertEqual(result["conclusion"], "及格")

    def test_score_total_is_recomputed_from_subscores(self):
        result = apply_scoring_rules(
            llm_score_general=30,
            llm_score_specific=37,
            llm_score_total=80,
            tci={"total": 90, "consistency_level": "高度一致"},
        )

        self.assertEqual(result["score_total"], 67)
        self.assertEqual(result["adjusted_score"], 67)

    def test_incomplete_clause_scores_soft_fallback_is_flagged(self):
        result = apply_scoring_rules(
            llm_score_general=30,
            llm_score_specific=37,
            llm_score_total=67,
            clause_scores=[
                {"clause_code": "G1", "max_score": 4, "actual_score": 4},
            ],
        )

        self.assertEqual(result["score_total"], 67)
        self.assertTrue(any("条款评分明细不完整" in flag for flag in result["review_flags"]))

    def test_complete_clause_scores_are_authoritative_for_totals(self):
        clause_scores = [
            {"clause_code": "G1", "max_score": 4, "actual_score": 4},
            {"clause_code": "G2", "max_score": 10, "actual_score": 5},
            {"clause_code": "G3", "max_score": 10, "actual_score": 9},
            {"clause_code": "G4", "max_score": 11, "actual_score": 10},
            {"clause_code": "G5", "max_score": 6, "actual_score": 5},
            {"clause_code": "G6", "max_score": 4, "actual_score": 4},
            {"clause_code": "S1", "max_score": 15, "actual_score": 14},
            {"clause_code": "S2", "max_score": 10, "actual_score": 9},
            {"clause_code": "S3", "max_score": 10, "actual_score": 8},
            {"clause_code": "S4", "max_score": 10, "actual_score": 9},
            {"clause_code": "S5", "max_score": 10, "actual_score": 2},
        ]
        result = apply_scoring_rules(
            llm_score_general=38,
            llm_score_specific=42,
            llm_score_total=80,
            clause_scores=clause_scores,
            issues=[{"severity": "major"}, {"severity": "major"}],
            tci={"total": 90, "consistency_level": "高度一致"},
        )

        self.assertEqual(result["score_general"], 37)
        self.assertEqual(result["score_specific"], 42)
        self.assertEqual(result["score_total"], 79)
        self.assertEqual(result["buffer_deduction"], 3)
        self.assertEqual(result["adjusted_score"], 76)

    def test_missing_tci_does_not_lock_score_to_55(self):
        result = apply_scoring_rules(
            llm_score_general=40,
            llm_score_specific=45,
            llm_score_total=85,
            tci={},
        )

        self.assertEqual(result["ceiling"], 100)
        self.assertEqual(result["adjusted_score"], 85)
        self.assertEqual(result["conclusion"], "良好")

    def test_tci_level_without_number_does_not_default_to_zero(self):
        result = apply_scoring_rules(
            llm_score_general=40,
            llm_score_specific=45,
            llm_score_total=85,
            tci={"total": 0, "consistency_level": "高度一致"},
        )

        self.assertEqual(result["ceiling"], 100)
        self.assertEqual(result["adjusted_score"], 85)

    def test_ceiling_keyword_requires_severe_issue_context(self):
        result = apply_scoring_rules(
            llm_score_general=40,
            llm_score_specific=45,
            llm_score_total=85,
            issues=[{
                "severity": "minor",
                "issue_category": "教学目标与内容闭环",
                "issue_subcategory": "内容表述",
                "issue_text": "教学内容纯基础理论扎实，可继续强化临床迁移。",
            }],
        )

        self.assertEqual(result["ceiling"], 100)
        self.assertEqual(result["adjusted_score"], 85)

    def test_ceiling_triggers_for_fatal_clinical_deviation(self):
        result = apply_scoring_rules(
            llm_score_general=45,
            llm_score_specific=50,
            llm_score_total=95,
            issues=[{
                "severity": "fatal",
                "issue_category": "教学内容偏离临床实践",
                "issue_subcategory": "偏离临床实践",
                "issue_text": "课程主体为纯基础研究，偏离临床实践。",
            }],
        )

        self.assertEqual(result["ceiling"], 55)
        self.assertEqual(result["adjusted_score"], 55)

    def test_high_score_review_caps_major_or_fatal_issues(self):
        result = apply_scoring_rules(
            llm_score_general=45,
            llm_score_specific=55,
            llm_score_total=100,
            issues=[{
                "severity": "major",
                "issue_category": "教学评价与反馈",
                "evidence_position": "教学评价部分",
                "issue_text": "评价任务缺少可执行标准。",
            }],
        )

        self.assertEqual(result["adjusted_score"], 89)
        self.assertEqual(result["conclusion"], "良好")
        self.assertTrue(any("高分复核" in flag for flag in result["review_flags"]))

    def test_low_score_review_flags_sparse_evidence_without_changing_score(self):
        result = apply_scoring_rules(
            llm_score_general=25,
            llm_score_specific=30,
            llm_score_total=55,
            issues=[],
        )

        self.assertEqual(result["adjusted_score"], 55)
        self.assertTrue(any("低分复核" in flag for flag in result["review_flags"]))

    def test_interaction_density_guard_caps_clause_and_recomputes_total(self):
        result = apply_scoring_rules(
            llm_score_general=40,
            llm_score_specific=50,
            llm_score_total=90,
            issues=[{
                "clause_code": "S2",
                "clause_name": "互动密度",
                "severity": "major",
                "issue_category": "教学设计与流程",
                "issue_subcategory": "仅写加强互动无具体设计",
                "evidence_position": "教学过程部分",
                "issue_text": "仅写加强互动，无具体问题或任务设计。",
            }],
            clause_scores=[
                {"clause_code": "S2", "clause_name": "互动密度", "max_score": 15, "actual_score": 12},
            ],
        )

        self.assertEqual(result["clause_scores"][0]["actual_score"], 3)
        self.assertEqual(result["score_specific"], 41)
        self.assertEqual(result["score_total"], 81)
        self.assertEqual(result["adjusted_score"], 78)
        self.assertTrue(any("互动密度复核" in flag for flag in result["review_flags"]))

    def test_report_markdown_score_overview_matches_summary(self):
        markdown = """# 报告

## 一、基本信息

| 项目 | 内容 |
|------|------|
| 课程内容 | 测试 |

## 二、评分总览

| 维度 | 得分 | 满分 |
|------|------|------|
| **调整后总分 (adjusted_score)** | **54** | **100** |
| **最终结论** | **及格** | — |

## 三、否决项检查

- 未触发。
"""
        summary = {
            "score_general": 27,
            "score_specific": 30,
            "score_total": 57,
            "adjusted_score": 54,
            "buffer_deduction": 3,
            "conclusion": "不合格",
        }

        synced = sync_report_markdown(markdown, summary, {"tci_deduction": 0, "ceiling": 100})

        self.assertIn("| **调整后总分 (adjusted_score)** | **54** | **100** |", synced)
        self.assertIn("| **最终结论** | **不合格** | — |", synced)
        self.assertNotIn("| **最终结论** | **及格** | — |", synced)

    def test_report_markdown_updates_basic_info_conclusion_row(self):
        markdown = """# 报告

## 一、基本信息

| 项目 | 内容 |
|------|------|
| **最终结论** | **及格** |

## 二、评分总览

| 维度 | 得分 | 满分 |
|------|------|------|
| **调整后总分 (adjusted_score)** | **64** | **100** |
| **最终结论** | **及格** | — |
"""
        summary = {
            "score_general": 30,
            "score_specific": 37,
            "score_total": 67,
            "adjusted_score": 59,
            "buffer_deduction": 5,
            "conclusion": "不合格",
        }

        synced = sync_report_markdown(markdown, summary, {"tci_deduction": 3, "ceiling": 100})

        self.assertIn("| **最终结论** | **不合格** |", synced)
        self.assertIn("| **最终结论** | **不合格** | — |", synced)
        self.assertNotIn("**及格**", synced)

    def test_report_markdown_replaces_score_overview_variants_and_tail_summary(self):
        markdown = """# 报告

## 一、基本信息

| 项目 | 内容 |
|------|------|
| 总分（调整后） | **62 / 100** |
| 结论 | **及格** |

## 二、评分概览

| 维度 | 满分 | 得分 |
|------|------|------|
| 通用维度（G1-G6） | 45 | 30 |
| 分项维度 | 55 | 35 |
| Buffer 扣分（黄色） | - | -3 |
| **调整后总分 (adjusted_score)** | **62** | **100** |

## 三、类型一致性指数（TCI）

| **TCI 总分** | **90/100** | **高度一致** |

## 七、结论

经调整后总分为62分，结论为**及格**。
"""
        summary = {
            "score_general": 30,
            "score_specific": 35,
            "score_total": 65,
            "adjusted_score": 60,
            "buffer_deduction": 5,
            "conclusion": "及格",
        }

        synced = sync_report_markdown(markdown, summary, {"tci_deduction": 0, "ceiling": 100})

        self.assertIn("| 总分（调整后） | **60 / 100** |", synced)
        self.assertIn("| **调整后总分 (adjusted_score)** | **60** | **100** |", synced)
        self.assertIn("经调整后总分为60分，结论为**及格**。", synced)
        self.assertNotIn("62", synced)
        self.assertNotIn("Buffer 扣分（黄色）", synced)

    def test_report_markdown_removes_duplicate_llm_score_overview(self):
        markdown = """# 报告

## 1. 基本信息

| 项目 | 内容 |
|------|------|
| 课程内容 | 测试 |

## 2. 评分总览

| 维度 | 得分 | 满分 |
|------|------|------|
| **总分 (score_total)** | **75** | **100** |
| 风险缓冲扣分 | -3 | - |
| **调整后总分 (adjusted_score)** | **72** | **100** |

## 3. 条款详情

| 条款 | 得分 |
|------|------|
| G1 | 4 |
"""
        summary = {
            "score_general": 35,
            "score_specific": 40,
            "score_total": 75,
            "adjusted_score": 70,
            "buffer_deduction": 5,
            "conclusion": "中等",
        }

        synced = sync_report_markdown(markdown, summary, {"tci_deduction": 0, "ceiling": 100})

        self.assertEqual(synced.count("评分总览"), 1)
        self.assertIn("| Buffer 风险扣分 | -5 | — |", synced)
        self.assertIn("| **调整后总分 (adjusted_score)** | **70** | **100** |", synced)
        self.assertNotIn("风险缓冲扣分 | -3", synced)
        self.assertNotIn("**72**", synced)

    def test_report_markdown_shows_red_fallback_warning(self):
        markdown = """# 报告

## 一、基本信息

| 项目 | 内容 |
|------|------|
| 课程内容 | 测试 |
"""
        summary = {
            "score_general": 30,
            "score_specific": 37,
            "score_total": 67,
            "adjusted_score": 67,
            "buffer_deduction": 0,
            "conclusion": "及格",
        }
        synced = sync_report_markdown(markdown, summary, {
            "tci_deduction": 0,
            "ceiling": 100,
            "review_flags": ["条款评分明细不完整，系统已暂用汇总分完成软处理；建议重新评审。"],
        })

        self.assertIn('style="color:#c2413a;font-weight:700;"', synced)
        self.assertIn("建议重新评审", synced)


if __name__ == "__main__":
    unittest.main()
