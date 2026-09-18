"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppHeader } from "./app-header";
import { PublicationPanel } from "./publication-panel";
import { KakaoMapPreview } from "./kakao-map-preview";
import { analyzePlanner, ApiError, getPredictionRegions } from "@/lib/api";
import { cleanEventForApi, duplicateDraft, findDraft } from "@/lib/drafts";
import { optionLabel, regionFromCode, REGIONS } from "@/lib/options";
import { buildPlanningContext } from "@/lib/planning-context";
import { buildRecommendationPrompt, buildRuleFallbackRecommendation, validateStructuredRecommendation } from "@/lib/recommendation";
import { buildReport, reportAsMarkdown } from "@/lib/report";
import { HeungDiagnosis } from "@/components/heung-diagnosis";
import { componentText, demandLevelText, predictionLabel, predictionNotice, predictionSummary, predictionValue } from "@/lib/prediction";
import type { DraftRecord, EventDraft, PlannerAnalysisRequest, PlannerAnalysisResponse, RegionRef, SourceRef } from "@/lib/types";

type Tab = "overview" | "report" | "compare" | "evidence";

const CATEGORY_LABELS: Record<string, string> = {
  demand: "수요", venue: "장소", budget: "예산", marketing: "홍보", operation: "운영",
  risk: "위험", accessibility: "접근성", tourism: "관광 연계",
};
const VALUE_LABELS: Record<string, string> = {
  user_input: "사용자 입력", verified_fact: "확인된 외부 정보", derived_value: "계산값",
  model_prediction: "모델 예측", assumption: "가정",
};
const PLACE_LABELS: Record<string, string> = {
  parking: "주차", lodging: "숙박", restaurant: "음식점", cafe: "카페",
  tourist_attraction: "관광지", cultural_facility: "문화시설", shopping: "쇼핑",
  restroom: "화장실", transit: "교통", other: "주변 장소",
};

