"""
法令改正検知モジュール。

Firestoreに保存した前回取得時のハッシュと比較し、
法令テキストに変更があったかどうかを検知する。
"""

import hashlib
import logging
from datetime import datetime, timezone

from google.cloud import firestore

logger = logging.getLogger(__name__)

# Firestoreコレクション名
LAW_HASHES_COLLECTION = "law_hashes"


def compute_law_hash(law_text: str) -> str:
    """
    法令テキストのSHA-256ハッシュを算出する。

    Args:
        law_text: 法令テキスト全文

    Returns:
        SHA-256ハッシュ文字列（hex）
    """
    return hashlib.sha256(law_text.encode("utf-8")).hexdigest()


async def detect_changes(law_id: str, current_text: str) -> bool:
    """
    前回取得との差分チェック。変更があればTrueを返す。

    Firestoreに保存されたハッシュと現在のテキストのハッシュを比較。
    初回取得（ドキュメント未存在）の場合は常にTrueを返す。

    Args:
        law_id: e-Gov法令ID
        current_text: 現在取得した法令テキスト

    Returns:
        変更があればTrue、なければFalse
    """
    try:
        db = firestore.Client()
        doc_ref = db.collection(LAW_HASHES_COLLECTION).document(law_id)
        doc = doc_ref.get()

        if not doc.exists:
            logger.info(f"法令 {law_id}: 初回取得（ハッシュ未保存）")
            return True

        stored_hash = doc.to_dict().get("hash", "")
        current_hash = compute_law_hash(current_text)

        if stored_hash != current_hash:
            logger.info(f"法令 {law_id}: 変更検知（ハッシュ不一致）")
            return True

        return False

    except Exception as e:
        logger.error(f"法令 {law_id}: Firestore読み取りエラー: {e}", exc_info=True)
        # エラー時は安全側に倒して更新ありとして扱う
        return True


async def save_law_hash(law_id: str, text: str, law_name: str) -> None:
    """
    法令テキストのハッシュをFirestoreに保存する。

    Args:
        law_id: e-Gov法令ID
        text: 法令テキスト全文
        law_name: 法令名（メタデータとして保存）
    """
    try:
        db = firestore.Client()
        doc_ref = db.collection(LAW_HASHES_COLLECTION).document(law_id)
        doc_ref.set({
            "hash": compute_law_hash(text),
            "law_name": law_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "text_length": len(text),
        })
        logger.info(f"法令 {law_id} ({law_name}): ハッシュをFirestoreに保存")
    except Exception as e:
        logger.error(
            f"法令 {law_id} ({law_name}): Firestoreハッシュ保存エラー: {e}",
            exc_info=True,
        )
