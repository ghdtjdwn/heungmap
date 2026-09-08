import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.HEUNGMAP_E2E_BASE_URL;
const baseURL = externalBaseURL ?? "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure" },
  webServer: externalBaseURL ? undefined : {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    env: { HEUNGMAP_SKIP_ROOT_ENV: "true" },
    url: `${baseURL}/planner`,
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    { name: "desktop-chrome", use: { ...devices["Desktop Chrome"], channel: "chrome" } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"], channel: "chrome" }, grep: /responsive/ },
  ],
});
