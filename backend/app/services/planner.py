from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel

from app.schemas import (
    AvailablePrediction,
    Evidence,
    EventDraft,
    NearbyAvailable,
    NearbyResult,
    NearbyUnavailable,
    PlannerAnalysisRequest,
    PlannerAnalysisResponse,
    PredictionFactor,
    PredictionIndicators,
    PredictionScoreMetric,
    Recommendation,
    ResponseMeta,
    SourceRef,
)
from app.services.tourapi import TourApiClient, TourApiUnavailable


def request_fingerprint(request: BaseModel) -> str:
    canonical = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _analysis_dates(draft: EventDraft) -> tuple[date, date]:
    if draft.start_date and draft.end_date:
        return draft.start_date, draft.end_date
    if draft.date_candidates:
        return draft.date_candidates[0].start_date, draft.date_candidates[0].end_date
    fallback = date.today() + timedelta(days=30)
    return fallback, fallback


def _level(score: float) -> str:
    if score >= 80:
        return "very_high"
    if score >= 65:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def build_base_evidence(draft: EventDraft) -> list[Evidence]:
    evidence = [
        Evidence(
            evidence_id="ev_planner_schedule",
            value_type="user_input",
            label="일정 확정 상태",
            display_value={
                "fixed": "일정 확정",
                "candidates": "후보 일정 비교",
                "recommend": "일정 추천 필요",
                "unknown": "일정 미정",
            }[draft.schedule_selection_mode],
            source_refs=[],
        ),
        Evidence(
            evidence_id="ev_planner_region",
            value_type="user_input",
            label="지역 확정 상태",
            display_value=draft.region.display_name if draft.region else {
                "candidates": "후보 지역 비교",
                "recommend": "지역 추천 필요",
                "unknown": "지역 미정",
                "fixed": "지역 정보 누락",
            }[draft.region_selection_mode],
            source_refs=[],
        ),
        Evidence(
            evidence_id="ev_planner_environment",
            value_type="user_input",
            label="공간 유형",
            display_value={
                "indoor": "실내",
                "outdoor": "실외",
                "mixed": "실내·실외 혼합",
                "undecided": "미정",
            }[draft.indoor_outdoor],
            source_refs=[],
        ),
    ]
    if draft.target_attendance:
        evidence.append(
            Evidence(
                evidence_id="ev_planner_target",
                value_type="user_input",
                label="목표 인원",
                display_value=f"{draft.target_attendance:,}명",
                numeric_value=draft.target_attendance,
                unit="people",
                source_refs=[],
                limitation="기획자가 입력한 목표이며 실제 관람객 수나 모델 예측값이 아닙니다.",
            )
        )
    if draft.budget_max_krw is not None:
        evidence.append(
            Evidence(
                evidence_id="ev_planner_budget",
                value_type="user_input",
                label="최대 예산",
                display_value=f"{draft.budget_max_krw:,}원",
                numeric_value=draft.budget_max_krw,
                unit="krw",
                source_refs=[],
            )
        )
    if draft.venue and draft.venue.capacity:
        evidence.append(
            Evidence(
                evidence_id="ev_venue_capacity",
                value_type="user_input",
                label="장소 수용인원",
                display_value=f"{draft.venue.capacity:,}명",
                numeric_value=draft.venue.capacity,
                unit="people",
                source_refs=[],
            )
        )
    return evidence


