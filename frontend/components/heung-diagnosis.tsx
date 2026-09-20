import type { Evidence, Prediction } from "@/lib/types";

type Role = "planner" | "visitor";

const LEVEL_LABELS: Record<string, string> = { low: "낮음", medium: "보통", high: "높음", very_high: "매우 높음" };
const CONFIDENCE_LABELS = { low: "낮음", medium: "보통", high: "높음" } as const;

const SEASON_TEXT: Record<Role, Record<string, string>> = {
  planner: {
    very_high: "지역 방문수요가 평소보다 크게 많은 시기라 방문객 유입 여건이 좋습니다. 숙박·교통 수요도 함께 늘 수 있습니다.",
    high: "지역 방문수요가 평소보다 많은 시기라 방문객 유입 여건이 좋은 편입니다.",
    medium: "평소 수준의 지역 방문수요가 예상됩니다.",
    low: "지역 방문수요가 평소보다 적은 시기라 외부 방문객을 끌어오는 홍보가 중요합니다.",
  },
  visitor: {
    very_high: "지역 방문객이 평소보다 크게 많은 시기입니다. 숙박·주차를 미리 확인하세요.",
    high: "지역 방문객이 평소보다 많은 시기입니다. 숙박·주차를 미리 확인하세요.",
    medium: "평소 수준의 지역 방문객이 예상됩니다.",
    low: "지역 방문객이 평소보다 적은 시기입니다.",
  },
};

function find(evidence: Evidence[], id: string) {
  return evidence.find((item) => item.evidence_id === id);
}

/** 이미 계산·확인된 근거만 묶은 흥행 진단. 관람객 수를 새로 만들지 않는다. */
export function HeungDiagnosis({ prediction, evidence = [], role }: { prediction: Prediction; evidence?: Evidence[]; role: Role }) {
  if (prediction.status !== "available" || prediction.is_mock || prediction.prediction_type !== "regional_visit_demand") return null;
  const all = [...prediction.evidence, ...evidence.filter((item) => !prediction.evidence.some((own) => own.evidence_id === item.evidence_id))];
  const level = prediction.indicators?.congestion_level ?? "unknown";
  const demand = find(all, "ev_daily_demand_level");
  const prior = find(all, "ev_mcst_prior_attendance");
  const rivals = find(all, "ev_tourapi_same_period");
  const holdout = find(all, "ev_daily_region_holdout");
  const rivalCount = rivals?.numeric_value;
  const sentences = [SEASON_TEXT[role][level]].filter(Boolean);
  if (rivalCount !== undefined) {
    if (rivalCount === 0) sentences.push(role === "planner" ? "같은 기간 같은 지역에 등록된 다른 축제가 없어 주목받기 쉽습니다." : "같은 기간 같은 지역에 등록된 다른 축제는 없습니다.");
    else if (rivalCount >= 3) sentences.push(role === "planner" ? `같은 기간 같은 지역에 다른 축제가 ${rivalCount}건 있어 차별화가 필요합니다.` : `같은 기간 같은 지역에서 다른 축제 ${rivalCount}건이 함께 열립니다.`);
  }
  if (prior) sentences.push(`지난 회차 보고 방문객은 ${prior.display_value}입니다.`);
  if (prediction.confidence === "low") sentences.push("이 지역은 과거 예측 오차가 커서 참고용으로 보세요.");

  return (
    <section className="heung-diagnosis" aria-labelledby={`heung-diagnosis-${role}`}>
      <div className="heung-diagnosis-head"><h3 id={`heung-diagnosis-${role}`}>흥행 진단</h3></div>
      {sentences.length > 0 && <p className="heung-diagnosis-summary">{sentences.join(" ")}</p>}
      <dl>
        <div><dt>방문 시기</dt><dd>{demand ? demand.display_value : LEVEL_LABELS[level] ?? "판단할 자료 부족"}</dd></div>
        <div><dt>지난 회차 규모</dt><dd>{prior ? `${prior.display_value} · 문체부` : "문체부 보고 실적 없음(신규이거나 보고되지 않은 축제)"}</dd></div>
        <div><dt>같은 기간 축제</dt><dd>{rivals ? `${rivals.display_value} · 출처 ⓒ한국관광공사` : "확인하지 못함"}</dd></div>
        <div><dt>예측 신뢰도</dt><dd>{CONFIDENCE_LABELS[prediction.confidence]}{holdout ? ` · 과거 오차 ${holdout.display_value}` : ""}</dd></div>
      </dl>
      <small>이미 확인한 근거를 묶은 해석이며 축제 관람객 수 예측이 아닙니다.</small>
    </section>
  );
}
