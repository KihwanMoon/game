/**
 * Playwright 설정 — 실제 브라우저로 핵심 루프를 클릭해 보는 e2e (M3 실증).
 *
 * 포트가 8090 이 아닌 이유: 배포 컨테이너(`game-frontend-1`)가 호스트 8090 을 잡고 있고,
 * Cloudflare Tunnel 이 거기로 직접 들어온다(deploy/README.md). e2e 를 돌리려고 그것을
 * 내리면 공개 도메인이 그동안 죽는다. 그래서 개발 서버만 다른 포트로 띄운다.
 *
 * `reuseExistingServer` 로 이미 떠 있는 서버를 그대로 쓴다 — 붙였다 뗐다 하는 시간이
 * 전체 실행 시간을 지배한다.
 */
import { defineConfig, devices } from '@playwright/test'

const PORT = 5199
const BASE_URL = `http://127.0.0.1:${String(PORT)}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    viewport: { width: 1600, height: 1000 },
    trace: 'off',
    screenshot: 'off',
  },
  // `devices['Desktop Chrome']` 은 1280×720 을 강제한다. 그 폭에서는 사후 분석의 로그 열이
  // 117px 짜리 조각으로 눌리므로(실측), 기본 스크린샷은 디자인이 상정한 데스크톱 폭으로
  // 찍는다. 좁은 폭의 거동은 `viewport.spec.ts` 가 따로 본다.
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 1000 } } },
  ],
  webServer: {
    command: `npx vite --port ${String(PORT)} --host 127.0.0.1`,
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
