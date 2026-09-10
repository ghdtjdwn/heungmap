import { expect, Page, test } from "@playwright/test";
import { mockSession } from "./session-fixture";

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

const events = Array.from({ length: 21 }, (_, index) => ({
  ...event,
  event_id: `evt_tourapi_${123 + index}`,
  title: index === 20 ? "21번째 축제" : `서울 테스트 축제 ${index + 1}`,
  ...(index === 0 ? { start_date: "2026-09-30", end_date: "2026-10-02" } : {}),
  sources: event.sources.map((source) => ({ ...source, source_record_id: String(123 + index) })),
}));

async function mockVisitorApis(page: Page) {
  await page.addInitScript(() => {
    (window as typeof window & { __HEUNGMAP_E2E_KAKAO_MAP_KEY__?: string }).__HEUNGMAP_E2E_KAKAO_MAP_KEY__ = "heungmap-e2e-key";
  });
  await page.route("https://dapi.kakao.com/v2/maps/sdk.js?**", async (route) => route.fulfill({
    status: 200,
    contentType: "application/javascript",
    body: `
      window.__heungmapMapMetrics = { width: 0, height: 0, relayouts: 0, boundsUpdates: 0 };
      class HeungMapLatLng { constructor(latitude, longitude) { this.latitude = latitude; this.longitude = longitude; } }
      class HeungMapLatLngBounds { extend() {} }
      class HeungMapMap {
        constructor(container) {
          window.__heungmapMapMetrics.width = container.offsetWidth;
          window.__heungmapMapMetrics.height = container.offsetHeight;
        }
        relayout() { window.__heungmapMapMetrics.relayouts += 1; }
        setBounds() { window.__heungmapMapMetrics.boundsUpdates += 1; }
        setCenter() {}
      }
      class HeungMapMarker { setMap() {} setOpacity() {} setZIndex() {} }
      window.kakao = { maps: { load: (callback) => callback(), LatLng: HeungMapLatLng, LatLngBounds: HeungMapLatLngBounds, Map: HeungMapMap, Marker: HeungMapMarker, event: { addListener() {} } } };
    `,
  }));
  await page.route(/\/api\/v1\/events\?.*/, async (route) => {
    const url = new URL(route.request().url());
    const requestedPage = Number(url.searchParams.get("page") ?? "1");
    const pageSize = Number(url.searchParams.get("page_size") ?? "20");
    const start = (requestedPage - 1) * pageSize;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: events.slice(start, start + pageSize),
        page: requestedPage,
        page_size: pageSize,
        total_count: events.length,
        applied_filters: { sort: "start_date", page: requestedPage, page_size: pageSize },
        meta: { contract_version: "0.1.0", generated_at: now, request_id: `events_page_${requestedPage}` },
      }),
    });
  });
  await page.route(/\/api\/v1\/events\/evt_tourapi_doesnotexist(?:\/(?:nearby|prediction))?(?:\?.*)?$/, async (route) => route.fulfill({
    status: 404,
    contentType: "application/problem+json",
    body: JSON.stringify({ status: 404, code: "EVENT_NOT_FOUND", detail: "존재하지 않거나 더 이상 제공되지 않는 행사입니다.", retryable: false }),
  }));
  await page.route("**/api/v1/events/evt_tourapi_123", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(event) }));
  await page.route("**/api/v1/events/evt_tourapi_143", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(events[20]) }));
  await page.route("**/api/v1/events/evt_tourapi_123/nearby?**", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ event_id: event.event_id, radius_m: 3000, items: [{ place_id: "place_1", place_type: "tourist_attraction", name: "하늘공원", address: "서울 마포구", distance_m: null, sources: event.sources }], meta: { contract_version: "0.1.0", generated_at: now, request_id: "nearby_e2e" } }),
  }));
  await page.route("**/api/v1/events/evt_tourapi_143/nearby?**", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ event_id: events[20].event_id, radius_m: 3000, items: [], meta: { contract_version: "0.1.0", generated_at: now, request_id: "nearby_page_2" } }),
  }));
  await page.route("**/api/v1/events/evt_tourapi_123/prediction", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ status: "available", prediction_id: "pred_e2e", event_id: event.event_id, prediction_type: "relative_demand_score", as_of: now, target_start_date: event.start_date, target_end_date: event.end_date, target_region: event.region, primary_metric: { metric_name: "relative_demand_score", unit: "index_0_100", value: 61 }, indicators: { demand_score: 61, congestion_level: "medium", ticket_demand_level: "unknown" }, confidence: "low", data_sufficiency: "limited", method: "rules", model_version: "mock-model-interface-0.1", factors: [{ factor_id: "weekend", label: "주말 포함", direction: "up", importance: 7, explanation: "행사 기간에 주말이 포함됩니다.", evidence_refs: [] }], evidence: [], sources: event.sources, limitations: ["이 점수는 자체 AI 모델 연결 전의 mock이며 실제 수요 예측이 아닙니다.", "지역 방문수요나 이 점수를 특정 행사 관람객 수로 해석할 수 없습니다."], out_of_distribution: true, fallback_used: true, created_at: now, is_mock: true }),
  }));
  await page.route("**/api/v1/events/evt_tourapi_143/prediction", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ status: "unavailable", event_id: events[20].event_id, reason_code: "insufficient_data", message: "테스트 데이터가 부족합니다.", as_of: now, sources: [], limitations: ["E2E fixture"], retryable: false, is_mock: true }),
  }));
}

