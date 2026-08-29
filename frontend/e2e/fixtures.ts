/**
 * e2e 공용 도구 — 진단 수집과 스크린샷.
 *
 * jsdom 테스트가 잡지 못하는 것을 잡으려고 만든 층이다. 마크업이 맞아도 실제 브라우저에서는
 * 토큰이 안 읽히거나(getComputedStyle 이 jsdom 에서 빈 문자열이다), canvas 가 안 그려지거나,
 * 자산 하나가 404 로 조용히 빠질 수 있다. 그래서 모든 시나리오가 **콘솔 에러·페이지 예외·
 * 실패한 요청 셋을 함께 수집하고 끝에서 0 인지 본다.** 화면이 그럴듯해 보인다는 것과
 * 아무것도 터지지 않았다는 것은 다른 사실이다.
 */
import { expect, type Page } from '@playwright/test'

/** 스크린샷을 두는 곳. 과업이 지정한 경로다. */
export const SHOT_DIR = 'e2e/screenshots'

/** 한 판이 실제로 돌아가는 것을 눈으로 확인할 만큼의 시간. 관전 배속 ×1 기준. */
export const WATCH_MS = 1200

/** 브라우저가 뱉은 것들. 비어 있어야 한다. */
export interface Diagnostics {
  readonly consoleErrors: string[]
  readonly pageErrors: string[]
  readonly failedRequests: string[]
}

/**
 * 페이지에 진단 수집기를 붙인다. `goto` 보다 먼저 불러야 첫 로드의 오류를 놓치지 않는다.
 *
 * @param page 대상 페이지.
 * @returns 수집 중인 목록들. 테스트가 끝날 때 읽는다.
 */
export function attachDiagnostics(page: Page): Diagnostics {
  const diagnostics: Diagnostics = { consoleErrors: [], pageErrors: [], failedRequests: [] }
  page.on('console', (message) => {
    if (message.type() === 'error') {
      diagnostics.consoleErrors.push(message.text())
    }
  })
  page.on('pageerror', (error) => {
    diagnostics.pageErrors.push(error.message)
  })
  page.on('requestfailed', (request) => {
    diagnostics.failedRequests.push(`${request.url()} — ${request.failure()?.errorText ?? '?'}`)
  })
  return diagnostics
}

/**
 * 수집된 진단이 전부 비었는지 본다.
 *
 * @param diagnostics `attachDiagnostics` 가 돌려준 목록.
 */
export function checkNoBrowserErrors(diagnostics: Diagnostics): void {
  expect(diagnostics.pageErrors, '페이지 예외').toEqual([])
  expect(diagnostics.consoleErrors, '콘솔 에러').toEqual([])
  expect(diagnostics.failedRequests, '실패한 요청').toEqual([])
}

/**
 * 빈 저장 상태에서 앱을 연다.
 *
 * localStorage 를 손으로 비우지 않는다. Playwright 는 테스트마다 새 브라우저 컨텍스트를
 * 주므로 저장은 이미 비어 있고, `addInitScript` 로 매번 비우면 **새로고침도 함께 비워져**
 * 저장 시나리오가 자기 자신을 무너뜨린다 (이 파일을 처음 쓸 때 실제로 그렇게 됐다).
 *
 * @param page 대상 페이지.
 */
export async function openFreshApp(page: Page): Promise<void> {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '규칙 에디터' })).toBeVisible()
}

/**
 * 스크린샷을 남긴다.
 *
 * @param page 대상 페이지.
 * @param name 파일 이름(확장자 없이).
 */
export async function saveShot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: `${SHOT_DIR}/${name}.png` })
}

/**
 * 판 하나를 끝까지 돌리고 판정 문구를 읽는다.
 *
 * @param page 전투 화면이 떠 있는 페이지.
 * @returns `승리`·`쓰러짐`·`시간 초과` 중 하나. 문구는 battle/outcomeText.ts 가 정한다.
 */
export async function runToOutcome(page: Page): Promise<string> {
  await page.getByRole('button', { name: '즉시' }).click()
  const label = page.locator('.battle__outcome')
  await expect(label).toBeVisible()
  return (await label.textContent()) ?? ''
}
