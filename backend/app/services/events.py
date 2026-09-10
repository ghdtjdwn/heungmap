from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from app.schemas import (
    AvailablePrediction,
    EventDetail,
    EventListResponse,
    EventType,
    NearbyPlace,
    NearbyPlaceListResponse,
    PredictionFactor,
    PredictionIndicators,
    PredictionScoreMetric,
    ResponseMeta,
    SearchFilter,
    SourceRef,
    UnavailablePrediction,
)
from app.services.kakao_places import KakaoPlacesClient, KakaoPlacesUnavailable
from app.services.tourapi import TourApiClient, TourApiUnavailable
from app.publications import published_event, published_events


def _response_meta() -> ResponseMeta:
    return ResponseMeta(
        contract_version="0.1.0",
        generated_at=datetime.now().astimezone(),
        request_id=f"req_{uuid4().hex}",
    )


def _demand_level(score: float) -> str:
    if score >= 80:
        return "very_high"
    if score >= 65:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _includes_weekend(start_date: date, end_date: date) -> bool:
    duration = (end_date - start_date).days + 1
    if duration >= 7:
        return True
    return any((start_date.weekday() + offset) % 7 >= 5 for offset in range(duration))


async def build_event_list(
    *,
    tourapi: TourApiClient,
    query: str | None,
    start_date: date | None,
    end_date: date | None,
    area_code: str | None,
    sigungu_code: str | None,
    event_types: list[EventType] | None,
    sort: str | None,
    page: int,
    page_size: int,
) -> EventListResponse:
    filters = SearchFilter(
        query=query,
        start_date=start_date,
        end_date=end_date,
        area_code=area_code,
        sigungu_code=sigungu_code,
        event_types=event_types,
        sort=sort or "start_date",
        page=page,
        page_size=page_size,
    )
    warnings = []
    local_items = published_events()
    if event_types is not None and "festival" not in event_types:
        items = []
    else:
        try:
            items = await tourapi.search_festivals(
                query=query, start_date=start_date, end_date=end_date,
                area_code=area_code, sigungu_code=sigungu_code,
            )
        except TourApiUnavailable:
            if not local_items:
                raise
            items = []
            warnings.append("TourAPI 조회에 실패해 기획자가 공개한 행사만 표시합니다. 잠시 뒤 다시 조회해 주세요.")
    range_start = start_date or date.today()
    range_end = end_date or (range_start + timedelta(days=90))
    items = [event for event in [*items, *local_items]
             if event.start_date <= range_end and event.end_date >= range_start
             and (not area_code or event.region.area_code == area_code)
             and (not sigungu_code or event.region.sigungu_code == sigungu_code)
             and (not event_types or event.event_type in event_types)
             and (not query or query.casefold() in (event.title + " " + event.region.display_name).casefold())]
    items.sort(key=lambda event: (event.start_date, event.event_id))
    total_count = len(items)
    page_start = (page - 1) * page_size
    page_items = items[page_start:page_start + page_size]
    return EventListResponse(
        items=page_items,
        page=page,
        page_size=page_size,
        total_count=total_count,
        applied_filters=filters,
        meta=_response_meta().model_copy(update={"warnings": warnings or None}),
    )


async def build_event_detail(event_id: str, tourapi: TourApiClient) -> EventDetail | None:
    if event_id.startswith("evt_planner_"):
        return published_event(event_id)
    prefix = "evt_tourapi_"
    if not event_id.startswith(prefix):
        return None
    content_id = event_id.removeprefix(prefix)
    if not content_id:
        return None
    return await tourapi.get_festival_by_id(content_id)


async def build_event_nearby(
    event: EventDetail,
    tourapi: TourApiClient,
    kakao_places: KakaoPlacesClient,
    radius_m: int,
) -> NearbyPlaceListResponse:
    if event.venue is None or event.venue.coordinates is None:
        raise ValueError("장소 좌표가 없어 주변 정보를 조회할 수 없습니다.")
    places = await tourapi.nearby_places(event.venue.coordinates, radius_m)
    warnings: list[str] = []
    if kakao_places.configured:
        try:
            places = _merge_nearby_places(
                places,
                await kakao_places.nearby_places(event.venue.coordinates, radius_m),
            )
        except KakaoPlacesUnavailable:
            warnings.append(
                "Kakao Local 주차·숙박 정보를 불러오지 못해 TourAPI 결과만 제공합니다."
            )
    else:
        warnings.append(
            "KAKAO_REST_API_KEY가 없어 주차장 보강을 생략했습니다. 숙박은 TourAPI 결과만 제공합니다."
        )
    places.sort(key=lambda place: (place.distance_m is None, place.distance_m or 0, place.name))
    return NearbyPlaceListResponse(
        event_id=event.event_id,
        items=places,
        radius_m=radius_m,
        meta=_response_meta().model_copy(update={"warnings": warnings or None}),
    )


def _merge_nearby_places(
    primary: list[NearbyPlace],
    supplemental: list[NearbyPlace],
) -> list[NearbyPlace]:
    merged = list(primary)
    for place in supplemental:
        existing_index = next(
            (
                index
                for index, existing in enumerate(merged)
                if _same_nearby_place(existing, place)
            ),
            None,
        )
        if existing_index is None:
            merged.append(place)
            continue
        existing = merged[existing_index]
        source_ids = {source.source_id for source in existing.sources}
        sources = existing.sources + [
            source for source in place.sources if source.source_id not in source_ids
        ]
        distances = [
            value
            for value in (existing.distance_m, place.distance_m)
            if value is not None
        ]
        merged[existing_index] = existing.model_copy(
            update={
                "address": existing.address or place.address,
                "coordinates": existing.coordinates or place.coordinates,
                "distance_m": min(distances) if distances else None,
                "sources": sources,
            }
        )
    return merged


