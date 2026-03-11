"""
BGE-M3 シングルトンモデル。

Dense (1024次元) と Sparse (SPLADE スタイル) を1モデルで提供する。
日本語・英語・中国語など100言語以上に対応。

FlagEmbedding ライブラリを使用:
  https://github.com/FlagOpen/FlagEmbedding

Usage:
    model = get_bge_m3_model()
    result = model.encode(["テキスト1", "テキスト2"])
    dense  = result["dense_vecs"]          # np.ndarray (n, 1024)
    sparse = result["lexical_weights"]     # list[dict[int, float]] token_id → weight
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Hugging Face のモデルキャッシュディレクトリ（環境変数で変更可能）
BGE_M3_MODEL_NAME = os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3")
BGE_M3_BATCH_SIZE = int(os.getenv("BGE_M3_BATCH_SIZE", "12"))
BGE_M3_MAX_LENGTH = int(os.getenv("BGE_M3_MAX_LENGTH", "8192"))

_bge_m3_model: Optional[Any] = None


def get_bge_m3_model() -> Any:
    """BGE-M3 モデルのシングルトンを返す。初回呼び出し時にロードする。"""
    global _bge_m3_model
    if _bge_m3_model is None:
        _bge_m3_model = _load_bge_m3_model()
    return _bge_m3_model


def _load_bge_m3_model() -> Any:
    try:
        # FlagEmbedding.__init__ が reranker 経由で使用する
        # transformers.utils.import_utils.is_torch_fx_available は
        # 新しい transformers で削除されたため、事前にパッチを当てる
        import transformers.utils.import_utils as _tu
        if not hasattr(_tu, "is_torch_fx_available"):
            _tu.is_torch_fx_available = lambda: False

        from FlagEmbedding import BGEM3FlagModel
    except ImportError as exc:
        raise ImportError(
            "FlagEmbedding is not installed or incompatible. "
            "Add 'FlagEmbedding>=1.3.0' to pyproject.toml and rebuild the image. "
            f"Original error: {exc}"
        ) from exc

    logger.info(f"BGE-M3 モデルをロード中: {BGE_M3_MODEL_NAME}")
    model = BGEM3FlagModel(
        BGE_M3_MODEL_NAME,
        use_fp16=False,  # CPU 環境では fp16 無効
    )
    logger.info("BGE-M3 モデルのロード完了")
    return model


def encode_texts(
    texts: List[str],
    *,
    return_dense: bool = True,
    return_sparse: bool = True,
) -> Dict[str, Any]:
    """
    テキストリストを Dense + Sparse ベクトルに変換する。

    Returns:
        {
            "dense_vecs":       np.ndarray shape (n, 1024),  # return_dense=True のとき
            "lexical_weights":  list[dict[int, float]],      # return_sparse=True のとき
        }
    """
    model = get_bge_m3_model()
    return model.encode(
        texts,
        batch_size=BGE_M3_BATCH_SIZE,
        max_length=BGE_M3_MAX_LENGTH,
        return_dense=return_dense,
        return_sparse=return_sparse,
        return_colbert_vecs=False,
    )


def encode_single_dense(text: str) -> List[float]:
    """1テキストの Dense ベクトル (1024次元) を返す。"""
    result = encode_texts([text], return_dense=True, return_sparse=False)
    return result["dense_vecs"][0].tolist()


def encode_single_sparse(text: str) -> Tuple[List[int], List[float]]:
    """
    1テキストの Sparse ベクトルを (indices, values) で返す。
    indices は BGE-M3 の tokenizer vocabulary ID。
    """
    result = encode_texts([text], return_dense=False, return_sparse=True)
    weights: Dict[int, float] = result["lexical_weights"][0]
    if not weights:
        return [], []
    indices = list(weights.keys())
    values = list(weights.values())
    return indices, values
