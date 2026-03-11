"""
契約種別自動分類サービス

PDF要件「ConPass AIアシスタント：Qdrant格納用 契約種別分類体系」に基づく3階層分類を実装。

分類戦略：
1. ルールベース（タイトルキーワードマッチ + 既存メタデータ）: 高信頼度ケース
2. LLMベース（gpt-4o-mini: タイトル + 本文冒頭 + 既存メタデータ）: 曖昧ケース
3. ルールベース本文パターン: フォールバック
"""
import json
import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# 3階層タクソノミー定義
# ============================================================

# 大分類 → 中分類のマッピング
TAXONOMY: dict[str, list[str]] = {
    "取引契約": [
        "基本契約書",
        "個別契約書・注文書",
        "売買契約書",
        "業務委託契約書",
        "請負契約書",
        "代理店契約書",
        "サービス利用契約書",
    ],
    "人事・労務契約": [
        "雇用契約書",
        "派遣契約書",
        "出向契約書",
        "顧問契約書",
    ],
    "不動産・賃貸借契約": [
        "賃貸借契約書",
        "リース契約書",
    ],
    "知的財産・情報契約": [
        "秘密保持契約書",
        "ライセンス契約書",
        "譲渡契約書",
    ],
    "金融・担保契約": [
        "金銭消費貸借契約",
        "保証契約書",
    ],
    "会社間・組織契約": [
        "業務提携契約書",
        "合弁契約書",
        "株主間契約書",
    ],
    "紛争解決・合意契約": [
        "和解契約書",
        "合意書・覚書",
    ],
    "誓約・同意・その他": [
        "誓約書",
        "その他",
    ],
}

# 中分類 → 大分類の逆引きマップ
_TYPE_TO_CATEGORY: dict[str, str] = {
    t: cat for cat, types in TAXONOMY.items() for t in types
}

# ============================================================
# Phase 1: タイトル・既存メタデータキーワードマッチ
# ============================================================

# タイトルパターン → 中分類 のマッピング
# 長いパターン（より具体的なもの）を先に並べること
_TITLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # ---- 知的財産・情報契約 ----
    (re.compile(r"秘密保持|機密保持|NDA|Non.Disclosure", re.I), "秘密保持契約書"),
    (re.compile(r"ライセンス|使用許諾|実施許諾|License Agreement", re.I), "ライセンス契約書"),
    (re.compile(r"譲渡"), "譲渡契約書"),
    # ---- 人事・労務契約 ----
    (re.compile(r"雇用|労働|Employment|Labor"), "雇用契約書"),
    (re.compile(r"派遣|Dispatch"), "派遣契約書"),
    (re.compile(r"出向"), "出向契約書"),
    (re.compile(r"顧問|Advisory|Advisor"), "顧問契約書"),
    # ---- 不動産・賃貸借契約 ----
    (re.compile(r"賃貸借|リース|Lease|賃料"), "賃貸借契約書"),
    # ---- 金融・担保契約 ----
    (re.compile(r"金銭消費貸借|金銭貸借|消費貸借|金銭借用|ローン"), "金銭消費貸借契約"),
    (re.compile(r"保証"), "保証契約書"),
    # ---- 会社間・組織契約 ----
    (re.compile(r"合弁|ジョイントベンチャー|JV|Joint.Venture"), "合弁契約書"),
    (re.compile(r"株主間"), "株主間契約書"),
    (re.compile(r"業務提携|提携|Alliance|Strategic"), "業務提携契約書"),
    # ---- 取引契約 ----
    (re.compile(r"売買|売渡|Purchase|Sales Agreement|Sale"), "売買契約書"),
    (re.compile(r"請負|工事|建設|製造|Turnkey", re.I), "請負契約書"),
    (re.compile(r"代理店|販売代理|フランチャイズ|Franchise|Dealer|Distributor Agreement", re.I), "代理店契約書"),
    (re.compile(r"SaaS|クラウド|サービス利用|Service Agreement|MSA|Master.Service|利用規約|SLA", re.I), "サービス利用契約書"),
    (re.compile(r"業務委託|委託|委任|Outsourc|Service.Order|SOW", re.I), "業務委託契約書"),
    (re.compile(r"基本取引|基本契約|Master.Agreement|基本", re.I), "基本契約書"),
    (re.compile(r"個別|注文書|発注書|Order", re.I), "個別契約書・注文書"),
    (re.compile(r"Content.*Agreement|Distribution.*Agreement|Data.*License|License.*Agreement", re.I), "ライセンス契約書"),
    (re.compile(r"コンテンツ.*契約|データ.*契約|情報.*提供.*契約"), "ライセンス契約書"),
    # ---- 紛争解決・合意契約 ----
    (re.compile(r"和解|示談|Settlement"), "和解契約書"),
    (re.compile(r"合意書|覚書|MOU|Memorandum|Amendment|変更合意|変更覚書"), "合意書・覚書"),
    # ---- 誓約・同意・その他 ----
    (re.compile(r"誓約書|誓約"), "誓約書"),
]

