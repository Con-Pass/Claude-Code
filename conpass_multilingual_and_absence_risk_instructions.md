# ConPass コンプライアンスエンジン 実装指示書
# 多言語対応 + absence_is_risk フラグ

## ファイル配置ガイド

```
conpass/
├── docs/                              # ← 設計ドキュメント
│   ├── conpass_compliance_engine_spec.md     # 既存：全体仕様書
│   ├── multilingual_structure_markers.md     # ★新規：多言語マーカー定義
│   └── absence_is_risk_spec.md              # ★新規：フラグ仕様
│
├── compliance/                        # ← コンプライアンスエンジン本体
│   ├── checkpoints/                   # チェックポイントJSON格納
│   │   ├── checkpoint_haiso.json
│   │   ├── checkpoint_toritekiho.json
│   │   └── checkpoint_new_lease.json  # ★更新：absence_is_risk追加
│   │
│   ├── pre_validate.py                # ★更新：多言語マーカー追加
│   ├── language_detect.py             # ★新規：言語検出モジュール
│   ├── prompt_builder.py              # ★更新：言語コンテキスト追加
│   ├── evaluate.py                    # ★更新：レスポンスに言語フラグ
│   └── checkpoint_generator.py        # ★新規：チェックポイント生成時のフラグ自動判定
│
├── prompts/                           # プロンプトテンプレート
│   ├── compliance_checkpoint_mode.txt # ★更新：判定厳守ルール追加
│   └── checkpoint_generation.txt      # ★新規：チェックポイント生成プロンプト
│
└── tests/
    └── test_multilingual.py           # ★新規：多言語テスト
```

> **注意**: 上記はプロジェクトの標準的なディレクトリ構成の想定です。
> 実際のリポジトリ構成に合わせて適宜読み替えてください。
> 配置先が不明な場合は `find . -name "pre_validate*"` 等で既存ファイルの場所を確認してください。

---

## 実装指示 1/5: 多言語構造マーカー（pre_validate.py）

### 目的
英語・中国語・韓国語等の契約書が `pre_validate_contract_text()` で
UNREADABLE として誤って除外されるのを防ぐ。

### 指示

`pre_validate_contract_text()` 内の `structure_markers` を以下に置き換えてください。
また、正規表現による条文番号パターン検出を追加し、OR条件で判定してください。

