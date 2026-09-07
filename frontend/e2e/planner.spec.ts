import { expect, Page, test } from "@playwright/test";

function analysisResponse(body: { event_draft: Record<string, unknown> }) {
  const event = body.event_draft;
  const now = "2026-09-06T12:00:00+09:00";
  return {
    analysis_id: `ana_${String(event.event_id)}`,
    contract_version: "0.1.0",
    request_snapshot: event,
    prediction: {
      status: "available", prediction_id: "pred_e2e", event_id: event.event_id,
      prediction_type: "relative_demand_score", as_of: now,
      target_start_date: event.start_date ?? "2026-10-01", target_end_date: event.end_date ?? "2026-10-01",
      target_region: event.region, primary_metric: { metric_name: "relative_demand_score", unit: "index_0_100", value: 58 },
      indicators: { demand_score: 58, congestion_level: "medium", ticket_demand_level: "unknown" },
      confidence: "low", data_sufficiency: "limited", method: "rules", model_version: "mock-model-interface-0.1",
      factors: [{ factor_id: "factor_e2e", label: "입력 완성도", direction: "up", importance: 4, explanation: "입력 조건을 확인했습니다.", evidence_refs: ["ev_event"] }],
      evidence: [], sources: [{ source_id: "src_model", source_type: "heungmap_model", provider_name: "흥할지도", dataset_name: "규칙 mock", retrieved_at: now }],
      limitations: ["지역 상대지수이며 특정 축제 실제 관람객 수가 아닙니다."], out_of_distribution: true, fallback_used: true, created_at: now, is_mock: true,
    },
    nearby_places: event.venue && (event.venue as { coordinates?: unknown }).coordinates ? {
      status: "available", radius_m: 5000, is_mock: false,
      items: [{ place_id: "place_1", place_type: "tourist_attraction", name: "가상 관광지", address: "서울", coordinates: { latitude: 37.57, longitude: 126.89 }, distance_m: 320, sources: [{ source_id: "src_tour", source_type: "tourapi", provider_name: "한국관광공사", dataset_name: "locationBasedList2", retrieved_at: now }] }],
    } : { status: "unavailable", reason_code: "missing_coordinates", message: "장소 좌표를 입력하면 확인할 수 있습니다.", retryable: false, is_mock: false },
    evidence: [{ evidence_id: "ev_event", value_type: "user_input", label: "행사 입력", display_value: "입력됨", source_refs: [] }],
    rule_recommendations: [{ recommendation_id: "rec_1", category: "venue", priority: "high", title: "장소를 확인하세요", action: "운영자에게 확인합니다.", reason: "공식 정보가 필요합니다.", evidence_refs: ["ev_event"], requires_human_review: true }],
    meta: { contract_version: "0.1.0", generated_at: now, request_id: "req_e2e" },
  };
}

function recommendationResponse(alternatives: number) {
  const now = "2026-09-06T12:00:01+09:00";
  return {
    recommendation: {
      schema_version: "1.0", prompt_version: "planner-recommendation-1.0", generation_mode: "llm", generated_at: now,
      executive_summary: "입력 근거에 따라 장소 확인을 우선합니다.",
      priorities: [{ id: "p1", priority: "high", category: "venue", title: "장소를 확인하세요", action: "운영자에게 확인합니다.", reason: "공식 정보가 필요합니다.", evidence_refs: ["ev_event"], assumptions: [], predicted_impact: "불확실성을 줄입니다.", confidence: "medium", cost_level: "unknown", difficulty: "needs_review", deadline: null, dependencies: [], risks: [], requires_human_review: true }],
      alternatives: Array.from({ length: alternatives }, (_, index) => ({ id: `a${index}`, title: `대안 ${index + 1}`, changes: ["확인 순서를 조정합니다."], verify: ["사람이 검토합니다."] })),
      roadmap: [{ phase: "지금", actions: ["공식 정보를 확인합니다."] }], missing_information: ["공식 수용인원"], limitations: ["사람 검토가 필요합니다."],
    },
    meta: { contract_version: "0.1.0", generated_at: now, request_id: "llm_e2e", provider: "ollama", model: "qwen3.5:9b", prompt_version: "planner-recommendation-1.0" },
  };
}

