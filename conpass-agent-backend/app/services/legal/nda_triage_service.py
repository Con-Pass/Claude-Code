"""
triage-nda: NDA 13基準並列スクリーニング
各基準を LLM で並列評価し、PASS / FLAG / FAIL を判定。
全体分類: GREEN（全PASS）/ YELLOW（FLAG含む）/ RED（FAIL含む）
"""
import asyncio
from typing import Optional

from llama_index.llms.openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# --- 13 審査基準 ---

SCREENING_CRITERIA = [
    "mutual_obligations",       # 相互性
    "confidential_info_scope",  # 秘密情報の定義範囲
    "term_duration",            # 契約期間
    "independent_dev_carveout", # 独立開発除外規定
    "public_info_carveout",     # 公知情報除外規定
    "third_party_carveout",     # 第三者受領情報除外規定
    "legal_disclosure",         # 法令開示除外規定
    "residuals_clause",         # 残留条項
    "non_solicitation",         # 非引抜条項
    "non_compete",              # 競業禁止条項
    "injunctive_relief",        # 差止請求権
    "governing_law",            # 準拠法・管轄
    "assignment",               # 譲渡制限
]

CRITERIA_DESCRIPTIONS = {
    "mutual_obligations":       "秘密保持義務が双方向（相互）であるか",
    "confidential_info_scope":  "秘密情報の定義範囲が適切か（過度に広すぎないか）",
    "term_duration":            "契約期間・存続期間が適切か（過度に長くないか）",
    "independent_dev_carveout": "独立開発された情報の除外規定があるか",
    "public_info_carveout":     "公知情報の除外規定があるか",
    "third_party_carveout":     "第三者から正当に取得した情報の除外規定があるか",
    "legal_disclosure":         "法令に基づく開示の除外規定があるか",
    "residuals_clause":         "残留条項（Residuals Clause）が含まれていないか、または合理的な範囲か",
    "non_solicitation":         "非引抜条項が含まれていないか、または合理的な範囲か",
    "non_compete":              "競業禁止条項が含まれていないか",
    "injunctive_relief":        "差止請求権の規定が一方的でないか",
    "governing_law":            "準拠法・管轄裁判所が合理的か",
    "assignment":               "譲渡制限条項が適切か",
}


# --- Request / Response Models ---

class NDATriageRequest(BaseModel):
    nda_text: str
    account_id: str
    contract_id: Optional[str] = None


class CriterionResult(BaseModel):
    criterion: str
    label_ja: str
    verdict: str  # PASS / FLAG / FAIL
    reasoning: str
    relevant_excerpt: str = ""


class NDATriageResult(BaseModel):
    contract_id: Optional[str] = None
    classification: str  # GREEN / YELLOW / RED
    criteria_results: list[CriterionResult]
    summary: str
    recommended_actions: list[str]


# --- LLM Prompt ---

CRITERION_PROMPT_TEMPLATE = """あなたは NDA（秘密保持契約）の法務審査の専門家です。

以下の NDA テキストについて、指定された審査基準を評価してください。

## NDA テキスト
{nda_text}

## 審査基準
基準ID: {criterion_id}
基準名: {criterion_label}
評価観点: {criterion_description}

## 出力指示
以下の JSON 形式で回答してください。他のテキストは一切含めないでください。

{{
  "verdict": "PASS or FLAG or FAIL",
  "reasoning": "判定理由を日本語で簡潔に記述",
  "relevant_excerpt": "判定根拠となる NDA テキストの該当箇所（50文字以内に要約）"
}}

判定基準:
- PASS: 当該基準を満たしている、またはリスクなし
- FLAG: 注意が必要だが重大ではない、または曖昧な記載
- FAIL: 基準を満たしていない、または重大なリスクあり
"""


# --- Service ---

