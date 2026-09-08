import type { Page } from "@playwright/test";
export async function mockSession(page: Page, role: "planner" | "visitor") {
  await page.route("**/api/v1/auth/session", route => route.fulfill({
    json: { user: { id: "usr_e2e", name: "테스트", role, provider: "mock" }, mode: "mock" },
  }));
  await page.route("**/api/v1/planner/publications", route => route.fulfill({ json: [] }));
}
