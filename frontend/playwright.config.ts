import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.HEUNGMAP_E2E_BASE_URL;
const baseURL = externalBaseURL ?? "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure" },
  webServer: externalBaseURL ? undefined : [{
    command: (process.platform === "win32" ? "..\\.venv\\Scripts\\python.exe" : "../.venv/bin/python") + " -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8100",
    env: { HEUNGMAP_ENV: "development", HEUNGMAP_AUTH_MODE: "mock", HEUNGMAP_PUBLIC_ORIGIN: baseURL,
      HEUNGMAP_DB_PATH: "../data/e2e.sqlite3", TOURAPI_SERVICE_KEY: "", KAKAO_REST_API_KEY: "", LLM_PROVIDER: "disabled" },
    url: "http://127.0.0.1:8100/api/v1/health", reuseExistingServer: false, timeout: 30_000,
  }, {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    env: { HEUNGMAP_SKIP_ROOT_ENV: "true", HEUNGMAP_BACKEND_URL: "http://127.0.0.1:8100" },
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
  }],
  projects: [
    { name: "desktop-chrome", use: { ...devices["Desktop Chrome"], channel: "chrome" } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"], channel: "chrome" }, grep: /responsive/ },
  ],
});
