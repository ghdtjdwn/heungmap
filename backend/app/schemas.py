from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


ContractVersion = Literal["0.1.0"]
PlannerType = Literal[
    "local_government",
    "public_agency",
    "company",
    "event_agency",
    "performance_agency",
    "venue_operator",
    "club_or_group",
    "independent_planner",
    "artist",
    "other",
]
PlanningStage = Literal[
    "idea",
    "research",
    "budget_application",
    "venue_search",
    "booking",
    "marketing_preparation",
    "ticket_sales",
    "final_preparation",
]
EventType = Literal[
    "festival",
    "local_event",
    "concert",
    "club_performance",
    "exhibition",
    "conference",
    "experience",
    "market",
    "other",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coordinates(ContractModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RegionRef(ContractModel):
    area_code: str = Field(min_length=1, max_length=20)
    sigungu_code: str | None = Field(default=None, min_length=1, max_length=20)
    legal_dong_code: str | None = Field(default=None, min_length=1, max_length=20)
    display_name: str = Field(min_length=1, max_length=100)


class Venue(ContractModel):
    venue_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    coordinates: Coordinates | None = None
    capacity: int | None = Field(default=None, ge=1)
    indoor_outdoor: Literal["indoor", "outdoor", "mixed", "unknown"] | None = None
    accessibility_summary: str | None = Field(default=None, max_length=500)


class DateRange(ContractModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_order(self) -> "DateRange":
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self


class EventDraft(ContractModel):
    event_id: str = Field(pattern=r"^evt_planner_[a-z0-9_\-]+$")
    working_title: str | None = Field(default=None, max_length=200)
    planner_type: PlannerType
    planning_stage: PlanningStage
    event_type: EventType
    event_type_other: str | None = Field(default=None, max_length=100)
    purpose: Literal[
        "profit",
        "regional_revitalization",
        "tourism",
        "brand",
        "fandom",
        "community",
        "culture",
        "education",
        "social_contribution",
        "other",
    ]
    purpose_other: str | None = Field(default=None, max_length=200)
    theme_keywords: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(max_length=20)
    schedule_selection_mode: Literal["fixed", "candidates", "recommend", "unknown"]
    start_date: date | None = None
    end_date: date | None = None
    date_candidates: list[DateRange] | None = Field(default=None, min_length=2, max_length=5)
    region_selection_mode: Literal["fixed", "candidates", "recommend", "unknown"]
    region: RegionRef | None = None
    region_candidates: list[RegionRef] | None = Field(default=None, min_length=2, max_length=5)
    venue: Venue | None = None
    indoor_outdoor: Literal["indoor", "outdoor", "mixed", "undecided"]
    target_audience: list[
        Literal[
            "child",
            "teen",
            "young_adult",
            "middle_aged",
            "senior",
            "family",
            "local_resident",
            "domestic_tourist",
            "foreign_tourist",
            "fandom",
            "other",
        ]
    ] = Field(min_length=1)
    target_audience_other: str | None = Field(default=None, max_length=300)
    target_attendance: int | None = Field(default=None, ge=1)
    ticket_type: Literal["free", "paid", "mixed", "undecided"]
    budget_min_krw: int | None = Field(default=None, ge=0)
    budget_max_krw: int | None = Field(default=None, ge=0)
    fixed_constraints: list[Annotated[str, Field(max_length=500)]] = Field(max_length=30)
    other_notes: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_conditionals(self) -> "EventDraft":
        if self.schedule_selection_mode == "fixed":
            if not self.start_date or not self.end_date:
                raise ValueError("확정 일정에는 시작일과 종료일이 필요합니다.")
            if self.end_date < self.start_date:
                raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        if self.schedule_selection_mode == "candidates" and not self.date_candidates:
            raise ValueError("일정 후보를 2개 이상 입력해 주세요.")
        if self.region_selection_mode == "fixed" and not self.region:
            raise ValueError("확정 지역을 선택해 주세요.")
        if self.region_selection_mode == "candidates" and not self.region_candidates:
            raise ValueError("지역 후보를 2개 이상 입력해 주세요.")
        if self.event_type == "other" and not self.event_type_other:
            raise ValueError("기타 행사 유형을 입력해 주세요.")
        if self.purpose == "other" and not self.purpose_other:
            raise ValueError("기타 행사 목적을 입력해 주세요.")
        if "other" in self.target_audience and not self.target_audience_other:
            raise ValueError("기타 목표 이용객을 입력해 주세요.")
        if self.budget_min_krw is not None and self.budget_max_krw is not None:
            if self.budget_max_krw < self.budget_min_krw:
                raise ValueError("최대 예산은 최소 예산보다 작을 수 없습니다.")
        if len(self.target_audience) != len(set(self.target_audience)):
            raise ValueError("목표 이용객은 중복될 수 없습니다.")
        return self


class PlannerAnalysisRequest(ContractModel):
    contract_version: ContractVersion
    client_request_id: UUID
    event_draft: EventDraft
    requested_outputs: list[Literal["prediction", "nearby_places", "rule_recommendations"]] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_unique_outputs(self) -> "PlannerAnalysisRequest":
        if len(self.requested_outputs) != len(set(self.requested_outputs)):
            raise ValueError("requested_outputs는 중복될 수 없습니다.")
        return self


class SourceRef(ContractModel):
    source_id: str = Field(min_length=1, max_length=128)
    source_type: Literal[
        "tourapi",
        "kto_datalab",
        "planner_input",
        "heungmap_derived",
        "heungmap_model",
        "weather",
        "other_public",
    ]
    provider_name: str = Field(min_length=1, max_length=100)
    dataset_name: str = Field(min_length=1, max_length=200)
    source_record_id: str | None = Field(default=None, max_length=200)
    source_url: HttpUrl | None = None
    retrieved_at: datetime
    data_as_of: datetime | None = None
    limitation: str | None = Field(default=None, max_length=1000)


class Evidence(ContractModel):
    evidence_id: str = Field(min_length=1, max_length=128)
    value_type: Literal["user_input", "verified_fact", "derived_value", "model_prediction", "assumption"]
    label: str = Field(min_length=1, max_length=200)
    display_value: str = Field(min_length=1, max_length=500)
    numeric_value: float | None = None
    unit: str | None = Field(default=None, max_length=50)
    as_of: datetime | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    source_refs: list[str]
    limitation: str | None = Field(default=None, max_length=1000)


class PredictionFactor(ContractModel):
    factor_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=200)
    direction: Literal["up", "down", "neutral", "unknown"]
    importance: float | None = Field(default=None, ge=0)
    explanation: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str]


class PredictionScoreMetric(ContractModel):
    metric_name: Literal["relative_demand_score"]
    unit: Literal["index_0_100"]
    value: float = Field(ge=0, le=100)


class PredictionIndicators(ContractModel):
    demand_score: float | None = Field(default=None, ge=0, le=100)
    congestion_level: Literal["low", "medium", "high", "very_high", "unknown"] | None = None
    ticket_demand_level: Literal["low", "medium", "high", "very_high", "unknown"] | None = None


class AvailablePrediction(ContractModel):
    status: Literal["available"]
    prediction_id: str
    event_id: str
    prediction_type: Literal["relative_demand_score"]
    as_of: datetime
    target_start_date: date
    target_end_date: date
    target_region: RegionRef | None = None
    primary_metric: PredictionScoreMetric
    indicators: PredictionIndicators | None = None
    confidence: Literal["low", "medium", "high"]
    data_sufficiency: Literal["limited", "sufficient"]
    method: Literal["rules", "machine_learning", "external_benchmark"]
    model_version: str
    factors: list[PredictionFactor]
    evidence: list[Evidence]
    sources: list[SourceRef] = Field(min_length=1)
    limitations: list[str]
    out_of_distribution: bool
    fallback_used: bool
    created_at: datetime
    is_mock: bool


class UnavailablePrediction(ContractModel):
    status: Literal["unavailable"]
    event_id: str
    reason_code: Literal[
        "insufficient_data",
        "unsupported_event_type",
        "missing_required_input",
        "model_unavailable",
        "upstream_unavailable",
    ]
    message: str
    as_of: datetime
    sources: list[SourceRef]
    limitations: list[str]
    retryable: bool
    is_mock: bool


PredictionResult = Annotated[AvailablePrediction | UnavailablePrediction, Field(discriminator="status")]


class NearbyPlace(ContractModel):
    place_id: str
    place_type: Literal[
        "parking",
        "lodging",
        "restaurant",
        "cafe",
        "tourist_attraction",
        "cultural_facility",
        "shopping",
        "restroom",
        "transit",
        "other",
    ]
    name: str
    address: str | None = None
    coordinates: Coordinates | None = None
    distance_m: int | None = Field(default=None, ge=0)
    accessibility_summary: str | None = None
    sources: list[SourceRef] = Field(min_length=1)


class NearbyAvailable(ContractModel):
    status: Literal["available"]
    items: list[NearbyPlace]
    radius_m: int = Field(ge=100, le=20000)
    is_mock: bool


class NearbyUnavailable(ContractModel):
    status: Literal["unavailable"]
    reason_code: Literal["not_requested", "missing_coordinates", "unsupported_scope", "upstream_unavailable"]
    message: str
    retryable: bool
    is_mock: bool


NearbyResult = Annotated[NearbyAvailable | NearbyUnavailable, Field(discriminator="status")]


class Recommendation(ContractModel):
    recommendation_id: str
    category: Literal["demand", "venue", "budget", "marketing", "operation", "risk", "accessibility", "tourism"]
    priority: Literal["low", "medium", "high"]
    title: str
    action: str
    reason: str
    evidence_refs: list[str]
    requires_human_review: bool


class ResponseMeta(ContractModel):
    contract_version: ContractVersion
    generated_at: datetime
    request_id: str
    warnings: list[str] | None = None


class VenueSearchItem(ContractModel):
    venue: Venue
    category: str | None = Field(default=None, max_length=100)
    content_type_id: str | None = Field(default=None, max_length=20)
    source: SourceRef


class VenueSearchResponse(ContractModel):
    items: list[VenueSearchItem]
    meta: ResponseMeta


class AddressSearchItem(ContractModel):
    address_name: str = Field(min_length=1, max_length=300)
    road_address_name: str | None = Field(default=None, max_length=300)
    jibun_address_name: str | None = Field(default=None, max_length=300)
    building_name: str | None = Field(default=None, max_length=200)
    coordinates: Coordinates
    source: SourceRef


class AddressSearchResponse(ContractModel):
    items: list[AddressSearchItem]
    meta: ResponseMeta


class PlannerAnalysisResponse(ContractModel):
    analysis_id: str
    contract_version: ContractVersion
    request_snapshot: EventDraft
    prediction: PredictionResult
    nearby_places: NearbyResult
    evidence: list[Evidence]
    rule_recommendations: list[Recommendation]
    meta: ResponseMeta


class PlannerRecommendationRequest(ContractModel):
    contract_version: ContractVersion
    client_request_id: UUID
    analysis_id: str = Field(min_length=1, max_length=128)
    planning_context: dict[str, Any]
    rule_recommendations: list[Recommendation] = Field(max_length=30)
    requested_alternatives: int = Field(default=2, ge=1, le=5)


class PlannerRecommendationPriority(ContractModel):
    id: str = Field(min_length=1, max_length=128)
    priority: Literal["low", "medium", "high"]
    category: Literal["demand", "venue", "budget", "marketing", "operation", "risk", "accessibility", "tourism"]
    title: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(min_length=1, max_length=30)
    assumptions: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=10)
    predicted_impact: str = Field(min_length=1, max_length=1000)
    confidence: Literal["low", "medium", "high"]
    cost_level: Literal["unknown", "low", "medium", "high"]
    difficulty: Literal["easy", "moderate", "hard", "needs_review"]
    deadline: str | None = Field(max_length=100)
    dependencies: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=10)
    risks: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=10)
    requires_human_review: Literal[True]


