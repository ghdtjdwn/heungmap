import { expect, test } from "@playwright/test";

test("responsive 소개→로그인→역할 선택→전환→로그아웃→재로그인", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /우리의 다음 흥/ })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("welcome.png"), fullPage: true });
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page).toHaveURL(/onboarding/);
  await expect(page.getByRole("button", { name: /기획자로 시작/ })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("roles.png"), fullPage: true });
  await page.getByRole("button", { name: /기획자로 시작/ }).click();
  await expect(page).toHaveURL(/\/planner$/);
  await page.reload();
  await expect(page.getByRole("button", { name: "사용자 모드로" })).toBeVisible();
  await page.getByRole("button", { name: "사용자 모드로" }).click();
  await expect(page).toHaveURL(/\/visitor$/);
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page).toHaveURL(/\/visitor$/);
  await page.getByRole("button", { name: "기획자 모드로" }).click();
  await expect(page).toHaveURL(/\/planner$/);
});

test("비로그인 기획 경로는 소개 페이지로 돌아간다", async ({ page }) => {
  await page.goto("/planner/new");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("button", { name: "로그인", exact: true })).toBeVisible();
});

test("실제 로컬 API로 기획 행사 공개→사용자 탐색→공개 철회", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("button", { name: /기획자로 시작/ }).click();
  const origin = new URL(page.url()).origin;
  const payload = {
    contract_version: "0.1.0", client_request_id: crypto.randomUUID(),
    event_draft: {
      event_id: "evt_planner_" + crypto.randomUUID().replaceAll("-", "_"),
      working_title: "공개 연결 검증 축제", planner_type: "independent_planner", planning_stage: "idea",
      event_type: "festival", purpose: "community", theme_keywords: ["음악"],
      schedule_selection_mode: "fixed", start_date: "2026-10-10", end_date: "2026-10-12",
      region_selection_mode: "fixed", region: { area_code: "1", display_name: "서울" },
      venue: { name: "확정 장소", address: "서울" }, indoor_outdoor: "outdoor",
      target_audience: ["young_adult"], ticket_type: "free", fixed_constraints: [],
    }, requested_outputs: ["prediction", "nearby_places", "rule_recommendations"],
  };
  // Browser context request shares the HttpOnly session; no fixture replaces these endpoints.
  const api = page.request;
  const analysisResponse = await api.post("/api/v1/planner/analyses", { data: payload, headers: { Origin: origin } });
  expect(analysisResponse.ok()).toBeTruthy();
  const analysis = await analysisResponse.json();
  const user = (await (await api.get("/api/v1/auth/session")).json()).user;
  await page.evaluate(({ analysis, user, payload }) => {
    localStorage.setItem("heungmap.planner.drafts.v1." + user.id, JSON.stringify([{
      id: "publication-e2e", event: payload.event_draft, analysis, details: {},
      status: "analyzed", current_step: 6, version: 1, history: [],
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    }]));
  }, { analysis, user, payload });
  await page.goto("/planner/result?draft=publication-e2e");
  await page.getByLabel("공개용 행사 소개").fill("누구나 즐기는 음악축제");
  await page.getByLabel("공개할 정보와 장소 정보를 확인했습니다.").check();
  await page.getByRole("button", { name: "행사 공개", exact: true }).click();
  await expect(page.getByText("사용자 목록에 공개했습니다.")).toBeVisible();
  const eventId = payload.event_draft.event_id;
  try {
    await page.getByRole("button", { name: "사용자 모드로" }).click();
    await page.goto("/visitor?view=calendar&start_date=2026-10-01&end_date=2026-10-31&query=공개 연결 검증");
    await expect(page.getByRole("link", { name: "공개 연결 검증 축제" }).first()).toBeVisible();
    await page.getByRole("link", { name: "공개 연결 검증 축제" }).first().click();
    await expect(page.getByRole("heading", { name: "공개 연결 검증 축제" })).toBeVisible();
    await expect(page.getByText("누구나 즐기는 음악축제")).toBeVisible();
    const prediction = await (await api.get("/api/v1/events/" + eventId + "/prediction")).json();
    expect(prediction.prediction_id).toBe(analysis.prediction.prediction_id);
    expect((await request.delete("/api/v1/planner/publications/" + eventId, { headers: { Origin: origin } })).status()).toBe(401);
  } finally {
    expect((await api.delete("/api/v1/planner/publications/" + eventId, { headers: { Origin: origin } })).ok()).toBeTruthy();
  }
  expect((await api.get("/api/v1/events/" + eventId)).status()).toBe(404);
});
