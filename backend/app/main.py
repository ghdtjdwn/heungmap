from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.schemas import (
    AddressSearchResponse,
    HealthResponse,
    PlannerAnalysisRequest,
    PlannerAnalysisResponse,
    PlannerRecommendationRequest,
    PlannerRecommendationResponse,
    Problem,
    ResponseMeta,
    VenueSearchResponse,
)
from app.services.kakao_address import KakaoAddressClient, KakaoAddressUnavailable
from app.services.llm import (
    LlmInvalidResponse,
    LlmNotConfigured,
    LlmTimeout,
    LlmUpstreamUnavailable,
    PlannerLlmClient,
)
from app.services.planner import build_analysis, request_fingerprint
from app.services.tourapi import TourApiClient, TourApiUnavailable


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(
    title="HeungMap API",
    version="0.1.0",
    description="흥할지도 기획자·방문객 공통 API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)

tourapi = TourApiClient()
kakao_address = KakaoAddressClient()
llm = PlannerLlmClient()
analysis_cache: dict[str, tuple[str, PlannerAnalysisResponse]] = {}
analysis_locks: dict[str, asyncio.Lock] = {}
recommendation_cache: dict[str, tuple[str, PlannerRecommendationResponse]] = {}
recommendation_locks: dict[str, asyncio.Lock] = {}


def problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    retryable: bool,
    field_errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    trace_id = uuid4().hex
    payload: dict[str, Any] = {
        "type": f"https://heungmap.local/problems/{code.lower()}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "retryable": retryable,
        "trace_id": trace_id,
    }
    if field_errors:
        payload["field_errors"] = field_errors
    return JSONResponse(payload, status_code=status, media_type="application/problem+json")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part not in {"body"}]
        field_errors.append({"field": ".".join(location), "message": str(error.get("msg", "입력값을 확인해 주세요."))})
    return problem_response(
        request,
        status=422,
        code="VALIDATION_ERROR",
        title="입력값을 확인해 주세요",
        detail="분석 요청에 유효하지 않은 값이 있습니다.",
        retryable=False,
        field_errors=field_errors,
    )


@app.get("/api/v1/health", response_model=HealthResponse, operation_id="getHealth", tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="heungmap-api", contract_version="0.1.0", checked_at=datetime.now().astimezone())


