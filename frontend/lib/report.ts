import { audienceLabel, optionLabel, seatingLabel } from "./options";
import { buildPlanningContext } from "./planning-context";
import type { DraftRecord, PlannerAnalysisResponse, StructuredPlanningRecommendation } from "./types";

export type ReportSection = { title: string; body: string; checks: string[] };

function amount(value: number | undefined, unit: string): string {
  return value === undefined ? "미정" : `${value.toLocaleString("ko-KR")}${unit}`;
}

export function buildReport(
  draft: DraftRecord,
  analysis: PlannerAnalysisResponse,
  recommendation?: StructuredPlanningRecommendation | null,
): ReportSection[] {
  const event = draft.event;
  const details = draft.details;
  const context = buildPlanningContext(draft, analysis);
  const audience = event.target_audience.map(audienceLabel).join(", ") || "목표 이용객 미정";
  const channels = details.marketing_channels.join(", ") || "홍보 채널 미정";
  const highPriority = recommendation?.priorities.filter((item) => item.priority === "high")
    ?? analysis.rule_recommendations.filter((item) => item.priority === "high");
  const budget = event.budget_max_krw !== undefined ? `${event.budget_max_krw.toLocaleString("ko-KR")}원` : "미정";
  const sections: ReportSection[] = [
    {
      title: "기획 요약",
      body: recommendation?.executive_summary ?? `${event.working_title || "이름 없는 행사"}는 ${optionLabel(event.purpose)} 목적의 ${optionLabel(event.event_type)}입니다. ${details.event_summary || "행사 한 줄 설명은 아직 없습니다."} 주요 이용객은 ${audience}이며 현재 단계는 ${optionLabel(event.planning_stage)}입니다.`,
      checks: [details.success_metric || "성공 판단 지표를 한 가지 이상 정하기", details.main_concern || "가장 먼저 풀 문제를 한 문장으로 정하기", "고정 조건과 변경 가능한 조건을 팀에 공유하기"],
    },
    {
      title: "추천 우선순위",
      body: recommendation?.generation_mode === "llm"
        ? "실제 LLM이 입력 Context와 기존 규칙 근거를 재구성한 실행안입니다. 모든 항목은 사람의 확인이 필요합니다."
        : "LLM을 사용할 수 없어 같은 입력과 근거를 규칙으로 정리한 실행안입니다.",
      checks: recommendation?.priorities.map((item) => `${item.title}: ${item.action}`)
        ?? analysis.rule_recommendations.map((item) => `${item.title}: ${item.action}`),
    },
    {
      title: "수요·규모 판단",
      body: analysis.prediction.status === "available"
        ? `현재 ${analysis.prediction.primary_metric.value}점은 자체 모델 연결 전 mock 상대지수입니다. 목표 ${amount(event.target_attendance, "명")}, 최소 성공 ${amount(details.minimum_success_attendance, "명")}, 최대 동시 체류 ${amount(details.maximum_concurrent_attendance, "명")}을 장소의 공식 수용인원과 별도로 비교해야 합니다.`
        : analysis.prediction.message,
      checks: ["목표·최소 성공·동시 체류·공식 수용인원을 구분하기", details.break_even_attendance ? `손익분기 ${details.break_even_attendance.toLocaleString("ko-KR")}명과 목표 인원 비교` : "유료 행사라면 손익분기 인원 계산", "실제 모델 연결 후 같은 입력 snapshot으로 다시 분석하기"],
    },
    {
      title: "날짜·지역·장소",
      body: `${event.region?.display_name || "지역 미정"}의 ${event.venue?.name || "장소 미정"}을 기준으로 검토했습니다. 운영 시간은 ${details.daily_hours || "미정"}, 좌석 방식은 ${seatingLabel(details.seating_mode)}이며 주차 계획은 ${details.parking_spaces === undefined ? "미정" : `${details.parking_spaces.toLocaleString("ko-KR")}대`}입니다.`,
      checks: [details.setup_rehearsal_teardown || "설치·리허설·철거 시간 확인", details.transit_plan || "대중교통·셔틀·막차 동선 확인", details.rain_or_weather_fallback || "기상 대체안과 결정 시점 확인"],
    },
    {
      title: "프로그램·이용객",
      body: details.program_outline || "핵심 프로그램이 아직 입력되지 않았습니다.",
      checks: [details.performer_partner_plan || "출연진·연사·파트너 후보와 대체안 확인", details.program_priority || "예산 부족 시에도 유지할 핵심 프로그램 결정", details.dropout_reason || "목표 이용객이 방문을 포기할 이유 한 가지 점검"],
    },
    {
      title: "예산·수익 점검",
      body: `입력한 최대예산은 ${budget}, 확보 예산은 ${amount(details.secured_budget_krw, "원")}입니다. 실제 견적이 아니므로 대관·시설·인력·안전·홍보·예비비를 나눠 확인해야 합니다.`,
      checks: [details.budget_breakdown || "고정비·변동비·예비비를 구분하기", event.ticket_type === "paid" || event.ticket_type === "mixed" ? details.refund_policy || "티켓 가격·환불·양도 정책 확인" : "무료 행사 노쇼·초과 방문 기준 확인", "입력 금액을 실제 견적이나 확정 수익처럼 사용하지 않기"],
    },
    {
      title: "홍보·판매",
      body: `현재 선택한 채널은 ${channels}이며 홍보 시작일은 ${details.marketing_start_date || "미정"}입니다. 채널 수보다 관심→등록→방문의 측정 기준과 확인 시점이 중요합니다.`,
      checks: [details.marketing_kpi || "관심등록·예매·방문 중 핵심 KPI 하나 정하기", "주간 콘텐츠 담당과 검토일 정하기", details.ticket_sales_channels || "등록·예매 채널과 장애 시 대안 확인"],
    },
    {
      title: "운영·안전",
      body: `${details.operation_plan || "운영 메모 없음"} / ${details.safety_plan || "안전 계획 없음"}`,
      checks: [...(highPriority.length ? highPriority.map((item) => item.action) : [details.queue_plan || "입장·대기·퇴장 동선을 현장에서 확인하기"]), details.technical_fallback || "전력·통신·결제·QR 장애 대안 확인", details.cancellation_rule || "취소·연기·중단 결정 기준 확인"],
    },
    {
      title: "접근성·주변 연계",
      body: details.accessibility_plan || "접근성 계획이 아직 입력되지 않았습니다.",
      checks: [details.audience_accessibility_needs || "무단차 동선·화장실·휴게 공간 확인", details.local_partnership_plan || "지역 상권·관광 연계 방식 확인", "TourAPI 주변 장소 결과와 현장 정보를 교차 확인"],
    },
    {
      title: "허가·지속가능성",
      body: `${details.permits_and_insurance || "허가·보험 확인 항목이 입력되지 않았습니다."} 이 문서는 법률·안전 적합성을 승인하지 않습니다.`,
      checks: ["담당기관과 전문가에게 허가·보험·저작권을 확인", details.sustainability_plan || "폐기물·교통·소음·철거 복구 계획 확인", "확인 담당자와 기한 기록"],
    },
    {
      title: "비교 대안",
      body: recommendation?.alternatives.length
        ? `${recommendation.alternatives.length}개 대안을 원본 기획을 바꾸지 않는 비교 후보로 제시합니다.`
        : "입력 조건을 바꾼 대안을 추가로 비교해야 합니다.",
      checks: recommendation?.alternatives.flatMap((item) => [
        `${item.title}: ${item.changes.join(" · ")}`,
        ...item.verify.map((value) => `${item.title} 확인: ${value}`),
      ]) ?? ["규모·예산·장소·일정 중 하나씩 바꿔 비교하기"],
    },
    {
      title: "실행 로드맵",
      body: `결정 기한은 ${details.decision_deadline || "미정"}이며, 요청한 결정은 ${details.requested_decisions || "아직 입력되지 않았습니다"}. 분석 결과를 확정안으로 사용하지 말고 담당자와 근거를 확인하세요.`,
      checks: recommendation?.roadmap.flatMap((item) => item.actions.map((action) => `${item.phase}: ${action}`))
        ?? ["이번 주: 높은 우선순위 위험의 담당자와 확인일 정하기", "다음 단계: 장소·일정·예산 견적을 입력해 새 버전으로 재분석하기", `누락 정보 ${context.missing_information.length}개 확인: ${context.missing_information.slice(0, 5).join(", ") || "핵심 누락 없음"}`, "행사 후: 실제 입장·혼잡·운영 기록을 남기기"],
    },
  ];
  if (details.detail_level === "quick") return sections.filter((section) => ["기획 요약", "추천 우선순위", "수요·규모 판단", "운영·안전", "실행 로드맵"].includes(section.title));
  if (details.detail_level === "standard") return sections.filter((section) => section.title !== "허가·지속가능성");
  return sections;
}

