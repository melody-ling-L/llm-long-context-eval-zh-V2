import unittest

import pandas as pd

from src.metrics_v2 import (
    attach_badcase_taxonomy,
    attach_judge_annotations,
    score_results_v2,
)


def _base_row(**overrides):
    row = {
        "model": "test-model",
        "sample_id": "sample-1",
        "model_response": "海外市场需求疲软",
        "expected_answer": "海外市场需求疲软导致订单下滑",
        "answer_aliases": '["海外需求疲软"]',
        "scoring_mode": "judge",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cached_tokens": 0,
        "latency_s": 0.1,
        "error": "",
    }
    row.update(overrides)
    return row


class JudgeScoringTests(unittest.TestCase):
    def test_judge_score_overrides_contains_but_not_em(self):
        rows = pd.DataFrame([_base_row()])
        annotations = pd.DataFrame(
            [
                {
                    "model": "test-model",
                    "sample_id": "sample-1",
                    "judge_score": 1,
                    "judge_reason": "语义一致",
                    "judge_method": "manual_review",
                }
            ]
        )

        scored = score_results_v2(rows, judge_annotations=annotations).iloc[0]

        self.assertEqual(scored["lexical_contains_score"], 0)
        self.assertEqual(scored["contains_score"], 1)
        self.assertEqual(scored["em_score"], 0)
        self.assertEqual(scored["judge_status"], "adjudicated")
        self.assertEqual(scored["score_source"], "judge")

    def test_unadjudicated_judge_keeps_lexical_score_and_is_visible(self):
        rows = pd.DataFrame([_base_row()])
        scored = score_results_v2(
            rows,
            judge_annotations=pd.DataFrame(
                columns=["model", "sample_id", "judge_score", "judge_reason", "judge_method"]
            ),
        ).iloc[0]

        self.assertEqual(scored["contains_score"], scored["lexical_contains_score"])
        self.assertEqual(scored["judge_status"], "unadjudicated")
        self.assertEqual(scored["score_source"], "lexical")

    def test_auto_mode_ignores_judge_annotation(self):
        rows = pd.DataFrame(
            [
                _base_row(
                    scoring_mode="auto",
                    model_response="错误答案",
                    expected_answer="正确答案",
                    answer_aliases="[]",
                )
            ]
        )
        annotations = pd.DataFrame(
            [
                {
                    "model": "test-model",
                    "sample_id": "sample-1",
                    "judge_score": 1,
                    "judge_reason": "不应应用",
                    "judge_method": "manual_review",
                }
            ]
        )

        scored = score_results_v2(rows, judge_annotations=annotations).iloc[0]

        self.assertEqual(scored["contains_score"], 0)
        self.assertEqual(scored["judge_status"], "not_required")
        self.assertEqual(scored["score_source"], "lexical")

    def test_annotation_merge_preserves_order_and_count(self):
        rows = pd.DataFrame(
            [
                _base_row(sample_id="sample-2"),
                _base_row(sample_id="sample-1"),
            ]
        )
        annotations = pd.DataFrame(
            [
                {
                    "model": "test-model",
                    "sample_id": "sample-1",
                    "judge_score": 1,
                    "judge_reason": "语义一致",
                    "judge_method": "manual_review",
                }
            ]
        )

        merged = attach_judge_annotations(rows, annotations)

        self.assertEqual(merged["sample_id"].tolist(), ["sample-2", "sample-1"])
        self.assertEqual(len(merged), 2)
        self.assertTrue(pd.isna(merged.iloc[0]["judge_score"]))
        self.assertEqual(merged.iloc[1]["judge_score"], 1)

    def test_judge_hit_has_distinct_badcase_taxonomy(self):
        rows = pd.DataFrame([_base_row(task="multi_hop")])
        annotations = pd.DataFrame(
            [
                {
                    "model": "test-model",
                    "sample_id": "sample-1",
                    "judge_score": 1,
                }
            ]
        )

        scored = score_results_v2(rows, judge_annotations=annotations)
        annotated = attach_badcase_taxonomy(scored).iloc[0]

        self.assertEqual(annotated["badcase_taxonomy"], "judge 语义正确（字面不匹配）")
        self.assertEqual(annotated["is_badcase"], 1)


if __name__ == "__main__":
    unittest.main()