def build_mock_prediction(draft: EventDraft, evidence: list[Evidence], sources: list[SourceRef]) -> AvailablePrediction:
    score = 50.0
    factors: list[PredictionFactor] = []

    def add_factor(factor_id: str, label: str, points: float, explanation: str, refs: list[str]) -> None:
        nonlocal score
        score += points
        factors.append(
            PredictionFactor(
                factor_id=factor_id,
                label=label,
                direction="up" if points > 0 else "down" if points < 0 else "neutral",
                importance=abs(points),
                explanation=explanation,
                evidence_refs=refs,
            )
        )

    if draft.schedule_selection_mode == "fixed":
        add_factor("mock_schedule_fixed", "일정 구체성", 5, "확정된 일정은 준비 항목을 구체화하기 쉽습니다.", ["ev_planner_schedule"])
    elif draft.schedule_selection_mode in {"unknown", "recommend"}:
        add_factor("mock_schedule_missing", "일정 불확실성", -8, "일정을 정해야 지역·기간 근거를 더 정확히 확인할 수 있습니다.", ["ev_planner_schedule"])
    if draft.region_selection_mode == "fixed":
        add_factor("mock_region_fixed", "지역 구체성", 5, "지역이 정해져 주변 행사와 편의시설을 확인할 수 있습니다.", ["ev_planner_region"])
    else:
        add_factor("mock_region_missing", "지역 불확실성", -8, "지역이 미정이라 지역 근거를 계산하지 못했습니다.", ["ev_planner_region"])
    if draft.purpose in {"regional_revitalization", "tourism"}:
        add_factor("mock_tourism_fit", "관광 연계 목적", 4, "지역 관광정보와 연결할 수 있는 목적입니다.", ["ev_planner_region"])
    if draft.indoor_outdoor == "outdoor":
        add_factor("mock_weather_risk", "실외 운영 위험", -4, "날씨 대체안이 수요와 운영 안정성에 영향을 줄 수 있습니다.", ["ev_planner_environment"])
    if draft.target_attendance and draft.venue and draft.venue.capacity:
        ratio = draft.target_attendance / draft.venue.capacity
        if ratio > 1:
            add_factor("mock_capacity_shortage", "수용인원 부족", -14, "목표 인원이 입력한 장소 수용인원을 넘습니다.", ["ev_planner_target", "ev_venue_capacity"])
        elif ratio >= 0.55:
            add_factor("mock_capacity_fit", "장소 규모 적합성", 7, "목표 인원과 장소 수용인원의 차이가 과도하지 않습니다.", ["ev_planner_target", "ev_venue_capacity"])
    elif not draft.venue:
        add_factor("mock_venue_missing", "장소 미정", -5, "장소가 없어 수용인원과 주변 편의시설을 확인하지 못했습니다.", [])
    if draft.target_attendance and draft.budget_max_krw is not None:
        budget_per_person = draft.budget_max_krw / draft.target_attendance
        if budget_per_person < 10_000:
            add_factor("mock_budget_tight", "인당 예산 여유", -7, "목표 인원 대비 최대예산이 낮아 세부 견적 확인이 필요합니다.", ["ev_planner_target", "ev_planner_budget"])
        elif budget_per_person >= 30_000:
            add_factor("mock_budget_buffer", "인당 예산 여유", 5, "목표 인원 대비 예산 범위가 비교적 여유 있게 입력됐습니다.", ["ev_planner_target", "ev_planner_budget"])

    score = max(0, min(100, round(score, 1)))
    start, end = _analysis_dates(draft)
    now = datetime.now().astimezone()
    model_source = SourceRef(
        source_id="src_heungmap_mock_model",
        source_type="heungmap_model",
        provider_name="흥할지도",
        dataset_name="자체 수요 모델 연결용 mock",
        retrieved_at=now,
        limitation="학습된 모델의 출력이 아닌 화면·계약 검증용 규칙 점수입니다.",
    )
    prediction_sources = [model_source, *sources]
    return AvailablePrediction(
        status="available",
        prediction_id=f"pred_mock_{uuid4().hex}",
        event_id=draft.event_id,
        prediction_type="relative_demand_score",
        as_of=now,
        target_start_date=start,
        target_end_date=end,
        target_region=draft.region,
        primary_metric=PredictionScoreMetric(metric_name="relative_demand_score", unit="index_0_100", value=score),
        indicators=PredictionIndicators(
            demand_score=score,
            congestion_level=_level(score),
            ticket_demand_level=_level(score) if draft.ticket_type in {"paid", "mixed"} else "unknown",
        ),
        confidence="low",
        data_sufficiency="limited",
        method="rules",
        model_version="mock-model-interface-0.1",
        factors=factors,
        evidence=evidence,
        sources=prediction_sources,
        limitations=[
            "이 점수는 자체 AI 모델 연결 전의 mock이며 실제 수요 예측이 아닙니다.",
            "지역 방문수요나 이 점수를 특정 행사 관람객 수로 해석할 수 없습니다.",
            "실제 모델 채택은 데이터 게이트와 baseline 비교를 통과한 뒤 결정합니다.",
        ],
        out_of_distribution=True,
        fallback_used=True,
        created_at=now,
        is_mock=True,
    )