# 既存メタデータ「契約種別」の旧値→新タクソノミー中分類マッピング
_LEGACY_TYPE_MAP: dict[str, str] = {
    "業務委託契約": "業務委託契約書",
    "秘密保持契約": "秘密保持契約書",
    "売買契約": "売買契約書",
    "賃貸借契約": "賃貸借契約書",
    "ライセンス契約": "ライセンス契約書",
    "雇用契約": "雇用契約書",
    "請負契約": "請負契約書",
    "代理店契約": "代理店契約書",
    "フランチャイズ契約": "代理店契約書",
    "合弁契約": "合弁契約書",
    "株主間契約": "株主間契約書",
    "基本契約": "基本契約書",
    "個別契約": "個別契約書・注文書",
    "覚書": "合意書・覚書",
    "念書": "合意書・覚書",
    "誓約書": "誓約書",
    "NDA": "秘密保持契約書",
    "SLA": "サービス利用契約書",
    "その他": "その他",
    # 新タクソノミーの値はそのまま通す
    **{t: t for types in TAXONOMY.values() for t in types},
}

# ============================================================
# Phase 2: 本文パターンマッチ（補助シグナル）
# ============================================================

_BODY_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # (pattern, contract_type, weight)
    (re.compile(r"秘密保持|機密保持|NDA"), "秘密保持契約書", 1.0),
    (re.compile(r"民法第643条|善管注意義務|準委任"), "業務委託契約書", 0.9),
    (re.compile(r"民法第632条|仕事の完成|瑕疵担保|契約不適合"), "請負契約書", 0.9),
    (re.compile(r"労働基準法|就業規則|解雇|賃金|雇用"), "雇用契約書", 0.9),
    (re.compile(r"労働者派遣法|派遣先|派遣元|派遣労働者"), "派遣契約書", 0.9),
    (re.compile(r"借地借家法|賃料|敷金|原状回復|賃借人"), "賃貸借契約書", 0.9),
    (re.compile(r"特許|実施権|ロイヤリティ|ライセンス|使用許諾"), "ライセンス契約書", 0.8),
    (re.compile(r"利息制限法|元本|弁済期|消費貸借"), "金銭消費貸借契約", 0.9),
    (re.compile(r"SLA|稼働率|サービスレベル"), "サービス利用契約書", 0.8),
    (re.compile(r"フランチャイズ|加盟金"), "代理店契約書", 0.8),
    (re.compile(r"和解|示談"), "和解契約書", 0.9),
    (re.compile(r"株主|株式"), "株主間契約書", 0.6),
    (re.compile(r"誓約|競業避止"), "誓約書", 0.7),
    # 英語パターン
    (re.compile(r"Non.Disclosure|Confidential", re.I), "秘密保持契約書", 0.9),
    (re.compile(r"License|Licens", re.I), "ライセンス契約書", 0.8),
    (re.compile(r"Employment|Employee", re.I), "雇用契約書", 0.8),
    (re.compile(r"Lease|Leasing", re.I), "賃貸借契約書", 0.8),
    (re.compile(r"Service.Level|SLA|SaaS|Cloud", re.I), "サービス利用契約書", 0.7),
    (re.compile(r"Master.Agreement|Master.Service", re.I), "基本契約書", 0.7),
    (re.compile(r"Distribution|Content.*Agreement|Data.*License", re.I), "ライセンス契約書", 0.8),
    (re.compile(r"Amendment|Addendum|Memorandum", re.I), "合意書・覚書", 0.8),
]

