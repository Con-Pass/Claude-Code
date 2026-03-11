"""
Legal Commands API: /vendor-check, /triage-nda, /review-contract, /brief, /respond
"""
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.logging_config import get_logger
from app.services.legal.vendor_check_service import (
    VendorCheckRequest,
    VendorCheckResult,
    VendorCheckService,
)
from app.services.legal.nda_triage_service import (
    NDATriageRequest,
    NDATriageResult,
    NDATriageService,
)
from app.services.legal.contract_review_service import (
    ContractReviewRequest,
    ContractReviewResult,
    ContractReviewService,
)
from app.services.legal.legal_brief_service import (
    LegalBriefRequest,
    LegalBriefResult,
    LegalBriefService,
)
from app.services.legal.legal_response_service import (
    LegalRespondRequest,
    LegalRespondResult,
    LegalResponseService,
)

logger = get_logger(__name__)

legal_commands_router = APIRouter()


@legal_commands_router.post(
    "/vendor-check",
    response_model=VendorCheckResult,
    summary="取引先横断チェック",
    description="5ソース並列検索で取引先の契約状況を横断的にチェックし、Gap Analysis を実行します",
    tags=["legal"],
)
async def vendor_check(request: Request, body: VendorCheckRequest):
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    try:
        service = VendorCheckService(conpass_jwt=conpass_jwt)
        result = await service.check(body)
        return result
    except Exception as exc:
        logger.exception("Error in vendor-check: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vendor check failed: {exc}",
        ) from exc


@legal_commands_router.post(
    "/triage-nda",
    response_model=NDATriageResult,
    summary="NDA トリアージ（13基準スクリーニング）",
    description="NDA テキストを13審査基準で並列評価し、GREEN/YELLOW/RED に分類します",
    tags=["legal"],
)
async def triage_nda(request: Request, body: NDATriageRequest):
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    if not body.nda_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="nda_text must not be empty.",
        )

    try:
        service = NDATriageService()
        result = await service.triage(body)
        return result
    except Exception as exc:
        logger.exception("Error in triage-nda: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NDA triage failed: {exc}",
        ) from exc


@legal_commands_router.post(
    "/review-contract",
    response_model=ContractReviewResult,
    summary="契約レビュー（12条項並列AI解析）",
    description="12条項カテゴリを並列AI解析し、GREEN/YELLOW/RED に分類。YELLOW/RED にはリドライン生成。",
    tags=["legal"],
)
async def review_contract(request: Request, body: ContractReviewRequest):
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    try:
        service = ContractReviewService(conpass_jwt=conpass_jwt)
        result = await service.review(body)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Error in review-contract: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contract review failed: {exc}",
        ) from exc


@legal_commands_router.get(
    "/brief",
    response_model=LegalBriefResult,
    summary="法務ブリーフィング",
    description="daily/topic/incident の3モードで法務ブリーフィングを生成します",
    tags=["legal"],
)
async def legal_brief(
    request: Request,
    mode: str = Query("daily", description="ブリーフィングモード: daily / topic / incident"),
    query: str = Query("", description="topic/incident モードの検索クエリ"),
):
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    if mode not in ("daily", "topic", "incident"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported mode: {mode}. Use daily, topic, or incident.",
        )

    if mode in ("topic", "incident") and not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{mode} mode requires a query parameter.",
        )

    try:
        service = LegalBriefService(conpass_jwt=conpass_jwt)
        brief_request = LegalBriefRequest(mode=mode, query=query or None)
        result = await service.generate(brief_request)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Error in brief: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Brief generation failed: {exc}",
        ) from exc


@legal_commands_router.post(
    "/respond",
    response_model=LegalRespondResult,
    summary="法務照会対応ドラフト生成",
    description="テンプレートベースの法務照会対応ドラフトを生成します。送信はユーザー確認後。",
    tags=["legal"],
)
async def legal_respond(request: Request, body: LegalRespondRequest):
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )

    valid_types = {"dsr", "hold", "vendor", "nda", "privacy", "subpoena", "custom"}
    if body.inquiry_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported inquiry_type: {body.inquiry_type}. "
                   f"Valid types: {', '.join(sorted(valid_types))}",
        )

    try:
        service = LegalResponseService(conpass_jwt=conpass_jwt)
        result = await service.respond(body)
        return result
    except Exception as exc:
        logger.exception("Error in respond: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response generation failed: {exc}",
        ) from exc
