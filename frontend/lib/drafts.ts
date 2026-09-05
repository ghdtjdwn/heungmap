import type { DraftRecord, EventDraft, PlanningDetails } from "./types";

const STORAGE_KEY = "heungmap.planner.drafts.v1";

export const EMPTY_DETAILS: PlanningDetails = {
  experience_level: "unknown",
  decision_deadline: "",
  recommendation_goals: [],
  detail_level: "standard",
  main_concern: "",
  event_summary: "",
  event_frequency: "unknown",
  event_format: "unknown",
  access_type: "unknown",
  success_metric: "",
  audience_interests: "",
  visit_motivation: "",
  dropout_reason: "",
  required_languages: [],
  audience_accessibility_needs: "",
  daily_hours: "",
  setup_rehearsal_teardown: "",
  rain_or_weather_fallback: "",
  preferred_daytime: "unknown",
  competing_event_tolerance: "unknown",
  venue_type: "",
  seating_mode: "unknown",
  transit_plan: "",
  facility_plan: "",
  program_outline: "",
  performer_partner_plan: "",
  program_priority: "",
  ticket_sales_channels: "",
  refund_policy: "",
  budget_breakdown: "",
  marketing_channels: [],
  marketing_start_date: "",
  marketing_kpi: "",
  operation_plan: "",
  queue_plan: "",
  technical_fallback: "",
  transport_accommodation_plan: "",
  local_partnership_plan: "",
  safety_plan: "",
  permits_and_insurance: "",
  cancellation_rule: "",
  accessibility_plan: "",
  sustainability_plan: "",
  past_event_summary: "",
  flexible_options: "",
  priority_criteria: [],
  risk_tolerance: "unknown",
  requested_alternatives: 2,
  requested_decisions: "",
};

function createEventId() {
  return `evt_planner_${crypto.randomUUID().replaceAll("-", "_")}`;
}

export function emptyDraft(): DraftRecord {
  const now = new Date().toISOString();
  const id = crypto.randomUUID();
  return {
    id,
    created_at: now,
    updated_at: now,
    status: "draft",
    current_step: 0,
    version: 0,
    event: {
      event_id: createEventId(),
      planner_type: "",
      planning_stage: "",
      event_type: "festival",
      purpose: "",
      theme_keywords: [],
      schedule_selection_mode: "unknown",
      region_selection_mode: "unknown",
      indoor_outdoor: "undecided",
      target_audience: [],
      ticket_type: "undecided",
      fixed_constraints: [],
    },
    details: { ...EMPTY_DETAILS },
    history: [],
  };
}

const sampleBase = (): DraftRecord => ({ ...emptyDraft(), current_step: 0 });

