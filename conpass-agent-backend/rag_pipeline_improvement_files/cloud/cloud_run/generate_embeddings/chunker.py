"""
日本語契約書対応 2層チャンキングモジュール。

Tier1: 構造分割（第X条、第X項、(1)(2)、一、二 等）
Tier2: 形態素境界を考慮した分割（SudachiPy使用、文境界・節境界で分割）

各チャンクに構造メタデータ（article_number, clause_number, section_title）を付与。
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# SudachiPyの遅延インポート（未インストール時はフォールバック）
_sudachi_tokenizer = None
_sudachi_available = None


def _get_sudachi_tokenizer():
    """SudachiPyトークナイザーのシングルトン取得（遅延初期化）。"""
    global _sudachi_tokenizer, _sudachi_available
    if _sudachi_available is None:
        try:
            from sudachipy import Dictionary

            _sudachi_tokenizer = Dictionary().create()
            _sudachi_available = True
        except ImportError:
            _sudachi_available = False
    return _sudachi_tokenizer if _sudachi_available else None


# --- 構造認識パターン ---

# 条番号パターン: 「第1条」「第１条」「第一条」
ARTICLE_PATTERN = re.compile(
    r"(?:^|\n)\s*第([0-9０-９一二三四五六七八九十百]+)条\s*[（(]?([^）)\n]*)[）)]?\s*"
)

# 項番号パターン: 「第1項」「1.」「１．」
CLAUSE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:第([0-9０-９一二三四五六七八九十]+)項|([0-9０-９]+)[.．])\s*"
)

# 号番号パターン: 「(1)」「（1）」「①」
SUBCLAUSE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[（(]([0-9０-９]+)[）)]|([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]))\s*"
)

# 日本語句点パターン
SENTENCE_BOUNDARY_RE = re.compile(r"[。．.!！?？\n]")

# 全角数字→半角数字変換
FULLWIDTH_TO_HALFWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")

# 漢数字→アラビア数字マッピング
KANJI_NUMBERS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "百": 100,
}


def _normalize_number(s: str) -> Optional[int]:
    """全角・漢数字をintに変換する。"""
    s = s.translate(FULLWIDTH_TO_HALFWIDTH)
    if s.isdigit():
        return int(s)
    return KANJI_NUMBERS.get(s)


def _extract_section_title(text: str) -> Optional[str]:
    """条文タイトルを抽出する（例: 「（秘密保持）」→「秘密保持」）。"""
    match = re.match(r"\s*[（(]([^）)]+)[）)]", text)
    if match:
        return match.group(1).strip()
    return None


# --- Tier 1: 構造分割 ---

def split_by_structure(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    契約書テキストを構造（条・項）で分割する。

    Returns:
        (チャンクテキスト, 構造メタデータ) のリスト
    """
    if not text or not text.strip():
        return []

    # 条番号の位置を特定
    article_positions = []
    for match in ARTICLE_PATTERN.finditer(text):
        num_str = match.group(1)
        title_str = match.group(2) if match.group(2) else ""
        article_num = _normalize_number(num_str)
        article_positions.append({
            "start": match.start(),
            "end": match.end(),
            "article_number": article_num,
            "section_title": title_str.strip() if title_str.strip() else None,
            "raw_match": match.group(0),
        })

    # 条番号が見つからない場合、テキスト全体を1チャンクとして返す
    if not article_positions:
        return [(text.strip(), {"article_number": None, "clause_number": None, "section_title": None})]

    chunks = []

    # 最初の条より前のテキスト（前文など）
    if article_positions[0]["start"] > 0:
        preamble = text[:article_positions[0]["start"]].strip()
        if preamble:
            chunks.append((preamble, {
                "article_number": None,
                "clause_number": None,
                "section_title": "前文",
            }))

    # 各条のテキストを抽出
    for i, pos in enumerate(article_positions):
        start = pos["start"]
        end = article_positions[i + 1]["start"] if i + 1 < len(article_positions) else len(text)
        chunk_text_str = text[start:end].strip()

        if chunk_text_str:
            metadata = {
                "article_number": pos["article_number"],
                "clause_number": None,
                "section_title": pos["section_title"],
            }
            chunks.append((chunk_text_str, metadata))

    return chunks


# --- Tier 2: 形態素境界を考慮した分割 ---

