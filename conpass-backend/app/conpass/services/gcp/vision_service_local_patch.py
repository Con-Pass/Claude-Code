import io
import re
import base64
from logging import getLogger
from typing import List

logger = getLogger(__name__)


# ======== テキスト前処理 ========
def _preprocess_text(text: str) -> str:
    """pdfminer出力のアーティファクト（余分なスペース・改行）を除去"""
    text = re.sub(
        r'(?<=[\u3000-\u9fff\u4e00-\u9fff\uff00-\uffef])\s+(?=[\u3000-\u9fff\u4e00-\u9fff\uff00-\uffef])',
        '',
        text,
    )
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join(line.strip() for line in text.splitlines())
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _is_poor_quality_text(text: str, page_count: int) -> bool:
    """pdfminerのテキスト品質が低く、Vision OCRが必要か判定"""
    if not text.strip():
        return True
    chars_per_page = len(text) / max(page_count, 1)
    if chars_per_page < 50:
        return True
    # 日本語文字の直後にスペースが多い → スキャンPDFのアーティファクト
    jp_space_ratio = len(re.findall(r'[\u3040-\u9fff] ', text)) / max(len(text), 1)
    if jp_space_ratio > 0.02:
        return True
    # 数字の途中にスペースが入る（例: "20 2 6年"）→ 日付が壊れている可能性
    garbled_number_ratio = len(re.findall(r'\d \d', text)) / max(len(text), 1)
    if garbled_number_ratio > 0.003:
        return True
    return False


def _strip_html(html: str) -> str:
    """HTMLタグを除去してプレーンテキストを取得"""
    return re.sub(r'<[^>]+>', ' ', html).strip()


# ======== 本番OCRシステムプロンプト（conpass-ocr-gemini/main.py より） ========
_OCR_SYSTEM_PROMPT = (
    "You are a highly accurate OCR (Optical Character Recognition) system, specialized in converting "
    "documents into clean, semantic HTML. Your sole output must be HTML, "
    "without any additional text, explanations, or extraneous information.\n\n"
    "You should consider the formatting of each page. If there are multiple columns, "
    "you should output the left column first and then the right columns sequentially. "
    "**Output Format Constraints:**\n"
    "- **Encoding:** UTF-8 HTML.\n"
    "- **Structure:** The HTML must always start with `<html>` and end with `</html>`.\n\n"
    "- **Preserve Formatting:** Maintain headings, paragraphs, lists, and table structures "
    "as accurately as possible based on the visual layout in the document.\n"
    "- **Allowed Block Elements ONLY:** `<html>`, `<body>`, `<h1>`, `<h2>`, `<h3>`, `<h4>`, "
    "`<h5>`, `<h6>`, `<p>`, `<ol>`, `<ul>`, `<li>`, `<table>`, `<tr>`, `<td>`.\n"
    "- **Accuracy:** Strive for perfect accuracy in text extraction, including capitalization, "
    "punctuation, and special characters.\n"
)

_OCR_USER_PROMPT = (
    "Please meticulously analyze the provided image of a document and convert all "
    "written text into valid and structured HTML, strictly adhering to the "
    "system instructions regarding element usage, two-column table formatting, "
    "and output constraints. Ensure all text is captured accurately and in the "
    "correct reading order."
)