```python
import re

def pre_validate_contract_text(contract_text: str) -> dict:
    """契約書テキストの前処理バリデーション"""

    # ガード1: テキスト長チェック（変更なし）
    if len(contract_text.strip()) < 100:
        return {
            "risk_level": "UNREADABLE",
            "reason": "テキストが短すぎます（100文字未満）。PDF解析に失敗している可能性があります。",
            "gaps": []
        }

    # ガード2: 契約書構造の検出（多言語対応版）
    structure_markers = [
        # ===== 日本語 =====
        "第1条", "第１条", "第一条", "条項", "契約",
        "甲", "乙", "委託", "受託", "賃貸借",

        # ===== 英語 =====
        "Article", "Section", "Clause", "Agreement", "Contract",
        "ARTICLE", "SECTION", "CLAUSE", "AGREEMENT", "CONTRACT",
        "shall", "herein", "hereby", "hereof", "thereof",
        "Party", "Parties", "PARTIES",
        "Whereas", "WHEREAS",
        "Term", "TERM",

        # ===== 中国語（簡体字） =====
        "第一条", "合同", "协议", "甲方", "乙方",
        "条款", "签订", "履行", "违约", "争议",
        "本合同", "双方", "委托",

        # ===== 中国語（繁体字） =====
        "協議", "條款", "簽訂", "履行", "違約",
        "本合約", "雙方", "委託",

        # ===== 韓国語 =====
        "제1조", "제2조", "제3조",
        "계약", "계약서", "협정",
        "갑", "을",
        "조항", "체결", "이행", "위반",
        "본 계약", "쌍방", "당사자",

        # ===== フランス語 =====
        "Contrat", "Convention", "Accord",
        "CONTRAT", "CONVENTION", "ACCORD",
        "Préambule", "Dispositions",
        "les parties", "Les Parties", "LES PARTIES",
        "ci-après", "dénommé",
        "en vertu de", "aux termes de",

        # ===== スペイン語 =====
        "Artículo", "Contrato", "Convenio", "Acuerdo",
        "CONTRATO", "CONVENIO", "ACUERDO",
        "Cláusula", "CLÁUSULA",
        "Las partes", "LAS PARTES",
        "en adelante", "denominado",
        "por una parte", "por otra parte",

        # ===== ドイツ語 =====
        "Vertrag", "Vereinbarung", "Abkommen",
        "VERTRAG", "VEREINBARUNG",
        "Artikel", "Klausel", "Paragraph",
        "die Parteien", "Vertragsparteien",
        "im Folgenden", "hiermit",
        "Präambel",

        # ===== ポルトガル語 =====
        "Contrato", "Acordo", "Convênio",
        "CONTRATO", "ACORDO",
        "Cláusula", "CLÁUSULA",
        "As partes", "AS PARTES",
        "doravante denominado",

        # ===== イタリア語 =====
        "Contratto", "Accordo", "Convenzione",
        "CONTRATTO", "ACCORDO",
        "Articolo", "Clausola",
        "Le parti", "LE PARTI",
        "di seguito denominato",

        # ===== ロシア語 =====
        "Договор", "Соглашение", "Контракт",
        "ДОГОВОР", "СОГЛАШЕНИЕ",
        "Статья", "Пункт",
        "Стороны", "стороны",
        "именуемый", "далее",

        # ===== アラビア語 =====
        "عقد", "اتفاقية", "اتفاق",
        "المادة", "البند",
        "الطرف الأول", "الطرف الثاني",
        "الأطراف",

        # ===== タイ語 =====
        "สัญญา", "ข้อตกลง",
        "ข้อ", "มาตรา",
        "คู่สัญญา",

        # ===== ベトナム語 =====
        "Hợp đồng", "Thỏa thuận",
        "Điều", "Khoản",
        "Các bên", "Bên A", "Bên B",

        # ===== インドネシア語 / マレー語 =====
        "Perjanjian", "Kontrak", "Kesepakatan",
        "Pasal", "Ayat",
        "Para Pihak", "Pihak Pertama", "Pihak Kedua",

        # ===== ヒンディー語 =====
        "अनुबंध", "समझौता", "करार",
        "अनुच्छेद", "धारा",
        "पक्ष",
    ]

    # 方法1: マーカーリストで検出
    has_marker = any(marker in contract_text for marker in structure_markers)

    # 方法2: 正規表現で条文番号パターンを検出（言語非依存の補完）
    has_article_pattern = bool(re.search(
        r'('
        r'第[一二三四五六七八九十\d１２３４５６７８９０]+条'   # 日本語・中国語
        r'|제\s*\d+\s*조'                                      # 韓国語
        r'|[Aa]rt(?:icle|ículo|icolo|igo)\.?\s*\d+'            # 英仏西伊葡
        r'|[Ss]ection\s+\d+'                                    # 英語
        r'|[Cc]lause\s+\d+'                                     # 英語
        r'|[Cc]láusula\s+\d+'                                   # 西葡語
        r'|§\s*\d+'                                             # ドイツ語等
        r'|Статья\s+\d+'                                        # ロシア語
        r'|المادة\s+\d+'                                        # アラビア語
        r'|Điều\s+\d+'                                          # ベトナム語
        r'|Pasal\s+\d+'                                         # インドネシア語
        r')',
        contract_text
    ))

    if not has_marker and not has_article_pattern:
        return {
            "risk_level": "UNREADABLE",
            "reason": "契約書の基本構造（条文番号・契約キーワード等）が検出できません。"
                      "対象文書が契約書でないか、PDF解析に失敗している可能性があります。",
            "gaps": []
        }

    # ガード3: 文字化け率チェック（変更なし）
    # ... 既存のロジックをそのまま維持 ...
```

---

