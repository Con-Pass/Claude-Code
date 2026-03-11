"""
respond: 法務照会対応ドラフト生成
テンプレートロード -> エスカレーションチェック -> 変数置換・文案生成 -> ドラフト返却
"""
import json
from typing import Optional

import httpx
from llama_index.llms.openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

API_TIMEOUT = httpx.Timeout(10.0)

# --- 照会タイプ別デフォルトテンプレート ---

DEFAULT_TEMPLATES: dict[str, str] = {
    "dsr": (
        "データ主体のリクエスト（DSR）への回答ドラフト:\n\n"
        "{{requester_name}} 様\n\n"
        "お問い合わせいただきました個人データに関するリクエストについて、"
        "以下の通りご回答いたします。\n\n"
        "リクエスト種別: {{request_type}}\n"
        "対応内容: {{response_detail}}\n\n"
        "ご不明点がございましたら、お気軽にお問い合わせください。"
    ),
    "hold": (
        "リーガルホールド通知ドラフト:\n\n"
        "関係者各位\n\n"
        "本件に関連する全ての文書・電子データの保全をお願いいたします。\n\n"
        "対象案件: {{matter_name}}\n"
        "保全開始日: {{hold_start_date}}\n"
        "対象範囲: {{scope}}\n\n"
        "詳細については法務部門までお問い合わせください。"
    ),
    "vendor": (
        "取引先からの照会への回答ドラフト:\n\n"
        "{{vendor_name}} 御中\n\n"
        "お問い合わせの件、下記の通りご回答いたします。\n\n"
        "照会内容: {{inquiry_detail}}\n"
        "回答: {{response_detail}}\n\n"
        "何卒よろしくお願いいたします。"
    ),
    "nda": (
        "NDA 関連照会への回答ドラフト:\n\n"
        "{{counterparty}} 様\n\n"
        "秘密保持契約に関するお問い合わせについて回答いたします。\n\n"
        "{{response_detail}}"
    ),
    "privacy": (
        "プライバシーに関する照会への回答ドラフト:\n\n"
        "{{requester_name}} 様\n\n"
        "個人情報の取り扱いに関するお問い合わせについて、"
        "以下の通りご回答いたします。\n\n"
        "{{response_detail}}"
    ),
    "subpoena": (
        "召喚状・開示請求への回答ドラフト:\n\n"
        "本件は法務部門のエスカレーション対象です。\n"
        "以下の情報を法務責任者に転送してください。\n\n"
        "発行機関: {{issuing_authority}}\n"
        "対象: {{subject}}\n"
        "期限: {{deadline}}\n"
    ),
    "custom": (
        "カスタム照会への回答ドラフト:\n\n"
        "{{response_detail}}"
    ),
}

# エスカレーション条件
ESCALATION_TRIGGERS: dict[str, list[str]] = {
    "subpoena": ["always"],
    "dsr": ["deletion_request", "portability_request"],
    "hold": ["litigation_related"],
    "privacy": ["breach_notification"],
}


# --- Request / Response Models ---

class LegalRespondRequest(BaseModel):
    inquiry_type: str  # dsr / hold / vendor / nda / privacy / subpoena / custom
    details: dict = {}
    account_id: str = ""


class EscalationInfo(BaseModel):
    required: bool
    reason: str = ""
    escalation_to: str = ""


class LegalRespondResult(BaseModel):
    inquiry_type: str
    draft: str
    template_source: str  # "custom" | "default"
    escalation: EscalationInfo
    variables_used: list[str]
    template_setup_guide: Optional[str] = None


# --- Service ---