def build_recommendations(draft: EventDraft) -> list[Recommendation]:
    recommendations: list[Recommendation] = []

    def add(category: str, priority: str, title: str, action: str, reason: str, refs: list[str]) -> None:
        recommendations.append(
            Recommendation(
                recommendation_id=f"rec_{len(recommendations) + 1}_{uuid4().hex[:8]}",
                category=category,
                priority=priority,
                title=title,
                action=action,
                reason=reason,
                evidence_refs=refs,
                requires_human_review=True,
            )
        )

    if draft.indoor_outdoor in {"outdoor", "mixed"}:
        add("risk", "high", "우천·기상 대체안을 확정하세요", "대체 공간, 연기 기준, 관객 공지 시점과 환불 원칙을 담당자와 확인하세요.", "실외 공간을 포함한 행사입니다.", ["ev_planner_environment"])
    if draft.target_attendance and draft.target_attendance >= 10_000:
        add("operation", "high", "대규모 안전·교통 검토를 먼저 여세요", "장소 수용인원, 출입구, 대피 동선, 대중교통과 임시 주차 계획을 관계기관과 검토하세요.", f"입력한 목표 인원이 {draft.target_attendance:,}명입니다.", ["ev_planner_target"])
    if not draft.venue:
        add("venue", "high", "후보 장소의 공식 수용인원을 확인하세요", "장소명, 좌표, 공식 수용인원과 필수 편의시설을 입력한 뒤 다시 분석하세요.", "장소 정보가 없어 규모 적합성과 주변 편의시설을 계산하지 못했습니다.", [])
    elif draft.target_attendance and draft.venue.capacity and draft.target_attendance > draft.venue.capacity:
        add("venue", "high", "목표 인원 또는 장소 규모를 조정하세요", "입장 회차를 나누거나 더 큰 장소를 비교하고, 공식 허용 수용인원은 장소 운영자에게 확인하세요.", "목표 인원이 입력한 장소 수용인원을 초과합니다.", ["ev_planner_target", "ev_venue_capacity"])
    if draft.ticket_type == "free":
        add("demand", "medium", "무료 행사 노쇼 기준을 정하세요", "사전등록 상한, 대기 명단, 당일 입장 마감과 초과 방문 대응을 정하세요.", "무료 행사는 등록 인원과 실제 방문 인원이 달라질 수 있습니다.", [])
    if draft.budget_max_krw is None:
        add("budget", "medium", "예산 상한을 먼저 입력하세요", "대관·시설·인력·안전·홍보·예비비의 견적 범위를 확인하고 최대예산을 정하세요.", "최대예산이 비어 있어 실행 가능성을 비교하기 어렵습니다.", [])
    if draft.schedule_selection_mode in {"unknown", "recommend"}:
        add("demand", "medium", "후보 일정 두 개를 만드세요", "주말·공휴일, 경쟁 행사, 준비기간과 기상 위험을 기준으로 최소 두 일정을 비교하세요.", "행사 일정이 아직 정해지지 않았습니다.", ["ev_planner_schedule"])
    if draft.region_selection_mode in {"unknown", "recommend"}:
        add("tourism", "medium", "후보 지역을 좁히세요", "목표 이용객 접근성, 장소 비용, 주변 관광자원과 같은 기간 행사를 기준으로 두 지역을 비교하세요.", "지역이 미정이라 TourAPI 근거를 조회하지 못했습니다.", ["ev_planner_region"])
    if "family" in draft.target_audience:
        add("accessibility", "medium", "가족 방문 편의를 점검하세요", "유모차 동선, 수유·휴게 공간, 가족 화장실, 아동 실종 대응과 보호자 안내를 확인하세요.", "목표 이용객에 가족이 포함됩니다.", [])
    add("marketing", "low", "홍보 기준일과 측정값을 정하세요", "홍보 시작일, 핵심 채널, 관심등록·예매·방문 중 추적할 KPI를 하나씩 정하세요.", "다시 분석할 때 같은 기준으로 변화를 비교하기 위해 필요합니다.", [])
    return recommendations


