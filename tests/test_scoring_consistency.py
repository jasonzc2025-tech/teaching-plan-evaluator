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


if __name__ == "__main__":
    unittest.main()
