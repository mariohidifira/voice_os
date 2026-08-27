import { defineConfig, devices } from "@playwright/test";

const externalServer = process.env.PLAYWRIGHT_EXTERNAL_SERVER === "1";
const localBaseUrl = "http://localhost:3100";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? localBaseUrl;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], permissions: ["microphone"] },
    },
  ],
  webServer: externalServer
    ? undefined
    : {
        command: "npm run dev -- --port 3100",
        url: `${localBaseUrl}/login`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          APP_ENV: "dev",
          APP_BASE_URL: localBaseUrl,
          AUTH_URL: localBaseUrl,
          AUTH_TRUST_HOST: "true",
          AUTH_SECRET: "dev-secret-change-me-at-least-32-bytes",
          DATABASE_URL: "postgresql://voiceos:voiceos@127.0.0.1:5432/voiceos",
          EMAIL_MOCK_URL: "http://127.0.0.1:9000/email",
          API_INTERNAL_URL: "http://127.0.0.1:8005",
          JWT_ISSUER: "voiceos",
          JWT_AUDIENCE: "voiceos-api",
        },
      },
});