# ======== 本番エンティティ抽出システムプロンプト（conpass-entity-extraction-gpt/prompt1.txt より） ========
_ENTITY_SYSTEM_PROMPT = """\
Role:

あなたは一般法務の知識を有した2050年の最新の契約書特化型OCRシステムです。
契約書のOCR認識精度は99.999999%であり、その他のOCRシステムを凌駕しています。

Task:

あなたのシステムの長所を最大限に活かして、EntitiesをJSON formatに従って与えられた契約書の撮影画像またはテキストから抽出すること。Example text, Expected Json outputの出力形式を適宜参考にすること。
Penaltyを決して発生させないように上記タスクを完遂してください。

Attentions:
- **甲、乙、丙、丁の株式会社名、個人名の情報を正確に抽出することを得意としています。**
- **甲、乙、丙、丁の株式会社名や個人名は、特に慎重に確認し、画像に記載された通りに忠実に抽出してください。これらは認知度が低く、表記に違和感がある場合もありますが、他の類似表記に置き換えずにそのまま抽出してください。**
- カタカナ表記の固有名詞は、「デー(D)」と「ディー(D)」のように似た表記が誤認されやすいです。これらの正規化は行わず、画像に記載された通りの文字列をそのまま抽出してください。
- 甲、乙、丙、丁の情報は「以下、甲という」「以下、乙という」の直前に記載されていることがほとんどです。そのことに注意して契約書から該当する情報を正確に抽出してください。
- **甲・乙・丙・丁等の当事者表記がない文書（給与明細、証明書、在留カード、身分証明書等）では、発行者・発行機関・雇用主等の組織名をcompanyaに、受取者・対象者・カード保持者・被雇用者等の個人名をcompanybに抽出してください。個人名は「氏名」「NAME」「宛名」「〇〇様」「署名欄」等で確認できます。**
- **Entity'docid'の抽出に注意してください。管理番号は英数字（アルファベットと数字）を用いて表記され、契約書の左上、左下、右上、右下など各ページの四隅のいずれかに記載されています。特に契約書のヘッダー・フッターを確認し、英数字（アルファベットと数字）を原文通りに抽出してください。原文が言語的に誤りであっても絶対に推測せず、必ず原文どおりに抽出してください。

Penalty:
- **類似した表記/単語が株式会社名、個人名に含まれていても、その類似した他の表記/単語に勝手に書き換えてOCRを行ってはいけません。書き換えてしまった場合、重大な誤認と見なされます。**
- **類似したカタカナ表記については、誤認して正規化することなく、画像に記載された通りの文字列を抽出すること。これを怠ると、重大な誤認と見なされます。**

Entities:
title: 文書から文書自体のタイトルのみを抽出してください。原文に記載されているとおりの表記で抽出してください。
companya: 【甲/乙等の表記がある場合】甲と記載された左側、右側または下側に記載された会社名または団体名。会社名、団体名の記載がない場合は、個人名。契約書の冒頭部分または末文に記載された画像およびテキストに記載された通りに抽出。【甲/乙等の表記がない場合】文書の発行者・発行機関・雇用主・委託元など主体側の会社名または団体名。
companyb: 【甲/乙等の表記がある場合】乙と記載された左側、右側または下側に記載された会社名または団体名。会社名、団体名の記載がない場合は、個人名。契約書の冒頭部分または末文に記載された画像およびテキストに記載された通りに抽出。【甲/乙等の表記がない場合】文書の受取者・対象者・被雇用者・カード保持者等の個人名。氏名・NAME・宛名・〇〇様などで確認できる人物名を原文通りに抽出。
companyc: 【甲/乙等の表記がある場合】丙と記載された左側、右側または下側に記載された会社名または団体名。会社名、団体名の記載がない場合は、個人名。契約書の冒頭部分または末文に記載された画像およびテキストに記載された通りに抽出。【甲/乙等の表記がない場合】null。
companyd: 【甲/乙等の表記がある場合】丁と記載された左側、右側または下側に記載された会社名または団体名。会社名、団体名の記載がない場合は、個人名。契約書の冒頭部分または末文に記載された画像およびテキストに記載された通りに抽出。【甲/乙等の表記がない場合】null。
contractdate: 契約日。締結日,調印日,署名日,作成日,発行日,交付日,合意日,発効日など文書が成立または発効した日付に相当する表現を抽出。在留カード・証明書等の場合は「許可年月日」「交付年月日」「発行日」を使用。
contractstartdate: 契約開始日。契約開始日,発効日,適用開始日,有効期間開始日,効力発生日,実施開始日,履行開始日,サービス開始日,利用開始日,秘密保持開始日,開示開始日,業務開始日,委託開始日などに該当する日付。特別な記載がない場合は契約日と同一
contractenddate: 契約終了日。契約終了日,秘密保持終了日,開示終了日,情報提供終了日,契約満了日,終了期日,契約失効日,契約効力終了日,有効期間終了日,保護終了日,業務終了日,委託終了日,サービス提供終了日などに該当する日付。在留カード・証明書等の場合は「在留期間満了日」「有効期限」「このカードは〇〇まで有効」に該当する日付を使用。該当の日付がない場合は、契約開始日から起算して契約期間、有効期間に基づき契約終了日を記載する。
cancelnotice: 契約解除する場合の予告期間。"期間満了の3か月前までに"、"thirty (30) days prior written notice"など、記載された予告期間を説明する原文通りの表現で抽出。
cancelnotice_date: contractenddateからcancelnoticeの期間を遡及した解約予告通知日。
autoupdate: 自動更新の有無。具体的な記載がない場合は更新なしと判断
docid: 管理番号。管理番号は英数字を用いて表記され、各ページの四隅のいずれかに記載されていることが多い。管理番号、契約番号、No、IDなどの識別表記が併記されている英数字を優先して抽出。異なる管理番号が複数存在する場合は、契約本文内で記載数の多い方を優先して抽出。
related_contract_name: 契約書本文に明示的に記載されている{title}に関連する関連契約書名。
related_contract_date: The date explicitly associated with the {related_contract_name}, formatted as YYYY-MM-DD.
conpass_amount: {title}に基づく売上、請求金額
antisocialProvisions: 反社会的勢力に関する条文有無。具体的な記載がない場合はなしと判断
cort: 紛争が生じた場合の管轄裁判所。

JSON format:
{
  "title": string,
  "companya": string,
  "companyb": string,
  "companyc": string,
  "companyd": string,
  "contractdate": date (YYYY-MM-DD),
  "contractstartdate": date (YYYY-MM-DD),
  "contractenddate": date (YYYY-MM-DD),
  "cancelnotice": string,
  "cancelnotice_date": date (YYYY-MM-DD),
  "autoupdate": boolean (true/false),
  "docid": string,
  "related_contract_name": string,
  "related_contract_date": date (YYYY-MM-DD),
  "conpass_amount": integer,
  "antisocialProvisions": boolean (true/false),
  "cort": string
}

Example text:
"業務委託個別契約書
株式会社AAA（以下、甲という）、BBB株式会社（以下、乙という）、CCC有限会社（以下、丙という）、一般財団法人DDD（以下、丁という）...
甲乙丙丁との2024年7月31日付け、業務委託基本契約書(以下「原契約」という)に基づき...
本業務における甲への対価は年120万円とする。...
第20条 (反社会的勢力との関係の遮断)...
第33条 (管轄裁判所)
甲および乙は、 本契約および個別契約に関し紛争が生じた場合は、 東京地方裁判所を第一審の専属的合意管轄裁判所とする。...
第34条 (有効期限)
本契約の有効期限は契約締結の日から1ヵ年とする。ただし、期間満了2カ月前までに、甲乙いずれからも何等の申し出がないときは、本契約は更に1ヵ年間有効なものとし、以後も同様とする。...
2024年7月31日..."

Expected Json output:
{
  "title": "業務委託個別契約書",
  "companya": "株式会社AAA",
  "companyb": "BBB株式会社",
  "companyc": "CCC有限会社",
  "companyd": "一般財団法人DDD",
  "contractdate": "2024-07-31",
  "contractstartdate": "2024-07-31",
  "contractenddate": "2025-07-31",
  "cancelnotice": "期間満了の2ヶ月前",
  "cancelnotice_date": "2025-05-31",
  "autoupdate": true,
  "docid": null,
  "related_contract_name": "業務委託基本契約書",
  "related_contract_date": "2024-07-31",
  "conpass_amount": 1200000,
  "antisocialProvisions": true,
  "cort": "東京地方裁判所"
}
"""