class LegalResponseService:
    """法務照会対応ドラフト生成サービス"""

    def __init__(self, conpass_jwt: Optional[str] = None):
        self.base_url = settings.CONPASS_API_BASE_URL
        self.cookie = f"auth-token={conpass_jwt};" if conpass_jwt else ""

    async def respond(self, request: LegalRespondRequest) -> LegalRespondResult:
        # 1. テンプレートロード
        template, template_source = await self._load_template(request.inquiry_type)

        # 2. エスカレーションチェック
        escalation = self._check_escalation(request.inquiry_type, request.details)

        # 3. 変数置換 + LLM 文案生成
        draft, variables_used = await self._generate_draft(
            template, request.inquiry_type, request.details
        )

        # 4. テンプレート未設定時のガイド
        template_setup_guide = None
        if template_source == "default":
            template_setup_guide = (
                "現在デフォルトテンプレートを使用しています。"
                "管理画面の「レスポンステンプレート」から、"
                f"照会タイプ「{request.inquiry_type}」の"
                "カスタムテンプレートを設定することで、"
                "より正確なドラフトが生成されます。"
            )

        return LegalRespondResult(
            inquiry_type=request.inquiry_type,
            draft=draft,
            template_source=template_source,
            escalation=escalation,
            variables_used=variables_used,
            template_setup_guide=template_setup_guide,
        )

    async def _load_template(self, inquiry_type: str) -> tuple[str, str]:
        """Django ResponseTemplate API からテンプレートをロード"""
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/tenant/response-templates/",
                    headers={"Cookie": self.cookie},
                    params={"inquiry_type": inquiry_type},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        template_text = data[0].get("template", "")
                        if template_text:
                            return template_text, "custom"
                    elif isinstance(data, dict) and data.get("template"):
                        return data["template"], "custom"
        except Exception as exc:
            logger.warning("Failed to load custom template: %s", exc)

        # デフォルトテンプレートにフォールバック
        default = DEFAULT_TEMPLATES.get(inquiry_type, DEFAULT_TEMPLATES["custom"])
        return default, "default"

    @staticmethod
    def _check_escalation(inquiry_type: str, details: dict) -> EscalationInfo:
        """エスカレーション必要性を判定"""
        triggers = ESCALATION_TRIGGERS.get(inquiry_type, [])

        if "always" in triggers:
            return EscalationInfo(
                required=True,
                reason=f"{inquiry_type} は常にエスカレーション対象です",
                escalation_to="法務責任者",
            )

        for trigger in triggers:
            if details.get(trigger) or details.get("type") == trigger:
                return EscalationInfo(
                    required=True,
                    reason=f"トリガー条件 '{trigger}' に該当",
                    escalation_to="法務責任者",
                )

        return EscalationInfo(required=False)

    async def _generate_draft(
        self, template: str, inquiry_type: str, details: dict
    ) -> tuple[str, list[str]]:
        """テンプレート変数置換 + LLM による自然な文章生成"""
        # まず単純な変数置換
        variables_used = []
        draft = template
        for key, value in details.items():
            placeholder = "{{" + key + "}}"
            if placeholder in draft:
                draft = draft.replace(placeholder, str(value))
                variables_used.append(key)

        # 未置換の変数をLLMで補完
        remaining_placeholders = []
        import re
        for match in re.finditer(r"\{\{(\w+)\}\}", draft):
            remaining_placeholders.append(match.group(1))

        if remaining_placeholders:
            # LLMで自然な文章に仕上げる
            draft = await self._polish_with_llm(draft, inquiry_type, details)
        elif details:
            # 変数は全て埋まったが、detailsに追加情報がある場合もLLMで洗練
            draft = await self._polish_with_llm(draft, inquiry_type, details)

        return draft, variables_used

    async def _polish_with_llm(
        self, draft: str, inquiry_type: str, details: dict
    ) -> str:
        """LLM でドラフトを自然な文章に仕上げる"""
        prompt = f"""あなたは企業法務の文書作成専門家です。

以下のテンプレートベースのドラフトを、提供された詳細情報を元に
自然で丁寧なビジネス文書に仕上げてください。

## 照会タイプ
{inquiry_type}

## 現在のドラフト
{draft}

## 追加詳細情報
{json.dumps(details, ensure_ascii=False, indent=2)}

## 出力指示
- テンプレートの構造は維持しつつ、未記入の変数（{{{{変数名}}}}）は詳細情報から適切に補完してください
- 丁寧なビジネス日本語で出力してください
- ドラフト文書のみを出力してください（説明や注釈は不要）
"""
        try:
            llm = OpenAI(
                model="gpt-4o",
                temperature=0.3,
                api_key=settings.OPENAI_API_KEY,
                timeout=60,
                max_retries=1,
            )
            response = await llm.acomplete(prompt)
            return response.text.strip()
        except Exception as exc:
            logger.warning("LLM polish failed, returning raw draft: %s", exc)
            return draft
