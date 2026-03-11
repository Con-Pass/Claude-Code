"""
クエリ理解・拡張モジュール。

ユーザーの口語クエリを検索に適した形に変換し、
日本語法務用語の同義語展開を行う。

- Dense検索用: 意味的に明確化されたクエリ
- Sparse検索用: 同義語・略語を展開したバリアント
"""

import os
from typing import Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)

QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "false").lower() == "true"

# 日本語法務用語辞書（同義語グループ）
LEGAL_SYNONYM_GROUPS = [
    {"秘密保持", "NDA", "守秘義務", "機密保持", "秘密保持契約"},
    {"損害賠償", "賠償責任", "損害の補償", "損害賠償責任"},
    {"解約", "契約解除", "解除", "終了", "契約終了"},
    {"不可抗力", "フォースマジュール", "force majeure", "天災地変"},
    {"競業避止", "競業禁止", "競合制限", "non-compete"},
    {"知的財産", "知的財産権", "知財", "IP", "著作権", "特許"},
    {"個人情報", "プライバシー", "個人データ", "privacy"},
    {"瑕疵担保", "契約不適合", "品質保証", "warranty"},
    {"善管注意義務", "善良な管理者の注意義務", "注意義務"},
    {"連帯保証", "保証", "guarantee", "保証人"},
    {"準拠法", "governing law", "適用法律"},
    {"管轄裁判所", "裁判管轄", "専属合意管轄"},
    {"期限の利益", "期限の利益喪失"},
    {"反社会的勢力", "反社", "暴力団"},
    {"支払条件", "支払い条件", "対価", "報酬"},
    {"業務委託", "委託", "アウトソーシング", "outsourcing"},
    {"ライセンス", "使用許諾", "実施権", "license"},
    {"機密情報", "秘密情報", "confidential information"},
    {"譲渡禁止", "譲渡制限", "権利譲渡"},
    {"存続条項", "残存条項", "survival"},
]

# 同義語の逆引きインデックス
_synonym_index = {}
for group in LEGAL_SYNONYM_GROUPS:
    for term in group:
        _synonym_index[term.lower()] = group


def expand_query_with_synonyms(query: str) -> str:
    """
    クエリに含まれる法務用語の同義語を展開する。

    Args:
        query: 元のクエリ

    Returns:
        同義語を追加したクエリバリアント（Sparse検索用）
    """
    found_synonyms = set()

    query_lower = query.lower()
    for term, group in _synonym_index.items():
        if term in query_lower:
            found_synonyms.update(group)

    if not found_synonyms:
        return query

    # 元のクエリに含まれるものを除外
    additional = {s for s in found_synonyms if s.lower() not in query_lower}

    if additional:
        expanded = f"{query} {' '.join(additional)}"
        logger.info(
            f"Query expanded with synonyms: '{query}' -> added {len(additional)} terms"
        )
        return expanded

    return query


async def rewrite_query(query: str) -> Tuple[str, str]:
    """
    クエリをDense検索用とSparse検索用に分離する。

    Args:
        query: ユーザーの元のクエリ

    Returns:
        (dense_query, sparse_query) のタプル
        - dense_query: 意味的検索に適したクエリ
        - sparse_query: キーワード検索に適したクエリ（同義語展開済み）
    """
    if not QUERY_EXPANSION_ENABLED:
        return query, query

    # Sparse検索用: 同義語展開
    sparse_query = expand_query_with_synonyms(query)

    # Dense検索用: 元のクエリをそのまま使用
    # （将来的にgpt-4o-miniでのクエリリライトを追加可能）
    dense_query = query

    if sparse_query != query:
        logger.info(
            f"Query split - Dense: '{dense_query}', "
            f"Sparse: '{sparse_query[:100]}...'"
        )

    return dense_query, sparse_query
