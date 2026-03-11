"""
RAG検索品質の回帰テスト。

CI連携: 検索・インジェスション・エージェントコード変更時に自動実行。
メトリクスが閾値を下回った場合にテスト失敗（マージブロック）。

実行方法:
    pytest evaluation/test_evaluation.py --directory-ids "1,2,3" --min-ndcg 0.3 --min-mrr 0.4
"""

import pytest

from evaluation.evaluation_runner import run_evaluation
from evaluation.metrics import (
    compute_all_metrics,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


# --- 単体テスト: メトリクス関数 ---


class TestPrecisionAtK:
    def test_perfect_precision(self):
        assert precision_at_k([1, 2, 3], [1, 2, 3], 3) == 1.0

    def test_zero_precision(self):
        assert precision_at_k([4, 5, 6], [1, 2, 3], 3) == 0.0

    def test_partial_precision(self):
        assert precision_at_k([1, 4, 2, 5, 3], [1, 2, 3], 5) == pytest.approx(0.6)

    def test_k_larger_than_results(self):
        assert precision_at_k([1, 2], [1, 2, 3], 5) == pytest.approx(2 / 2)

    def test_empty_retrieved(self):
        assert precision_at_k([], [1, 2], 5) == 0.0

    def test_k_zero(self):
        assert precision_at_k([1, 2], [1], 0) == 0.0


class TestRecallAtK:
    def test_perfect_recall(self):
        assert recall_at_k([1, 2, 3], [1, 2, 3], 3) == 1.0

    def test_zero_recall(self):
        assert recall_at_k([4, 5, 6], [1, 2, 3], 3) == 0.0

    def test_partial_recall(self):
        assert recall_at_k([1, 4, 5], [1, 2, 3], 3) == pytest.approx(1 / 3)

    def test_empty_relevant(self):
        assert recall_at_k([1, 2], [], 5) == 0.0


class TestMRR:
    def test_first_position(self):
        assert mean_reciprocal_rank([1, 2, 3], [1]) == 1.0

    def test_second_position(self):
        assert mean_reciprocal_rank([4, 1, 3], [1]) == pytest.approx(0.5)

    def test_not_found(self):
        assert mean_reciprocal_rank([4, 5, 6], [1]) == 0.0

    def test_multiple_relevant(self):
        assert mean_reciprocal_rank([4, 1, 2], [1, 2]) == pytest.approx(0.5)


class TestNDCG:
    def test_perfect_ranking(self):
        retrieved = [1, 2, 3]
        relevance = {1: 2, 2: 1, 3: 1}
        assert ndcg_at_k(retrieved, relevance, 3) == pytest.approx(1.0)

    def test_empty_relevance(self):
        assert ndcg_at_k([1, 2, 3], {}, 3) == 0.0

    def test_k_zero(self):
        assert ndcg_at_k([1, 2], {1: 2}, 0) == 0.0

    def test_no_relevant_in_results(self):
        assert ndcg_at_k([4, 5, 6], {1: 2, 2: 1}, 3) == 0.0


class TestComputeAllMetrics:
    def test_all_metrics_computed(self):
        metrics = compute_all_metrics(
            retrieved_ids=[1, 2, 3, 4, 5],
            relevant_ids=[1, 3, 5],
            relevance_scores={1: 2, 3: 1, 5: 1},
        )
        assert "precision_at_5" in metrics
        assert "recall_at_10" in metrics
        assert "mrr" in metrics
        assert "ndcg_at_10" in metrics


# --- 統合テスト: 評価ランナー ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluation_metrics_above_threshold(
    directory_ids,
    min_ndcg,
    min_mrr,
):
    """
    RAG検索品質が閾値以上であることを検証する回帰テスト。

    CI環境で実行し、メトリクスが閾値を下回った場合にマージをブロックする。
    """
    report = await run_evaluation(
        directory_ids=directory_ids,
        query_type="semantic_search",
    )

    aggregates = report.get("aggregates", {})

    if aggregates.get("annotated_query_count", 0) == 0:
        pytest.skip("アノテーション済みクエリがありません")

    actual_ndcg = aggregates.get("mean_ndcg_at_10", 0.0)
    actual_mrr = aggregates.get("mean_mrr", 0.0)

    assert actual_ndcg >= min_ndcg, (
        f"nDCG@10 ({actual_ndcg:.4f}) が閾値 ({min_ndcg:.4f}) を下回っています"
    )
    assert actual_mrr >= min_mrr, (
        f"MRR ({actual_mrr:.4f}) が閾値 ({min_mrr:.4f}) を下回っています"
    )