# 小分類の自動提案（中分類 → 本文パターンマッチ → 小分類）
_SUBTYPE_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("業務委託契約書", re.compile(r"SES|システムエンジニア|エンジニアリング|稼働時間|月額"), "SES契約（準委任型）"),
    ("業務委託契約書", re.compile(r"コンサルティング|コンサルタント|Consulting"), "コンサルティング契約"),
    ("業務委託契約書", re.compile(r"保守|運用|メンテナンス|Maintenance"), "保守運用委託"),
    ("請負契約書", re.compile(r"ソフトウェア|システム開発|SE"), "ソフトウェア開発請負"),
    ("請負契約書", re.compile(r"建設|工事|建築"), "建設工事請負"),
    ("賃貸借契約書", re.compile(r"オフィス|事務所|ビル"), "オフィス賃貸借"),
    ("賃貸借契約書", re.compile(r"駐車場|パーキング"), "駐車場賃貸借"),
    ("秘密保持契約書", re.compile(r"相互|双方|Mutual"), "相互NDA"),
    ("秘密保持契約書", re.compile(r"片務|一方|Unilateral"), "片務NDA"),
    ("秘密保持契約書", re.compile(r"入社|採用|Employment"), "入社時NDA"),
    ("ライセンス契約書", re.compile(r"ソフトウェア|Software"), "ソフトウェアライセンス"),
    ("ライセンス契約書", re.compile(r"特許|Patent"), "特許ライセンス"),
    ("ライセンス契約書", re.compile(r"商標|Trademark"), "商標ライセンス"),
    ("ライセンス契約書", re.compile(r"コンテンツ|Content|Distribution|配信"), "コンテンツ配信契約"),
    ("ライセンス契約書", re.compile(r"データ|Data|情報提供"), "データライセンス契約"),
    ("雇用契約書", re.compile(r"正社員|正規"), "正社員"),
    ("雇用契約書", re.compile(r"契約社員|有期"), "契約社員"),
    ("雇用契約書", re.compile(r"パート|アルバイト|パートタイム"), "パートタイム"),
    ("サービス利用契約書", re.compile(r"SaaS|クラウド|Cloud"), "SaaS利用契約"),
    ("サービス利用契約書", re.compile(r"SLA|サービスレベル"), "SLA"),
]


def _normalize(text: str) -> str:
    """NFKC正規化 + 小文字化。"""
    return unicodedata.normalize("NFKC", text).lower().strip()


def _rule_based_classify(
    name: str,
    text: str,
    existing_type: Optional[str] = None,
) -> dict:
    """
    ルールベース分類。タイトルキーワード + 既存メタデータ + 本文パターンを組み合わせる。
    """
    norm_name = _normalize(name or "")
    norm_text = _normalize(text[:2000] if text else "")

    contract_type: Optional[str] = None
    confidence: float = 0.0
    method = "rule"

    # 1) 既存メタデータの契約種別をヒントとして使用（最も信頼性高い）
    if existing_type:
        norm_existing = _normalize(existing_type)
        for raw, mapped in _LEGACY_TYPE_MAP.items():
            if norm_existing == _normalize(raw):
                contract_type = mapped
                confidence = 0.75
                method = "rule:existing_metadata"
                break

    # 2) タイトルキーワードマッチ（上書き：タイトルの方が信頼性高い）
    for pattern, ctype in _TITLE_PATTERNS:
        if pattern.search(name or ""):
            # タイトルマッチは既存メタデータより優先
            if confidence < 0.85:
                contract_type = ctype
                confidence = 0.85
                method = "rule:title"
            break

    # 3) 本文パターンマッチ（タイトルで決まらない場合の補助）
    if confidence < 0.6:
        best_body_type: Optional[str] = None
        best_body_score = 0.0
        body_match_counts: dict[str, float] = {}
        for pattern, ctype, weight in _BODY_PATTERNS:
            matches = len(pattern.findall(norm_text))
            if matches > 0:
                body_match_counts[ctype] = body_match_counts.get(ctype, 0) + weight * matches
        if body_match_counts:
            best_body_type = max(body_match_counts, key=lambda k: body_match_counts[k])
            best_body_score = min(body_match_counts[best_body_type] * 0.15, 0.7)
            if best_body_score > confidence:
                contract_type = best_body_type
                confidence = best_body_score
                method = "rule:body"

    if not contract_type:
        contract_type = "その他"
        confidence = 0.3
        method = "rule:fallback"

    category = _TYPE_TO_CATEGORY.get(contract_type, "誓約・同意・その他")

    # 4) 小分類の自動提案
    subtype: Optional[str] = None
    for ct, pattern, st in _SUBTYPE_PATTERNS:
        if ct == contract_type:
            if pattern.search(name or "") or pattern.search(text[:1000] if text else ""):
                subtype = st
                break

    return {
        "contract_category": category,
        "contract_type": contract_type,
        "contract_subtype": subtype,
        "classification_confidence": round(confidence, 2),
        "classification_method": method,
    }


# ============================================================
# Phase 2: LLMベース分類（gpt-4o-mini）
# ============================================================

_TAXONOMY_JSON = json.dumps(
    {cat: types for cat, types in TAXONOMY.items()},
    ensure_ascii=False,
    indent=2,
)