export function reportAsMarkdown(
  draft: DraftRecord,
  analysis: PlannerAnalysisResponse,
  recommendation?: StructuredPlanningRecommendation | null,
): string {
  const sections = buildReport(draft, analysis, recommendation);
  const generatedAt = new Date(recommendation?.generated_at ?? analysis.meta.generated_at).toLocaleString("ko-KR");
  return [
    `# ${draft.event.working_title || "이름 없는 기획"} 기획 점검 보고서`,
    "",
    `생성 시각: ${generatedAt}`,
    `기획 버전: v${draft.version}`,
    "",
    "> 수요 점수는 자체 AI 모델 연결 전 mock 상대지수이며 실제 관람객 수가 아닙니다.",
    recommendation?.generation_mode === "llm"
      ? "> 기획 문장은 설정된 실제 LLM이 구조화 계약에 맞춰 생성했으며 사람의 확인이 필요합니다."
      : "> 실제 LLM을 사용할 수 없어 기획 문장을 규칙 fallback으로 생성했습니다.",
    "",
    ...sections.flatMap((section) => [
      `## ${section.title}`,
      "",
      section.body,
      "",
      ...section.checks.map((item) => `- [ ] ${item}`),
      "",
    ]),
    "## 데이터 한계",
    "",
    ...analysis.prediction.limitations.map((item) => `- ${item}`),
    ...(recommendation?.limitations.map((item) => `- ${item}`) ?? []),
    "",
  ].join("\n");
}