test.beforeEach(async ({ page }) => { await mockSession(page, "visitor"); await mockVisitorApis(page); });

test("방문객 행사 상세에서 주변 정보와 mock 수요 지표를 확인한다", async ({ page }) => {
  await page.goto("/visitor/evt_tourapi_123");
  await expect(page.getByRole("heading", { name: "서울 테스트 축제" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "주변 정보" })).toBeVisible();
  await expect(page.getByText("하늘공원")).toBeVisible();
  await expect(page.getByText("관광지 · 거리 미제공")).toBeVisible();
  await expect(page.getByRole("heading", { name: "수요 지표" })).toBeVisible();
  await expect(page.getByText("실제 관람객 수가 아니라 상대적 수요 지수(mock)입니다.")).toBeVisible();
  await expect(page.getByText("한국관광공사", { exact: true }).last()).toBeVisible();
});

test("21번째 이후 행사까지 URL 페이지 상태로 탐색한다", async ({ page }) => {
  await page.goto("/visitor?view=list");
  await expect(page.getByText("총 21건")).toBeVisible();
  await page.getByRole("button", { name: "다음 페이지" }).click();
  await expect(page).toHaveURL(/(?:\?|&)page=2(?:&|$)/);
  await page.reload();
  const lastCard = page.locator(".visitor-event-card").filter({ hasText: "21번째 축제" });
  await expect(lastCard).toBeVisible();
  await lastCard.getByRole("link", { name: "상세 보기 →" }).click();
  await expect(page.getByRole("heading", { name: "21번째 축제" })).toBeVisible();
});

test("표시된 크기로 Kakao 지도를 초기화하고 다시 배치한다", async ({ page }) => {
  await page.goto("/visitor?view=map");
  await expect(page.getByLabel("검색된 축제 위치 지도")).toBeVisible();
  await expect.poll(async () => page.evaluate(() => (window as typeof window & { __heungmapMapMetrics?: { relayouts: number } }).__heungmapMapMetrics?.relayouts ?? 0)).toBeGreaterThan(0);
  const metrics = await page.evaluate(() => (window as typeof window & { __heungmapMapMetrics: { width: number; height: number; relayouts: number; boundsUpdates: number } }).__heungmapMapMetrics);
  expect(metrics.width).toBeGreaterThan(0);
  expect(metrics.height).toBeGreaterThan(0);
  expect(metrics.boundsUpdates).toBeGreaterThan(0);
});