@app.get(
    "/api/v1/venues/search",
    response_model=VenueSearchResponse,
    operation_id="searchVenues",
    tags=["locations"],
    responses={
        422: {
            "description": "검색어 검증 실패",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        503: {
            "description": "TourAPI 미설정 또는 일시 오류",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
    },
)
async def search_venues(
    request: Request,
    keyword: str = Query(min_length=2, max_length=100),
    area_code: str | None = Query(default=None, min_length=1, max_length=20),
    limit: int = Query(default=10, ge=1, le=10),
) -> VenueSearchResponse | JSONResponse:
    try:
        items = await tourapi.search_venues(keyword=keyword, area_code=area_code, limit=limit)
    except TourApiUnavailable as exc:
        return problem_response(
            request,
            status=503,
            code="UPSTREAM_UNAVAILABLE",
            title="관광정보 장소 검색을 사용할 수 없습니다",
            detail=str(exc),
            retryable=tourapi.configured,
        )
    return VenueSearchResponse(
        items=items,
        meta=ResponseMeta(
            contract_version="0.1.0",
            generated_at=datetime.now().astimezone(),
            request_id=uuid4().hex,
            warnings=["검색 결과는 장소 후보 탐색용이며 공식 수용인원과 대관 가능 여부는 별도 확인해야 합니다."],
        ),
    )


@app.get(
    "/api/v1/addresses/search",
    response_model=AddressSearchResponse,
    operation_id="searchAddresses",
    tags=["locations"],
    responses={
        422: {
            "description": "검색어 검증 실패",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        503: {
            "description": "Kakao Local API 미설정 또는 일시 오류",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
    },
)
async def search_addresses(
    request: Request,
    query: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=10, ge=1, le=10),
) -> AddressSearchResponse | JSONResponse:
    try:
        items = await kakao_address.search_addresses(query=query, limit=limit)
    except KakaoAddressUnavailable as exc:
        return problem_response(
            request,
            status=503,
            code="UPSTREAM_UNAVAILABLE",
            title="주소 검색을 사용할 수 없습니다",
            detail=str(exc),
            retryable=kakao_address.configured,
        )
    return AddressSearchResponse(
        items=items,
        meta=ResponseMeta(
            contract_version="0.1.0",
            generated_at=datetime.now().astimezone(),
            request_id=uuid4().hex,
        ),
    )


@app.post(
    "/api/v1/planner/analyses",
    response_model=PlannerAnalysisResponse,
    operation_id="createPlannerAnalysis",
    tags=["planner"],
    responses={
        409: {
            "description": "같은 client_request_id에 다른 요청 body가 전달됨",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        422: {
            "description": "입력값 검증 실패",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
    },
)
async def create_planner_analysis(request: Request, payload: PlannerAnalysisRequest) -> PlannerAnalysisResponse | JSONResponse:
    fingerprint = request_fingerprint(payload)
    request_id = str(payload.client_request_id)
    lock = analysis_locks.setdefault(request_id, asyncio.Lock())
    async with lock:
        cached = analysis_cache.get(request_id)
        if cached:
            cached_fingerprint, cached_response = cached
            if cached_fingerprint == fingerprint:
                return cached_response
            return problem_response(
                request,
                status=409,
                code="IDEMPOTENCY_CONFLICT",
                title="중복 요청 식별자가 충돌했습니다",
                detail="같은 client_request_id에 다른 입력이 전달됐습니다. 새 분석 요청을 만들어 주세요.",
                retryable=False,
            )
        response = await build_analysis(payload, tourapi)
        if len(analysis_cache) >= 500:
            oldest_id = next(iter(analysis_cache))
            analysis_cache.pop(oldest_id)
            analysis_locks.pop(oldest_id, None)
        analysis_cache[request_id] = (fingerprint, response)
        return response


@app.post(
    "/api/v1/planner/recommendations",
    response_model=PlannerRecommendationResponse,
    operation_id="createPlannerRecommendation",
    tags=["planner"],
    responses={
        409: {
            "description": "같은 client_request_id에 다른 요청 body가 전달됨",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        422: {
            "description": "입력값 또는 크기 검증 실패",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        502: {
            "description": "LLM 응답 계약 검증 실패",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        503: {
            "description": "LLM 미설정 또는 upstream 오류",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
        504: {
            "description": "LLM timeout",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema(ref_template="#/components/schemas/{model}")}},
        },
    },
)
async def create_planner_recommendation(
    request: Request,
    payload: PlannerRecommendationRequest,
) -> PlannerRecommendationResponse | JSONResponse:
    fingerprint = request_fingerprint(payload)
    request_id = str(payload.client_request_id)
    lock = recommendation_locks.setdefault(request_id, asyncio.Lock())
    async with lock:
        cached = recommendation_cache.get(request_id)
        if cached:
            cached_fingerprint, cached_response = cached
            if cached_fingerprint == fingerprint:
                return cached_response
            return problem_response(
                request,
                status=409,
                code="IDEMPOTENCY_CONFLICT",
                title="중복 요청 식별자가 충돌했습니다",
                detail="같은 client_request_id에 다른 입력이 전달됐습니다. 새 추천 요청을 만들어 주세요.",
                retryable=False,
            )
        try:
            response = await llm.generate(payload)
        except LlmNotConfigured as exc:
            return problem_response(
                request,
                status=503,
                code="LLM_NOT_CONFIGURED",
                title="실제 LLM이 설정되지 않았습니다",
                detail=str(exc),
                retryable=False,
            )
        except ValueError as exc:
            return problem_response(
                request,
                status=422,
                code="CONTEXT_TOO_LARGE",
                title="기획 Context가 너무 큽니다",
                detail=str(exc),
                retryable=False,
            )
        except LlmTimeout as exc:
            return problem_response(
                request,
                status=504,
                code="LLM_TIMEOUT",
                title="LLM 응답 시간이 초과됐습니다",
                detail=str(exc),
                retryable=True,
            )
        except LlmInvalidResponse as exc:
            return problem_response(
                request,
                status=502,
                code="LLM_INVALID_RESPONSE",
                title="LLM 결과를 안전하게 사용할 수 없습니다",
                detail=str(exc),
                retryable=True,
            )
        except LlmUpstreamUnavailable as exc:
            return problem_response(
                request,
                status=503,
                code="LLM_UPSTREAM_UNAVAILABLE",
                title="LLM 서비스를 사용할 수 없습니다",
                detail=str(exc),
                retryable=True,
            )
        if len(recommendation_cache) >= 500:
            oldest_id = next(iter(recommendation_cache))
            recommendation_cache.pop(oldest_id)
            recommendation_locks.pop(oldest_id, None)
        recommendation_cache[request_id] = (fingerprint, response)
        return response
