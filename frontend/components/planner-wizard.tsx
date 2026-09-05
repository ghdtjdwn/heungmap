"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { AppHeader } from "./app-header";
import { analyzePlanner, ApiError, generatePlannerRecommendation, searchAddresses, searchVenues } from "@/lib/api";
import { cleanEventForApi, duplicateDraft, emptyDraft, findDraft, sampleDraft, saveDraft } from "@/lib/drafts";
import {
  AUDIENCES, EVENT_TYPES, MARKETING_CHANNELS, PLANNER_TYPES, PLANNING_STAGES,
  PURPOSES, REGIONS, audienceLabel, optionLabel, regionFromCode,
} from "@/lib/options";
import { buildPlanningContext } from "@/lib/planning-context";
import { buildRuleFallbackRecommendation, validateStructuredRecommendation } from "@/lib/recommendation";
import type {
  AddressSearchItem,
  DraftRecord,
  EventDraft,
  PlanningDetails,
  PlannerAnalysisRequest,
  RegionRef,
  Venue,
  VenueSearchItem,
} from "@/lib/types";

const STEP_TITLES = [
  "기획 상태", "행사 목표", "이용객·티켓", "일정·지역", "장소·규모", "실행 계획", "검토·분석",
];

const scheduleLabels = { fixed: "날짜 확정", candidates: "후보 날짜 비교", recommend: "추천받기", unknown: "아직 모름" };
const regionLabels = { fixed: "지역 확정", candidates: "후보 지역 비교", recommend: "추천받기", unknown: "아직 모름" };
const RECOMMENDATION_GOALS = ["아이디어", "타당성 검증", "수요 예측", "장소 비교", "예산 배분", "홍보", "운영", "위험 점검", "전체 기획"];
const LANGUAGE_OPTIONS = ["한국어", "영어", "중국어", "일본어", "쉬운 안내"];
const PRIORITY_OPTIONS = ["흥행", "수익", "안전", "지역효과", "만족도", "접근성", "홍보", "지속가능성", "비용", "실행 난이도"];