export function sampleDraft(kind: "independent" | "large"): DraftRecord {
  const record = sampleBase();
  if (kind === "large") {
    record.event = {
      ...record.event,
      working_title: "가상 바다문화축제",
      planner_type: "local_government",
      planning_stage: "budget_application",
      event_type: "festival",
      purpose: "regional_revitalization",
      theme_keywords: ["지역문화", "바다", "가족"],
      schedule_selection_mode: "candidates",
      date_candidates: [
        { start_date: "2026-10-09", end_date: "2026-10-11" },
        { start_date: "2026-10-16", end_date: "2026-10-18" },
      ],
      region_selection_mode: "fixed",
      region: { area_code: "6", display_name: "부산" },
      indoor_outdoor: "outdoor",
      target_audience: ["family", "local_resident", "domestic_tourist"],
      target_attendance: 20000,
      ticket_type: "free",
      budget_min_krw: 200000000,
      budget_max_krw: 300000000,
      fixed_constraints: ["개최 지역 변경 불가", "총예산 3억원 초과 불가"],
      other_notes: "대규모 혼잡과 우천 시 운영 대안을 먼저 확인하고 싶습니다.",
    };
    record.details = {
      ...EMPTY_DETAILS,
      team_size: 18,
      decision_makers: 4,
      experience_level: "six_plus",
      decision_deadline: "2026-09-25",
      recommendation_goals: ["타당성 검증", "장소 비교", "안전 점검"],
      detail_level: "detailed",
      main_concern: "무료 대형 야외행사의 혼잡과 우천 대응",
      event_summary: "지역 예술과 해양 관광을 연결하는 3일 가족 축제",
      event_frequency: "annual",
      event_format: "offline",
      access_type: "public",
      success_metric: "지역 외 방문객 비중과 지역 상권 연계 참여",
      minimum_success_attendance: 12000,
      maximum_concurrent_attendance: 6500,
      audience_interests: "지역 문화, 가족 체험, 바다 관광",
      visit_motivation: "가족이 함께 즐기는 무료 공연과 지역 체험",
      dropout_reason: "우천, 교통 혼잡, 긴 대기시간",
      expected_stay_hours: 4,
      required_languages: ["한국어", "영어"],
      audience_accessibility_needs: "유모차와 휠체어 이동, 가족 휴게 공간",
      daily_hours: "10:00~21:00",
      setup_rehearsal_teardown: "전일 설치·리허설, 종료 다음 날 철거",
      rain_or_weather_fallback: "우천 시 실내 프로그램 전환과 일부 공연 연기 기준 필요",
      preferred_daytime: "day",
      competing_event_tolerance: "avoid",
      venue_type: "야외광장",
      seating_mode: "mixed",
      venue_area_sqm: 18000,
      parking_spaces: 900,
      transit_plan: "거점역 셔틀과 임시 주차장 검토",
      facility_plan: "화장실·수유실·의료실·휴게 텐트 필요",
      program_outline: "지역 예술가 공연, 가족 체험, 지역 식음 부스",
      performer_partner_plan: "지역 예술가 12팀, 헤드라이너 후보 2팀, 상인회 협업",
      program_priority: "가족 체험과 지역 상권 프로그램은 유지",
      budget_breakdown: "무대·시설 35%, 운영·안전 25%, 프로그램 20%, 홍보 10%, 예비비 10%",
      secured_budget_krw: 200000000,
      expected_revenue_krw: 50000000,
      marketing_channels: ["인스타그램", "블로그", "보도자료"],
      marketing_start_date: "2026-08-10",
      marketing_budget_krw: 30000000,
      marketing_kpi: "지역 외 사전등록과 제휴 쿠폰 사용",
      operation_plan: "다중 출입구와 임시 주차·셔틀을 검토 중",
      staff_count: 120,
      queue_plan: "입구 3곳 분산, 실시간 혼잡 안내",
      technical_fallback: "정전·결제·무전 장애별 수기 운영표 필요",
      transport_accommodation_plan: "막차 전 메인 공연 종료, 출연진 숙소 30실 확보 검토",
      local_partnership_plan: "상인회 할인 쿠폰과 지역 관광 코스 연계",
      safety_plan: "소방·경찰·의료 협의 일정 필요",
      permits_and_insurance: "지자체·소방·경찰 협의와 행사 배상보험 확인",
      cancellation_rule: "강풍·호우 특보와 현장 위험 수준을 기준으로 결정",
      accessibility_plan: "유모차·휠체어 동선과 가족 휴게 공간 필요",
      sustainability_plan: "다회용기와 분리배출, 대중교통 이용 캠페인",
      past_event_summary: "전년도 가상 행사에서 입장 대기와 주차 민원이 반복됨",
      flexible_options: "프로그램 회차, 부스 수, 홍보 채널",
      priority_criteria: ["안전", "지역효과", "만족도"],
      risk_tolerance: "low",
      requested_alternatives: 3,
      requested_decisions: "우천 대체안과 주차·셔틀 규모 결정",
    };
    return record;
  }
  record.event = {
    ...record.event,
    working_title: "가상 청년 음악축제",
    planner_type: "independent_planner",
    planning_stage: "idea",
    event_type: "festival",
    purpose: "community",
    theme_keywords: ["청년", "인디음악"],
    schedule_selection_mode: "fixed",
    start_date: "2026-10-10",
    end_date: "2026-10-10",
    region_selection_mode: "fixed",
    region: { area_code: "1", display_name: "서울" },
    indoor_outdoor: "outdoor",
    target_audience: ["young_adult", "local_resident"],
    target_attendance: 500,
    ticket_type: "free",
    budget_max_krw: 10000000,
    fixed_constraints: ["행사 날짜 변경 불가"],
    other_notes: "우천 대체 공간을 아직 정하지 못했습니다.",
  };
  record.details = {
    ...EMPTY_DETAILS,
    team_size: 2,
    decision_makers: 2,
    experience_level: "one_or_two",
    decision_deadline: "2026-09-20",
    recommendation_goals: ["예산 배분", "운영", "위험 점검"],
    detail_level: "standard",
    main_concern: "적은 인력과 예산으로 우천에 대응하는 방법",
    event_summary: "지역 청년과 인디 음악가를 연결하는 하루 야외 행사",
    event_frequency: "new",
    event_format: "offline",
    access_type: "public",
    success_metric: "사전등록 대비 실제 방문과 만족도",
    minimum_success_attendance: 300,
    maximum_concurrent_attendance: 350,
    audience_interests: "인디 음악, 지역 커뮤니티, 청년 창작",
    visit_motivation: "가까운 곳에서 새로운 음악가와 셀러를 만나는 경험",
    dropout_reason: "비, 프로그램 정보 부족, 긴 대기",
    expected_stay_hours: 2.5,
    required_languages: ["한국어"],
    audience_accessibility_needs: "무단차 입장과 휴게 좌석",
    daily_hours: "14:00~21:00",
    setup_rehearsal_teardown: "당일 오전 설치·리허설, 23시 철거 완료",
    rain_or_weather_fallback: "100명 규모 실내 대체 공간 후보 필요",
    preferred_daytime: "evening",
    competing_event_tolerance: "some",
    venue_type: "야외광장",
    seating_mode: "mixed",
    parking_spaces: 30,
    transit_plan: "지하철 도보 경로 중심 안내",
    facility_plan: "간이 휴게석과 응급 키트",
    program_outline: "인디 공연 4팀, 지역 청년 셀러 부스",
    performer_partner_plan: "인디 4팀 섭외 후보, 지역 셀러 10팀",
    program_priority: "공연 4팀과 음향 품질 우선",
    ticket_sales_channels: "무료 사전등록 폼",
    budget_breakdown: "출연·음향 45%, 대관·시설 25%, 운영·안전 15%, 홍보 5%, 예비비 10%",
    secured_budget_krw: 7000000,
    marketing_channels: ["인스타그램", "지역 커뮤니티"],
    marketing_start_date: "2026-09-10",
    marketing_budget_krw: 500000,
    marketing_kpi: "사전등록 600명과 방문 전환율",
    operation_plan: "기획자 2명이 안내와 무대 진행을 나눠 담당",
    staff_count: 8,
    queue_plan: "QR 사전등록과 현장 대기줄 분리",
    technical_fallback: "QR 장애 시 이름·전화번호 없이 등록번호 수기 확인",
    transport_accommodation_plan: "막차 전 종료, 출연진 이동은 개별 협의",
    local_partnership_plan: "인근 카페와 포스터·할인 협업",
    safety_plan: "우천 대체 공간과 응급 연락망 미정",
    permits_and_insurance: "장소 사용 승인과 행사 보험 견적 필요",
    cancellation_rule: "행사 48시간 전 기상예보로 1차 결정",
    accessibility_plan: "무단차 입장과 휴게 좌석 확인 필요",
    sustainability_plan: "종이 인쇄 최소화와 분리배출",
    flexible_options: "셀러 부스 수와 홍보비",
    priority_criteria: ["안전", "비용", "실행 난이도"],
    risk_tolerance: "low",
    requested_alternatives: 2,
    requested_decisions: "우천 대체 공간과 최소 운영 인원 결정",
  };
  return record;
}