## 実装指示 2/5: 言語検出モジュール（language_detect.py）新規作成

### 目的
インジェスト時に契約書の言語を検出し、メタデータに保存する。

### 依存パッケージ

```bash
pip install langdetect
```

### コード

```python
"""
契約書テキストの言語検出モジュール

使い方:
    from compliance.language_detect import detect_contract_language

    result = detect_contract_language(contract_text)
    # => {"language_code": "en", "language_name": "English", "confidence": 0.99, "is_japanese": False}
"""

from langdetect import detect_langs, LangDetectException

# 言語コード → 表示名マッピング
LANGUAGE_NAMES = {
    "ja": "日本語",
    "en": "English",
    "zh-cn": "中文（简体）",
    "zh-tw": "中文（繁體）",
    "ko": "한국어",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "pt": "Português",
    "it": "Italiano",
    "ru": "Русский",
    "ar": "العربية",
    "th": "ภาษาไทย",
    "vi": "Tiếng Việt",
    "id": "Bahasa Indonesia",
    "ms": "Bahasa Melayu",
    "hi": "हिन्दी",
}


def detect_contract_language(contract_text: str) -> dict:
    """
    契約書テキストの言語を検出する。

    Args:
        contract_text: 契約書の全文テキスト

    Returns:
        dict: {
            "language_code": str,    # ISO 639-1 コード（例: "ja", "en", "zh-cn"）
            "language_name": str,    # 表示用言語名（例: "日本語", "English"）
            "confidence": float,     # 検出信頼度 0.0〜1.0
            "is_japanese": bool      # 日本語かどうか
        }
    """
    try:
        detected = detect_langs(contract_text[:5000])  # 先頭5000文字で十分
        primary = detected[0]
        lang_code = primary.lang
        return {
            "language_code": lang_code,
            "language_name": LANGUAGE_NAMES.get(lang_code, lang_code),
            "confidence": round(primary.prob, 3),
            "is_japanese": lang_code == "ja"
        }
    except LangDetectException:
        return {
            "language_code": "unknown",
            "language_name": "不明",
            "confidence": 0.0,
            "is_japanese": False
        }
```

### インジェストパイプラインへの組み込み

契約書のインジェスト処理（テキスト抽出後、DB保存前）に以下を追加してください。

```python
from compliance.language_detect import detect_contract_language

# テキスト抽出後
language_info = detect_contract_language(contract_text)

# 契約書メタデータに保存
contract_metadata["language_code"] = language_info["language_code"]
contract_metadata["language_name"] = language_info["language_name"]
contract_metadata["language_confidence"] = language_info["confidence"]
contract_metadata["is_japanese"] = language_info["is_japanese"]
```

---

## 実装指示 3/5: プロンプトへの言語コンテキスト追加（prompt_builder.py）

### 目的
LLMが日本語チェックポイントと外国語契約書のブリッジを正しく行えるようにする。

### 変更箇所

プロンプト組み立て部分で、契約書テキストの直前に言語情報を挿入してください。

```python
def build_compliance_prompt(
    law_config: dict,
    articles_block: str,
    contract_text: str,
    language_info: dict,       # ← 引数追加
    evaluation_mode: str = "checkpoint"
) -> str:
    """コンプライアンス判定プロンプトを組み立てる"""

    # ... 既存のプロンプト組み立て処理 ...

    # 言語コンテキストブロック（契約書テキストの直前に挿入）
    if language_info and not language_info.get("is_japanese", True):
        language_context = f"""
【契約書の言語】{language_info['language_code']}（{language_info['language_name']}）
※チェックポイントおよび法令条文は日本語で記述されていますが、
  契約書は{language_info['language_name']}で記載されています。
  契約書の言語で同等の条項・記載を照合してください。
  contract_referenceには契約書の原文（{language_info['language_name']}）をそのまま引用してください。
"""
    else:
        language_context = ""

    # 最終プロンプト組み立て
    prompt = f"""
{law_block}

{articles_block}

{rules_block}

{language_context}

【評価対象の契約書テキスト】
{contract_text}

{evaluation_steps}
"""
    return prompt
```