class NDATriageService:
    """NDA 13基準並列スクリーニングサービス"""

    async def triage(self, request: NDATriageRequest) -> NDATriageResult:
        """全13基準を並列評価し、分類結果を返す"""
        tasks = [
            self._evaluate_criterion(request.nda_text, criterion)
            for criterion in SCREENING_CRITERIA
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        criteria_results: list[CriterionResult] = []
        for idx, result in enumerate(results):
            criterion = SCREENING_CRITERIA[idx]
            if isinstance(result, Exception):
                logger.error(
                    "Criterion %s evaluation failed: %s", criterion, result
                )
                criteria_results.append(
                    CriterionResult(
                        criterion=criterion,
                        label_ja=CRITERIA_DESCRIPTIONS.get(criterion, criterion),
                        verdict="FLAG",
                        reasoning=f"評価中にエラーが発生しました: {result}",
                    )
                )
            else:
                criteria_results.append(result)

        classification = self._classify(criteria_results)
        summary = self._build_summary(criteria_results, classification)
        recommended_actions = self._build_recommendations(criteria_results, classification)

        return NDATriageResult(
            contract_id=request.contract_id,
            classification=classification,
            criteria_results=criteria_results,
            summary=summary,
            recommended_actions=recommended_actions,
        )

    async def _evaluate_criterion(
        self, nda_text: str, criterion: str
    ) -> CriterionResult:
        """単一基準を LLM で評価"""
        description = CRITERIA_DESCRIPTIONS.get(criterion, criterion)

        prompt = CRITERION_PROMPT_TEMPLATE.format(
            nda_text=nda_text,
            criterion_id=criterion,
            criterion_label=description,
            criterion_description=description,
        )

        llm = OpenAI(
            model="gpt-4o",
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY,
            timeout=60,
            max_retries=1,
        )

        response = await llm.acomplete(prompt)
        raw_text = response.text.strip()

        # JSON パース
        import json
        try:
            # コードブロック表記を除去
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse LLM response for criterion %s: %s",
                criterion, raw_text[:200],
            )
            parsed = {
                "verdict": "FLAG",
                "reasoning": f"LLM応答のパースに失敗: {raw_text[:100]}",
                "relevant_excerpt": "",
            }

        verdict = parsed.get("verdict", "FLAG").upper()
        if verdict not in ("PASS", "FLAG", "FAIL"):
            verdict = "FLAG"

        return CriterionResult(
            criterion=criterion,
            label_ja=description,
            verdict=verdict,
            reasoning=parsed.get("reasoning", ""),
            relevant_excerpt=parsed.get("relevant_excerpt", ""),
        )

    @staticmethod
    def _classify(results: list[CriterionResult]) -> str:
        """全体分類: GREEN / YELLOW / RED"""
        verdicts = {r.verdict for r in results}
        if "FAIL" in verdicts:
            return "RED"
        if "FLAG" in verdicts:
            return "YELLOW"
        return "GREEN"

    @staticmethod
    def _build_summary(
        results: list[CriterionResult], classification: str
    ) -> str:
        pass_count = sum(1 for r in results if r.verdict == "PASS")
        flag_count = sum(1 for r in results if r.verdict == "FLAG")
        fail_count = sum(1 for r in results if r.verdict == "FAIL")

        classification_label = {
            "GREEN": "承認推奨",
            "YELLOW": "条件付き承認（要確認）",
            "RED": "要法務レビュー",
        }.get(classification, classification)

        return (
            f"NDA スクリーニング結果: {classification_label}\n"
            f"PASS: {pass_count} / FLAG: {flag_count} / FAIL: {fail_count} "
            f"(全{len(results)}基準)"
        )

    @staticmethod
    def _build_recommendations(
        results: list[CriterionResult], classification: str
    ) -> list[str]:
        actions = []
        if classification == "RED":
            actions.append("法務部門による詳細レビューを実施してください")

        for r in results:
            if r.verdict == "FAIL":
                actions.append(f"[FAIL] {r.label_ja}: {r.reasoning}")
            elif r.verdict == "FLAG":
                actions.append(f"[FLAG] {r.label_ja}: {r.reasoning}")

        if classification == "GREEN":
            actions.append("全基準クリア。標準承認フローで処理可能です")

        return actions