export function readDrafts(): DraftRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.map(normalizeDraft).filter(Boolean) as DraftRecord[] : [];
  } catch {
    return [];
  }
}

function normalizeDraft(value: unknown): DraftRecord | null {
  if (!value || typeof value !== "object") return null;
  const draft = value as Partial<DraftRecord>;
  if (!draft.id || !draft.event) return null;
  return {
    ...draft,
    version: draft.version ?? (draft.analysis ? 1 : 0),
    details: { ...EMPTY_DETAILS, ...(draft.details ?? {}) },
    history: Array.isArray(draft.history) ? draft.history : [],
  } as DraftRecord;
}

export function findDraft(id: string): DraftRecord | undefined {
  return readDrafts().find((draft) => draft.id === id);
}

export function saveDraft(draft: DraftRecord): DraftRecord {
  const updated = { ...draft, updated_at: new Date().toISOString() };
  const drafts = readDrafts();
  const index = drafts.findIndex((item) => item.id === draft.id);
  if (index >= 0) drafts[index] = updated;
  else drafts.unshift(updated);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
  return updated;
}

export function removeDraft(id: string): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(readDrafts().filter((draft) => draft.id !== id)));
}

export function duplicateDraft(source: DraftRecord): DraftRecord {
  const now = new Date().toISOString();
  const clone: DraftRecord = {
    ...structuredClone(source),
    id: crypto.randomUUID(),
    created_at: now,
    updated_at: now,
    status: "draft",
    current_step: 0,
    version: source.version,
    event: {
      ...structuredClone(source.event),
      event_id: createEventId(),
      working_title: `${source.event.working_title || "이름 없는 기획"} 복사본`,
    },
    analysis: undefined,
    recommendation: undefined,
    recommendation_meta: undefined,
    history: [],
  };
  return saveDraft(clone);
}

export function cleanEventForApi(event: EventDraft): EventDraft {
  const copy = structuredClone(event);
  if (copy.schedule_selection_mode !== "fixed") {
    delete copy.start_date;
    delete copy.end_date;
  }
  if (copy.schedule_selection_mode !== "candidates") delete copy.date_candidates;
  if (copy.region_selection_mode !== "fixed") delete copy.region;
  if (copy.region_selection_mode !== "candidates") delete copy.region_candidates;
  if (!copy.venue?.name) delete copy.venue;
  if (!copy.event_type_other) delete copy.event_type_other;
  if (!copy.purpose_other) delete copy.purpose_other;
  if (!copy.target_audience_other) delete copy.target_audience_other;
  if (!copy.working_title) delete copy.working_title;
  if (!copy.other_notes) delete copy.other_notes;
  return copy;
}
