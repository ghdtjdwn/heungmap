import { chromium } from "@playwright/test";

const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage();
try {
  const session = await (await page.request.get("http://localhost:3000/api/v1/auth/session")).json();
  if (session.mode !== "mock") throw new Error("이 smoke는 개발용 mock 로그인에서만 실행합니다.");
  await page.goto("http://localhost:3000");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("button", { name: /기획자로 시작/ }).click();
  await page.route("**/api/v1/planner/recommendations", (route) => route.fulfill({
    status: 503,
    contentType: "application/problem+json",
    body: JSON.stringify({ detail: "지도 smoke에서는 LLM을 실행하지 않습니다.", retryable: false }),
  }));
  await page.goto("http://localhost:3000/planner/new?sample=independent");
  for (let index = 0; index < 4; index += 1) {
    await page.getByRole("button", { name: "다음" }).click();
  }
  await page.getByRole("textbox", { name: "장소명" }).fill("문화비축기지");
  await page.getByRole("button", { name: "관광정보 검색" }).click();
  await page.getByRole("button", { name: /문화비축기지 서울/ }).first().click();
  await page.getByRole("textbox", { name: "주소" }).fill("서울 마포구 증산로 87");
  await page.getByRole("button", { name: "주소 찾기" }).click();
  await page.getByRole("button", { name: /서울특별시 마포구 증산로 87|서울 마포구 증산로 87/ }).first().click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "분석·보고서 생성" }).click();
  await page.waitForURL(/\/planner\/result\?draft=/, { timeout: 30_000 });
  await page.waitForFunction(() => Boolean(window.kakao?.maps), undefined, { timeout: 15_000 });
  await page.locator(".map-canvas:not(.hidden)").waitFor({ state: "visible", timeout: 15_000 });
  const result = await page.locator(".map-canvas").evaluate((element) => ({
    kakao_sdk_loaded: Boolean(window.kakao?.maps),
    map_visible: !element.classList.contains("hidden"),
    canvas_children: element.childElementCount,
  }));
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
}
