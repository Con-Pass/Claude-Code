"""
e-Gov法令XMLパーサー

e-Gov APIから取得した法令XMLを解析し、
編・章・条・項 の階層構造を保持した条文データを生成する。

main.py の parse_articles() から呼び出される専用パーサー。
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# e-Gov法令XMLの主要タグ（名前空間なし）
TAG_LAW = "Law"
TAG_LAW_BODY = "LawBody"
TAG_MAIN_PROVISION = "MainProvision"
TAG_PART = "Part"
TAG_CHAPTER = "Chapter"
TAG_SECTION = "Section"
TAG_ARTICLE = "Article"
TAG_PARAGRAPH = "Paragraph"
TAG_ITEM = "Item"
TAG_ARTICLE_CAPTION = "ArticleCaption"
TAG_ARTICLE_TITLE = "ArticleTitle"
TAG_PARAGRAPH_NUM = "ParagraphNum"
TAG_PARAGRAPH_SENTENCE = "ParagraphSentence"
TAG_ITEM_SENTENCE = "ItemSentence"
TAG_SENTENCE = "Sentence"
TAG_PART_TITLE = "PartTitle"
TAG_CHAPTER_TITLE = "ChapterTitle"
TAG_SECTION_TITLE = "SectionTitle"
TAG_SUPPL_PROVISION = "SupplProvision"


def _strip_ns(tag: str) -> str:
    """XMLタグから名前空間プレフィックスを除去する"""
    if "}" in tag:
        return tag.split("}")[-1]
    return tag


def _collect_text(element: ET.Element, exclude_tags: Optional[set] = None) -> str:
    """
    要素内のテキストを再帰的に収集する。

    Args:
        element: XML要素
        exclude_tags: 除外するタグ名のセット

    Returns:
        結合されたテキスト
    """
    exclude = exclude_tags or set()
    parts: List[str] = []

    for child in element:
        child_tag = _strip_ns(child.tag)
        if child_tag in exclude:
            continue
        text = "".join(child.itertext()).strip()
        if text:
            parts.append(text)

    return "\n".join(parts)


def parse_law_xml(
    xml_text: str,
    law_name: str,
    law_id: str,
) -> List[Dict[str, Any]]:
    """
    e-Gov法令XMLを解析し、条文単位のデータリストを生成する。

    階層構造（編 > 章 > 節 > 条 > 項）を保持し、
    各条文に所属する編・章・節の情報をメタデータとして付与する。

    Args:
        xml_text: e-Gov APIから取得したXMLテキスト
        law_name: 法令名
        law_id: e-Gov法令ID

    Returns:
        条文データのリスト。各要素:
        {
            "law_name": str,
            "law_id": str,
            "part": str | None,        # 編タイトル
            "chapter": str | None,      # 章タイトル
            "section": str | None,      # 節タイトル
            "article_number": str,      # 条番号（例: "第1条"）
            "article_title": str,       # 条のタイトル
            "text": str,                # 条文テキスト
        }
    """
    articles: List[Dict[str, Any]] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning(f"XMLパース失敗: {law_id} ({law_name})")
        if xml_text.strip():
            articles.append({
                "law_name": law_name,
                "law_id": law_id,
                "part": None,
                "chapter": None,
                "section": None,
                "article_number": "全文",
                "article_title": "",
                "text": xml_text,
            })
        return articles

    # MainProvision（本則）を探す
    main_provisions = _find_elements(root, TAG_MAIN_PROVISION)
    if not main_provisions:
        # MainProvisionがない場合、ルートから直接探索
        main_provisions = [root]

    for main_provision in main_provisions:
        _parse_provision(
            main_provision, law_name, law_id, articles,
            current_part=None, current_chapter=None, current_section=None,
        )

    # 附則（SupplProvision）も処理
    for suppl in _find_elements(root, TAG_SUPPL_PROVISION):
        _parse_provision(
            suppl, law_name, law_id, articles,
            current_part="附則", current_chapter=None, current_section=None,
        )

    if not articles:
        # 条文が見つからない場合、全テキストを1件として扱う
        all_text = "".join(root.itertext()).strip()
        if all_text:
            articles.append({
                "law_name": law_name,
                "law_id": law_id,
                "part": None,
                "chapter": None,
                "section": None,
                "article_number": "全文",
                "article_title": "",
                "text": all_text,
            })

    logger.info(f"{law_name}: {len(articles)}条文を階層パース")
    return articles


def _find_elements(parent: ET.Element, target_tag: str) -> List[ET.Element]:
    """名前空間を考慮して要素を検索する"""
    results = []
    for elem in parent.iter():
        if _strip_ns(elem.tag) == target_tag:
            results.append(elem)
    return results


def _get_title(parent: ET.Element, title_tag: str) -> str:
    """直下の子要素からタイトルテキストを取得する"""
    for child in parent:
        if _strip_ns(child.tag) == title_tag:
            return "".join(child.itertext()).strip()
    return ""


def _parse_provision(
    element: ET.Element,
    law_name: str,
    law_id: str,
    articles: List[Dict[str, Any]],
    current_part: Optional[str],
    current_chapter: Optional[str],
    current_section: Optional[str],
) -> None:
    """
    法令構造を再帰的に解析し、条文を抽出する。

    編 > 章 > 節 > 条 の階層を走査し、
    各階層のタイトルを条文メタデータに付与する。
    """
    for child in element:
        child_tag = _strip_ns(child.tag)

        if child_tag == TAG_PART:
            part_title = _get_title(child, TAG_PART_TITLE)
            part_num = child.get("Num", "")
            part_label = f"第{part_num}編 {part_title}".strip() if part_num else part_title
            _parse_provision(
                child, law_name, law_id, articles,
                current_part=part_label or current_part,
                current_chapter=None,
                current_section=None,
            )

        elif child_tag == TAG_CHAPTER:
            chapter_title = _get_title(child, TAG_CHAPTER_TITLE)
            chapter_num = child.get("Num", "")
            chapter_label = f"第{chapter_num}章 {chapter_title}".strip() if chapter_num else chapter_title
            _parse_provision(
                child, law_name, law_id, articles,
                current_part=current_part,
                current_chapter=chapter_label or current_chapter,
                current_section=None,
            )

        elif child_tag == TAG_SECTION:
            section_title = _get_title(child, TAG_SECTION_TITLE)
            section_num = child.get("Num", "")
            section_label = f"第{section_num}節 {section_title}".strip() if section_num else section_title
            _parse_provision(
                child, law_name, law_id, articles,
                current_part=current_part,
                current_chapter=current_chapter,
                current_section=section_label or current_section,
            )

        elif child_tag == TAG_ARTICLE:
            article_num = child.get("Num", "")
            article_number = f"第{article_num}条" if article_num else ""

            # ArticleCaption or ArticleTitle
            article_title = (
                _get_title(child, TAG_ARTICLE_CAPTION)
                or _get_title(child, TAG_ARTICLE_TITLE)
            )

            # 条文テキスト（ArticleCaption/ArticleTitleを除く）
            text = _collect_text(
                child,
                exclude_tags={TAG_ARTICLE_CAPTION, TAG_ARTICLE_TITLE},
            )

            if text.strip():
                articles.append({
                    "law_name": law_name,
                    "law_id": law_id,
                    "part": current_part,
                    "chapter": current_chapter,
                    "section": current_section,
                    "article_number": article_number,
                    "article_title": article_title,
                    "text": text,
                })
