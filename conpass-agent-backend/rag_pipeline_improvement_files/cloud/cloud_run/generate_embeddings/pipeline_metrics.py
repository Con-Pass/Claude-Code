"""
パイプライン可観測性メトリクス。

Cloud Monitoringカスタムメトリクスとして以下を記録:
- embedding_pipeline.documents_processed (counter)
- embedding_pipeline.chunks_per_document (histogram)
- embedding_pipeline.embedding_latency_ms (histogram)
- embedding_pipeline.batch_processing_time_ms (histogram)
- embedding_pipeline.sparse_failure_rate (gauge)
"""

import logging
import time
from contextlib import contextmanager
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# メトリクス集計（インメモリ。将来Cloud Monitoringに送信）
_metrics: Dict[str, List[float]] = {
    "documents_processed_new": [],
    "documents_processed_updated": [],
    "documents_processed_skipped": [],
    "documents_processed_failed": [],
    "chunks_per_document": [],
    "embedding_latency_ms": [],
    "sparse_embedding_latency_ms": [],
    "batch_processing_time_ms": [],
}

_counters: Dict[str, int] = {
    "sparse_failures": 0,
    "sparse_total": 0,
}


@contextmanager
def measure_latency(metric_name: str):
    """レイテンシを計測するコンテキストマネージャ。"""
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        _metrics.setdefault(metric_name, []).append(elapsed_ms)


def record_document_processed(status: str) -> None:
    """ドキュメント処理結果を記録する。"""
    key = f"documents_processed_{status}"
    _metrics.setdefault(key, []).append(1.0)


def record_chunks_per_document(count: int) -> None:
    """ドキュメントあたりのチャンク数を記録する。"""
    _metrics["chunks_per_document"].append(float(count))


def record_sparse_result(success: bool) -> None:
    """スパースEmbedding結果を記録する。"""
    _counters["sparse_total"] += 1
    if not success:
        _counters["sparse_failures"] += 1


def record_batch_time(elapsed_ms: float) -> None:
    """バッチ処理時間を記録する。"""
    _metrics["batch_processing_time_ms"].append(elapsed_ms)


def get_sparse_failure_rate() -> float:
    """スパースEmbeddingの失敗率を返す。"""
    total = _counters.get("sparse_total", 0)
    if total == 0:
        return 0.0
    return _counters.get("sparse_failures", 0) / total


def get_metrics_summary() -> Dict[str, any]:
    """現在のメトリクスサマリーを返す。"""
    summary = {}

    for key, values in _metrics.items():
        if values:
            summary[key] = {
                "count": len(values),
                "sum": sum(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }

    summary["sparse_failure_rate"] = get_sparse_failure_rate()

    return summary


def check_alerts() -> List[str]:
    """
    アラート条件をチェックする。

    Returns:
        発火したアラートメッセージのリスト
    """
    alerts = []

    # Embedding失敗率 > 5%
    failure_rate = get_sparse_failure_rate()
    if failure_rate > 0.05:
        alerts.append(
            f"ALERT: Sparse embedding failure rate {failure_rate:.1%} > 5%"
        )

    # バッチ処理時間 > 120秒
    batch_times = _metrics.get("batch_processing_time_ms", [])
    if batch_times and max(batch_times) > 120000:
        alerts.append(
            f"ALERT: Batch processing time {max(batch_times):.0f}ms > 120s"
        )

    return alerts


def reset_metrics() -> None:
    """メトリクスをリセットする（テスト用）。"""
    for key in _metrics:
        _metrics[key] = []
    for key in _counters:
        _counters[key] = 0
