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
    prediction = analysis.prediction.model_copy(deep=True)
    if isinstance(prediction, AvailablePrediction):
        # Preserve the same prediction ID and score without disclosing private inputs.
        prediction.factors = []
        prediction.evidence = []
        prediction.sources = [source, *[s for s in prediction.sources if s.source_type == "heungmap_model"]]
        prediction.indicators.ticket_demand_level = "unknown"
        prediction.limitations = [*prediction.limitations, "비공개 기획 입력의 세부 영향 요인은 공개하지 않습니다."]
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