# 本番JSONキー → ローカルDBラベルへのマッピング（変換が必要なもの）
_KEY_REMAP = {
    'antisocialProvisions': 'antisocial',
    'related_contract_name': 'related_contract',
}

# ローカルDBに存在するラベル一覧（これ以外のキーは無視）
_VALID_DB_LABELS = {
    'title', 'companya', 'companyb', 'companyc', 'companyd',
    'contractdate', 'contractstartdate', 'contractenddate',
    'cancelnotice', 'autoupdate', 'conpass_amount', 'antisocial',
    'related_contract', 'related_contract_date', 'docid', 'cort',
}

_MAX_CHARS = 8000
_MAX_VISION_PAGES = 15

# AI文書分類で使用する有効な文書種別リスト（conpass_contract_type）
_VALID_DOCUMENT_TYPES = [
    '秘密保持契約書', '雇用契約書', '申込注文書', '業務委託契約書',
    '売買契約書', '請負契約書', '賃貸借契約書', '派遣契約書',
    '金銭消費貸借契約', '代理店契約書', '業務提携契約書', 'ライセンス契約書',
    '顧問契約書', '譲渡契約書', '和解契約書', '誓約書', '証明書', 'その他',
]


# ======== GPT-4o Vision OCR ========
def _extract_text_with_gpt4o_vision(pdf_binary: bytes, openai_api_key: str, page_count: int) -> str:
    """GPT-4o vision APIで各ページをOCR（本番Gemini OCRと同じシステムプロンプト使用）"""
    try:
        from pdf2image import convert_from_bytes
        from openai import OpenAI

        client = OpenAI(api_key=openai_api_key)
        max_pages = min(page_count, _MAX_VISION_PAGES)
        images = convert_from_bytes(
            pdf_binary, dpi=100, fmt='jpeg',
            first_page=1, last_page=max_pages,
        )

        page_texts = []
        for i, img in enumerate(images):
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            resp = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': _OCR_SYSTEM_PROMPT},
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image_url',
                                'image_url': {
                                    'url': f'data:image/jpeg;base64,{img_b64}',
                                    'detail': 'high',
                                },
                            },
                            {'type': 'text', 'text': _OCR_USER_PROMPT},
                        ],
                    },
                ],
                max_tokens=4000,
                temperature=0,
            )
            page_html = resp.choices[0].message.content or ''
            # 本番と同様に ```html ``` を除去
            page_html = re.sub(r'```html|```', '', page_html)
            page_texts.append(page_html)
            logger.info(f'[LocalOCR] GPT-4o vision page {i + 1}/{max_pages}: {len(page_html)} chars (img_size={len(img_b64)}bytes)')

        full_html = '\n'.join(page_texts)
        logger.info(f'[LocalOCR] GPT-4o vision OCR complete: {len(full_html)} chars total')
        return full_html

    except Exception as e:
        logger.warning(f'[LocalOCR] GPT-4o vision OCR failed: {e}')
        return ''


