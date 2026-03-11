"""
テンプレート比較ツール
契約書をテンプレートと比較し、条項ごとの差分をエージェントから利用可能にする
"""
from typing import Any, Dict, List, Optional

from llama_index.core.tools import FunctionTool

from app.core.logging_config import get_logger
from app.services.templates.template_service import TemplateService

logger = get_logger(__name__)

_template_service: Optional[TemplateService] = None


def _get_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service


async def template_list(
    industry: Optional[str] = None,
    contract_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """利用可能な契約テンプレートの一覧を返す。"""
    logger.info(
        f"template_list called: industry={industry}, contract_type={contract_type}"
    )
    return await _get_service().list_templates(
        industry=industry, contract_type=contract_type
    )


async def template_compare(
    contract_id: str,
    template_type: Optional[str] = None,
) -> Dict[str, Any]:
    """契約書をテンプレートと比較し、条項ごとのGREEN/YELLOW/REDラベリングを返す。"""
    logger.info(
        f"template_compare called: contract_id={contract_id}, "
        f"template_type={template_type}"
    )
    return await _get_service().compare_with_template(
        contract_id=contract_id, template_type=template_type
    )


def get_template_list_tool() -> FunctionTool:
    return FunctionTool.from_defaults(
        async_fn=template_list,
        name="template_list",
        description=(
            "List available contract templates. Can filter by industry and/or "
            "contract type. Returns template_id, template_type, industry, "
            "description, and clause list for each template. "
            "Use when the user asks about available templates or template types."
        ),
    )


def get_template_compare_tool() -> FunctionTool:
    return FunctionTool.from_defaults(
        async_fn=template_compare,
        name="template_compare",
        description=(
            "Compare a contract against an industry-standard template. "
            "Takes a contract_id and optional template_type. Returns clause-by-clause "
            "diff with GREEN (standard), YELLOW (needs review), RED (significant deviation) labels. "
            "Use when the user asks to check a contract against a template or industry standard."
        ),
    )