function downloadFile(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function scoreOf(analysis: PlannerAnalysisResponse | undefined): number | undefined {
  return analysis ? predictionValue(analysis.prediction) : undefined;
}

function amount(value: number | undefined, unit: string): string {
  return value === undefined ? "미정" : `${value.toLocaleString("ko-KR")}${unit}`;
}

export function PlannerResult() {
  const router = useRouter();
  const [draft, setDraft] = useState<DraftRecord | null | undefined>(undefined);
  const [tab, setTab] = useState<Tab>("overview");
  const [scenario, setScenario] = useState<{ attendance?: number; budget?: number; environment: EventDraft["indoor_outdoor"]; date: string; regionCode: string; venueCapacity?: number }>({ environment: "undecided", date: "", regionCode: "" });
  const [comparison, setComparison] = useState<PlannerAnalysisResponse | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [scenarioError, setScenarioError] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [predictionRegions, setPredictionRegions] = useState<RegionRef[]>([]);
  const [scenarioRegion, setScenarioRegion] = useState("");

  useEffect(() => {
    let active = true;
    getPredictionRegions().then(regions => { if (active) setPredictionRegions(regions); }).catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const id = new URLSearchParams(window.location.search).get("draft");
      const record = id ? findDraft(id) : undefined;
      setDraft(record ?? null);
      if (record) setScenarioRegion(record.event.region?.legal_dong_code ?? "");
      if (record) setScenario({
        attendance: record.event.target_attendance,
        budget: record.event.budget_max_krw,
        environment: record.event.indoor_outdoor,
        date: record.event.start_date ?? record.event.date_candidates?.[0]?.start_date ?? "",
        regionCode: record.event.region?.area_code ?? record.event.region_candidates?.[0]?.area_code ?? "",
        venueCapacity: record.event.venue?.capacity,
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const planningContext = useMemo(() => draft?.analysis ? buildPlanningContext(draft, draft.analysis) : null, [draft]);
  const structuredRecommendation = useMemo(() => {
    if (!draft?.analysis || !planningContext) return null;
    return draft.recommendation ?? buildRuleFallbackRecommendation(draft, draft.analysis, planningContext);
  }, [draft, planningContext]);
  const report = useMemo(() => draft?.analysis ? buildReport(draft, draft.analysis, structuredRecommendation) : [], [draft, structuredRecommendation]);
  const recommendationValidation = useMemo(() => validateStructuredRecommendation(structuredRecommendation), [structuredRecommendation]);

  if (draft === undefined) return <main className="page-shell"><AppHeader detail="결과 불러오는 중" /><section className="panel loading-panel">분석 결과를 불러오고 있습니다.</section></main>;
  if (!draft) return <main className="page-shell"><AppHeader detail="결과 없음" /><section className="panel empty-panel"><h1>저장된 분석 결과가 없습니다</h1><p>기획 입력을 검토하고 분석을 실행해 주세요.</p><Link className="button primary" href="/planner">내 기획으로 이동</Link></section></main>;
  const analysis = draft.analysis;
  if (!analysis) return <main className="page-shell"><AppHeader detail="결과 없음" /><section className="panel empty-panel"><h1>저장된 분석 결과가 없습니다</h1><p>기획 입력을 검토하고 분석을 실행해 주세요.</p><Link className="button primary" href={`/planner/new?draft=${draft.id}`}>분석하러 이동</Link></section></main>;
  const currentDraft = draft;
  const prediction = analysis.prediction;
  const score = scoreOf(analysis);
  const comparisonScore = scoreOf(comparison ?? undefined);
  const regional = prediction.status === "available" && prediction.primary_metric.metric_name === "regional_visit_demand";
  const regionalPeople = regional && prediction.primary_metric.unit === "people";
  const scoreDisplay = score === undefined ? undefined : regionalPeople ? Math.round(score).toLocaleString("ko-KR") : score;
  const comparable = prediction.status === "available" && comparison?.prediction.status === "available"
    && prediction.primary_metric.unit === comparison.prediction.primary_metric.unit
    && prediction.prediction_type === comparison.prediction.prediction_type
    && prediction.model_version === comparison.prediction.model_version;
  const recommendationMode = structuredRecommendation?.generation_mode ?? "rule_fallback";
  const recommendationMeta = currentDraft.recommendation_meta;
  const sortedRecommendations = [...(structuredRecommendation?.priorities ?? [])].sort((a, b) => ({ high: 0, medium: 1, low: 2 }[a.priority] - { high: 0, medium: 1, low: 2 }[b.priority]));
  const allSources: SourceRef[] = [...prediction.sources];
  for (const source of [currentDraft.details.venue_search_source, currentDraft.details.address_search_source]) {
    if (source && !allSources.some((item) => item.source_id === source.source_id)) allSources.push(source);
  }
  if (analysis.nearby_places.status === "available") {
    analysis.nearby_places.items.forEach((place) => place.sources.forEach((source) => {
      if (!allSources.some((item) => item.source_id === source.source_id)) allSources.push(source);
    }));
  }

  function makeCopy() {
    const copy = duplicateDraft(currentDraft);
    router.push(`/planner/new?draft=${copy.id}`);
  }

  // 변경안도 원본과 같은 기간으로 비교한다. 일정 후보면 첫 번째 후보의 기간을 쓴다.
  function scenarioEndDate(start: string): string {
    const original = currentDraft.event.start_date && currentDraft.event.end_date
      ? { start_date: currentDraft.event.start_date, end_date: currentDraft.event.end_date } : currentDraft.event.date_candidates?.[0];
    return original ? new Date(Date.parse(start) + Date.parse(original.end_date) - Date.parse(original.start_date)).toISOString().slice(0, 10) : start;
  }

  async function runScenario() {
    setScenarioLoading(true);
    setScenarioError("");
    const changedEvent: EventDraft = {
      ...currentDraft.event,
      event_id: `evt_planner_${crypto.randomUUID().replaceAll("-", "_")}`,
      target_attendance: scenario.attendance,
      budget_max_krw: scenario.budget,
      indoor_outdoor: scenario.environment,
      ...(scenario.date ? { schedule_selection_mode: "fixed", start_date: scenario.date, end_date: scenarioEndDate(scenario.date) } : {}),
      ...(scenario.regionCode ? { region_selection_mode: "fixed", region: predictionRegions.find(region => region.legal_dong_code === scenarioRegion)
        ?? (scenario.regionCode === currentDraft.event.region?.area_code ? currentDraft.event.region : regionFromCode(scenario.regionCode)) } : {}),
      venue: currentDraft.event.venue ? { ...currentDraft.event.venue, capacity: scenario.venueCapacity } : scenario.venueCapacity ? { name: "비교용 후보 장소", capacity: scenario.venueCapacity } : undefined,
    };
    const request: PlannerAnalysisRequest = {
      contract_version: "0.1.0",
      client_request_id: crypto.randomUUID(),
      event_draft: cleanEventForApi(changedEvent),
      requested_outputs: ["prediction", "nearby_places", "rule_recommendations"],
    };
    try {
      setComparison(await analyzePlanner(request));
    } catch (caught) {
      setScenarioError((caught as ApiError).message);
    } finally {
      setScenarioLoading(false);
    }
  }

  function exportMarkdown() {
    const safeName = (currentDraft.event.working_title || "heungmap-plan").replace(/[\\/:*?"<>|]/g, "-");
    downloadFile(`${safeName}-report.md`, reportAsMarkdown(currentDraft, analysis!, structuredRecommendation), "text/markdown;charset=utf-8");
  }

  function exportJson() {
    const safeName = (currentDraft.event.working_title || "heungmap-plan").replace(/[\\/:*?"<>|]/g, "-");
    downloadFile(`${safeName}-analysis.json`, JSON.stringify({ draft: currentDraft, analysis, planning_context: planningContext, structured_recommendation: structuredRecommendation, recommendation_validation: recommendationValidation }, null, 2), "application/json;charset=utf-8");
  }

  function exportContext() {
    const safeName = (currentDraft.event.working_title || "heungmap-plan").replace(/[\\/:*?"<>|]/g, "-");
    downloadFile(`${safeName}-planning-context.json`, JSON.stringify({ planning_context: planningContext, llm_handoff: { prompt_version: "planner-recommendation-1.0", prompt: planningContext ? buildRecommendationPrompt(planningContext) : null }, structured_fallback: structuredRecommendation, validation: recommendationValidation }, null, 2), "application/json;charset=utf-8");
  }

  async function copySummary() {
    const summary = `${currentDraft.event.working_title || "이름 없는 기획"}\n${currentDraft.event.region?.display_name || "지역 미정"} · 목표 ${amount(currentDraft.event.target_attendance, "명")} · 최대예산 ${amount(currentDraft.event.budget_max_krw, "원")}\n${predictionSummary(prediction)}\n${predictionNotice(prediction)}\n우선 확인: ${sortedRecommendations.slice(0, 3).map((item) => item.title).join(", ")}`;
    try {
      await navigator.clipboard.writeText(summary);
      setCopyStatus("복사됨");
    } catch {
      setCopyStatus("복사 실패");
    }
  }

  function printReport() {
    setTab("report");
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => window.print()));
  }

  return (
    <main className="page-shell result-shell">
      <AppHeader detail={draft.event.working_title || "분석 결과"} />
      <div className="result-toolbar no-print">
        <Link href="/planner" className="back-link">← 내 기획</Link>
        <div><Link href={`/planner/new?draft=${draft.id}`} className="button secondary">입력 수정</Link><button className="button secondary" onClick={makeCopy}>복사본</button><button className="button secondary" onClick={copySummary}>{copyStatus || "요약 복사"}</button><button className="button secondary" onClick={printReport}>PDF로 인쇄</button><button className="button primary" onClick={exportMarkdown}>보고서 저장</button></div>
      </div>

      <section className="result-hero">
        <div>
          <div className="hero-badges"><span className="status-pill analyzed">분석 v{draft.version}</span><span className="mock-badge">{prediction.is_mock ? "MODEL MOCK" : prediction.status === "available" ? "AI 지역 수요 예측" : "수요 예측 불가"}</span><span className="status-pill analyzed">{recommendationMode === "llm" ? "LLM REPORT" : "RULE FALLBACK"}</span></div>
          <h1>{draft.event.working_title || "이름 없는 기획"}</h1>
          <p>{optionLabel(draft.event.event_type)} · {draft.event.region?.display_name || "지역 미정"} · {draft.event.target_attendance === undefined ? "목표 미정" : `목표 ${draft.event.target_attendance.toLocaleString("ko-KR")}명`}</p>
        </div>
        {score !== undefined && <div className="score-card"><span>{predictionLabel(prediction)}</span><strong>{scoreDisplay}{regional ? regionalPeople ? "" : "%" : ""}</strong><small>{regional ? regionalPeople ? "방문자-일 · 중앙 예측값" : "평상시 대비 · 중앙 예측값" : "/ 100 · 실제 예측 아님"}</small></div>}
      </section>

      <div className="mock-alert"><strong>{prediction.is_mock ? "현재 점수는 학습된 자체 AI 모델의 결과가 아닙니다." : prediction.status === "available" ? regionalPeople ? "행사기간 지역 방문자-일을 예측했습니다." : "평상시 대비 지역 방문수요를 예측했습니다." : "현재 조건에서는 수요 예측을 제공할 수 없습니다."}</strong><span>{predictionNotice(prediction)}</span></div>

      <nav className="result-tabs no-print" aria-label="분석 결과 메뉴">
        {(["overview", "report", "compare", "evidence"] as Tab[]).map((value) => <button className={tab === value ? "active" : ""} key={value} onClick={() => setTab(value)}>{({ overview: "한눈에 보기", report: "기획 보고서", compare: "대안 비교", evidence: "근거·출처" })[value]}</button>)}
      </nav>
      <PublicationPanel draft={draft} />

      {tab === "overview" && (
        <div className="result-content">
          {recommendationMeta?.warning ? <section className="warning-list"><strong>보고서 생성 안내</strong><p>{recommendationMeta.warning}</p></section> : null}
          {analysis.meta.warnings?.length ? <section className="warning-list"><strong>확인하지 못한 외부 근거</strong>{analysis.meta.warnings.map((warning) => <p key={warning}>{warning}</p>)}</section> : null}
          {structuredRecommendation && <section className="result-panel full-span"><div className="panel-title"><div><span className="eyebrow">PLANNING SUMMARY</span><h2>{recommendationMode === "llm" ? "LLM 기획 요약" : "규칙 기반 기획 요약"}</h2></div></div><p>{structuredRecommendation.executive_summary}</p></section>}
          <section className="result-grid">
            <article className="result-panel demand-panel">
              <div className="panel-title"><div><span className="eyebrow">DEMAND</span><h2>수요 진단</h2></div><span className="confidence">신뢰도 {prediction.status === "available" ? ({ low: "낮음", medium: "보통", high: "높음" })[prediction.confidence] : "확인 불가"}</span></div>
              {prediction.status === "available" ? <>
                {prediction.primary_metric.metric_name === "relative_demand_score" ? <>
                  <div className="score-scale"><span style={{ width: `${prediction.primary_metric.value}%` }} /><i style={{ left: `${prediction.primary_metric.value}%` }} /></div>
                  <div className="scale-labels"><span>낮음</span><span>중간</span><span>높음</span></div>
                </> : <><HeungDiagnosis prediction={prediction} evidence={analysis.evidence} role="planner" /><p>{predictionSummary(prediction)}</p>{demandLevelText(prediction) && <p>{demandLevelText(prediction)}</p>}<p>과거 검증 오차로 보정한 예측 범위이며 실제 포함률은 달라질 수 있습니다.</p>{prediction.components?.map(component => <p key={component.component_type}>{componentText(component)}</p>)}</>}
                {prediction.out_of_distribution && <div className="warning-list" role="status"><strong>학습 범위를 벗어난 조건이 포함되어 있습니다.</strong><p>예측 오차가 커질 수 있으므로 확정 판단에 사용하지 마세요.</p></div>}
                <p>기준 시각 {new Date(prediction.as_of).toLocaleString("ko-KR")} · {prediction.method === "machine_learning" ? "학습 모델" : "규칙 기반"}</p>
                <ul className="factor-list">{prediction.factors.map((factor) => <li key={factor.factor_id}><span className={`direction ${factor.direction}`}>{factor.direction === "up" ? "↑" : factor.direction === "down" ? "↓" : "–"}</span><div><strong>{factor.label}</strong><p>{factor.explanation}</p></div></li>)}</ul>
                <details><summary>예측 해석 한계 확인</summary><ul>{prediction.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></details>
              </> : <p>{prediction.message}</p>}
            </article>
            <article className="result-panel">
              <div className="panel-title"><div><span className="eyebrow">TOUR API</span><h2>주변 관광정보</h2></div><span className={`source-state ${analysis.nearby_places.status}`}>{analysis.nearby_places.status === "available" ? "조회됨" : "확인 필요"}</span></div>
              {analysis.nearby_places.status === "available" ? <ul className="nearby-list">{analysis.nearby_places.items.length ? analysis.nearby_places.items.map((place) => <li key={place.place_id}><strong>{place.name}</strong><span>{PLACE_LABELS[place.place_type] || place.place_type}{place.distance_m !== undefined ? ` · ${place.distance_m.toLocaleString("ko-KR")}m` : ""}</span></li>) : <li>반경 5km 안에 표시할 관광정보가 없습니다.</li>}</ul> : <div className="unavailable-box"><strong>주변 정보 미조회</strong><p>{analysis.nearby_places.message}</p><Link href={`/planner/new?draft=${draft.id}`}>장소 정보 수정 →</Link></div>}
              <KakaoMapPreview venue={draft.event.venue} nearby={analysis.nearby_places} />
            </article>
          </section>
          <section className="result-panel recommendations-panel">
            <div className="panel-title"><div><span className="eyebrow">NEXT ACTIONS</span><h2>우선 보완할 항목</h2></div><span>{sortedRecommendations.length}개</span></div>
            <div className="recommendation-list">{sortedRecommendations.map((item, index) => <article key={item.id}><span className={`priority ${item.priority}`}>{item.priority === "high" ? "높음" : item.priority === "medium" ? "중간" : "낮음"}</span><div className="recommendation-number">{String(index + 1).padStart(2, "0")}</div><div><small>{CATEGORY_LABELS[item.category]}</small><h3>{item.title}</h3><p>{item.action}</p><details><summary>추천 근거</summary><p>{item.reason}</p><p>예상 효과: {item.predicted_impact}</p>{item.assumptions.length ? <p>가정: {item.assumptions.join(" · ")}</p> : null}</details></div></article>)}</div>
          </section>
        </div>
      )}

      {tab === "report" && (
        <div className="result-content report-layout">
          <aside className="report-index no-print"><strong>보고서 구성</strong>{report.map((section, index) => <a key={section.title} href={`#report-${index}`}>{index + 1}. {section.title}</a>)}</aside>
          <article className="report-document">
            <header><p>흥할지도 기획 점검 보고서</p><h2>{draft.event.working_title || "이름 없는 기획"}</h2><span>{new Date(structuredRecommendation?.generated_at ?? analysis.meta.generated_at).toLocaleString("ko-KR")} · 계약 {analysis.contract_version} · {recommendationMode === "llm" ? `LLM ${recommendationMeta?.model ?? "configured model"}` : "규칙 fallback"} · schema {recommendationValidation.valid ? "통과" : "확인 필요"}</span></header>
            {report.map((section, index) => <section id={`report-${index}`} key={section.title}><span>{String(index + 1).padStart(2, "0")}</span><h3>{section.title}</h3><p>{section.body}</p><ul>{section.checks.map((check) => <li key={check}><i />{check}</li>)}</ul></section>)}
            <footer><strong>해석 한계</strong>{[...new Set([...prediction.limitations, ...(structuredRecommendation?.limitations ?? [])])].map((item) => <p key={item}>{item}</p>)}</footer>
          </article>
        </div>
      )}

      {tab === "compare" && (
        <div className="result-content compare-layout">
          <section className="result-panel scenario-form">
            <div className="panel-title"><div><span className="eyebrow">WHAT-IF</span><h2>조건을 바꿔 비교</h2></div></div>
            <p>원본 기획은 바뀌지 않습니다. 변경한 조건으로 새 분석을 실행합니다. 지역 방문수요 모델은 일정·지역과 과거 방문 패턴을 사용하므로 예산·목표 인원 변경을 수요 증가로 계산하지 않습니다.</p>
            <label><span>목표 인원</span><div className="input-with-suffix"><input type="number" min="1" value={scenario.attendance ?? ""} onChange={(e) => setScenario({ ...scenario, attendance: Number(e.target.value) || undefined })} /><b>명</b></div></label>
            <label><span>최대 예산</span><div className="input-with-suffix"><input type="number" min="0" value={scenario.budget ?? ""} onChange={(e) => setScenario({ ...scenario, budget: e.target.value === "" ? undefined : Number(e.target.value) })} /><b>원</b></div></label>
            <label><span>공간 유형</span><select value={scenario.environment} onChange={(e) => setScenario({ ...scenario, environment: e.target.value as EventDraft["indoor_outdoor"] })}><option value="undecided">미정</option><option value="indoor">실내</option><option value="outdoor">실외</option><option value="mixed">혼합</option></select></label>
            <label><span>행사 날짜</span><input type="date" value={scenario.date} onChange={(e) => setScenario({ ...scenario, date: e.target.value })} /></label>
            <label><span>개최 지역</span><select value={scenario.regionCode} onChange={(e) => { setScenario({ ...scenario, regionCode: e.target.value }); setScenarioRegion(""); }}><option value="">원본 유지</option>{REGIONS.map(([code, label]) => <option value={code} key={code}>{label}</option>)}</select></label>
            <label><span>비교할 시군구</span><select value={scenarioRegion} onChange={e => setScenarioRegion(e.target.value)}><option value="">시군구 선택 / 같은 지역이면 원본 유지</option>{predictionRegions.filter(region => region.area_code === scenario.regionCode).map(region => <option key={region.legal_dong_code} value={region.legal_dong_code}>{region.display_name}</option>)}</select></label>
            <label><span>장소 수용인원</span><div className="input-with-suffix"><input type="number" min="1" value={scenario.venueCapacity ?? ""} onChange={(e) => setScenario({ ...scenario, venueCapacity: Number(e.target.value) || undefined })} /><b>명</b></div></label>
            <div className="quick-scenarios"><button onClick={() => setScenario({ ...scenario, attendance: Math.max(1, Math.round((draft.event.target_attendance || 100) * 0.8)) })}>규모 20% 축소</button><button onClick={() => setScenario({ ...scenario, budget: Math.round((draft.event.budget_max_krw || 0) * 1.2) })}>예산 20% 확대</button><button onClick={() => setScenario({ ...scenario, environment: "indoor" })}>실내로 변경</button></div>
            {scenarioError && <div className="form-error" role="alert">{scenarioError}</div>}
            <button className="button primary" onClick={runScenario} disabled={scenarioLoading}>{scenarioLoading ? "비교 중…" : "변경안 분석"}</button>
          </section>
          <section className="comparison-cards">
            <article className="compare-card baseline"><span>현재안</span><strong>{scoreDisplay ?? "–"}{regional && !regionalPeople ? "%" : ""}</strong><small>{predictionLabel(prediction)}</small><dl><div><dt>목표</dt><dd>{amount(draft.event.target_attendance, "명")}</dd></div><div><dt>예산</dt><dd>{amount(draft.event.budget_max_krw, "원")}</dd></div><div><dt>날짜·지역</dt><dd>{draft.event.start_date ? `${draft.event.start_date}~${draft.event.end_date}` : draft.event.date_candidates?.[0] ? `${draft.event.date_candidates[0].start_date}~${draft.event.date_candidates[0].end_date}(후보)` : "미정"} · {draft.event.region?.display_name || draft.event.region_candidates?.[0]?.display_name || "미정"}</dd></div><div><dt>공간·수용</dt><dd>{optionLabel(draft.event.indoor_outdoor)} · {amount(draft.event.venue?.capacity, "명")}</dd></div></dl></article>
            <article className={`compare-card ${comparison ? "alternative" : "placeholder"}`}><span>변경안</span><strong>{comparisonScore === undefined ? "?" : regionalPeople ? Math.round(comparisonScore).toLocaleString("ko-KR") : comparisonScore}{comparison?.prediction.status === "available" && comparison.prediction.primary_metric.unit === "percent_change" ? "%" : ""}</strong><small>{comparison ? comparable && comparisonScore !== undefined && score !== undefined ? `현재안 대비 ${comparisonScore - score >= 0 ? "+" : ""}${regionalPeople ? Math.round(comparisonScore - score).toLocaleString("ko-KR") : (comparisonScore - score).toFixed(1)}${regionalPeople ? " 방문자-일" : regional ? "%p" : "점"}` : "같은 종류·단위·모델의 예측이 있어야 비교할 수 있습니다." : "조건을 바꾸고 분석하세요"}</small>{comparison?.prediction.status === "unavailable" && <p>{comparison.prediction.message}</p>}<dl><div><dt>목표</dt><dd>{amount(scenario.attendance, "명")}</dd></div><div><dt>예산</dt><dd>{amount(scenario.budget, "원")}</dd></div><div><dt>날짜·지역</dt><dd>{scenario.date ? `${scenario.date}~${scenarioEndDate(scenario.date)}` : "원본"} · {predictionRegions.find(region => region.legal_dong_code === scenarioRegion)?.display_name || regionFromCode(scenario.regionCode)?.display_name || "원본"}</dd></div><div><dt>공간·수용</dt><dd>{optionLabel(scenario.environment)} · {amount(scenario.venueCapacity, "명")}</dd></div></dl></article>
          </section>
          {comparison && <section className="result-panel full-span"><div className="panel-title"><h2>변경안 확인 항목</h2></div><div className="recommendation-list compact">{comparison.rule_recommendations.map((item) => <article key={item.recommendation_id}><span className={`priority ${item.priority}`}>{item.priority}</span><div><h3>{item.title}</h3><p>{item.action}</p></div></article>)}</div></section>}
        </div>
      )}

      {tab === "evidence" && (
        <div className="result-content evidence-layout">
          <section className="result-panel">
            <div className="panel-title"><div><span className="eyebrow">EVIDENCE</span><h2>분석에 사용한 값</h2></div></div>
            <div className="evidence-list">{analysis.evidence.map((item) => <article key={item.evidence_id}><span>{VALUE_LABELS[item.value_type]}</span><div><strong>{item.label}</strong><p>{item.display_value}</p>{item.limitation && <small>{item.limitation}</small>}</div></article>)}</div>
          </section>
          <section className="result-panel">
            <div className="panel-title"><div><span className="eyebrow">PROVENANCE</span><h2>출처·버전</h2></div><button className="text-button no-print" onClick={exportJson}>전체 JSON 저장</button></div>
            <div className="source-list">{allSources.map((source) => <article key={source.source_id}><span className={`source-icon ${source.source_type}`}>{source.source_type === "tourapi" ? "관" : "흥"}</span><div><strong>{source.provider_name}</strong><p>{source.dataset_name}</p><small>조회 {new Date(source.retrieved_at).toLocaleString("ko-KR")}</small>{source.limitation && <em>{source.limitation}</em>}</div></article>)}</div>
            <dl className="version-list"><div><dt>계약</dt><dd>{analysis.contract_version}</dd></div><div><dt>모델 인터페이스</dt><dd>{prediction.status === "available" ? prediction.model_version : "사용 불가"}</dd></div><div><dt>보고서 생성</dt><dd>{recommendationMode === "llm" ? `${recommendationMeta?.provider ?? "LLM"} · ${recommendationMeta?.model ?? "configured model"}` : "로컬 규칙 fallback"}</dd></div><div><dt>prompt</dt><dd>{structuredRecommendation?.prompt_version ?? "planner-recommendation-1.0"}</dd></div><div><dt>분석 ID</dt><dd>{analysis.analysis_id}</dd></div></dl>
          </section>
          <section className="result-panel full-span">
            <div className="panel-title"><div><span className="eyebrow">PLANNING CONTEXT</span><h2>구조화된 기획 Context</h2></div><button className="text-button no-print" onClick={exportContext}>Context JSON 저장</button></div>
            <p className="context-description">원본 form과 분석 결과를 역할별 항목으로 정리했습니다. 이번 보고서는 {recommendationMode === "llm" ? "설정된 실제 LLM이 구조화 계약에 맞춰 생성했습니다." : "LLM 실패에도 사용할 수 있는 로컬 규칙으로 생성했습니다."}</p>
            <div className="context-summary"><article><strong>{planningContext?.missing_information.length ?? 0}</strong><span>추가 확인 정보</span></article><article><strong>{currentDraft.event.fixed_constraints.length}</strong><span>고정 제약</span></article><article><strong>{structuredRecommendation?.alternatives.length ?? 0}</strong><span>구조화 대안</span></article><article><strong>{recommendationValidation.valid ? "Valid" : "Check"}</strong><span>추천 schema</span></article></div>
            {planningContext?.missing_information.length ? <div className="missing-list"><strong>추가로 확인하면 좋은 정보</strong><p>{planningContext.missing_information.join(" · ")}</p></div> : <div className="missing-list complete"><strong>핵심 입력이 채워졌습니다</strong><p>현장·기관 확인 후 새 버전으로 다시 분석하세요.</p></div>}
            {!recommendationValidation.valid && <div className="form-error" role="alert">{recommendationValidation.errors.join(" ")}</div>}
          </section>
          <section className="result-panel full-span">
            <div className="panel-title"><div><span className="eyebrow">VERSION HISTORY</span><h2>분석 변경 이력</h2></div><span>최근 20개</span></div>
            <ol className="history-list">{[...currentDraft.history].reverse().map((item) => <li key={`${item.version}-${item.analysis_id}`}><span>v{item.version}</span><div><strong>{item.summary}</strong><small>{new Date(item.created_at).toLocaleString("ko-KR")} · {item.analysis_id}</small></div></li>)}</ol>
          </section>
        </div>
      )}
    </main>
  );
}