---

## 実装指示 4/5: レスポンスへの言語フラグ付加（evaluate.py）

### 目的
判定結果に言語情報を含め、UI側で外国語契約を識別できるようにする。

### 変更箇所

LLM判定結果の後処理で言語フラグを追加してください。

```python
def build_evaluation_response(
    llm_result: dict,
    language_info: dict,       # ← 引数追加
    evaluation_mode: str
) -> dict:
    """LLM判定結果をレスポンス形式に整形する"""

    response = {
        "contract_id": llm_result["contract_id"],
        "risk_level": llm_result["risk_level"],
        "mode": evaluation_mode,
        "gap_count": len(llm_result.get("gaps", [])),
        "gaps": llm_result.get("gaps", []),

        # ★ 言語フラグ追加
        "language": {
            "code": language_info.get("language_code", "ja"),
            "name": language_info.get("language_name", "日本語"),
            "is_japanese": language_info.get("is_japanese", True)
        }
    }

    return response
```

### UI側の表示（参考）

```
is_japanese: false の場合 → 「🌐 外国語契約（English）」バッジ表示
is_japanese: true の場合  → バッジなし（通常表示）
```

---

## 実装指示 5/5: absence_is_risk フラグの半自動化

### 目的
チェックポイント生成時に `absence_is_risk` フラグをLLMに同時判定させ、
コンプライアンス判定プロンプトでの挙動を制御する。

### 5-A: チェックポイントJSONスキーマ更新

全チェックポイントJSONに `absence_is_risk` と `absence_is_risk_reason` を追加してください。

```json
{
  "id": "LEASE-01",
  "requirement": "オンバランス化判定",
  "legal_basis": ["企業会計基準第34号 第5項", "第16項"],
  "default_severity": "HIGH",
  "description": "使用権資産およびリース負債のオンバランス化が必要となるリース取引の判定要素が契約に含まれているか",
  "absence_is_risk": true,
  "absence_is_risk_reason": "使用権資産の計上に関する記載がない場合、会計処理の見落としリスクがある",
  "compliant_patterns": ["..."],
  "compliant_keywords": ["..."],
  "violation_patterns": ["..."],
  "violation_keywords": ["..."]
}
```

### 5-B: 既存3法令のフラグ設定値

以下の値を各チェックポイントJSONに適用してください。

#### 廃掃法（checkpoint_haiso.json）

| ID | absence_is_risk | 理由 |
|---|---|---|
| HAISO-01 二者契約の原則 | `true` | 直接契約の記載がなければ再委託リスク |
| HAISO-02 廃棄物の種類・数量 | `true` | 法定必須記載事項の欠落 |
| HAISO-03 処分場所・方法 | `true` | 法定必須記載事項の欠落 |
| HAISO-04 委託料金 | `true` | 法定必須記載事項の欠落 |
| HAISO-05 許可証の確認 | `true` | 法定必須記載事項の欠落 |
| HAISO-06 マニフェスト | `false` | 記載内容の不備が問題 |
| HAISO-07 再委託禁止 | `true` | 再委託禁止条項の欠落自体がリスク |
| HAISO-08 契約解除時の処理未了 | `true` | 解除時対応の欠落自体がリスク |
| HAISO-09 適正処理情報 | `true` | 法定必須記載事項の欠落 |
| HAISO-10 最終処分情報 | `true` | 法定必須記載事項の欠落 |

#### 取適法（checkpoint_toritekiho.json）

| ID | absence_is_risk | 理由 |
|---|---|---|
| TORI-01 業務内容書面明示 | `true` | 書面交付義務の不履行 |
| TORI-02 報酬額事前明示 | `true` | 書面交付義務の不履行 |
| TORI-03 60日支払期限 | `false` | 記載された支払期日の内容が問題 |
| TORI-04 受領拒否禁止 | `false` | 記載された条件の内容が問題 |
| TORI-05 報酬減額禁止 | `false` | 記載された条件の内容が問題 |
| TORI-06 不当やり直し禁止 | `false` | 記載された条件の内容が問題 |
| TORI-07 経済利益提供要請禁止 | `false` | 記載された条件の内容が問題 |
| TORI-08 過度な競業避止 | `false` | 記載された制約の内容が問題 |
| TORI-09 中途解除予告義務 | `true` | 予告条項の欠落自体がリスク |
| TORI-10 支払期日明示 | `true` | 書面交付義務の不履行 |

