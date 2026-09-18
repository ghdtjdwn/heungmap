import type { Prediction } from "./types";

export function predictionValue(prediction: Prediction): number | undefined {
  if (prediction.status !== "available") return undefined;
  const metric = prediction.primary_metric;
  return metric.metric_name === "relative_demand_score" ? metric.value : metric.p50;
}

export function predictionLabel(prediction: Prediction): string {
  if (prediction.status !== "available") return "수요 예측 불가";
  if (prediction.prediction_type !== "regional_visit_demand") return "상대 수요 점수";
  return prediction.primary_metric.unit === "percent_change" ? "지역 방문수요 증감률" : "행사기간 지역 방문자-일";
}

export function predictionSummary(prediction: Prediction): string {
  if (prediction.status !== "available") return prediction.message;
  const metric = prediction.primary_metric;
  if (metric.metric_name === "relative_demand_score") return `상대 수요점수 ${metric.value}/100${prediction.is_mock ? " (학습 모델 연결 전 mock)" : ""}`;
  const unit = metric.unit === "percent_change" ? "%" : " 방문자-일";
  const format = (value: number) => metric.unit === "people" ? Math.round(value).toLocaleString("ko-KR") : value.toFixed(1);
  const day = (value: string) => { const [, month, date] = value.split("-"); return `${Number(month)}/${Number(date)}`; };
  const period = prediction.target_start_date === prediction.target_end_date ? day(prediction.target_start_date) : `${day(prediction.target_start_date)}~${day(prediction.target_end_date)}`;
  return `${prediction.target_region?.display_name ?? "대상 지역"} 지역 방문수요 ${format(metric.p50)}${unit} · 예측 범위 ${format(metric.p10)}~${format(metric.p90)}${unit} · 대상 기간 ${period}`;
}

export function predictionNotice(prediction: Prediction): string {
  if (prediction.status !== "available") return prediction.message;
  return prediction.is_mock
    ? "모델 입출력 연결을 확인하기 위한 규칙 기반 mock 상대지수이며 실제 행사 관람객 수가 아닙니다."
    : "행사기간 시군구 전체의 방문자-일 예측이며 특정 행사 관람객 수, 고유 방문자, 행사로 인한 추가 효과나 혼잡도는 아닙니다.";
}

const DEMAND_LEVEL_LABELS: Record<string, string> = { low: "낮음", medium: "보통", high: "높음", very_high: "매우 높음" };

export function demandLevelText(prediction: Prediction): string | undefined {
  if (prediction.status !== "available" || prediction.is_mock) return undefined;
  const label = DEMAND_LEVEL_LABELS[prediction.indicators?.congestion_level ?? ""];
  return label ? `평소 대비 지역 방문수요: ${label} (최근 1년 이 지역 관측 분포 기준, 현장 혼잡도 아님)` : undefined;
}