async def build_analysis(request: PlannerAnalysisRequest, tourapi: TourApiClient) -> PlannerAnalysisResponse:
    draft = request.event_draft
    evidence = build_base_evidence(draft)
    external_sources: list[SourceRef] = []
    warnings: list[str] = []

    start, end = _analysis_dates(draft)
    if draft.region and draft.schedule_selection_mode in {"fixed", "candidates"}:
        if tourapi.configured:
            try:
                count, source = await tourapi.competing_festival_count(
                    region=draft.region,
                    start_date=start,
                    end_date=end,
                )
                external_sources.append(source)
                evidence.append(
                    Evidence(
                        evidence_id="ev_tourapi_same_period",
                        value_type="verified_fact",
                        label="같은 지역·기간 TourAPI 행사",
                        display_value=f"{count}건",
                        numeric_value=count,
                        unit="events",
                        as_of=source.retrieved_at,
                        confidence="medium",
                        source_refs=[source.source_id],
                        limitation="검색 건수이며 실제 경쟁 강도나 관람객 수가 아닙니다.",
                    )
                )
            except TourApiUnavailable:
                warnings.append("한국관광공사 TourAPI 행사 근거를 불러오지 못했습니다.")
        else:
            warnings.append("TOURAPI_SERVICE_KEY가 없어 실제 관광 근거 조회를 건너뛰었습니다.")

    nearby: NearbyResult
    if "nearby_places" not in request.requested_outputs:
        nearby = NearbyUnavailable(status="unavailable", reason_code="not_requested", message="주변 장소 조회를 요청하지 않았습니다.", retryable=False, is_mock=False)
    elif not draft.venue or not draft.venue.coordinates:
        nearby = NearbyUnavailable(status="unavailable", reason_code="missing_coordinates", message="장소 좌표를 입력하면 한국관광공사 주변 관광정보를 확인할 수 있습니다.", retryable=False, is_mock=False)
    elif not tourapi.configured:
        nearby = NearbyUnavailable(status="unavailable", reason_code="upstream_unavailable", message="TourAPI 키가 없어 주변 장소를 조회하지 못했습니다.", retryable=False, is_mock=False)
    else:
        try:
            places = await tourapi.nearby_places(draft.venue.coordinates)
            nearby = NearbyAvailable(status="available", items=places, radius_m=5000, is_mock=False)
        except TourApiUnavailable:
            nearby = NearbyUnavailable(status="unavailable", reason_code="upstream_unavailable", message="한국관광공사 주변 관광정보를 불러오지 못했습니다.", retryable=True, is_mock=False)

    prediction = build_mock_prediction(draft, evidence, external_sources)
    now = datetime.now().astimezone()
    return PlannerAnalysisResponse(
        analysis_id=f"ana_{uuid4().hex}",
        contract_version="0.1.0",
        request_snapshot=draft,
        prediction=prediction,
        nearby_places=nearby,
        evidence=evidence,
        rule_recommendations=build_recommendations(draft),
        meta=ResponseMeta(
            contract_version="0.1.0",
            generated_at=now,
            request_id=f"req_{uuid4().hex}",
            warnings=warnings or None,
        ),
    )