#### 新リース会計基準（checkpoint_new_lease.json）

| ID | absence_is_risk | 理由 |
|---|---|---|
| LEASE-01 オンバランス化判定 | `true` | 判定要素の欠落で会計処理の見落としリスク |
| LEASE-02 変動リース料 | `false` | 記載された変動条件の内容が問題 |
| LEASE-03 自動更新・延長オプション | `false` | 記載された更新条件の内容が問題 |
| LEASE-04 原状回復義務 | `false` | 記載された義務内容が問題 |
| LEASE-05 中途解約オプション | `false` | 記載された解約条件の内容が問題 |
| LEASE-06 非リース構成要素 | `true` | 区分がなければ会計処理の誤りリスク |
| LEASE-07 購入オプション | `false` | 記載された購入条件の内容が問題 |
| LEASE-08 少額リース免除 | `true` | 少額判定の記載がなければ免除適用の見落としリスク |
| LEASE-09 リース期間の定義 | `false` | 記載された期間の内容が問題 |

### 5-C: チェックポイント生成プロンプト（新規法令追加時用）

新しい法令のチェックポイントをLLMに生成させる際、以下をプロンプトに含めてください。
保存先: `prompts/checkpoint_generation.txt`

```
あなたは日本の法令に精通したコンプライアンス専門家です。
以下の法令について、契約書のコンプライアンスチェックに使用する
チェックポイントを生成してください。

【法令情報】
法令名: {law_name}
法令ID: {law_id}
関連条文: {law_articles}

【出力形式】
以下のJSON形式で出力してください。

{{
  "law_id": "{law_id}",
  "law_name": "{law_name}",
  "checkpoints": [
    {{
      "id": "{LAW_ID}-01",
      "requirement": "要件名（簡潔に）",
      "legal_basis": ["根拠条文（例: 第6条の2第1号）"],
      "default_severity": "HIGH / MEDIUM / LOW",
      "description": "この要件が契約書でなぜ重要かの説明",
      "absence_is_risk": true または false,
      "absence_is_risk_reason": "true の場合: なぜ記載がないこと自体がリスクなのか / false の場合: 空文字",
      "compliant_patterns": ["適合と判断できるパターンの自然言語記述"],
      "compliant_keywords": ["適合を示すキーワード"],
      "violation_patterns": ["違反と判断できるパターンの自然言語記述"],
      "violation_keywords": ["違反を示すキーワード"]
    }}
  ]
}}

【absence_is_risk の判定基準】
各チェックポイントについて、以下を判定してください：
- true: 「契約書にこの要件に関する記載がないこと自体」がリスクとなるもの
  例: 法定必須記載事項の欠落、書面交付義務の不履行、
      会計上の考慮事項の欠落
- false: 「記載された内容が不適切であること」が問題となるもの
  例: 支払期日が法定上限を超えている、禁止事項に違反する条件がある

判断に迷う場合は true を設定してください（安全側に倒す）。

【チェックポイント数】
1法令あたり10前後を目安にしてください。
法定必須記載事項が多い法令は超過しても構いません。

【severity の基準】
- HIGH: 法令違反に直結する、または重大な会計処理の誤りにつながる
- MEDIUM: リスクはあるが即座に法令違反とはならない
- LOW: 推奨事項、ベストプラクティスレベル

【キーワード設計の注意】
- compliant_keywords: 部分一致で適合と判断できる具体的な語句
  NG例: 「承諾」（文脈次第で違反にもなる）
  OK例: 「書面による事前承諾を得た場合に限り」
- violation_keywords: 部分一致で違反と判断できる具体的な語句
  文脈が重要な場合は十分な長さのフレーズにする
```