class PlannerRecommendationAlternative(ContractModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    changes: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=10)
    verify: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=10)


class PlannerRecommendationRoadmapItem(ContractModel):
    phase: str = Field(min_length=1, max_length=100)
    actions: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=20)


class PlannerRecommendationContent(ContractModel):
    executive_summary: str = Field(min_length=1, max_length=3000)
    priorities: list[PlannerRecommendationPriority] = Field(min_length=1, max_length=20)
    alternatives: list[PlannerRecommendationAlternative] = Field(min_length=1, max_length=5)
    roadmap: list[PlannerRecommendationRoadmapItem] = Field(min_length=1, max_length=10)
    missing_information: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=30)
    limitations: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1, max_length=20)


class StructuredPlanningRecommendation(PlannerRecommendationContent):
    schema_version: Literal["1.0"]
    prompt_version: Literal["planner-recommendation-1.0"]
    generation_mode: Literal["llm"]
    generated_at: datetime


class LlmResponseMeta(ContractModel):
    contract_version: ContractVersion
    generated_at: datetime
    request_id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    prompt_version: Literal["planner-recommendation-1.0"]


class PlannerRecommendationResponse(ContractModel):
    recommendation: StructuredPlanningRecommendation
    meta: LlmResponseMeta


class HealthResponse(ContractModel):
    status: Literal["ok"]
    service: Literal["heungmap-api"]
    contract_version: ContractVersion
    checked_at: datetime


class FieldError(ContractModel):
    field: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=500)


class Problem(ContractModel):
    type: str
    title: str = Field(min_length=1, max_length=200)
    status: int = Field(ge=100, le=599)
    detail: str = Field(min_length=1, max_length=1000)
    instance: str
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    retryable: bool
    trace_id: str = Field(min_length=1, max_length=128)
    field_errors: list[FieldError] | None = None
