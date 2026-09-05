import { audienceLabel, optionLabel } from "./options";
import type { DraftRecord, PlannerAnalysisResponse, PlanningContext, StructuredPlanningRecommendation } from "./types";

export type RecommendationValidation = { valid: boolean; errors: string[] };

export function buildRecommendationPrompt(context: PlanningContext): string {
  return [
    "역할: 행사 기획 보조자",
    "입력: 아래 Planning Context 1.0 JSON만 사용한다.",
    "규칙: model_prediction 숫자를 바꾸거나 새 수요·비용·법률·장소 사실을 만들지 않는다.",
    "규칙: 추천마다 근거, 신뢰도, 비용 수준, 난이도와 사람 확인 필요 여부를 포함한다.",
    "규칙: 고정 제약을 지키고 누락 정보는 질문으로 돌려준다.",
    "출력: StructuredPlanningRecommendation 1.0 JSON만 반환한다.",
    JSON.stringify(context),
  ].join("\n");
}

export function buildRuleFallbackRecommendation(
  draft: DraftRecord,
  analysis: PlannerAnalysisResponse,
  context: PlanningContext,
): StructuredPlanningRecommendation {
  const event = draft.event;
  const details = draft.details;
  const axes = [
    event.schedule_selection_mode !== "fixed" ? "후보 날짜를 확정해 비교" : "날짜를 유지하고 운영 시간을 조정",
    event.region_selection_mode !== "fixed" ? "후보 지역을 좁혀 TourAPI 근거 비교" : "지역을 유지하고 후보 장소 수용인원 비교",
    event.target_attendance ? `목표 인원 ${Math.max(1, Math.round(event.target_attendance * 0.8)).toLocaleString("ko-KR")}명 축소안 비교` : "목표 인원 보수안 입력",
    event.budget_max_krw ? "최대예산 20% 변동안 비교" : "예산 상한 입력",
    event.indoor_outdoor !== "indoor" ? "실내 대체안 비교" : "현재 실내안 유지",
  ];
  const alternativeCount = Math.min(5, Math.max(1, details.requested_alternatives));
  return {
    schema_version: "1.0",
    prompt_version: "planner-recommendation-1.0",
    generation_mode: "rule_fallback",
    generated_at: analysis.meta.generated_at,
    executive_summary: `${event.working_title || "이름 없는 행사"}는 ${optionLabel(event.purpose)} 목적의 ${optionLabel(event.event_type)}이며 주요 이용객은 ${event.target_audience.map(audienceLabel).join(", ") || "미정"}입니다. 현재 추천은 학습 모델과 LLM을 사용하지 않는 규칙 fallback입니다.`,
    priorities: analysis.rule_recommendations.map((item) => ({
      id: item.recommendation_id,
      priority: item.priority,
      category: item.category,
      title: item.title,
      action: item.action,
      reason: item.reason,
      evidence_refs: item.evidence_refs,
      assumptions: [],
      predicted_impact: "입력된 조건의 불확실성을 줄이고 다음 결정을 준비합니다.",
      confidence: item.evidence_refs.length ? "medium" : "low",
      cost_level: "unknown",
      difficulty: "needs_review",
      deadline: details.decision_deadline || null,
      dependencies: [],
      risks: ["현장·기관·견적 확인 전에는 확정안으로 사용할 수 없습니다."],
      requires_human_review: true,
    })),
    alternatives: axes.slice(0, alternativeCount).map((change, index) => ({
      id: `alternative_${index + 1}`,
      title: `대안 ${index + 1}`,
      changes: [change],
      verify: ["What-if를 실행해 같은 mock 기준으로 비교", "현장·기관·견적 근거를 확인"],
    })),
    roadmap: [
      { phase: "지금", actions: analysis.rule_recommendations.filter((item) => item.priority === "high").map((item) => item.action).slice(0, 3) },
      { phase: "결정 전", actions: ["누락 정보를 채우고 새 분석 version 생성", "일정·장소·예산 대안을 같은 기준으로 비교"] },
      { phase: "행사 전·후", actions: ["현장 안전·접근성 체크 완료", "실제 입장·혼잡·운영 기록을 개인정보 없이 보관"] },
    ],
    missing_information: context.missing_information,
    limitations: [
      "외부 LLM을 호출하지 않았으며 규칙 template으로 생성했습니다.",
      "자체 수요점수는 학습 모델 연결 전 mock 상대지수입니다.",
      "장소·비용·법률·안전 적합성은 담당자와 전문가가 확인해야 합니다.",
    ],
  };
}

export function validateStructuredRecommendation(value: unknown): RecommendationValidation {
  const errors: string[] = [];
  if (!value || typeof value !== "object") return { valid: false, errors: ["결과가 object가 아닙니다."] };
  const item = value as Partial<StructuredPlanningRecommendation>;
  if (item.schema_version !== "1.0") errors.push("schema_version이 1.0이 아닙니다.");
  if (item.prompt_version !== "planner-recommendation-1.0") errors.push("prompt_version이 올바르지 않습니다.");
  if (!item.executive_summary?.trim()) errors.push("executive_summary가 없습니다.");
  if (!Array.isArray(item.priorities)) errors.push("priorities가 배열이 아닙니다.");
  else item.priorities.forEach((priority, index) => {
    if (!priority.title || !priority.action || !priority.reason) errors.push(`priorities[${index}]의 필수 문장이 없습니다.`);
    if (priority.requires_human_review !== true) errors.push(`priorities[${index}]에 사람 확인 표시가 없습니다.`);
    if (!Array.isArray(priority.evidence_refs)) errors.push(`priorities[${index}]의 evidence_refs가 없습니다.`);
  });
  if (!Array.isArray(item.alternatives)) errors.push("alternatives가 배열이 아닙니다.");
  if (!Array.isArray(item.roadmap)) errors.push("roadmap이 배열이 아닙니다.");
  if (!Array.isArray(item.missing_information)) errors.push("missing_information이 배열이 아닙니다.");
  if (!Array.isArray(item.limitations) || item.limitations.length === 0) errors.push("limitations가 없습니다.");
  return { valid: errors.length === 0, errors };
}