def _extract_text_best_effort(pdf_binary: bytes, page_count: int = 1) -> str:
    """OCR優先順位: pdfminer → 品質不足なら GPT-4o vision（HTML形式）"""
    import os
    openai_api_key = os.environ.get('OPENAI_API_KEY', '')

    # Step 1: pdfminer（高速・無料）
    try:
        from pdfminer.high_level import extract_text
        raw = extract_text(io.BytesIO(pdf_binary)) or ''
        text = _preprocess_text(raw)
        logger.info(f'[LocalOCR] pdfminer: {len(text)} chars (raw: {len(raw)}), pages={page_count}')
    except Exception as e:
        logger.warning(f'[LocalOCR] pdfminer failed: {e}')
        text = ''

    # Step 2: pdfminer品質不足 → GPT-4o vision OCR（本番Gemini相当・HTML形式）
    if _is_poor_quality_text(text, page_count) and openai_api_key:
        logger.info('[LocalOCR] pdfminer quality poor → GPT-4o vision OCR')
        vision_html = _extract_text_with_gpt4o_vision(pdf_binary, openai_api_key, page_count)
        if vision_html and len(vision_html) > len(text):
            return vision_html

    return text or '（テキスト抽出なし）'


# ======== パッチ: ローカル開発用ローカルPDFテキスト抽出 ========
def _extract_text_local(pdf_info) -> str:
    """GCS Vision APIの代替：pdfminer/GPT-4o visionでテキスト抽出"""
    try:
        import pikepdf
        contents = pdf_info.contents
        try:
            with pikepdf.open(io.BytesIO(contents)) as pdf:
                page_count = len(pdf.pages)
        except Exception:
            page_count = 1
        return _extract_text_best_effort(contents, page_count)
    except Exception as e:
        logger.warning(f'[LocalOCR] _extract_text_local failed: {e}')
        return '（テキスト抽出失敗）'


# vision_service.pyに動的パッチ
from conpass.services.gcp import vision_service as _vs_module


_original_init = _vs_module.VisionService.__init__


def _patched_init(self):
    try:
        _original_init(self)
        self._local_fallback = False
    except Exception as e:
        logger.warning(f'[LocalOCR] VisionService init failed ({e}), using local fallback')
        self._local_fallback = True
        self.client = None


_original_get_text = _vs_module.VisionService.get_pdf_text_for_sync


def _patched_get_pdf_text(self, pdf_info) -> str:
    if getattr(self, '_local_fallback', False):
        return _extract_text_local(pdf_info)
    try:
        return _original_get_text(self, pdf_info)
    except Exception as e:
        logger.warning(f'[LocalOCR] Vision API failed ({e}), using local fallback')
        return _extract_text_local(pdf_info)