function numericValue(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatSaved(value: string | null) {
  if (!value) return "저장 대기";
  return `${new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit" }).format(new Date(value))} 저장됨`;
}

export function PlannerWizard() {
  const router = useRouter();
  const [draft, setDraft] = useState<DraftRecord | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionPhase, setSubmissionPhase] = useState("");
  const [canCancelLlm, setCanCancelLlm] = useState(false);
  const [venueMatches, setVenueMatches] = useState<VenueSearchItem[]>([]);
  const [addressMatches, setAddressMatches] = useState<AddressSearchItem[]>([]);
  const [venueSearchMessage, setVenueSearchMessage] = useState("");
  const [addressSearchMessage, setAddressSearchMessage] = useState("");
  const [searchingVenue, setSearchingVenue] = useState(false);
  const [searchingAddress, setSearchingAddress] = useState(false);
  const hydrated = useRef(false);
  const llmAbort = useRef<AbortController | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const params = new URLSearchParams(window.location.search);
      const draftId = params.get("draft");
      const sample = params.get("sample");
      let initial = draftId ? findDraft(draftId) : undefined;
      if (!initial && (sample === "large" || sample === "independent")) initial = sampleDraft(sample);
      if (!initial) initial = emptyDraft();
      const stored = saveDraft(initial);
      setDraft(stored);
      setStep(Math.min(stored.current_step, 6));
      setSavedAt(stored.updated_at);
      window.history.replaceState(null, "", `/planner/new?draft=${stored.id}`);
      hydrated.current = true;
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!draft || !hydrated.current) return;
    const timer = window.setTimeout(() => {
      const stored = saveDraft({ ...draft, current_step: step, status: draft.analysis ? "analyzed" : "draft" });
      setSavedAt(stored.updated_at);
    }, 450);
    return () => window.clearTimeout(timer);
  }, [draft, step]);

  const completion = useMemo(() => Math.round(((step + 1) / STEP_TITLES.length) * 100), [step]);

  if (!draft) {
    return <main className="page-shell"><AppHeader detail="기획 불러오는 중" /><section className="panel loading-panel">저장한 입력을 불러오고 있습니다.</section></main>;
  }

  const currentDraft = draft;
  const event = currentDraft.event;
  const details = currentDraft.details;

  function updateEvent<K extends keyof EventDraft>(key: K, value: EventDraft[K]) {
    setDraft((current) => current ? { ...current, event: { ...current.event, [key]: value } } : current);
  }

  function updateDetails<K extends keyof PlanningDetails>(key: K, value: PlanningDetails[K]) {
    setDraft((current) => current ? { ...current, details: { ...current.details, [key]: value } } : current);
  }

  function updateVenue(key: keyof Venue, value: Venue[keyof Venue]) {
    const venue = { ...(event.venue ?? { name: "" }), [key]: value };
    updateEvent("venue", venue);
  }

  function updateCoordinate(axis: "latitude" | "longitude", rawValue: string) {
    const value = numericValue(rawValue);
    const current = event.venue?.coordinates;
    const otherAxis = axis === "latitude" ? "longitude" : "latitude";
    const otherValue = current?.[otherAxis];
    if (value === undefined && !Number.isFinite(otherValue)) {
      updateVenue("coordinates", undefined);
      return;
    }
    updateVenue("coordinates", {
      latitude: axis === "latitude" ? value ?? Number.NaN : current?.latitude ?? Number.NaN,
      longitude: axis === "longitude" ? value ?? Number.NaN : current?.longitude ?? Number.NaN,
    });
  }

  async function runVenueSearch() {
    const keyword = event.venue?.name.trim() ?? "";
    if (keyword.length < 2) {
      setVenueSearchMessage("장소명을 두 글자 이상 입력해 주세요.");
      return;
    }
    setSearchingVenue(true);
    setVenueSearchMessage("");
    setVenueMatches([]);
    try {
      const areaCode = event.region?.area_code || event.region_candidates?.[0]?.area_code;
      const result = await searchVenues(keyword, areaCode);
      setVenueMatches(result.items);
      setVenueSearchMessage(result.items.length ? `${result.items.length}개 후보를 찾았습니다.` : "일치하는 관광정보가 없습니다. 직접 입력해 주세요.");
    } catch (searchError) {
      setVenueSearchMessage(searchError instanceof ApiError ? searchError.message : "장소 검색을 사용할 수 없습니다. 직접 입력해 주세요.");
    } finally {
      setSearchingVenue(false);
    }
  }

  function chooseVenue(item: VenueSearchItem) {
    const sameVenue = event.venue?.venue_id === item.venue.venue_id;
    updateEvent("venue", {
      ...item.venue,
      capacity: sameVenue ? event.venue?.capacity : undefined,
      indoor_outdoor: event.venue?.indoor_outdoor,
      accessibility_summary: event.venue?.accessibility_summary,
    });
    updateDetails("venue_search_source", item.source);
    if (!details.venue_type && item.category) updateDetails("venue_type", item.category);
    setVenueMatches([]);
    setVenueSearchMessage("관광정보에서 장소명·주소·좌표를 입력했습니다. 공식 수용인원은 별도 확인해 주세요.");
  }

  async function runAddressSearch() {
    const query = event.venue?.address?.trim() ?? "";
    if (query.length < 2) {
      setAddressSearchMessage("도로명이나 지번 주소를 두 글자 이상 입력해 주세요.");
      return;
    }
    setSearchingAddress(true);
    setAddressSearchMessage("");
    setAddressMatches([]);
    try {
      const result = await searchAddresses(query);
      setAddressMatches(result.items);
      setAddressSearchMessage(result.items.length ? `${result.items.length}개 주소를 찾았습니다.` : "일치하는 주소가 없습니다. 직접 입력해 주세요.");
    } catch (searchError) {
      setAddressSearchMessage(searchError instanceof ApiError ? searchError.message : "주소 검색을 사용할 수 없습니다. 직접 입력해 주세요.");
    } finally {
      setSearchingAddress(false);
    }
  }

  function chooseAddress(item: AddressSearchItem) {
    updateEvent("venue", {
      ...(event.venue ?? { name: item.building_name || item.address_name }),
      name: event.venue?.name.trim() || item.building_name || item.address_name,
      address: item.address_name,
      coordinates: item.coordinates,
    });
    updateDetails("address_search_source", item.source);
    setAddressMatches([]);
    setAddressSearchMessage("주소와 좌표를 입력했습니다.");
  }

  function setRegion(mode: "fixed" | "candidate", code: string, index = 0) {
    const region = regionFromCode(code);
    if (mode === "fixed") {
      updateEvent("region", region);
      return;
    }
    const candidates = [...(event.region_candidates ?? [{ area_code: "", display_name: "" }, { area_code: "", display_name: "" }])];
    candidates[index] = region ?? { area_code: "", display_name: "" };
    updateEvent("region_candidates", candidates);
  }

  function toggleAudience(value: string) {
    updateEvent("target_audience", event.target_audience.includes(value)
      ? event.target_audience.filter((item) => item !== value)
      : [...event.target_audience, value]);
  }

  function toggleChannel(value: string) {
    updateDetails("marketing_channels", details.marketing_channels.includes(value)
      ? details.marketing_channels.filter((item) => item !== value)
      : [...details.marketing_channels, value]);
  }

  function toggleDetailList(key: "recommendation_goals" | "required_languages" | "priority_criteria", value: string) {
    const values = details[key];
    updateDetails(key, values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  }

  function validate(targetStep: number): string {
    if (targetStep === 0) {
      if (!event.planner_type) return "기획자 유형을 선택해 주세요.";
      if (!event.planning_stage) return "현재 기획 단계를 선택해 주세요.";
    }
    if (targetStep === 1) {
      if (!event.event_type) return "행사 유형을 선택해 주세요.";
      if (event.event_type === "other" && !event.event_type_other?.trim()) return "기타 행사 유형을 입력해 주세요.";
      if (!event.purpose) return "행사 목적을 선택해 주세요.";
      if (event.purpose === "other" && !event.purpose_other?.trim()) return "기타 목적을 입력해 주세요.";
      if (event.theme_keywords.length === 0) return "테마 키워드를 하나 이상 입력해 주세요.";
    }
    if (targetStep === 2) {
      if (event.target_audience.length === 0) return "목표 이용객을 하나 이상 선택해 주세요.";
      if (event.target_audience.includes("other") && !event.target_audience_other?.trim()) return "기타 목표 이용객을 입력해 주세요.";
      if (details.minimum_success_attendance !== undefined && event.target_attendance !== undefined && details.minimum_success_attendance > event.target_attendance) return "최소 성공 인원은 목표 인원보다 클 수 없습니다.";
      if (details.ticket_price_min_krw !== undefined && details.ticket_price_max_krw !== undefined && details.ticket_price_max_krw < details.ticket_price_min_krw) return "최대 티켓 가격은 최소 가격보다 작을 수 없습니다.";
    }
    if (targetStep === 3) {
      if (event.schedule_selection_mode === "fixed") {
        if (!event.start_date || !event.end_date) return "확정 일정의 시작일과 종료일을 입력해 주세요.";
        if (event.end_date < event.start_date) return "종료일은 시작일보다 빠를 수 없습니다.";
      }
      if (event.schedule_selection_mode === "candidates") {
        if (!event.date_candidates || event.date_candidates.length < 2 || event.date_candidates.some((item) => !item.start_date || !item.end_date)) return "날짜 후보 두 개를 모두 입력해 주세요.";
        if (event.date_candidates.some((item) => item.end_date < item.start_date)) return "후보 종료일은 시작일보다 빠를 수 없습니다.";
      }
      if (event.region_selection_mode === "fixed" && !event.region?.area_code) return "확정 지역을 선택해 주세요.";
      if (event.region_selection_mode === "candidates" && (!event.region_candidates || event.region_candidates.length < 2 || event.region_candidates.some((item) => !item.area_code))) return "지역 후보 두 개를 선택해 주세요.";
      if (event.region_candidates && new Set(event.region_candidates.map((item) => item.area_code)).size !== event.region_candidates.length) return "서로 다른 지역 후보를 선택해 주세요.";
    }
    if (targetStep === 4) {
      if (event.venue?.capacity && event.venue.capacity < 1) return "장소 수용인원은 1명 이상이어야 합니다.";
      const coordinates = event.venue?.coordinates;
      if (coordinates && (!Number.isFinite(coordinates.latitude) || !Number.isFinite(coordinates.longitude))) return "위도와 경도를 모두 숫자로 입력해 주세요.";
    }
    if (targetStep === 5) {
      if (event.budget_min_krw !== undefined && event.budget_max_krw !== undefined && event.budget_max_krw < event.budget_min_krw) return "최대 예산은 최소 예산보다 작을 수 없습니다.";
      if (details.secured_budget_krw !== undefined && event.budget_max_krw !== undefined && details.secured_budget_krw > event.budget_max_krw) return "확보 예산은 입력한 최대 총예산보다 클 수 없습니다.";
    }
    return "";
  }

  function nextStep() {
    const message = validate(step);
    if (message) { setError(message); return; }
    setError("");
    setStep((value) => Math.min(6, value + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function previousStep() {
    setError("");
    setStep((value) => Math.max(0, value - 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function makeCopy() {
    const copy = duplicateDraft(currentDraft);
    setDraft(copy);
    setStep(0);
    setSavedAt(copy.updated_at);
    router.push(`/planner/new?draft=${copy.id}`);
  }

  async function submitAnalysis() {
    for (let index = 0; index < 6; index += 1) {
      const message = validate(index);
      if (message) { setStep(index); setError(message); return; }
    }
    setSubmitting(true);
    setSubmissionPhase("데이터 분석 중");
    setError("");
    const request: PlannerAnalysisRequest = {
      contract_version: "0.1.0",
      client_request_id: crypto.randomUUID(),
      event_draft: cleanEventForApi(event),
      requested_outputs: ["prediction", "nearby_places", "rule_recommendations"],
    };
    try {
      const analysis = await analyzePlanner(request);
      const nextVersion = currentDraft.version + 1;
      const analyzedDraft: DraftRecord = {
        ...currentDraft,
        status: "analyzed",
        current_step: 6,
        version: nextVersion,
        analysis,
        history: [
          ...currentDraft.history,
          {
            version: nextVersion,
            created_at: analysis.meta.generated_at,
            summary: `${event.target_attendance?.toLocaleString("ko-KR") || "목표 미정"}명 · ${event.region?.display_name || "지역 미정"} · 최대 ${event.budget_max_krw?.toLocaleString("ko-KR") || "예산 미정"}원`,
            event: structuredClone(event),
            details: structuredClone(details),
            analysis_id: analysis.analysis_id,
          },
        ].slice(-20),
      };
      const planningContext = buildPlanningContext(analyzedDraft, analysis);
      let recommendation = buildRuleFallbackRecommendation(analyzedDraft, analysis, planningContext);
      let recommendationMeta: DraftRecord["recommendation_meta"] = {
        contract_version: "0.1.0",
        generated_at: recommendation.generated_at,
        request_id: crypto.randomUUID(),
        provider: "local_rules",
        model: "planner-rule-fallback-1.0",
        prompt_version: "planner-recommendation-1.0",
        is_fallback: true,
        warning: "실제 LLM을 사용할 수 없어 규칙 보고서로 생성했습니다.",
      };
      try {
        setSubmissionPhase("로컬 AI 보고서 작성 중");
        llmAbort.current = new AbortController();
        setCanCancelLlm(true);
        const generated = await generatePlannerRecommendation({
          contract_version: "0.1.0",
          client_request_id: crypto.randomUUID(),
          analysis_id: analysis.analysis_id,
          planning_context: planningContext,
          rule_recommendations: analysis.rule_recommendations,
          requested_alternatives: Math.min(5, Math.max(1, details.requested_alternatives)),
        }, llmAbort.current.signal);
        setSubmissionPhase("결과 검증 중");
        const validation = validateStructuredRecommendation(generated.recommendation);
        if (!validation.valid) throw new ApiError(`LLM 결과 계약 검증 실패: ${validation.errors.join(" ")}`);
        recommendation = generated.recommendation;
        recommendationMeta = { ...generated.meta, is_fallback: false };
      } catch (recommendationError) {
        recommendationMeta.warning = recommendationError instanceof ApiError
          ? `${recommendationError.message} 규칙 보고서로 안전하게 전환했습니다.`
          : "LLM 결과를 사용할 수 없어 규칙 보고서로 안전하게 전환했습니다.";
      }
      llmAbort.current = null;
      setCanCancelLlm(false);
      saveDraft({ ...analyzedDraft, recommendation, recommendation_meta: recommendationMeta });
      router.push(`/planner/result?draft=${currentDraft.id}`);
    } catch (caught) {
      const apiError = caught as ApiError;
      const fields = apiError.problem?.field_errors?.map((item) => item.message).join(" ");
      setError(fields || apiError.message);
      setSubmitting(false);
      setSubmissionPhase("");
      setCanCancelLlm(false);
    }
  }

  function cancelLlm() {
    llmAbort.current?.abort();
    setSubmissionPhase("취소 처리 중 · 분석 결과 보존");
  }

  return (
    <main className="page-shell wizard-shell">
      <AppHeader detail={event.working_title || "새 기획"} />
      <div className="wizard-layout">
        <aside className="wizard-sidebar" aria-label="입력 단계">
          <Link href="/planner" className="back-link">← 내 기획</Link>
          <div className="save-status"><span className="save-dot" />{formatSaved(savedAt)}</div>
          <ol>
            {STEP_TITLES.map((title, index) => (
              <li key={title} className={index === step ? "active" : index < step ? "done" : ""}>
                <button type="button" onClick={() => index <= step && setStep(index)} disabled={index > step}>
                  <span>{index < step ? "✓" : index + 1}</span>{title}
                </button>
              </li>
            ))}
          </ol>
          <p className="sidebar-note">입력은 로그인 계정이나 서버가 아닌 현재 브라우저에만 저장됩니다.</p>
        </aside>

        <section className="wizard-main">
          <div className="mobile-progress"><span>{step + 1} / 7 · {STEP_TITLES[step]}</span><strong>{completion}%</strong></div>
          <div className="progress-track"><span style={{ width: `${completion}%` }} /></div>

          <div className="form-heading">
            <div><p className="eyebrow">STEP {step + 1}</p><h1>{STEP_TITLES[step]}</h1></div>
            <button type="button" className="text-button" onClick={makeCopy}>복사본 만들기</button>
          </div>

          {step === 0 && (
            <div className="form-stack">
              <FormBlock title="누가 기획하고 있나요?" description="상황에 따라 결과의 우선순위를 다르게 제시합니다.">
                <Field label="기획자 유형" required>
                  <select value={event.planner_type} onChange={(e) => updateEvent("planner_type", e.target.value as EventDraft["planner_type"])}>
                    <option value="">선택해 주세요</option>{PLANNER_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                  </select>
                </Field>
                <Field label="현재 단계" required>
                  <select value={event.planning_stage} onChange={(e) => updateEvent("planning_stage", e.target.value as EventDraft["planning_stage"])}>
                    <option value="">선택해 주세요</option>{PLANNING_STAGES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                  </select>
                </Field>
                <Field label="행사명 또는 임시 이름" hint="선택">
                  <input value={event.working_title ?? ""} maxLength={200} onChange={(e) => updateEvent("working_title", e.target.value)} placeholder="예: 가을 청년 음악축제" />
                </Field>
              </FormBlock>
              <FormBlock title="어떤 수준의 도움이 필요한가요?" description="팀 상황과 결정해야 할 내용을 결과 보고서에 반영합니다.">
                <Field label="팀 규모" hint="선택" suffix="명"><input type="number" min="1" value={details.team_size ?? ""} onChange={(e) => updateDetails("team_size", numericValue(e.target.value))} /></Field>
                <Field label="의사결정자" hint="선택" suffix="명"><input type="number" min="1" value={details.decision_makers ?? ""} onChange={(e) => updateDetails("decision_makers", numericValue(e.target.value))} /></Field>
                <Field label="관련 행사 경험"><select value={details.experience_level} onChange={(e) => updateDetails("experience_level", e.target.value as PlanningDetails["experience_level"])}><option value="unknown">아직 모름</option><option value="none">없음</option><option value="one_or_two">1~2회</option><option value="three_to_five">3~5회</option><option value="six_plus">6회 이상</option></select></Field>
                <Field label="최종 결정 기한" hint="선택"><input type="date" value={details.decision_deadline} onChange={(e) => updateDetails("decision_deadline", e.target.value)} /></Field>
                <Field label="결과 상세 수준"><select value={details.detail_level} onChange={(e) => updateDetails("detail_level", e.target.value as PlanningDetails["detail_level"])}><option value="quick">빠른 진단</option><option value="standard">표준 기획안</option><option value="detailed">상세 실행안</option></select></Field>
                <Field label="가장 큰 걱정" hint="선택"><input value={details.main_concern} onChange={(e) => updateDetails("main_concern", e.target.value)} placeholder="예: 우천과 적은 운영 인력" /></Field>
                <Field label="추천받을 목적" hint="복수 선택" full group><div className="choice-grid compact-choices">{RECOMMENDATION_GOALS.map((goal) => <label className={`check-card ${details.recommendation_goals.includes(goal) ? "selected" : ""}`} key={goal}><input type="checkbox" checked={details.recommendation_goals.includes(goal)} onChange={() => toggleDetailList("recommendation_goals", goal)} />{goal}</label>)}</div></Field>
              </FormBlock>
            </div>
          )}

          {step === 1 && (
            <div className="form-stack">
              <FormBlock title="무엇을 위한 행사인가요?" description="테마는 쉼표로 나눠 최대 20개까지 입력할 수 있습니다.">
                <Field label="행사 유형" required>
                  <select value={event.event_type} onChange={(e) => updateEvent("event_type", e.target.value as EventDraft["event_type"])}>
                    <option value="">선택해 주세요</option>{EVENT_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                  </select>
                </Field>
                {event.event_type === "other" && <Field label="기타 행사 유형" required><input value={event.event_type_other ?? ""} onChange={(e) => updateEvent("event_type_other", e.target.value)} /></Field>}
                <Field label="핵심 목적" required>
                  <select value={event.purpose} onChange={(e) => updateEvent("purpose", e.target.value as EventDraft["purpose"])}>
                    <option value="">선택해 주세요</option>{PURPOSES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                  </select>
                </Field>
                {event.purpose === "other" && <Field label="기타 목적" required><input value={event.purpose_other ?? ""} onChange={(e) => updateEvent("purpose_other", e.target.value)} /></Field>}
                <Field label="테마 키워드" required hint={`${event.theme_keywords.length}/20`}>
                  <input value={event.theme_keywords.join(", ")} onChange={(e) => updateEvent("theme_keywords", e.target.value.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 20))} placeholder="예: 지역문화, 바다, 가족" />
                </Field>
                <Field label="행사 한 줄 설명" hint="선택" full><input value={details.event_summary} onChange={(e) => updateDetails("event_summary", e.target.value)} placeholder="누구에게 어떤 경험을 제공하는 행사인지 적어주세요." /></Field>
                <Field label="개최 형태"><select value={details.event_frequency} onChange={(e) => updateDetails("event_frequency", e.target.value as PlanningDetails["event_frequency"])}><option value="unknown">아직 모름</option><option value="new">신규</option><option value="repeat">반복 개최</option><option value="annual">연례 행사</option></select></Field>
                <Field label="진행 방식"><select value={details.event_format} onChange={(e) => updateDetails("event_format", e.target.value as PlanningDetails["event_format"])}><option value="unknown">아직 모름</option><option value="offline">오프라인</option><option value="online">온라인</option><option value="hybrid">온·오프라인 혼합</option></select></Field>
                <Field label="공개 범위"><select value={details.access_type} onChange={(e) => updateDetails("access_type", e.target.value as PlanningDetails["access_type"])}><option value="unknown">아직 모름</option><option value="public">공개 행사</option><option value="invite">초대 행사</option><option value="members">회원 전용</option></select></Field>
                <Field label="성공 판단 기준" hint="선택"><input value={details.success_metric} onChange={(e) => updateDetails("success_metric", e.target.value)} placeholder="예: 실제 방문 500명과 만족도 80%" /></Field>
              </FormBlock>
            </div>
          )}

          {step === 2 && (
            <div className="form-stack">
              <FormBlock title="누가 얼마나 방문하길 바라나요?" description="개인을 식별하는 정보가 아니라 기획 목표만 입력합니다.">
                <Field label="목표 이용객" required full group>
                  <div className="choice-grid">{AUDIENCES.map(([value, label]) => <label className={`check-card ${event.target_audience.includes(value) ? "selected" : ""}`} key={value}><input type="checkbox" checked={event.target_audience.includes(value)} onChange={() => toggleAudience(value)} />{label}</label>)}</div>
                </Field>
                {event.target_audience.includes("other") && <Field label="기타 목표 이용객" required><input value={event.target_audience_other ?? ""} onChange={(e) => updateEvent("target_audience_other", e.target.value)} /></Field>}
                <Field label="티켓 방식" required>
                  <select value={event.ticket_type} onChange={(e) => updateEvent("ticket_type", e.target.value as EventDraft["ticket_type"])}>
                    <option value="undecided">아직 모름</option><option value="free">무료</option><option value="paid">유료</option><option value="mixed">부분 유료</option>
                  </select>
                </Field>
                <Field label="목표 인원" hint="선택·예측값 아님" suffix="명">
                  <input type="number" min="1" inputMode="numeric" value={event.target_attendance ?? ""} onChange={(e) => updateEvent("target_attendance", numericValue(e.target.value))} placeholder="예: 500" />
                </Field>
                <Field label="최소 성공 인원" hint="선택" suffix="명"><input type="number" min="1" value={details.minimum_success_attendance ?? ""} onChange={(e) => updateDetails("minimum_success_attendance", numericValue(e.target.value))} /></Field>
                <Field label="최대 동시 체류" hint="선택" suffix="명"><input type="number" min="1" value={details.maximum_concurrent_attendance ?? ""} onChange={(e) => updateDetails("maximum_concurrent_attendance", numericValue(e.target.value))} /></Field>
                <Field label="관심사" hint="선택"><input value={details.audience_interests} onChange={(e) => updateDetails("audience_interests", e.target.value)} placeholder="예: 인디 음악, 지역 먹거리" /></Field>
                <Field label="방문 결정 이유" hint="선택"><input value={details.visit_motivation} onChange={(e) => updateDetails("visit_motivation", e.target.value)} /></Field>
                <Field label="방문 포기 이유" hint="선택"><input value={details.dropout_reason} onChange={(e) => updateDetails("dropout_reason", e.target.value)} /></Field>
                <Field label="예상 체류시간" hint="선택" suffix="시간"><input type="number" min="0" step="0.5" value={details.expected_stay_hours ?? ""} onChange={(e) => updateDetails("expected_stay_hours", numericValue(e.target.value))} /></Field>
                <Field label="필요 언어·안내" hint="복수 선택" full group><div className="choice-grid compact-choices">{LANGUAGE_OPTIONS.map((language) => <label className={`check-card ${details.required_languages.includes(language) ? "selected" : ""}`} key={language}><input type="checkbox" checked={details.required_languages.includes(language)} onChange={() => toggleDetailList("required_languages", language)} />{language}</label>)}</div></Field>
                <Field label="이용객 접근성 요구" hint="선택" full><textarea rows={2} value={details.audience_accessibility_needs} onChange={(e) => updateDetails("audience_accessibility_needs", e.target.value)} placeholder="휠체어, 유모차, 수어, 휴게 공간 등" /></Field>
              </FormBlock>
              {(event.ticket_type === "paid" || event.ticket_type === "mixed") && <FormBlock title="유료 티켓 조건" description="가격을 모르면 비워두고 결과에서 확인 순서를 받습니다.">
                <Field label="최소 가격" hint="선택" suffix="원"><input type="number" min="0" value={details.ticket_price_min_krw ?? ""} onChange={(e) => updateDetails("ticket_price_min_krw", numericValue(e.target.value))} /></Field>
                <Field label="최대 가격" hint="선택" suffix="원"><input type="number" min="0" value={details.ticket_price_max_krw ?? ""} onChange={(e) => updateDetails("ticket_price_max_krw", numericValue(e.target.value))} /></Field>
                <Field label="목표 판매량" hint="선택" suffix="장"><input type="number" min="1" value={details.ticket_sales_target ?? ""} onChange={(e) => updateDetails("ticket_sales_target", numericValue(e.target.value))} /></Field>
                <Field label="예매 채널" hint="선택"><input value={details.ticket_sales_channels} onChange={(e) => updateDetails("ticket_sales_channels", e.target.value)} /></Field>
                <Field label="취소·환불·양도 정책" hint="선택" full><textarea rows={2} value={details.refund_policy} onChange={(e) => updateDetails("refund_policy", e.target.value)} /></Field>
              </FormBlock>}
            </div>
          )}

          {step === 3 && (
            <div className="form-stack">
              <FormBlock title="언제 열 계획인가요?" description="모르는 상태로도 진행할 수 있으며 필요한 확인 항목을 결과에 표시합니다.">
                <Field label="일정 상태" required>
                  <select value={event.schedule_selection_mode} onChange={(e) => {
                    const mode = e.target.value as EventDraft["schedule_selection_mode"];
                    updateEvent("schedule_selection_mode", mode);
                    if (mode === "candidates" && !event.date_candidates) updateEvent("date_candidates", [{ start_date: "", end_date: "" }, { start_date: "", end_date: "" }]);
                  }}>{Object.entries(scheduleLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
                </Field>
                {event.schedule_selection_mode === "fixed" && <DatePair label="확정 일정" value={{ start_date: event.start_date ?? "", end_date: event.end_date ?? "" }} onChange={(value) => { updateEvent("start_date", value.start_date); updateEvent("end_date", value.end_date); }} />}
                {event.schedule_selection_mode === "candidates" && (event.date_candidates ?? []).map((candidate, index) => <DatePair key={index} label={`후보 ${index + 1}`} value={candidate} onChange={(value) => { const candidates = [...(event.date_candidates ?? [])]; candidates[index] = value; updateEvent("date_candidates", candidates); }} />)}
              </FormBlock>
              <FormBlock title="어느 지역에서 열 계획인가요?" description="지역 코드는 TourAPI 근거 조회에 사용합니다.">
                <Field label="지역 상태" required>
                  <select value={event.region_selection_mode} onChange={(e) => {
                    const mode = e.target.value as EventDraft["region_selection_mode"];
                    updateEvent("region_selection_mode", mode);
                    if (mode === "candidates" && !event.region_candidates) updateEvent("region_candidates", [{ area_code: "", display_name: "" }, { area_code: "", display_name: "" }]);
                  }}>{Object.entries(regionLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
                </Field>
                {event.region_selection_mode === "fixed" && <Field label="확정 지역" required><RegionSelect value={event.region?.area_code ?? ""} onChange={(value) => setRegion("fixed", value)} /></Field>}
                {event.region_selection_mode === "candidates" && (event.region_candidates ?? []).map((candidate, index) => <Field label={`지역 후보 ${index + 1}`} required key={index}><RegionSelect value={candidate.area_code} onChange={(value) => setRegion("candidate", value, index)} /></Field>)}
              </FormBlock>
              <FormBlock title="운영 시간과 일정 제약" description="추천이 실제 준비 일정과 기상 위험을 놓치지 않게 합니다.">
                <Field label="일별 운영 시간" hint="선택"><input value={details.daily_hours} onChange={(e) => updateDetails("daily_hours", e.target.value)} placeholder="예: 14:00~21:00" /></Field>
                <Field label="선호 시간대"><select value={details.preferred_daytime} onChange={(e) => updateDetails("preferred_daytime", e.target.value as PlanningDetails["preferred_daytime"])}><option value="unknown">아직 모름</option><option value="day">낮</option><option value="evening">저녁</option><option value="late_night">심야</option><option value="flexible">상관없음</option></select></Field>
                <Field label="경쟁 행사 허용"><select value={details.competing_event_tolerance} onChange={(e) => updateDetails("competing_event_tolerance", e.target.value as PlanningDetails["competing_event_tolerance"])}><option value="unknown">아직 모름</option><option value="avoid">가능하면 피하기</option><option value="some">일부 허용</option><option value="acceptable">상관없음</option></select></Field>
                <Field label="설치·리허설·철거" hint="선택" full><textarea rows={2} value={details.setup_rehearsal_teardown} onChange={(e) => updateDetails("setup_rehearsal_teardown", e.target.value)} /></Field>
                <Field label="우천·기상 대체안" hint="실외·혼합이면 권장" full><textarea rows={3} value={details.rain_or_weather_fallback} onChange={(e) => updateDetails("rain_or_weather_fallback", e.target.value)} placeholder="대체 공간, 연기 가능 여부, 결정 시점을 적어주세요." /></Field>
              </FormBlock>
            </div>
          )}

          {step === 4 && (
            <div className="form-stack">
              <FormBlock title="장소가 정해졌나요?" description="정해졌다면 검색해 자동 입력하세요. 아직이면 비워두어도 분석 결과에서 필요한 규모·접근성·시설 조건과 후보 확인 순서를 추천합니다.">
                <Field label="장소명" hint="선택·TourAPI 검색" full group help="비워두면 목표 인원과 운영 조건을 기준으로 장소 선택 기준을 추천합니다.">
                  <div className="search-control"><input aria-label="장소명" value={event.venue?.name ?? ""} onChange={(e) => { updateVenue("name", e.target.value); updateDetails("venue_search_source", undefined); setVenueMatches([]); setVenueSearchMessage(""); }} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void runVenueSearch(); } }} placeholder="예: 서울문화비축기지" /><button type="button" className="button secondary" onClick={() => void runVenueSearch()} disabled={searchingVenue}>{searchingVenue ? "검색 중…" : "관광정보 검색"}</button></div>
                  {venueSearchMessage && <p className="search-message" role="status">{venueSearchMessage}</p>}
                  {venueMatches.length > 0 && <ul className="search-results">{venueMatches.map((item) => <li key={item.venue.venue_id}><button type="button" onClick={() => chooseVenue(item)}><strong>{item.venue.name}</strong><span>{item.venue.address || "주소 정보 없음"}{item.category ? ` · ${item.category}` : ""}</span></button></li>)}</ul>}
                </Field>
                <Field label="주소" hint="선택·Kakao 검색" full group help="주소를 선택하면 위도·경도가 자동 입력됩니다. 비워두면 주변 정보 조회는 생략되고 접근성 확인 항목을 추천합니다.">
                  <div className="search-control"><input aria-label="주소" value={event.venue?.address ?? ""} onChange={(e) => { updateVenue("address", e.target.value); updateDetails("address_search_source", undefined); setAddressMatches([]); setAddressSearchMessage(""); }} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void runAddressSearch(); } }} placeholder="도로명 또는 지번 주소" /><button type="button" className="button secondary" onClick={() => void runAddressSearch()} disabled={searchingAddress}>{searchingAddress ? "검색 중…" : "주소 찾기"}</button></div>
                  {addressSearchMessage && <p className="search-message" role="status">{addressSearchMessage}</p>}
                  {addressMatches.length > 0 && <ul className="search-results">{addressMatches.map((item, index) => <li key={`${item.address_name}-${index}`}><button type="button" onClick={() => chooseAddress(item)}><strong>{item.road_address_name || item.address_name}</strong>{item.jibun_address_name && item.jibun_address_name !== item.road_address_name && <span>지번 {item.jibun_address_name}</span>}</button></li>)}</ul>}
                </Field>
                <Field label="공식 수용인원" hint="선택" suffix="명" help="TourAPI에는 공식 수용인원이 없습니다. 확인 전에는 비워두면 목표 인원 기준의 필요 규모를 추천합니다."><input type="number" min="1" inputMode="numeric" value={event.venue?.capacity ?? ""} onChange={(e) => updateVenue("capacity", numericValue(e.target.value))} /></Field>
                <Field label="공간 유형" required>
                  <select value={event.indoor_outdoor} onChange={(e) => updateEvent("indoor_outdoor", e.target.value as EventDraft["indoor_outdoor"])}><option value="undecided">아직 모름</option><option value="indoor">실내</option><option value="outdoor">실외</option><option value="mixed">실내·실외 혼합</option></select>
                </Field>
                <Field label="위도" hint="검색 시 자동 입력"><input type="number" step="any" value={Number.isFinite(event.venue?.coordinates?.latitude) ? event.venue?.coordinates?.latitude : ""} onChange={(e) => updateCoordinate("latitude", e.target.value)} placeholder="37.5665" /></Field>
                <Field label="경도" hint="검색 시 자동 입력"><input type="number" step="any" value={Number.isFinite(event.venue?.coordinates?.longitude) ? event.venue?.coordinates?.longitude : ""} onChange={(e) => updateCoordinate("longitude", e.target.value)} placeholder="126.9780" /></Field>
                <Field label="접근성 메모" hint="선택" full><textarea rows={3} value={event.venue?.accessibility_summary ?? ""} onChange={(e) => updateVenue("accessibility_summary", e.target.value)} placeholder="예: 주 출입구 무단차, 장애인 화장실 확인 필요" /></Field>
              </FormBlock>
              <FormBlock title="공간 운영 조건" description="공식 확인 전에는 기획 가정으로 저장됩니다.">
                <Field label="장소 유형" hint="선택"><input value={details.venue_type} onChange={(e) => updateDetails("venue_type", e.target.value)} placeholder="공원, 공연장, 클럽, 전시장 등" /></Field>
                <Field label="좌석 운영"><select value={details.seating_mode} onChange={(e) => updateDetails("seating_mode", e.target.value as PlanningDetails["seating_mode"])}><option value="unknown">아직 모름</option><option value="seated">좌석</option><option value="standing">스탠딩</option><option value="mixed">혼합</option></select></Field>
                <Field label="사용 가능 면적" hint="선택" suffix="㎡"><input type="number" min="1" value={details.venue_area_sqm ?? ""} onChange={(e) => updateDetails("venue_area_sqm", numericValue(e.target.value))} /></Field>
                <Field label="주차 가능 대수" hint="선택" suffix="대"><input type="number" min="0" value={details.parking_spaces ?? ""} onChange={(e) => updateDetails("parking_spaces", numericValue(e.target.value))} /></Field>
                <Field label="대중교통·셔틀" hint="선택" full><textarea rows={2} value={details.transit_plan} onChange={(e) => updateDetails("transit_plan", e.target.value)} /></Field>
                <Field label="필수 시설·장비" hint="선택" full><textarea rows={2} value={details.facility_plan} onChange={(e) => updateDetails("facility_plan", e.target.value)} placeholder="전력, 급수, 화장실, 휴게, 의료, 창고 등" /></Field>
              </FormBlock>
            </div>
          )}

          {step === 5 && (
            <div className="form-stack">
              <FormBlock title="프로그램과 협력자" description="핵심 콘텐츠와 예산 부족 시 지킬 우선순위를 적습니다.">
                <Field label="프로그램 구성" hint="선택" full><textarea rows={3} value={details.program_outline} onChange={(e) => updateDetails("program_outline", e.target.value)} /></Field>
                <Field label="출연진·연사·파트너" hint="선택" full><textarea rows={3} value={details.performer_partner_plan} onChange={(e) => updateDetails("performer_partner_plan", e.target.value)} /></Field>
                <Field label="반드시 유지할 프로그램" hint="선택" full><textarea rows={2} value={details.program_priority} onChange={(e) => updateDetails("program_priority", e.target.value)} /></Field>
              </FormBlock>
              <FormBlock title="예산과 수익" description="확정 견적이 아니라 현재 기획 범위입니다. 결과에서 필요한 견적 순서를 제시합니다.">
                <Field label="최소 예산" hint="선택" suffix="원"><input type="number" min="0" inputMode="numeric" value={event.budget_min_krw ?? ""} onChange={(e) => updateEvent("budget_min_krw", numericValue(e.target.value))} /></Field>
                <Field label="최대 예산" hint="선택" suffix="원"><input type="number" min="0" inputMode="numeric" value={event.budget_max_krw ?? ""} onChange={(e) => updateEvent("budget_max_krw", numericValue(e.target.value))} /></Field>
                <Field label="확보 예산" hint="선택" suffix="원"><input type="number" min="0" value={details.secured_budget_krw ?? ""} onChange={(e) => updateDetails("secured_budget_krw", numericValue(e.target.value))} /></Field>
                <Field label="예상 수익" hint="선택·가정" suffix="원"><input type="number" min="0" value={details.expected_revenue_krw ?? ""} onChange={(e) => updateDetails("expected_revenue_krw", numericValue(e.target.value))} /></Field>
                <Field label="손익분기 인원" hint="선택" suffix="명"><input type="number" min="1" value={details.break_even_attendance ?? ""} onChange={(e) => updateDetails("break_even_attendance", numericValue(e.target.value))} /></Field>
                <Field label="예산 배분안" hint="선택" full><textarea rows={3} value={details.budget_breakdown} onChange={(e) => updateDetails("budget_breakdown", e.target.value)} placeholder="대관, 프로그램, 장비, 인력, 안전, 홍보, 예비비" /></Field>
              </FormBlock>
              <FormBlock title="홍보와 판매" description="채널과 함께 시작일·예산·측정 기준을 정합니다.">
                <Field label="홍보 채널" hint="선택" full group><div className="choice-grid compact-choices">{MARKETING_CHANNELS.map((channel) => <label className={`check-card ${details.marketing_channels.includes(channel) ? "selected" : ""}`} key={channel}><input type="checkbox" checked={details.marketing_channels.includes(channel)} onChange={() => toggleChannel(channel)} />{channel}</label>)}</div></Field>
                <Field label="홍보 시작일" hint="선택"><input type="date" value={details.marketing_start_date} onChange={(e) => updateDetails("marketing_start_date", e.target.value)} /></Field>
                <Field label="홍보 예산" hint="선택" suffix="원"><input type="number" min="0" value={details.marketing_budget_krw ?? ""} onChange={(e) => updateDetails("marketing_budget_krw", numericValue(e.target.value))} /></Field>
                <Field label="홍보 KPI" hint="선택" full><input value={details.marketing_kpi} onChange={(e) => updateDetails("marketing_kpi", e.target.value)} placeholder="도달, 관심등록, 예매, 방문 전환 등" /></Field>
              </FormBlock>
              <FormBlock title="현장 운영" description="인력·대기·교통·기술 장애 대응을 한곳에서 점검합니다.">
                <Field label="운영 계획" hint="선택" full><textarea rows={3} value={details.operation_plan} onChange={(e) => updateDetails("operation_plan", e.target.value)} placeholder="인력, 입장, 동선, 교통 관련 현재 계획" /></Field>
                <Field label="운영 인력" hint="선택" suffix="명"><input type="number" min="1" value={details.staff_count ?? ""} onChange={(e) => updateDetails("staff_count", numericValue(e.target.value))} /></Field>
                <Field label="입장·대기·퇴장" hint="선택"><textarea rows={2} value={details.queue_plan} onChange={(e) => updateDetails("queue_plan", e.target.value)} /></Field>
                <Field label="전력·통신·결제 장애 대안" hint="선택" full><textarea rows={2} value={details.technical_fallback} onChange={(e) => updateDetails("technical_fallback", e.target.value)} /></Field>
                <Field label="교통·숙박 계획" hint="선택" full><textarea rows={2} value={details.transport_accommodation_plan} onChange={(e) => updateDetails("transport_accommodation_plan", e.target.value)} /></Field>
                <Field label="지역 상권·관광 연계" hint="선택" full><textarea rows={2} value={details.local_partnership_plan} onChange={(e) => updateDetails("local_partnership_plan", e.target.value)} /></Field>
              </FormBlock>
              <FormBlock title="안전·허가·포용·지속가능성" description="적합성을 확정하지 않고 전문가·담당기관에 확인할 초안을 만듭니다.">
                <Field label="안전 계획" hint="선택" full><textarea rows={3} value={details.safety_plan} onChange={(e) => updateDetails("safety_plan", e.target.value)} placeholder="날씨, 혼잡, 의료, 비상 대응 관련 현재 계획" /></Field>
                <Field label="허가·보험·권리" hint="선택" full><textarea rows={2} value={details.permits_and_insurance} onChange={(e) => updateDetails("permits_and_insurance", e.target.value)} placeholder="지자체, 소방, 경찰, 저작권, 보험 등" /></Field>
                <Field label="취소·연기·중단 기준" hint="선택" full><textarea rows={2} value={details.cancellation_rule} onChange={(e) => updateDetails("cancellation_rule", e.target.value)} /></Field>
                <Field label="접근성 계획" hint="선택" full><textarea rows={3} value={details.accessibility_plan} onChange={(e) => updateDetails("accessibility_plan", e.target.value)} /></Field>
                <Field label="환경·지역 상생" hint="선택" full><textarea rows={2} value={details.sustainability_plan} onChange={(e) => updateDetails("sustainability_plan", e.target.value)} /></Field>
                <Field label="과거 행사·근거 메모" hint="선택" full><textarea rows={2} value={details.past_event_summary} onChange={(e) => updateDetails("past_event_summary", e.target.value)} placeholder="실적·민원·사고·잘된 점을 개인정보 없이 요약" /></Field>
              </FormBlock>
            </div>
          )}

          {step === 6 && (
            <div className="form-stack">
              <FormBlock title="바꿀 수 없는 조건" description="한 줄에 하나씩 입력하세요. 추천은 이 조건을 우선해 보여줍니다.">
                <Field label="고정 제약" hint="없으면 비워두기" full><textarea rows={4} value={event.fixed_constraints.join("\n")} onChange={(e) => updateEvent("fixed_constraints", e.target.value.split("\n").map((item) => item.trim()).filter(Boolean).slice(0, 30))} placeholder="예: 행사 날짜 변경 불가" /></Field>
                <Field label="변경 가능한 항목" hint="한 줄에 하나" full><textarea rows={3} value={details.flexible_options} onChange={(e) => updateDetails("flexible_options", e.target.value)} placeholder="예: 부스 수 ±5개" /></Field>
                <Field label="우선 판단 기준" hint="복수 선택" full group><div className="choice-grid compact-choices">{PRIORITY_OPTIONS.map((priority) => <label className={`check-card ${details.priority_criteria.includes(priority) ? "selected" : ""}`} key={priority}><input type="checkbox" checked={details.priority_criteria.includes(priority)} onChange={() => toggleDetailList("priority_criteria", priority)} />{priority}</label>)}</div></Field>
                <Field label="감수 가능한 위험"><select value={details.risk_tolerance} onChange={(e) => updateDetails("risk_tolerance", e.target.value as PlanningDetails["risk_tolerance"])}><option value="unknown">아직 모름</option><option value="low">낮음</option><option value="medium">보통</option><option value="high">높음</option></select></Field>
                <Field label="원하는 대안 수" suffix="개"><input type="number" min="1" max="5" value={details.requested_alternatives} onChange={(e) => updateDetails("requested_alternatives", Math.min(5, Math.max(1, Number(e.target.value) || 1)))} /></Field>
                <Field label="최종 결정할 질문" hint="한 줄에 하나" full><textarea rows={3} value={details.requested_decisions} onChange={(e) => updateDetails("requested_decisions", e.target.value)} /></Field>
                <Field label="기타 고려사항" hint="선택" full><textarea rows={4} maxLength={3000} value={event.other_notes ?? ""} onChange={(e) => updateEvent("other_notes", e.target.value)} /></Field>
              </FormBlock>
              <ReviewSummary event={event} details={details} />
              <div className="model-notice"><span>MODEL MOCK</span><div><strong>이번 분석의 수요 점수는 실제 AI 모델 결과가 아닙니다.</strong><p>입력·API 계약과 결과 화면 검증용 규칙 점수입니다. 실제 관람객 수를 표시하지 않습니다.</p><p>설정된 경우 기획 Context는 실제 LLM에 전달되며, 사용할 수 없으면 규칙 보고서로 자동 전환됩니다.</p></div></div>
            </div>
          )}

          {error && <div className="form-error" role="alert">{error}</div>}
          <footer className="wizard-footer">
            <button type="button" className="button secondary" onClick={previousStep} disabled={step === 0}>이전</button>
            <div className="footer-right">
              <span>{formatSaved(savedAt)}</span>
              {step < 6 ? <button type="button" className="button primary" onClick={nextStep}>다음</button> : <><button type="button" className="button primary analyze-button" onClick={submitAnalysis} disabled={submitting}>{submitting ? submissionPhase || "분석·보고서 생성 중…" : "분석·보고서 생성"}</button>{submitting && canCancelLlm ? <button type="button" className="button secondary" onClick={cancelLlm}>AI 보고서 취소</button> : null}</>}
            </div>
          </footer>
        </section>
      </div>
    </main>
  );
}

function FormBlock({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="form-block"><div className="block-heading"><h2>{title}</h2><p>{description}</p></div><div className="field-grid">{children}</div></section>;
}

function Field({ label, hint, help, required, suffix, full, group, children }: { label: string; hint?: string; help?: string; required?: boolean; suffix?: string; full?: boolean; group?: boolean; children: React.ReactNode }) {
  const labelId = useId();
  const title = <span className="field-label" id={labelId}>{label}{required && <em>필수</em>}{hint && <small>{hint}</small>}</span>;
  const helpText = help ? <span className="field-help">{help}</span> : null;
  if (group) return <div className={`field ${full ? "full" : ""}`}>{title}<div role="group" aria-labelledby={labelId}>{children}</div>{helpText}</div>;
  return <label className={`field ${full ? "full" : ""}`}>{title}<span className={suffix ? "input-with-suffix" : ""}>{children}{suffix && <b>{suffix}</b>}</span>{helpText}</label>;
}

function DatePair({ label, value, onChange }: { label: string; value: { start_date: string; end_date: string }; onChange: (value: { start_date: string; end_date: string }) => void }) {
  return <div className="field full"><span className="field-label">{label}<em>필수</em></span><div className="date-pair"><label><span>시작일</span><input type="date" value={value.start_date} onChange={(e) => onChange({ ...value, start_date: e.target.value })} /></label><label><span>종료일</span><input type="date" value={value.end_date} onChange={(e) => onChange({ ...value, end_date: e.target.value })} /></label></div></div>;
}

function RegionSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <select value={value} onChange={(e) => onChange(e.target.value)}><option value="">선택해 주세요</option>{REGIONS.map(([code, label]) => <option value={code} key={code}>{label}</option>)}</select>;
}

function ReviewSummary({ event, details }: { event: EventDraft; details: PlanningDetails }) {
  const schedule = event.schedule_selection_mode === "fixed" ? `${event.start_date || "미정"} ~ ${event.end_date || "미정"}` : scheduleLabels[event.schedule_selection_mode];
  const regions: RegionRef[] = event.region_selection_mode === "fixed" && event.region ? [event.region] : event.region_candidates ?? [];
  const rows = [
    ["기획", `${optionLabel(event.planner_type)} · ${optionLabel(event.planning_stage)}`],
    ["행사", `${event.working_title || "이름 미정"} · ${optionLabel(event.event_type)}`],
    ["목적·테마", `${optionLabel(event.purpose)} · ${event.theme_keywords.join(", ") || "미정"}`],
    ["이용객", event.target_audience.map(audienceLabel).join(", ") || "미정"],
    ["일정", schedule],
    ["지역", regions.map((region) => region.display_name).join(", ") || regionLabels[event.region_selection_mode]],
    ["장소·규모", `${event.venue?.name || "장소 미정"} · ${event.target_attendance === undefined ? "목표 미정" : `목표 ${event.target_attendance.toLocaleString("ko-KR")}명`}`],
    ["예산", event.budget_max_krw !== undefined ? `최대 ${event.budget_max_krw.toLocaleString("ko-KR")}원` : "미정"],
    ["실행 메모", details.success_metric || "성공 기준 미정"],
  ];
  return <section className="form-block review-block"><div className="block-heading"><h2>입력 내용 확인</h2><p>분석에는 아래 시점의 입력 사본을 사용합니다.</p></div><dl className="review-list">{rows.map(([term, value]) => <div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl></section>;
}
