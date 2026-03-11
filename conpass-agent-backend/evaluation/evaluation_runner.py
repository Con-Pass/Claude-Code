"""
ConPass RAG パイプライン オフライン評価ランナー。

テストクエリセットに対して検索を実行し、品質メトリクスを計算・レポートする。

使用方法:
    # 全クエリを評価
    python -m evaluation.evaluation_runner

    # セマンティック検索のみ評価
    python -m evaluation.evaluation_runner --type semantic_search

    # レポート出力先を指定
    python -m evaluation.evaluation_runner --output evaluation/reports/
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from evaluation.metrics import compute_all_metrics

logger = logging.getLogger(__name__)

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_QUERIES_PATH = Path(__file__).parent / "test_queries.yaml"
DEFAULT_REPORTS_DIR = Path(__file__).parent / "reports"


def load_test_queries(
    queries_path: Path = DEFAULT_QUERIES_PATH,
    query_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """テストクエリをYAMLから読み込む。"""
    with open(queries_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    queries = data.get("queries", [])

    if query_type:
        queries = [q for q in queries if q.get("type") == query_type]

    # expected_contractsが空のクエリを警告
    annotated = [q for q in queries if q.get("expected_contracts")]
    if len(annotated) < len(queries):
        logger.warning(
            f"アノテーション済みクエリ: {len(annotated)}/{len(queries)} "
            f"(未アノテーションのクエリはメトリクス計算をスキップ)"
        )

    return queries


async def run_semantic_search_query(
    query: str,
    directory_ids: List[int],
    top_k: int = 100,
) -> List[Dict[str, Any]]:
    """
    セマンティック検索クエリを実行する。

    Returns:
        検索結果のリスト（各要素にcontract_id, scoreを含む）
    """
    try:
        from app.services.chatbot.tools.semantic_search.semantic_search_tool import (
            semantic_search,
        )

        results = await semantic_search(
            directory_ids=directory_ids,
            query=query,
            similarity_top_k=top_k,
            deduplicate_by_contract=False,  # 全チャンクを取得して評価
        )
        return results
    except Exception as e:
        logger.error(f"セマンティック検索エラー: query='{query}', error={e}")
        return []


def extract_contract_ids(results: List[Dict[str, Any]]) -> List[int]:
    """検索結果からcontract_idリストを抽出（重複排除、スコア順維持）。"""
    seen = set()
    contract_ids = []
    for result in results:
        cid = result.get("contract_id")
        if cid is not None and cid not in seen:
            seen.add(cid)
            contract_ids.append(cid)
    return contract_ids


async def evaluate_query(
    query_data: Dict[str, Any],
    directory_ids: List[int],
) -> Dict[str, Any]:
    """
    単一クエリを評価する。

    Returns:
        クエリID、メトリクス、検索結果を含む辞書
    """
    query_id = query_data["id"]
    query_text = query_data["query"]
    query_type = query_data["type"]
    expected_contracts = query_data.get("expected_contracts", [])
    relevance_scores = query_data.get("relevance", {})

    # 関連度スコアのキーを整数に変換
    relevance_scores = {int(k): v for k, v in relevance_scores.items()}

    logger.info(f"評価中: [{query_id}] {query_text}")

    # 検索実行
    if query_type == "semantic_search":
        results = await run_semantic_search_query(query_text, directory_ids)
    else:
        logger.warning(f"未対応のクエリタイプ: {query_type}")
        results = []

    # contract_id抽出
    retrieved_ids = extract_contract_ids(results)

    # メトリクス計算（アノテーション済みの場合のみ）
    metrics = {}
    if expected_contracts:
        metrics = compute_all_metrics(
            retrieved_ids=retrieved_ids,
            relevant_ids=expected_contracts,
            relevance_scores=relevance_scores,
        )

    return {
        "query_id": query_id,
        "query": query_text,
        "type": query_type,
        "category": query_data.get("category", ""),
        "retrieved_count": len(retrieved_ids),
        "retrieved_contract_ids": retrieved_ids[:20],  # 上位20件のみ保存
        "expected_contracts": expected_contracts,
        "metrics": metrics,
        "has_annotation": bool(expected_contracts),
    }


def compute_aggregate_metrics(
    results: List[Dict[str, Any]],
) -> Dict[str, float]:
    """全クエリの平均メトリクスを計算する。"""
    annotated_results = [r for r in results if r.get("has_annotation")]

    if not annotated_results:
        return {}

    metric_keys = [
        "precision_at_5",
        "precision_at_10",
        "recall_at_5",
        "recall_at_10",
        "mrr",
        "ndcg_at_5",
        "ndcg_at_10",
    ]

    aggregates = {}
    for key in metric_keys:
        values = [r["metrics"].get(key, 0.0) for r in annotated_results]
        aggregates[f"mean_{key}"] = sum(values) / len(values) if values else 0.0

    aggregates["annotated_query_count"] = len(annotated_results)
    aggregates["total_query_count"] = len(results)

    return aggregates


def generate_markdown_report(
    results: List[Dict[str, Any]],
    aggregates: Dict[str, float],
    run_timestamp: str,
) -> str:
    """Markdownレポートを生成する。"""
    lines = [
        f"# ConPass RAG 評価レポート",
        f"",
        f"**実行日時**: {run_timestamp}",
        f"**評価クエリ数**: {len(results)}",
        f"**アノテーション済み**: {aggregates.get('annotated_query_count', 0)}",
        f"",
        f"## 集約メトリクス",
        f"",
        f"| メトリクス | 値 |",
        f"|-----------|-----|",
    ]

    metric_labels = {
        "mean_precision_at_5": "Mean Precision@5",
        "mean_precision_at_10": "Mean Precision@10",
        "mean_recall_at_5": "Mean Recall@5",
        "mean_recall_at_10": "Mean Recall@10",
        "mean_mrr": "Mean MRR",
        "mean_ndcg_at_5": "Mean nDCG@5",
        "mean_ndcg_at_10": "Mean nDCG@10",
    }

    for key, label in metric_labels.items():
        value = aggregates.get(key, 0.0)
        lines.append(f"| {label} | {value:.4f} |")

    lines.extend([
        f"",
        f"## クエリ別結果",
        f"",
        f"| ID | カテゴリ | クエリ | 検索件数 | P@5 | R@10 | MRR | nDCG@10 |",
        f"|-----|----------|--------|----------|------|------|------|---------|",
    ])

    for r in results:
        m = r.get("metrics", {})
        if r["has_annotation"]:
            lines.append(
                f"| {r['query_id']} | {r['category']} | {r['query'][:30]}... "
                f"| {r['retrieved_count']} "
                f"| {m.get('precision_at_5', 0):.3f} "
                f"| {m.get('recall_at_10', 0):.3f} "
                f"| {m.get('mrr', 0):.3f} "
                f"| {m.get('ndcg_at_10', 0):.3f} |"
            )
        else:
            lines.append(
                f"| {r['query_id']} | {r['category']} | {r['query'][:30]}... "
                f"| {r['retrieved_count']} | - | - | - | - |"
            )

    lines.append("")
    return "\n".join(lines)


async def run_evaluation(
    directory_ids: List[int],
    query_type: Optional[str] = None,
    queries_path: Path = DEFAULT_QUERIES_PATH,
    output_dir: Path = DEFAULT_REPORTS_DIR,
) -> Dict[str, Any]:
    """
    評価を実行してレポートを生成する。

    Args:
        directory_ids: 検索対象のディレクトリID
        query_type: フィルタするクエリタイプ（None=全て）
        queries_path: テストクエリYAMLのパス
        output_dir: レポート出力ディレクトリ
    """
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # テストクエリ読み込み
    queries = load_test_queries(queries_path, query_type)
    logger.info(f"評価対象クエリ数: {len(queries)}")

    # 各クエリを評価
    results = []
    for query_data in queries:
        result = await evaluate_query(query_data, directory_ids)
        results.append(result)

    # 集約メトリクス計算
    aggregates = compute_aggregate_metrics(results)

    # レポート生成
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON レポート
    json_report = {
        "run_timestamp": run_timestamp,
        "directory_ids": directory_ids,
        "query_type_filter": query_type,
        "aggregates": aggregates,
        "results": results,
    }

    json_path = output_dir / f"evaluation_{run_timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)

    # Markdown レポート
    md_report = generate_markdown_report(results, aggregates, run_timestamp)
    md_path = output_dir / f"evaluation_{run_timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)

    # 最新レポートのシンボリックリンク
    latest_json = output_dir / "latest.json"
    latest_md = output_dir / "latest.md"
    for link, target in [(latest_json, json_path), (latest_md, md_path)]:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target.name)

    logger.info(f"レポート出力: {json_path}")
    logger.info(f"レポート出力: {md_path}")

    # 集約メトリクスをログ出力
    if aggregates:
        logger.info("=== 集約メトリクス ===")
        for key, value in aggregates.items():
            if isinstance(value, float):
                logger.info(f"  {key}: {value:.4f}")

    return json_report


def main():
    parser = argparse.ArgumentParser(description="ConPass RAG評価ランナー")
    parser.add_argument(
        "--type",
        choices=["semantic_search", "metadata_search"],
        help="評価するクエリタイプ",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=DEFAULT_QUERIES_PATH,
        help="テストクエリYAMLのパス",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="レポート出力ディレクトリ",
    )
    parser.add_argument(
        "--directory-ids",
        type=int,
        nargs="+",
        required=True,
        help="検索対象のディレクトリID",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(
        run_evaluation(
            directory_ids=args.directory_ids,
            query_type=args.type,
            queries_path=args.queries,
            output_dir=args.output,
        )
    )


if __name__ == "__main__":
    main()