test("검색·날짜·지역 필터를 보기 전환 URL에 유지하고 지도에서 더 많은 행사를 요청한다", async ({ page }) => {
  await page.goto("/visitor?view=list");
  await page.getByLabel("축제명").fill("서울 축제");
  await page.getByLabel("시작일").fill("2026-10-01");
  await page.getByLabel("종료일").fill("2026-10-31");
  await page.getByLabel("지역").selectOption("1");
  await page.getByRole("button", { name: "검색", exact: true }).click();
  await expect(page).toHaveURL(/view=list/);
  await expect(page).toHaveURL(/query=%EC%84%9C%EC%9A%B8\+%EC%B6%95%EC%A0%9C/);
  await expect(page).toHaveURL(/start_date=2026-10-01/);
  await expect(page).toHaveURL(/end_date=2026-10-31/);
  await expect(page).toHaveURL(/region_code=1/);

  const mapRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/v1/events" && url.searchParams.get("page_size") === "100";
  });
  await page.getByRole("link", { name: "지도 보기" }).click();
  await mapRequest;
  await expect(page).toHaveURL(/view=map/);
  await expect(page).toHaveURL(/region_code=1/);
  await expect(page.getByRole("heading", { name: "지도로 넓게 보는 축제" })).toBeVisible();
  await expect(page.getByText("최대 100건을 한 지도에서 표시합니다")).toBeVisible();
  await page.locator(".map-point-list button").first().click();
  await expect(page).toHaveURL(/selected_event_id=evt_tourapi_123/);
  await expect(page.locator(".visitor-map-selection").getByText("서울 테스트 축제 1", { exact: true })).toBeVisible();
  await expect(page.locator(".visitor-map-selection").getByRole("link", { name: "상세 보기" })).toHaveAttribute("href", "/visitor/evt_tourapi_123");
});

test("달력 날짜 선택을 목록·지도·URL과 동기화하고 월 경계 다일 행사를 표시한다", async ({ page }) => {
  await page.goto("/visitor?view=calendar&start_date=2026-10-01&end_date=2026-10-31&region_code=1");

  const octoberFirst = page.locator('.calendar-day[data-date="2026-10-01"]');
  const octoberSecond = page.locator('.calendar-day[data-date="2026-10-02"]');
  await expect(octoberFirst.getByRole("link", { name: "서울 테스트 축제 1" })).toBeVisible();
  await expect(octoberSecond.getByRole("link", { name: "서울 테스트 축제 1" })).toBeVisible();

  const selectedDateRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/v1/events"
      && url.searchParams.get("start_date") === "2026-10-02"
      && url.searchParams.get("end_date") === "2026-10-02";
  });
  await page.getByRole("button", { name: "2026년 10월 2일 선택" }).click();
  await selectedDateRequest;
  await expect(page).toHaveURL(/start_date=2026-10-02/);
  await expect(page).toHaveURL(/end_date=2026-10-02/);
  await expect(page).toHaveURL(/region_code=1/);
  await expect(page.getByRole("button", { name: "2026년 10월 2일 선택" })).toHaveAttribute("aria-pressed", "true");

  await page.reload();
  await expect(page.getByRole("button", { name: "2026년 10월 2일 선택" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("link", { name: "목록 보기" }).click();
  await expect(page).toHaveURL(/view=list/);
  await expect(page).toHaveURL(/start_date=2026-10-02/);
  await page.getByRole("link", { name: "지도 보기" }).click();
  await expect(page).toHaveURL(/view=map/);
  await expect(page).toHaveURL(/end_date=2026-10-02/);

  await page.goBack();
  await expect(page).toHaveURL(/view=list/);
  await page.goBack();
  await expect(page).toHaveURL(/view=calendar/);
  await expect(page.getByRole("button", { name: "2026년 10월 2일 선택" })).toHaveAttribute("aria-pressed", "true");
});

test("responsive 방문자 목록과 큰 지도를 작은 화면에서도 탐색한다", async ({ page }) => {
  await page.goto("/visitor?view=list");
  const listBox = await page.getByLabel("검색된 축제 목록").boundingBox();
  const cardBox = await page.locator(".visitor-event-card").first().boundingBox();
  expect(listBox).not.toBeNull();
  expect(cardBox).not.toBeNull();
  if ((page.viewportSize()?.width ?? 0) <= 720) {
    expect(cardBox!.width).toBeGreaterThan(listBox!.width * 0.9);
  } else {
    expect(cardBox!.width).toBeLessThan(listBox!.width * 0.6);
  }

  await page.getByRole("link", { name: "지도 보기" }).click();
  const mapBox = await page.getByLabel("검색된 축제 위치 지도").boundingBox();
  expect(mapBox).not.toBeNull();
  expect(mapBox!.height).toBeGreaterThan(300);
  await expect(page.getByRole("navigation", { name: "축제 보기 방식" })).toBeVisible();
});

test("존재하지 않는 행사 안내와 목록 복귀 링크를 보여준다", async ({ page }) => {
  await page.goto("/visitor/evt_tourapi_doesnotexist");
  await expect(page.getByRole("heading", { name: "존재하지 않거나 종료된 행사입니다" })).toBeVisible();
  await expect(page.getByRole("link", { name: "축제 목록으로" })).toHaveAttribute("href", "/visitor");
});
