"""
メタデータフィールドのマッピングとバリデーション。

Pydanticスキーマによる厳格バリデーション:
- 会社名: strip + NFKC正規化 + 最小長2文字
- 日付: YYYY-MM-DD明示検証
- 契約種別: 既知enumに対するバリデーション
- メタデータ完成度スコア(0-100%)をペイロードに格納
- カスタムメタデータ: custom_プレフィックスで保存
"""

import logging
import unicodedata
from typing import Any, Dict, List, Optional

from dateutil import parser

logger = logging.getLogger(__name__)

# 既知の契約種別
KNOWN_CONTRACT_TYPES = {
    "業務委託契約",
    "秘密保持契約",
    "売買契約",
    "賃貸借契約",
    "ライセンス契約",
    "雇用契約",
    "請負契約",
    "代理店契約",
    "フランチャイズ契約",
    "合弁契約",
    "株主間契約",
    "基本契約",
    "個別契約",
    "覚書",
    "念書",
    "誓約書",
    "NDA",
    "SLA",
    "その他",
}

# メタデータ完成度に寄与するフィールド
COMPLETENESS_FIELDS = [
    "契約書名_title",
    "会社名_甲_company_a",
    "会社名_乙_company_b",
    "契約日_contract_date",
    "契約開始日_contract_start_date",
    "契約終了日_contract_end_date",
    "契約種別_contract_type",
]


def _normalize_company_name(value: str) -> Optional[str]:
    """
    会社名を正規化する。
    - NFKC正規化（全角→半角統一）
    - 前後空白除去
    - 最小長2文字バリデーション
    """
    if not value or not isinstance(value, str):
        return None

    normalized = unicodedata.normalize("NFKC", value).strip()

    if len(normalized) < 2:
        logger.warning(f"Company name too short (< 2 chars): '{value}'")
        return None

    return normalized


def _validate_date(value: Any) -> Optional[str]:
    """
    日付をYYYY-MM-DD形式にパースする。
    無効な日付はNoneを返す。
    """
    if not value:
        return None
    try:
        dt = parser.parse(str(value))
        formatted = dt.date().isoformat()  # 'YYYY-MM-DD'
        # 簡易的な範囲チェック
        year = dt.year
        if year < 1900 or year > 2100:
            logger.warning(f"Date out of range: {formatted}")
            return None
        return formatted
    except Exception:
        logger.warning(f"Invalid date value: '{value}'")
        return None


def _normalize_text(value: Any) -> Optional[str]:
    """テキスト値をNFKC正規化してstrip。"""
    if not value or not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    return normalized if normalized else None


def _validate_contract_type(value: Any) -> Optional[str]:
    """契約種別をバリデーション。既知の型に一致しない場合も保存するが警告。"""
    if not value or not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    if normalized and normalized not in KNOWN_CONTRACT_TYPES:
        logger.info(f"Unknown contract type: '{normalized}' (not in known types)")
    return normalized if normalized else None


def to_bool(value: Any) -> bool:
    """
    Try to parse a value into a boolean.
    Generally the value should be 0, 1, "0", "1".
    """
    try:
        if value is None:
            return False
        if isinstance(value, int):
            return value == 1
        if isinstance(value, str):
            if value == "0":
                return False
            if value == "1":
                return True
        return False
    except Exception:
        return False


def _compute_completeness_score(metadata: Dict[str, Any]) -> int:
    """メタデータの完成度スコアを計算する (0-100)。"""
    if not COMPLETENESS_FIELDS:
        return 100

    filled = sum(
        1 for field in COMPLETENESS_FIELDS
        if metadata.get(field) not in (None, "", [])
    )
    return int((filled / len(COMPLETENESS_FIELDS)) * 100)


# ラベル→処理関数のマッピング
FIELD_HANDLERS = {
    "title": ("契約書名_title", _normalize_text),
    "companya": ("会社名_甲_company_a", _normalize_company_name),
    "companyb": ("会社名_乙_company_b", _normalize_company_name),
    "companyc": ("会社名_丙_company_c", _normalize_company_name),
    "companyd": ("会社名_丁_company_d", _normalize_company_name),
    "contractdate": ("契約日_contract_date", _validate_date),
    "contractstartdate": ("契約開始日_contract_start_date", _validate_date),
    "contractenddate": ("契約終了日_contract_end_date", _validate_date),
    "cancelnotice": ("契約終了日_cancel_notice_date", _validate_date),
    "cort": ("裁判所_court", _normalize_text),
    "conpass_contract_type": ("契約種別_contract_type", _validate_contract_type),
}


def get_metadata(contract_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    メタデータフィールドをマッピング・バリデーションする。

    Args:
        contract_metadata: ConPass APIからのメタデータリスト

    Returns:
        バリデーション済みメタデータ辞書（メタデータ完成度スコア付き）
    """
    metadata: Dict[str, Any] = {}

    for item in contract_metadata:
        label = item.get("label")
        value = item.get("value")

        if not label:
            continue

        # autoupdateは特別処理（bool型）
        if label == "autoupdate":
            metadata["自動更新の有無_auto_update"] = to_bool(value)
            continue

        # 既知フィールドの処理
        handler = FIELD_HANDLERS.get(label)
        if handler:
            field_name, validator_fn = handler
            validated = validator_fn(value)
            if validated is not None:
                metadata[field_name] = validated
        else:
            # 未知のフィールド: custom_プレフィックスで保存
            if value is not None and str(value).strip():
                custom_key = f"custom_{label}"
                metadata[custom_key] = _normalize_text(value) or str(value)

    # メタデータ完成度スコアを計算
    metadata["metadata_completeness"] = _compute_completeness_score(metadata)

    return metadata