def _same_nearby_place(first: NearbyPlace, second: NearbyPlace) -> bool:
    if first.place_type != second.place_type:
        return False
    normalized_first_name = "".join(first.name.casefold().split())
    normalized_second_name = "".join(second.name.casefold().split())
    if normalized_first_name != normalized_second_name:
        return False
    if first.coordinates is not None and second.coordinates is not None:
        return (
            abs(first.coordinates.latitude - second.coordinates.latitude) <= 0.001
            and abs(first.coordinates.longitude - second.coordinates.longitude) <= 0.001
        )
    if first.address and second.address:
        return (
            "".join(first.address.casefold().split())
            == "".join(second.address.casefold().split())
        )
    return False


async def build_event_prediction(
    event: EventDetail,
    tourapi: TourApiClient,
) -> AvailablePrediction | UnavailablePrediction:
    score = 50.0
    factors: list[PredictionFactor] = []
    prediction_sources = list(event.sources)

    def add_factor(factor_id: str, label: str, points: float, explanation: str) -> None:
        nonlocal score
        score += points
        factors.append(
            PredictionFactor(
                factor_id=factor_id,
                label=label,
                direction="up" if points > 0 else "down" if points < 0 else "neutral",
                importance=abs(points),
                explanation=explanation,
                evidence_refs=[],
            )
        )

    if _includes_weekend(event.start_date, event.end_date):
        add_factor("mock_weekend", "주말 포함", 7, "행사 기간에 토요일 또는 일요일이 포함됩니다.")
    else:
        add_factor("mock_weekday", "평일 일정", -2, "행사 기간이 평일로만 구성되어 있습니다.")

    days_until_start = (event.start_date - date.today()).days
    if 3 <= days_until_start <= 30:
        add_factor("mock_lead_time_fit", "방문 준비 기간", 5, "행사까지 3~30일 남아 방문 계획을 세우기 좋은 시점입니다.")
    elif days_until_start < 3:
        add_factor("mock_lead_time_short", "정보 반영 시간 부족", -6, "행사가 임박했거나 이미 시작되어 최신 정보를 반영할 시간이 부족합니다.")
    else:
        add_factor("mock_lead_time_long", "행사까지 남은 기간", 0, "행사까지 30일 넘게 남아 현재 정보만으로 수요 방향을 조정하지 않습니다.")

    duration_days = (event.end_date - event.start_date).days + 1
    if 1 <= duration_days <= 3:
        add_factor("mock_duration_focused", "집중된 행사 기간", 4, "1~3일 일정으로 방문 시점이 비교적 집중됩니다.")
    else:
        add_factor("mock_duration_long", "긴 행사 기간", -3, "행사 기간이 길어 방문 수요가 여러 날로 분산될 수 있습니다.")

    try:
        competing_count, competition_source = await tourapi.competing_festival_count(
            region=event.region,
            start_date=event.start_date,
            end_date=event.end_date,
        )
        prediction_sources.append(competition_source)
        if competing_count >= 5:
            add_factor("mock_competition_high", "동시기 지역 행사", -6, f"같은 지역·기간에 TourAPI 행사 {competing_count}건이 검색됩니다.")
        elif competing_count >= 2:
            add_factor("mock_competition_some", "동시기 지역 행사", -3, f"같은 지역·기간에 TourAPI 행사 {competing_count}건이 검색됩니다.")
        else:
            add_factor("mock_competition_low", "동시기 지역 행사", 0, f"같은 지역·기간의 TourAPI 행사 검색 결과는 {competing_count}건입니다.")
    except TourApiUnavailable:
        pass

    now = datetime.now().astimezone()
    model_source = SourceRef(
        source_id="src_heungmap_event_mock_model",
        source_type="heungmap_model",
        provider_name="흥할지도",
        dataset_name="자체 수요 모델 연결용 mock",
        retrieved_at=now,
        limitation="학습된 모델 출력이 아닌 화면·계약 검증용 규칙 점수입니다.",
    )
    prediction_sources.append(model_source)
    score = max(0, min(100, round(score, 1)))
    return AvailablePrediction(
        status="available",
        prediction_id=f"pred_mock_{uuid4().hex}",
        event_id=event.event_id,
        prediction_type="relative_demand_score",
        as_of=now,
        target_start_date=event.start_date,
        target_end_date=event.end_date,
        target_region=event.region,
        primary_metric=PredictionScoreMetric(
            metric_name="relative_demand_score",
            unit="index_0_100",
            value=score,
        ),
        indicators=PredictionIndicators(
            demand_score=score,
            congestion_level=_demand_level(score),
            ticket_demand_level="unknown",
        ),
        confidence="low",
        data_sufficiency="limited",
        method="rules",
        model_version="mock-model-interface-0.1",
        factors=factors,
        evidence=[],
        sources=prediction_sources,
        limitations=[
            "이 점수는 자체 AI 모델 연결 전의 mock이며 실제 수요 예측이 아닙니다.",
            "지역 방문수요나 이 점수를 특정 행사 관람객 수로 해석할 수 없습니다.",
        ],
        out_of_distribution=True,
        fallback_used=True,
        created_at=now,
        is_mock=True,
    )
