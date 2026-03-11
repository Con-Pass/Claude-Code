"""
テンプレートエンジン API エンドポイント
テンプレート一覧・テンプレート比較・初期データ投入を提供する
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.logging_config import get_logger
from app.services.templates.template_service import TemplateService

logger = get_logger(__name__)

template_router = APIRouter()

_template_service: Optional[TemplateService] = None


def _get_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service


@template_router.get(
    "/list",
    summary="テンプレート一覧取得",
    description="利用可能な契約書テンプレートの一覧を返す",
)
async def list_templates(
    industry: Optional[str] = Query(None, description="業界フィルタ（例: 建設業, IT, 不動産, 汎用）"),
    contract_type: Optional[str] = Query(None, description="契約種別フィルタ（例: 工事請負契約書, NDA）"),
):
    try:
        service = _get_service()
        templates = await service.list_templates(
            industry=industry, contract_type=contract_type
        )
        return {"status": "success", "data": templates}
    except Exception as e:
        logger.exception(f"Template list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@template_router.get(
    "/compare",
    summary="テンプレート比較",
    description="指定契約をテンプレートと比較し、条項ごとのGREEN/YELLOW/REDラベリングを返す",
)
async def compare_with_template(
    request: Request,
    contract_id: str = Query(..., description="比較対象の契約ID"),
    template_type: Optional[str] = Query(None, description="比較テンプレートの種別"),
):
    try:
        conpass_jwt = getattr(request.state, "conpass_token", None)
        service = _get_service()
        result = await service.compare_with_template(
            contract_id=contract_id,
            template_type=template_type,
            conpass_jwt=conpass_jwt,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Template compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@template_router.post(
    "/seed",
    summary="テンプレート初期データ投入",
    description="業界標準テンプレートの初期データをQdrantに投入する",
)
async def seed_templates():
    try:
        service = _get_service()
        result = await service.seed_default_templates()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Seed failed"))
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Template seed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
