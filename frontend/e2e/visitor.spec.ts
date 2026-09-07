import { expect, Page, test } from "@playwright/test";

const now = "2026-09-07T12:00:00+09:00";
const event = {
  event_id: "evt_tourapi_123",
  origin: "tourapi",
  visibility: "public",
  title: "서울 테스트 축제",
  event_type: "festival",
  event_status: "scheduled",
  start_date: "2026-10-10",
  end_date: "2026-10-12",
  region: { area_code: "1", sigungu_code: "13", display_name: "서울 마포구" },
  venue: { name: "테스트 광장", address: "서울 마포구 월드컵로", coordinates: { latitude: 37.56, longitude: 126.9 } },
  description: "한국관광공사 TourAPI 행사 정보를 사용하는 테스트 축제입니다.",
  homepage_url: "https://example.com/festival",
  sources: [{ source_id: "src_tourapi_123", source_type: "tourapi", provider_name: "한국관광공사", dataset_name: "국문 관광정보 서비스", source_record_id: "123", retrieved_at: now }],
  data_quality: { completeness: "high", warnings: [], is_mock: false },
  updated_at: now,
};

async function mockVisitorApis(page: Page) {
  await page.route("**/api/v1/events/evt_tourapi_doesnotexist{,/nearby,/prediction}", async (route) => route.fulfill({
    status: 404,
    contentType: "application/problem+json",
    body: JSON.stringify({ status: 404, code: "EVENT_NOT_FOUND", detail: "존재하지 않거나 더 이상 제공되지 않는 행사입니다.", retryable: false }),
  }));
  await page.route("**/api/v1/events/evt_tourapi_123", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(event) }));
  await page.route("**/api/v1/events/evt_tourapi_123/nearby?**", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ event_id: event.event_id, radius_m: 3000, items: [{ place_id: "place_1", place_type: "tourist_attraction", name: "하늘공원", address: "서울 마포구", distance_m: 320, sources: event.sources }], meta: { contract_version: "0.1.0", generated_at: now, request_id: "nearby_e2e" } }),
  }));
  await page.route("**/api/v1/events/evt_tourapi_123/prediction", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ status: "available", prediction_id: "pred_e2e", event_id: event.event_id, prediction_type: "relative_demand_score", as_of: now, target_start_date: event.start_date, target_end_date: event.end_date, target_region: event.region, primary_metric: { metric_name: "relative_demand_score", unit: "index_0_100", value: 61 }, indicators: { demand_score: 61, congestion_level: "medium", ticket_demand_level: "unknown" }, confidence: "low", data_sufficiency: "limited", method: "rules", model_version: "mock-model-interface-0.1", factors: [{ factor_id: "weekend", label: "주말 포함", direction: "up", importance: 7, explanation: "행사 기간에 주말이 포함됩니다.", evidence_refs: [] }], evidence: [], sources: event.sources, limitations: ["이 점수는 자체 AI 모델 연결 전의 mock이며 실제 수요 예측이 아닙니다.", "지역 방문수요나 이 점수를 특정 행사 관람객 수로 해석할 수 없습니다."], out_of_distribution: true, fallback_used: true, created_at: now, is_mock: true }),
  }));
}

test.beforeEach(async ({ page }) => { await mockVisitorApis(page); });

test("방문객 행사 상세에서 주변 정보와 mock 수요 지표를 확인한다", async ({ page }) => {
  await page.goto("/visitor/evt_tourapi_123");
  await expect(page.getByRole("heading", { name: "서울 테스트 축제" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "주변 정보" })).toBeVisible();
  await expect(page.getByText("하늘공원")).toBeVisible();
  await expect(page.getByRole("heading", { name: "수요 지표" })).toBeVisible();
  await expect(page.getByText("실제 관람객 수가 아니라 상대적 수요 지수(mock)입니다.")).toBeVisible();
  await expect(page.getByText("한국관광공사", { exact: true }).last()).toBeVisible();
});

test("존재하지 않는 행사 안내와 목록 복귀 링크를 보여준다", async ({ page }) => {
  await page.goto("/visitor/evt_tourapi_doesnotexist");
  await expect(page.getByRole("heading", { name: "존재하지 않거나 종료된 행사입니다" })).toBeVisible();
  await expect(page.getByRole("link", { name: "축제 목록으로" })).toHaveAttribute("href", "/visitor");
});