async function mockApis(page: Page, failures: Set<string> = new Set()) {
  await page.route("**/api/v1/planner/analyses", async (route) => {
    if (failures.has("model")) return route.fulfill({ status: 503, contentType: "application/problem+json", body: JSON.stringify({ detail: "모델을 사용할 수 없습니다.", retryable: false }) });
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(analysisResponse(body)) });
  });
  await page.route("**/api/v1/planner/recommendations", async (route) => {
    if (failures.has("ollama")) return route.fulfill({ status: 503, contentType: "application/problem+json", body: JSON.stringify({ detail: "Ollama를 사용할 수 없습니다.", retryable: true }) });
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(recommendationResponse(body.requested_alternatives)) });
  });
  await page.route("**/api/v1/venues/search?**", async (route) => route.fulfill(failures.has("tourapi") ? { status: 429, contentType: "application/problem+json", body: JSON.stringify({ detail: "TourAPI 호출 한도에 도달했습니다.", code: "UPSTREAM_QUOTA_EXCEEDED" }) } : { status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ venue: { venue_id: "venue_1", name: "문화비축기지", address: "서울 마포구 증산로 87", coordinates: { latitude: 37.57, longitude: 126.89 } }, category: "문화시설", content_type_id: "14", source: { source_id: "src_venue", source_type: "tourapi", provider_name: "한국관광공사", dataset_name: "searchKeyword2", retrieved_at: "2026-09-06T12:00:00+09:00" } }], meta: { contract_version: "0.1.0", generated_at: "2026-09-06T12:00:00+09:00", request_id: "venue" } }) }));
  await page.route("**/api/v1/addresses/search?**", async (route) => route.fulfill(failures.has("kakao") ? { status: 504, contentType: "application/problem+json", body: JSON.stringify({ detail: "Kakao Local 응답 시간이 초과됐습니다.", code: "UPSTREAM_TIMEOUT" }) } : { status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ address_name: "서울 마포구 증산로 87", road_address_name: "서울 마포구 증산로 87", building_name: "문화비축기지", coordinates: { latitude: 37.57, longitude: 126.89 }, source: { source_id: "src_address", source_type: "other_public", provider_name: "카카오", dataset_name: "주소 검색", retrieved_at: "2026-09-06T12:00:00+09:00" } }], meta: { contract_version: "0.1.0", generated_at: "2026-09-06T12:00:00+09:00", request_id: "address" } }) }));
}

async function reachStep(page: Page, step: number, sample = "large") {
  await page.goto(`/planner/new?sample=${sample}`);
  for (let index = 0; index < step; index += 1) await page.getByRole("button", { name: "다음" }).click();
}

async function analyzeSample(page: Page, sample = "large") {
  await reachStep(page, 6, sample);
  await page.getByRole("button", { name: "분석·보고서 생성" }).click();
  await expect(page).toHaveURL(/\/planner\/result\?draft=/);
}

test.beforeEach(async ({ page }) => { await mockApis(page); await page.goto("/planner"); await page.evaluate(() => localStorage.clear()); });

test("대형·소규모 sample 분석과 Ollama 구조화 결과", async ({ page }) => {
  for (const sample of ["large", "independent"]) {
    await analyzeSample(page, sample);
    await expect(page.getByText("LLM REPORT")).toBeVisible();
    await expect(page.getByText("실제 행사 관람객 수가 아닙니다.")).toBeVisible();
    await expect(page.getByText("지도 위치 미정")).toBeVisible();
  }
});