_vs_module.VisionService.__init__ = _patched_init
_vs_module.VisionService.get_pdf_text_for_sync = _patched_get_pdf_text
logger.info('[LocalOCR] VisionService patched with local fallback')


# ======== パッチ: GvPredict.get_predict の外部API失敗時フォールバック ========
def _patch_gv_predict():
    try:
        from conpass.services.growth_verse import gv_prediction as _gv_module
        _original_get_predict = _gv_module.GvPredict.get_predict

        def _patched_get_predict(self, gcs_files, conpass_contract_type, contract_id):
            try:
                return _original_get_predict(self, gcs_files, conpass_contract_type, contract_id)
            except Exception as e:
                logger.warning(f'[LocalOCR] GvPredict.get_predict failed ({e}), using local fallback')
                return _local_get_predict(self, gcs_files)

        _gv_module.GvPredict.get_predict = _patched_get_predict
        logger.info('[LocalOCR] GvPredict.get_predict patched with local fallback')
    except Exception as e:
        logger.warning(f'[LocalOCR] Failed to patch GvPredict: {e}')


def _extract_entities_from_text(text: str) -> list:
    """PDFテキストからエンティティを抽出する（OpenAI優先、regexフォールバック）"""
    import os
    api_key = os.environ.get('OPENAI_API_KEY', '')
    # エンティティ抽出はプレーンテキストで行う（HTML形式の場合はタグを除去）
    plain_text = _strip_html(text) if text.strip().startswith('<') else text
    if api_key and plain_text.strip():
        try:
            return _extract_with_openai(plain_text, api_key)
        except Exception as e:
            logger.warning(f'[LocalOCR] OpenAI extraction failed: {e}, falling back to regex')
    return _extract_with_regex(plain_text)


def _map_prediction(key: str, val) -> tuple:
    """
    本番JSON キー → ローカルDBラベルへ変換し、値も適切に変換する。
    本番 gv_prediction.py の _to_predicts() と同じ変換ロジック。
    戻り値: (db_label, content_str) または (None, None) で無視
    """
    # キー名のリマップ（本番 _to_predicts() と同様）
    db_label = _KEY_REMAP.get(key, key)

    # ローカルDBに存在しないラベルは無視
    if db_label not in _VALID_DB_LABELS:
        return None, None

    # 値の型変換
    if isinstance(val, bool):
        content = '有' if val else '無'
    elif val is None:
        return None, None
    else:
        content = str(val).strip()

    if not content or content.lower() in ('null', 'none', '', 'n/a', '-'):
        return None, None

    # conpass_amount が "None" の場合は無視（本番と同様）
    if db_label == 'conpass_amount' and content == 'None':
        return None, None

    return db_label, content


def _extract_with_openai(text: str, api_key: str) -> list:
    """本番と同じシステムプロンプト（prompt1.txt）でエンティティ抽出"""
    from openai import OpenAI
    import json as _json

    client = OpenAI(api_key=api_key)
    excerpt = text[:_MAX_CHARS]

    resp = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': _ENTITY_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'Contract:'},
                    {'type': 'text', 'text': excerpt},
                ],
            },
        ],
        response_format={'type': 'json_object'},
        max_tokens=4095,
        temperature=0,
    )
    data = _json.loads(resp.choices[0].message.content)

    predictions = []
    for key, val in data.items():
        db_label, content = _map_prediction(key, val)
        if db_label is None:
            continue
        predictions.append({
            'entity':  db_label,
            'content': content,
            'score':   0.92,
            'start':   0,
            'end':     len(content),
        })

    logger.info(f'[LocalOCR] OpenAI extracted {len(predictions)} entities')
    return predictions


