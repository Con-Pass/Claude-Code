"""
RAG検索品質のオフライン評価メトリクス。

Precision@K, Recall@K, MRR, nDCG@K を計算する。
"""

import math
from typing import Dict, List


def precision_at_k(
    retrieved_ids: List[int],
    relevant_ids: List[int],
    k: int,
) -> float:
    """
    Precision@K: 上位K件中の関連ドキュメントの割合。

    Args:
        retrieved_ids: 検索結果のcontract_idリスト（スコア降順）
        relevant_ids: 正解のcontract_idリスト
        k: 評価する上位件数
    """
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for rid in top_k if rid in relevant_set)
    return hits / len(top_k)


def recall_at_k(
    retrieved_ids: List[int],
    relevant_ids: List[int],
    k: int,
) -> float:
    """
    Recall@K: 正解ドキュメントのうち上位K件に含まれる割合。

    Args:
        retrieved_ids: 検索結果のcontract_idリスト（スコア降順）
        relevant_ids: 正解のcontract_idリスト
        k: 評価する上位件数
    """
    if not relevant_ids or k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    hits = sum(1 for rid in top_k if rid in relevant_set)
    return hits / len(relevant_ids)


def mean_reciprocal_rank(
    retrieved_ids: List[int],
    relevant_ids: List[int],
) -> float:
    """
    MRR: 最初の関連ドキュメントの順位の逆数。

    Args:
        retrieved_ids: 検索結果のcontract_idリスト（スコア降順）
        relevant_ids: 正解のcontract_idリスト
    """
    relevant_set = set(relevant_ids)
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(
    retrieved_ids: List[int],
    relevance_scores: Dict[int, int],
    k: int,
) -> float:
    """
    nDCG@K: Normalized Discounted Cumulative Gain。

    Args:
        retrieved_ids: 検索結果のcontract_idリスト（スコア降順）
        relevance_scores: contract_id -> 関連度スコア（2=高, 1=中, 0=非関連）のマッピング
        k: 評価する上位件数
    """
    if k <= 0 or not relevance_scores:
        return 0.0

    # DCG計算
    top_k = retrieved_ids[:k]
    dcg = 0.0
    for i, rid in enumerate(top_k):
        rel = relevance_scores.get(rid, 0)
        dcg += (2**rel - 1) / math.log2(i + 2)  # i+2 because log2(1) = 0

    # Ideal DCG計算
    ideal_rels = sorted(relevance_scores.values(), reverse=True)[:k]
    idcg = 0.0
    for i, rel in enumerate(ideal_rels):
        idcg += (2**rel - 1) / math.log2(i + 2)

    if idcg == 0.0:
        return 0.0

    return dcg / idcg


def compute_all_metrics(
    retrieved_ids: List[int],
    relevant_ids: List[int],
    relevance_scores: Dict[int, int],
) -> Dict[str, float]:
    """
    全メトリクスを一括計算する。

    Args:
        retrieved_ids: 検索結果のcontract_idリスト（スコア降順）
        relevant_ids: 正解のcontract_idリスト
        relevance_scores: contract_id -> 関連度スコアのマッピング

    Returns:
        各メトリクスの値を含む辞書
    """
    return {
        "precision_at_5": precision_at_k(retrieved_ids, relevant_ids, 5),
        "precision_at_10": precision_at_k(retrieved_ids, relevant_ids, 10),
        "recall_at_5": recall_at_k(retrieved_ids, relevant_ids, 5),
        "recall_at_10": recall_at_k(retrieved_ids, relevant_ids, 10),
        "mrr": mean_reciprocal_rank(retrieved_ids, relevant_ids),
        "ndcg_at_5": ndcg_at_k(retrieved_ids, relevance_scores, 5),
        "ndcg_at_10": ndcg_at_k(retrieved_ids, relevance_scores, 10),
    }