test("TourAPI 장소와 Kakao 주소 선택, 미입력 fallback", async ({ page }) => {
  await reachStep(page, 4, "independent");
  await page.getByRole("textbox", { name: "장소명" }).fill("문화비축기지");
  await page.getByRole("button", { name: "관광정보 검색" }).click();
  await page.getByRole("button", { name: /문화비축기지 서울/ }).click();
  await page.getByRole("textbox", { name: "주소" }).fill("서울 마포구");
  await page.getByRole("button", { name: "주소 찾기" }).click();
  await page.getByRole("button", { name: /서울 마포구 증산로/ }).click();
  await expect(page.getByLabel("위도")).toHaveValue("37.57");
  await expect(page.getByLabel("공식 수용인원")).toHaveValue("");
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "분석·보고서 생성" }).click();
  await expect(page.getByText("지도 SDK 키 미설정")).toBeVisible();
});

test("validation 오류와 외부 API·Ollama fallback", async ({ page }) => {
  await reachStep(page, 4, "independent");
  await page.getByRole("textbox", { name: "장소명" }).fill("실패 장소");
  await page.unrouteAll();
  await mockApis(page, new Set(["tourapi", "kakao", "ollama"]));
  await page.getByRole("button", { name: "관광정보 검색" }).click();
  await expect(page.getByRole("status")).toContainText("호출 한도");
  await page.getByRole("textbox", { name: "주소" }).fill("서울 마포구");
  await page.getByRole("button", { name: "주소 찾기" }).click();
  await expect(page.getByText("Kakao Local 응답 시간이 초과됐습니다.")).toBeVisible();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByLabel("최소 예산").fill("200");
  await page.getByLabel("최대 예산").fill("100");
  await page.getByRole("button", { name: "다음" }).click();
  await expect(page.locator(".form-error")).toContainText("최대 예산");
  await page.getByLabel("최대 예산").fill("9000000");
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "분석·보고서 생성" }).click();
  await expect(page).toHaveURL(/\/planner\/result\?draft=/);
  await expect(page.getByText("RULE FALLBACK")).toBeVisible();
  await expect(page.getByText(/Ollama를 사용할 수 없습니다/)).toBeVisible();
});

test("수정 version·What-if·localStorage 복구", async ({ page }) => {
  await analyzeSample(page, "independent");
  await page.reload();
  await expect(page.getByText("분석 v1")).toBeVisible();
  await page.getByRole("button", { name: "대안 비교" }).click();
  await page.getByRole("button", { name: "규모 20% 축소" }).click();
  await page.getByRole("button", { name: "변경안 분석" }).click();
  await expect(page.getByText("변경안 확인 항목")).toBeVisible();
  await page.getByRole("link", { name: "입력 수정" }).click();
  await expect(page.getByRole("heading", { name: "검토·분석" })).toBeVisible();
  await page.getByRole("button", { name: "분석·보고서 생성" }).click();
  await expect(page.getByText("분석 v2")).toBeVisible();
});

test("Markdown·JSON download와 PDF 인쇄 진입", async ({ page }) => {
  await analyzeSample(page);
  const markdown = page.waitForEvent("download");
  await page.getByRole("button", { name: "보고서 저장" }).click();
  expect((await markdown).suggestedFilename()).toMatch(/report\.md$/);
  await page.getByRole("button", { name: "근거·출처" }).click();
  const json = page.waitForEvent("download");
  await page.getByRole("button", { name: "전체 JSON 저장" }).click();
  expect((await json).suggestedFilename()).toMatch(/analysis\.json$/);
  await page.evaluate(() => { window.print = () => document.body.setAttribute("data-print-entered", "true"); });
  await page.getByRole("button", { name: "PDF로 인쇄" }).click();
  await expect(page.locator("body")).toHaveAttribute("data-print-entered", "true");
});

test("responsive 접근성·키보드 focus", async ({ page }) => {
  await reachStep(page, 1, "independent");
  await expect(page.getByRole("heading", { name: "행사 목표" })).toBeVisible();
  const next = page.getByRole("button", { name: "다음" });
  await next.focus();
  await expect(next).toBeFocused();
  await expect(page.locator("label").filter({ hasText: "테마 키워드" })).toBeVisible();
});