def _extract_with_regex(text: str) -> list:
    """regexでエンティティ抽出（OpenAI失敗時のフォールバック）"""
    predictions = []

    # タイトル
    title_candidate = ''
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 4 and re.search(r'契約|協定|覚書|合意書|誓約書|念書', stripped):
            title_candidate = stripped[:80]
            break
    if not title_candidate:
        for line in text.splitlines():
            stripped = line.strip()
            if len(stripped) >= 4:
                title_candidate = stripped[:80]
                break
    if title_candidate:
        predictions.append({'entity': 'title', 'content': title_candidate, 'score': 0.70, 'start': 0, 'end': len(title_candidate)})

    # 会社名
    company_pattern = (
        r'(?:株式会社|有限会社|合同会社|一般社団法人|公益社団法人|'
        r'一般財団法人|公益財団法人|学校法人|医療法人|社会福祉法人)'
        r'\s*[\w\u3000-\u9fff\u4e00-\u9fff]+'
        r'|[\w\u3000-\u9fff\u4e00-\u9fff]+'
        r'\s*(?:株式会社|有限会社|合同会社)'
    )
    companies = list(dict.fromkeys(re.findall(company_pattern, text)))[:4]
    for i, label in enumerate(['companya', 'companyb', 'companyc', 'companyd'][:len(companies)]):
        c = companies[i].strip()
        predictions.append({'entity': label, 'content': c, 'score': 0.65, 'start': 0, 'end': len(c)})

    # 日付
    date_pattern = r'\d{4}年\s*\d{1,2}月\s*\d{1,2}日|\d{4}[/-]\d{1,2}[/-]\d{1,2}'
    dates = list(dict.fromkeys(re.findall(date_pattern, text)))[:3]
    for i, label in enumerate(['contractdate', 'contractstartdate', 'contractenddate'][:len(dates)]):
        d = dates[i].strip()
        predictions.append({'entity': label, 'content': d, 'score': 0.60, 'start': 0, 'end': len(d)})

    # 金額
    for amount in list(dict.fromkeys(re.findall(r'[¥￥][\d,]+|[\d,]+\s*万?円', text)))[:1]:
        a = amount.strip()
        predictions.append({'entity': 'conpass_amount', 'content': a, 'score': 0.60, 'start': 0, 'end': len(a)})

    # 自動更新
    if re.search(r'自動(?:的に)?更新|自動延長', text):
        predictions.append({'entity': 'autoupdate', 'content': '有', 'score': 0.70, 'start': 0, 'end': 1})

    # 反社条項
    if re.search(r'反社会的勢力|暴力団|不当要求行為|社会的排除', text):
        predictions.append({'entity': 'antisocial', 'content': '有', 'score': 0.70, 'start': 0, 'end': 1})

    # 解約通知期間
    cancel_match = re.search(
        r'(?:解約|更新拒絶|終了の申[し出入]).{0,30}?(\d+)\s*(?:ヶ月|ヵ月|か月|カ月|日|週間)前',
        text,
    )
    if cancel_match:
        content = cancel_match.group(0).strip()[:50]
        predictions.append({'entity': 'cancelnotice', 'content': content, 'score': 0.65, 'start': 0, 'end': len(content)})

    logger.info(f'[LocalOCR] regex extracted {len(predictions)} entities')
    return predictions


def _identify_document_from_image(pdf_binary: bytes, api_key: str) -> dict:
    """
    画像（PDF第1ページ）からAIが直接文書種別とタイトルを識別する。
    テキスト抽出の精度に依存しない視覚的な判定を行う。
    戻り値: {'title': str, 'document_type': str}
    """
    try:
        from pdf2image import convert_from_bytes
        from openai import OpenAI
        import os

        images = convert_from_bytes(pdf_binary, dpi=100, fmt='png', first_page=1, last_page=1)
        if not images:
            return {}

        buf = io.BytesIO()
        images[0].save(buf, format='PNG')
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        type_list = '、'.join(_VALID_DOCUMENT_TYPES)
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{img_b64}', 'detail': 'low'},
                    },
                    {
                        'type': 'text',
                        'text': (
                            'この文書を見て以下を日本語で答えてください。\n'
                            '1. 文書の正式名称（例: 運転免許証、業務委託契約書 など）\n'
                            f'2. 文書種別（次のリストから1つ選ぶ）: {type_list}\n\n'
                            '回答形式:\n'
                            'タイトル: <正式名称>\n'
                            '種別: <種別>'
                        ),
                    },
                ],
            }],
            max_tokens=80,
            temperature=0,
        )
        content = resp.choices[0].message.content or ''
        result = {}
        for line in content.splitlines():
            if line.startswith('タイトル:'):
                result['title'] = line.split(':', 1)[1].strip()
            elif line.startswith('種別:'):
                doc_type = line.split(':', 1)[1].strip()
                if doc_type in _VALID_DOCUMENT_TYPES:
                    result['document_type'] = doc_type
        logger.info(f'[LocalOCR] image identification: {result}')
        return result
    except Exception as e:
        logger.warning(f'[LocalOCR] image identification failed: {e}')
        return {}


