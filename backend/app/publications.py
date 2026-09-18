from __future__ import annotations

import json
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.auth import AUTH_ERRORS, require_user, same_origin
from app.schemas import AvailablePrediction, DataQuality, EventDetail, PlannerAnalysisResponse, SourceRef
from app.services.accounts import database

router = APIRouter(prefix="/api/v1/planner/publications", tags=["planner"], responses=AUTH_ERRORS)


def analysis_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS publishable_analyses (
        analysis_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, payload TEXT NOT NULL)""")


def remember_analysis(user_id: str, analysis: PlannerAnalysisResponse):
    with database() as db:
        analysis_table(db)
        db.execute("INSERT OR REPLACE INTO publishable_analyses VALUES (?, ?, ?)",
                   (analysis.analysis_id, user_id, analysis.model_dump_json()))


# 공개 일정·지역·행사명만으로 계산되는 근거. 기획자 입력(예산·목표 인원·수용인원 등) 기반 근거는 포함하지 않는다.
PUBLIC_EVIDENCE_IDS = {"ev_daily_baseline", "ev_daily_region_holdout", "ev_daily_demand_level",
                       "ev_mcst_prior_attendance", "ev_tourapi_same_period"}


def public_prediction(analysis: PlannerAnalysisResponse, source: SourceRef):
    """공개용 예측. 같은 ID·수치는 유지하고 비공개 기획 입력 근거는 뺀다."""
    prediction = analysis.prediction.model_copy(deep=True)
    if isinstance(prediction, AvailablePrediction):
        # 같은 예측 ID·수치는 유지하고 비공개 기획 입력(예산·목표 인원·메모 등)은 내보내지 않는다.
        # 공개 일정·지역·행사명만으로 정해지는 공공 근거와 모델 요인은 방문객 흥행 진단을 위해 남긴다.
        public_evidence = [item for item in [*prediction.evidence, *analysis.evidence]
                           if item.evidence_id in PUBLIC_EVIDENCE_IDS]
        prediction.evidence = list({item.evidence_id: item for item in public_evidence}.values())
        prediction.factors = [factor for factor in prediction.factors if factor.factor_id.startswith("daily_")]
        kept_refs = {ref for item in prediction.evidence for ref in item.source_refs}
        prediction.sources = [source, *[s for s in prediction.sources
                                         if s.source_type in {"heungmap_model", "kto_datalab", "tourapi"}
                                         or s.source_id in kept_refs]]
        kept_ids = {item.evidence_id for item in prediction.evidence}
        for component in prediction.components or []:
            component.evidence_refs = [ref for ref in component.evidence_refs if ref in kept_ids]
        if prediction.indicators is not None:
            prediction.indicators.ticket_demand_level = "unknown"
        prediction.limitations = [*prediction.limitations, "비공개 기획 입력의 세부 영향 요인은 공개하지 않습니다."]
    return prediction


class PublishRequest(BaseModel):
    analysis_id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=3000)
    consent: bool


@router.get("", response_model=list[EventDetail], response_model_exclude_none=True, operation_id="listMyPublications")
def my_publications(request: Request):
    user = require_user(request)
    with database() as db:
        return [EventDetail.model_validate_json(row["event_json"]) for row in db.execute(
            "SELECT event_json FROM publications WHERE owner_id=?", (user["id"],))]


@router.post("", response_model=EventDetail, response_model_exclude_none=True, operation_id="publishPlannerEvent")
def publish(body: PublishRequest, request: Request):
    same_origin(request)
    user = require_user(request)
    if user["role"] != "planner":
        raise HTTPException(403, "기획자 모드에서 공개할 수 있습니다.")
    if not body.consent:
        raise HTTPException(422, "공개 항목을 확인하고 동의해 주세요.")
    with database() as db:
        analysis_table(db)
        row = db.execute("SELECT payload FROM publishable_analyses WHERE analysis_id=? AND owner_id=?",
                         (body.analysis_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(409, "현재 계정에서 기획을 다시 분석한 후 공개해 주세요.")
    analysis = PlannerAnalysisResponse.model_validate_json(row["payload"])
    draft = analysis.request_snapshot
    if not draft.event_id.startswith("evt_planner_"):
        raise HTTPException(422, "기획자 행사 ID로 분석한 결과만 공개할 수 있습니다.")
    if not body.description.strip():
        raise HTTPException(422, "공개용 소개문을 입력해 주세요.")
    if not draft.working_title or not draft.start_date or not draft.end_date or not draft.region or not draft.venue:
        raise HTTPException(422, "행사명, 확정 일정·지역과 장소를 입력하고 다시 분석해 주세요.")
    if draft.schedule_selection_mode != "fixed" or draft.region_selection_mode != "fixed":
        raise HTTPException(422, "일정과 지역을 확정한 뒤 공개해 주세요.")
    now = datetime.now().astimezone()
    source = SourceRef(source_id="src_" + draft.event_id, source_type="planner_input",
                       provider_name="행사 기획자", dataset_name="기획자가 공개한 행사 정보", retrieved_at=now)
    event = EventDetail(
        event_id=draft.event_id, origin="planner", visibility="public", title=draft.working_title,
        event_type=draft.event_type, event_status="scheduled", start_date=draft.start_date,
        end_date=draft.end_date, region=draft.region, venue=draft.venue, description=body.description,
        sources=[source], data_quality=DataQuality(completeness="medium",
            warnings=["기획자가 직접 등록한 정보입니다. 방문 전 개최 여부를 확인해 주세요."], is_mock=False),
        updated_at=now,
    )
    prediction = public_prediction(analysis, source)
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT owner_id FROM publications WHERE event_id=?", (event.event_id,)).fetchone()
        if existing and existing["owner_id"] != user["id"]:
            raise HTTPException(403, "다른 기획자의 행사를 변경할 수 없습니다.")
        db.execute("INSERT OR REPLACE INTO publications VALUES (?, ?, ?, ?, ?)",
                   (event.event_id, user["id"], event.model_dump_json(exclude_none=True),
                    prediction.model_dump_json(exclude_none=True), "[]"))
    return event


@router.delete("/{event_id}", operation_id="unpublishPlannerEvent")
def unpublish(event_id: str, request: Request):
    same_origin(request)
    user = require_user(request)
    with database() as db:
        removed = db.execute("DELETE FROM publications WHERE event_id=? AND owner_id=?", (event_id, user["id"]))
        if not removed.rowcount:
            raise HTTPException(404, "공개한 행사를 찾을 수 없습니다.")
    return {"ok": True}


def current_event(event: EventDetail) -> EventDetail:
    event.event_status = "ended" if event.end_date < date.today() else "ongoing" if event.start_date <= date.today() else "scheduled"
    return event


def published_events() -> list[EventDetail]:
    with database() as db:
        return [current_event(EventDetail.model_validate_json(row["event_json"]))
                for row in db.execute("SELECT event_json FROM publications")]


def published_event(event_id: str) -> EventDetail | None:
    with database() as db:
        row = db.execute("SELECT event_json FROM publications WHERE event_id=?", (event_id,)).fetchone()
        return current_event(EventDetail.model_validate_json(row["event_json"])) if row else None


def published_prediction(event_id: str):
    with database() as db:
        row = db.execute("SELECT prediction_json FROM publications WHERE event_id=?", (event_id,)).fetchone()
        return json.loads(row["prediction_json"]) if row else None