### 5-D: コンプライアンス判定プロンプトへの反映

`prompts/compliance_checkpoint_mode.txt` に以下のルールを追加してください。

```
【「該当する記載なし」の使用ルール】

各チェックポイントには absence_is_risk フラグがあります。

■ absence_is_risk: true の場合
  → 契約書に該当する記載がない場合、それ自体がリスクです。
  → gapとして登録し、contract_reference に「該当する記載なし」と記載してください。

■ absence_is_risk: false の場合
  → 契約書に該当する記載がない場合、リスクではありません。
  → COMPLIANT としてください。
  → 「該当する記載なし」は使用しないでください。

【重要】absence_is_risk: false のチェックポイントで「該当する記載なし」を
contract_reference に使うことは禁止です。この場合は必ず COMPLIANT にしてください。
```

---

## テスト指示

### 動作確認項目

```python
# test_multilingual.py

def test_structure_markers_japanese():
    """日本語契約書がUNREADABLEにならないこと"""
    text = "第1条 本契約は甲と乙の間で..."
    result = pre_validate_contract_text(text * 10)  # 100文字以上
    assert result["risk_level"] != "UNREADABLE"

def test_structure_markers_english():
    """英文契約書がUNREADABLEにならないこと"""
    text = "Article 1. This Agreement is entered into between Party A and Party B..."
    result = pre_validate_contract_text(text * 10)
    assert result["risk_level"] != "UNREADABLE"

def test_structure_markers_chinese():
    """中国語契約書がUNREADABLEにならないこと"""
    text = "第一条 本合同由甲方与乙方签订..."
    result = pre_validate_contract_text(text * 10)
    assert result["risk_level"] != "UNREADABLE"

def test_structure_markers_korean():
    """韓国語契約書がUNREADABLEにならないこと"""
    text = "제1조 본 계약은 갑과 을 사이에..."
    result = pre_validate_contract_text(text * 10)
    assert result["risk_level"] != "UNREADABLE"

def test_structure_markers_non_contract():
    """契約書でないテキストがUNREADABLEになること"""
    text = "今日はいい天気ですね。散歩に行きましょう。" * 10
    result = pre_validate_contract_text(text)
    assert result["risk_level"] == "UNREADABLE"

def test_language_detection():
    """言語検出が正しく動作すること"""
    assert detect_contract_language("本契約は...")["language_code"] == "ja"
    assert detect_contract_language("This Agreement...")["language_code"] == "en"
    assert detect_contract_language("本合同由...")["language_code"] in ["zh-cn", "zh-tw"]
    assert detect_contract_language("본 계약은...")["language_code"] == "ko"

def test_absence_is_risk_flag():
    """absence_is_riskフラグが全チェックポイントに設定されていること"""
    import json
    for filename in ["checkpoint_haiso.json", "checkpoint_toritekiho.json", "checkpoint_new_lease.json"]:
        with open(f"compliance/checkpoints/{filename}") as f:
            data = json.load(f)
        for cp in data["checkpoints"]:
            assert "absence_is_risk" in cp, f"{cp['id']} に absence_is_risk がありません"
            assert isinstance(cp["absence_is_risk"], bool), f"{cp['id']} の absence_is_risk が bool ではありません"
```

---

## 実装順序（推奨）

| 順序 | タスク | 依存 |
|---|---|---|
| 1 | 多言語構造マーカー（pre_validate.py） | なし |
| 2 | 言語検出モジュール（language_detect.py） | pip install langdetect |
| 3 | インジェストパイプラインに言語検出を組み込み | 2完了後 |
| 4 | プロンプトに言語コンテキスト追加（prompt_builder.py） | 2完了後 |
| 5 | レスポンスに言語フラグ付加（evaluate.py） | 2完了後 |
| 6 | チェックポイントJSONにabsence_is_riskフラグ追加 | なし |
| 7 | 判定プロンプトにabsence_is_riskルール追加 | 6完了後 |
| 8 | テスト実行 | 全完了後 |

1と6は並行作業可能です。