def _classify_document_type(title: str, body_text: str, api_key: str) -> str:
    """タイトルと本文テキストから文書種別をAI（gpt-4o-mini）で分類する"""
    plain_body = _strip_html(body_text) if body_text.strip().startswith('<') else body_text
    type_list = '\n'.join(f'- {t}' for t in _VALID_DOCUMENT_TYPES)
    system_prompt = (
        "あなたは文書分類の専門家です。文書のタイトルと本文から種別を判定してください。\n\n"
        "【重要な分類ルール】\n"
        "- 免許証、運転免許証、パスポート、マイナンバーカード、健康保険証、住民票、"
        "  戸籍謄本、印鑑証明書、資格証明書、登記事項証明書、納税証明書など"
        "  公的な証明書・身分証明書類は必ず「証明書」に分類すること\n"
        "- 契約や合意を結ぶ文書は該当する契約種別を選ぶこと\n"
        "- どの種別にも当てはまらない場合のみ「その他」を選ぶこと\n\n"
        f"選択肢（必ずこのリストから1つ選ぶ）:\n{type_list}"
    )
    user_prompt = (
        f"タイトル: {title or '不明'}\n"
        f"本文（先頭500文字）: {plain_body[:500]}\n\n"
        f"文書種別（上記リストから1つだけ）:"
    )
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=30,
            temperature=0,
        )
        result = resp.choices[0].message.content.strip()
        if result in _VALID_DOCUMENT_TYPES:
            logger.info(f'[LocalOCR] document_type classified: {result}')
            return result
        logger.warning(f'[LocalOCR] classification returned unknown type: {result!r}, fallback to その他')
    except Exception as e:
        logger.warning(f'[LocalOCR] document type classification failed: {e}')
    return 'その他'


def _local_get_predict(self, gcs_files):
    """GrowthVerse/VisionAPI失敗時のローカルフォールバック（ローカルファイル直接読み込み）"""
    import pikepdf
    import os
    UPLOAD_DIR = '/app/media/uploads'
    predictfiles = []
    document_type = 'その他'

    for file in gcs_files:
        try:
            local_filename = file.url.replace('/', '_')
            local_path = os.path.join(UPLOAD_DIR, local_filename)
            logger.info(f'[LocalOCR] reading from {local_path}')
            with open(local_path, 'rb') as f:
                pdf_binary = f.read()

            with pikepdf.open(io.BytesIO(pdf_binary)) as pdf:
                page_size = len(pdf.pages)

            api_key = os.environ.get('OPENAI_API_KEY', '')

            # Step1: 画像から直接文書種別とタイトルを識別（最も信頼性が高い・高速）
            # OCRより先に実行することで文書種別を早期確定できる
            image_identification = {}
            if api_key:
                image_identification = _identify_document_from_image(pdf_binary, api_key)

            # pdfminer → 品質不足なら GPT-4o vision OCR（HTML形式）
            text = _extract_text_best_effort(pdf_binary, page_size)
            logger.info(f'[LocalOCR] final text: {len(text)} chars, pages={page_size}')

            predictions = _extract_entities_from_text(text)

            # Step2: 画像識別でタイトルが取れた場合は entity prediction を上書き
            if image_identification.get('title'):
                img_title = image_identification['title']
                # 既存の title 予測を置き換え
                predictions = [p for p in predictions if p.get('entity') != 'title']
                predictions.insert(0, {
                    'entity': 'title', 'content': img_title,
                    'score': 0.97, 'start': 0, 'end': len(img_title),
                })

            # Step3: 文書種別を決定（画像識別 > テキスト分類 の優先順位）
            if image_identification.get('document_type'):
                document_type = image_identification['document_type']
                logger.info(f'[LocalOCR] document_type from image: {document_type}')
            elif api_key and text and text != '（テキスト抽出なし）':
                extracted_title = next(
                    (p['content'] for p in predictions if p.get('entity') == 'title'), ''
                )
                document_type = _classify_document_type(extracted_title, text, api_key)

        except Exception as e2:
            logger.error(f'[LocalOCR] local fallback failed: {e2}')
            text = ''
            page_size = 1
            predictions = []

        predictfiles.append({'predictions': predictions, 'body': text, 'pdf_page_size': page_size})

    return {'files': predictfiles, 'document_type': document_type}


_patch_gv_predict()
