"""
評価テスト用のpytest設定。

CI環境でメトリクスの閾値チェックを行うためのフィクスチャ。
"""

import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--directory-ids",
        type=str,
        default=os.getenv("EVAL_DIRECTORY_IDS", ""),
        help="カンマ区切りのディレクトリID",
    )
    parser.addoption(
        "--min-ndcg",
        type=float,
        default=float(os.getenv("EVAL_MIN_NDCG", "0.0")),
        help="nDCG@10の最低閾値",
    )
    parser.addoption(
        "--min-mrr",
        type=float,
        default=float(os.getenv("EVAL_MIN_MRR", "0.0")),
        help="MRRの最低閾値",
    )


@pytest.fixture
def directory_ids(request):
    ids_str = request.config.getoption("--directory-ids")
    if not ids_str:
        pytest.skip("--directory-ids が指定されていません")
    return [int(x.strip()) for x in ids_str.split(",")]


@pytest.fixture
def min_ndcg(request):
    return request.config.getoption("--min-ndcg")


@pytest.fixture
def min_mrr(request):
    return request.config.getoption("--min-mrr")