def _split_at_sentence_boundaries(text: str, max_size: int, overlap: int) -> List[str]:
    """
    文境界（。）で分割する。文境界が見つからない場合は節境界（、）で分割。
    形態素解析が利用可能な場合、形態素の途中では分割しない。
    """
    if len(text) <= max_size:
        return [text]

    tokenizer = _get_sudachi_tokenizer()

    # 形態素解析が利用可能な場合、トークン境界を取得
    token_boundaries = set()
    if tokenizer:
        try:
            from sudachipy import Tokenizer as SudachiMode
            morphemes = tokenizer.tokenize(text, SudachiMode.SplitMode.C)
            pos = 0
            for morpheme in morphemes:
                surface = morpheme.surface()
                token_boundaries.add(pos)
                pos += len(surface)
            token_boundaries.add(pos)
        except Exception:
            # フォールバック: 全位置をトークン境界とみなす
            token_boundaries = set(range(len(text) + 1))
    else:
        token_boundaries = set(range(len(text) + 1))

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + max_size, len(text))

        if end >= len(text):
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            break

        # 文境界（。）を探す
        best_split = _find_best_split_point(
            text, start, end, token_boundaries, r"[。．]"
        )

        # 文境界が見つからない場合、節境界（、）を探す
        if best_split is None:
            best_split = _find_best_split_point(
                text, start, end, token_boundaries, r"[、,]"
            )

        # それでも見つからない場合、トークン境界で分割
        if best_split is None:
            # end位置から遡って最も近いトークン境界を探す
            for pos in range(end, max(start, end - overlap), -1):
                if pos in token_boundaries:
                    best_split = pos
                    break

        # 最悪の場合、max_size位置で分割
        if best_split is None or best_split <= start:
            best_split = end

        chunk = text[start:best_split].strip()
        if chunk:
            chunks.append(chunk)

        # 次のスタート位置（オーバーラップ考慮）
        next_start = best_split
        if overlap > 0 and next_start < len(text):
            # オーバーラップ分を戻す
            overlap_start = max(start + 1, next_start - overlap)
            # トークン境界に合わせる
            for pos in range(overlap_start, next_start):
                if pos in token_boundaries:
                    next_start = pos
                    break

        if next_start <= start:
            next_start = start + 1

        start = next_start

    return chunks


def _find_best_split_point(
    text: str,
    start: int,
    end: int,
    token_boundaries: set,
    boundary_pattern: str,
) -> Optional[int]:
    """
    指定パターンの境界のうち、endに最も近いものを返す。
    トークン境界と一致する位置を優先する。
    """
    search_start = max(start, end - (end - start) // 2)  # 後半で探す
    segment = text[search_start:end]
    boundaries = list(re.finditer(boundary_pattern, segment))

    if not boundaries:
        return None

    # 最後の境界を使用
    last = boundaries[-1]
    split_pos = search_start + last.end()

    # トークン境界に合わせる
    if split_pos in token_boundaries:
        return split_pos

    # 最も近いトークン境界を探す
    for offset in range(5):
        if (split_pos + offset) in token_boundaries:
            return split_pos + offset
        if (split_pos - offset) in token_boundaries and (split_pos - offset) > start:
            return split_pos - offset

    return split_pos


# --- メインAPI ---

def chunk_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[str]:
    """
    日本語契約書対応テキストチャンカー。

    2層チャンキング:
    1. 構造分割（第X条、第X項）
    2. 大きすぎるチャンクを形態素境界で再分割

    Args:
        text: 入力テキスト
        chunk_size: 最大チャンクサイズ（文字数）
        chunk_overlap: チャンク間のオーバーラップ（文字数）

    Returns:
        チャンクテキストのリスト
    """
    if not text:
        return []

    # Normalize whitespace
    text = text.replace("\u3000", " ").strip()

    chunks = []

    # Tier 1: 構造分割
    structural_chunks = split_by_structure(text)

    for chunk_text_str, _metadata in structural_chunks:
        if len(chunk_text_str) <= chunk_size:
            # チャンクサイズ以下ならそのまま使用
            chunks.append(chunk_text_str)
        else:
            # Tier 2: 形態素境界を考慮した再分割
            sub_chunks = _split_at_sentence_boundaries(
                chunk_text_str, chunk_size, chunk_overlap
            )
            chunks.extend(sub_chunks)

    return chunks


def chunk_text_with_metadata(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    チャンクと構造メタデータを返すバージョン。

    Returns:
        (チャンクテキスト, 構造メタデータ) のリスト
        メタデータ: {"article_number": int|None, "clause_number": int|None, "section_title": str|None}
    """
    if not text:
        return []

    text = text.replace("\u3000", " ").strip()

    results = []

    structural_chunks = split_by_structure(text)

    for chunk_text_str, metadata in structural_chunks:
        if len(chunk_text_str) <= chunk_size:
            results.append((chunk_text_str, metadata))
        else:
            sub_chunks = _split_at_sentence_boundaries(
                chunk_text_str, chunk_size, chunk_overlap
            )
            for sub_chunk in sub_chunks:
                results.append((sub_chunk, metadata.copy()))

    return results
