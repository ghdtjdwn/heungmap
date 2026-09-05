import type {
  ContextValue,
  DraftRecord,
  PlannerAnalysisResponse,
  PlanningContext,
} from "./types";

function input(value: unknown, unit?: string, limitation?: string): ContextValue {
  return {
    value: value === "" || value === undefined ? null : value,
    value_type: "user_input",
    source: "planner_form",
    ...(unit ? { unit } : {}),
    ...(limitation ? { limitation } : {}),
  };
}

function prediction(value: unknown, limitation?: string): ContextValue {
  return {
    value,
    value_type: "model_prediction",
    source: "planner_analysis.prediction",
    confidence: "low",
    ...(limitation ? { limitation } : {}),
  };
}

function verified(value: unknown, limitation?: string): ContextValue {
  return {
    value,
    value_type: "verified_fact",
    source: "planner_analysis.evidence",
    confidence: "medium",
    ...(limitation ? { limitation } : {}),
  };
}

export function buildPlanningContext(
  draft: DraftRecord,
  analysis: PlannerAnalysisResponse,
): PlanningContext {
  const event = draft.event;
  const details = draft.details;
  const missing: string[] = [];
  const requireValue = (value: unknown, label: string) => {
    if (value === "" || value === undefined || value === null || value === "unknown") missing.push(label);
  };

  requireValue(event.working_title, "행사명");
  requireValue(details.decision_deadline, "최종 의사결정 기한");
  requireValue(details.event_summary, "행사 한 줄 설명");
  requireValue(event.target_attendance, "목표 이용객 수");
  requireValue(details.minimum_success_attendance, "최소 성공 인원");
  requireValue(event.start_date ?? event.date_candidates?.[0]?.start_date, "행사 일정");
  requireValue(event.region?.display_name ?? event.region_candidates?.[0]?.display_name, "개최 지역");
  requireValue(event.venue?.name, "장소");
  requireValue(details.success_metric, "핵심 KPI");
  requireValue(details.program_outline, "프로그램 구성");
  requireValue(details.safety_plan, "안전 계획");
  if (event.ticket_type === "paid" || event.ticket_type === "mixed") {
    requireValue(details.ticket_price_max_krw, "티켓 가격");
    requireValue(details.refund_policy, "취소·환불 정책");
  }
  if (event.indoor_outdoor === "outdoor" || event.indoor_outdoor === "mixed") {
    requireValue(details.rain_or_weather_fallback, "기상 대체안");
  }

  const nearby = analysis.nearby_places.status === "available"
    ? analysis.nearby_places.items.map((place) => ({ name: place.name, type: place.place_type, distance_m: place.distance_m }))
    : { status: "unavailable", reason: analysis.nearby_places.message };
  const predictionValue = analysis.prediction.status === "available"
    ? analysis.prediction.primary_metric.value
    : null;

  return {
    context_version: "1.0",
    generated_at: new Date().toISOString(),
    planner_profile: {
      planner_type: input(event.planner_type),
      planning_stage: input(event.planning_stage),
      team_size: input(details.team_size, "people"),
      decision_makers: input(details.decision_makers, "people"),
      experience_level: input(details.experience_level),
      decision_deadline: input(details.decision_deadline),
      recommendation_goals: input(details.recommendation_goals),
      detail_level: input(details.detail_level),
      main_concern: input(details.main_concern),
    },
    event_brief: {
      working_title: input(event.working_title),
      event_type: input(event.event_type),
      purpose: input(event.purpose),
      themes: input(event.theme_keywords),
      summary: input(details.event_summary),
      frequency: input(details.event_frequency),
      format: input(details.event_format),
      access_type: input(details.access_type),
      success_metric: input(details.success_metric),
    },
    target_audience: {
      segments: input(event.target_audience),
      target_attendance: input(event.target_attendance, "people", "기획 목표이며 실제 방문자 수가 아닙니다."),
      minimum_success_attendance: input(details.minimum_success_attendance, "people"),
      maximum_concurrent_attendance: input(details.maximum_concurrent_attendance, "people"),
      interests: input(details.audience_interests),
      visit_motivation: input(details.visit_motivation),
      dropout_reason: input(details.dropout_reason),
      expected_stay_hours: input(details.expected_stay_hours, "hours"),
      required_languages: input(details.required_languages),
      accessibility_needs: input(details.audience_accessibility_needs),
    },
    schedule_candidates: {
      selection_mode: input(event.schedule_selection_mode),
      fixed_range: input(event.start_date && event.end_date ? { start: event.start_date, end: event.end_date } : null),
      candidates: input(event.date_candidates ?? []),
      daily_hours: input(details.daily_hours),
      setup_rehearsal_teardown: input(details.setup_rehearsal_teardown),
      preferred_daytime: input(details.preferred_daytime),
      competing_event_tolerance: input(details.competing_event_tolerance),
      weather_fallback: input(details.rain_or_weather_fallback),
    },
    location_and_venue_candidates: {
      selection_mode: input(event.region_selection_mode),
      region: input(event.region ?? null),
      region_candidates: input(event.region_candidates ?? []),
      venue: input(event.venue ?? null),
      venue_type: input(details.venue_type),
      seating_mode: input(details.seating_mode),
      venue_area: input(details.venue_area_sqm, "m2"),
      parking_spaces: input(details.parking_spaces, "spaces"),
      transit_plan: input(details.transit_plan),
      facilities: input(details.facility_plan),
    },
    program_and_performers: {
      program_outline: input(details.program_outline),
      performer_partner_plan: input(details.performer_partner_plan),
      program_priority: input(details.program_priority),
    },
    ticket_and_budget: {
      ticket_type: input(event.ticket_type),
      ticket_price_range: input({ min: details.ticket_price_min_krw ?? null, max: details.ticket_price_max_krw ?? null }, "krw"),
      ticket_sales_target: input(details.ticket_sales_target, "tickets"),
      sales_channels: input(details.ticket_sales_channels),
      refund_policy: input(details.refund_policy),
      budget_range: input({ min: event.budget_min_krw ?? null, max: event.budget_max_krw ?? null }, "krw"),
      secured_budget: input(details.secured_budget_krw, "krw"),
      budget_breakdown: input(details.budget_breakdown),
      expected_revenue: input(details.expected_revenue_krw, "krw"),
      break_even_attendance: input(details.break_even_attendance, "people"),
    },
    marketing_and_operations: {
      marketing_channels: input(details.marketing_channels),
      marketing_start_date: input(details.marketing_start_date),
      marketing_budget: input(details.marketing_budget_krw, "krw"),
      marketing_kpi: input(details.marketing_kpi),
      operation_plan: input(details.operation_plan),
      staff_count: input(details.staff_count, "people"),
      queue_plan: input(details.queue_plan),
      technical_fallback: input(details.technical_fallback),
      transport_accommodation: input(details.transport_accommodation_plan),
      local_partnership: input(details.local_partnership_plan),
    },
    safety_accessibility_sustainability: {
      safety_plan: input(details.safety_plan),
      permits_and_insurance: input(details.permits_and_insurance, undefined, "담당 기관과 전문가 확인이 필요합니다."),
      cancellation_rule: input(details.cancellation_rule),
      accessibility_plan: input(details.accessibility_plan),
      sustainability_plan: input(details.sustainability_plan),
      past_event_summary: input(details.past_event_summary),
    },
    prediction_result: {
      relative_demand_score: prediction(predictionValue, "학습 모델 연결 전 mock 상대지수이며 실제 관람객 수가 아닙니다."),
      status: prediction(analysis.prediction.status),
      model_version: prediction(analysis.prediction.status === "available" ? analysis.prediction.model_version : null),
      factors: prediction(analysis.prediction.status === "available" ? analysis.prediction.factors : []),
    },
    tourism_and_local_evidence: {
      nearby_places: verified(nearby, "TourAPI 조회 결과이며 현장 운영 가능 여부는 별도 확인이 필요합니다."),
      evidence: verified(analysis.evidence),
      venue_search_source: verified(details.venue_search_source ?? null, "TourAPI 장소 후보를 직접 선택한 경우에만 기록됩니다."),
      address_search_source: verified(details.address_search_source ?? null, "Kakao 주소 검색 결과를 직접 선택한 경우에만 기록됩니다."),
    },
    fixed_constraints: event.fixed_constraints,
    flexible_options: details.flexible_options.split("\n").map((item) => item.trim()).filter(Boolean),
    missing_information: [...new Set(missing)],
    requested_decisions: details.requested_decisions.split("\n").map((item) => item.trim()).filter(Boolean),
    generation: {
      mode: "context_only",
      llm_used: false,
      model_mock: true,
      limitation: "이 객체는 LLM 입력용 Context입니다. 추천 생성 방식은 별도 응답 metadata에서 확인합니다.",
    },
  };
}