_LLM_SYSTEM_PROMPT = f"""あなたは日本の契約書分類の専門家です。
以下のタクソノミーに従い、契約書を正確に分類してください。

## 利用可能な分類体系
{_TAXONOMY_JSON}

## 出力形式（必ずこのJSON形式で回答）
{{
  "contract_category": "大分類名（上記タクソノミーの大分類のみ）",
  "contract_type": "中分類名（上記タクソノミーの中分類のみ）",
  "contract_subtype": "小分類名（自由記述、不明な場合はnull）",
  "confidence": 0.0〜1.0の数値,
  "reasoning": "分類理由（50文字以内）"
}}

## 注意事項
- contract_categoryとcontract_typeは必ず上記タクソノミーの値を使うこと
- 英語タイトルや英語本文でも適切に分類すること
- 「覚書」「Amendment」は合意書・覚書に分類すること
- 確信度が低い場合でも、最も近い分類を選ぶこと
"""


def _llm_classify(
    name: str,
    text: str,
    existing_type: Optional[str] = None,
) -> Optional[dict]:
    """
    LLM（gpt-4o-mini）を使った高精度分類。失敗時はNoneを返す。
    """
    try:
        from openai import OpenAI
        import os

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # 本文冒頭500文字 + 末尾200文字（前文・署名欄の情報を含む）
        body_excerpt = ""
        if text:
            head = text[:500]
            tail = text[-200:] if len(text) > 700 else ""
            body_excerpt = head + ("\n...\n" + tail if tail else "")

        existing_hint = f"\n既存の契約種別メタデータ: {existing_type}" if existing_type else ""

        user_content = f"""契約書名: {name or '（不明）'}
{existing_hint}

本文抜粋:
{body_excerpt or '（本文なし）'}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=20,
        )

        raw = response.choices[0].message.content
        result = json.loads(raw)

        # バリデーション
        cat = result.get("contract_category", "")
        ctype = result.get("contract_type", "")

        # タクソノミーに存在するか確認
        if cat not in TAXONOMY or ctype not in _TYPE_TO_CATEGORY:
            logger.warning(f"LLM returned unknown taxonomy value: {cat} / {ctype}")
            # 最も近い値に修正
            if cat not in TAXONOMY:
                cat = _TYPE_TO_CATEGORY.get(ctype, "誓約・同意・その他")
            if ctype not in _TYPE_TO_CATEGORY:
                ctype = "その他"

        confidence = float(result.get("confidence", 0.7))
        subtype = result.get("contract_subtype") or None
        if subtype == "null" or subtype == "":
            subtype = None

        return {
            "contract_category": cat,
            "contract_type": ctype,
            "contract_subtype": subtype,
            "classification_confidence": round(min(max(confidence, 0.0), 1.0), 2),
            "classification_method": "llm:gpt-4o-mini",
        }

    except Exception as e:
        logger.warning(f"LLM classification failed: {e}")
        return None


# ============================================================
# Public API
# ============================================================

def classify_contract(
    name: str,
    text: str,
    existing_type: Optional[str] = None,
    use_llm: bool = True,
) -> dict:
    """
    契約書を3階層タクソノミーで分類する。

    Args:
        name: 契約書名（ファイル名）
        text: 契約書本文テキスト（HTMLデコード済み）
        existing_type: 既存の契約種別メタデータ値（ヒントとして使用）
        use_llm: TrueならLLMを使用（信頼度が低い場合または常時）

    Returns:
        {
            "contract_category": str,  # 大分類
            "contract_type": str,      # 中分類
            "contract_subtype": Optional[str],  # 小分類
            "classification_confidence": float,
            "classification_method": str,
        }
    """
    # ルールベース分類（高速・常時実行）
    rule_result = _rule_based_classify(name, text, existing_type)

    # ルールで高信頼度なら即返す（LLMスキップ）
    if not use_llm or rule_result["classification_confidence"] >= 0.85:
        logger.info(
            f"[Classifier] '{name}' → {rule_result['contract_type']} "
            f"({rule_result['classification_confidence']:.2f}, {rule_result['classification_method']})"
        )
        return rule_result

    # LLMで高精度分類
    llm_result = _llm_classify(name, text, existing_type)

    if llm_result and llm_result["classification_confidence"] >= rule_result["classification_confidence"]:
        logger.info(
            f"[Classifier] '{name}' → {llm_result['contract_type']} "
            f"({llm_result['classification_confidence']:.2f}, {llm_result['classification_method']})"
        )
        return llm_result

    # LLM失敗またはルールの方が信頼度高い場合
    logger.info(
        f"[Classifier] '{name}' → {rule_result['contract_type']} "
        f"({rule_result['classification_confidence']:.2f}, rule fallback)"
    )
    return rule_result
