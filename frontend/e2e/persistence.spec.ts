/**
 * 새로고침해도 짠 것이 남는가 (M3 — 저장, `frontend/src/storage/`).
 *
 * 저장 결함은 **새로고침을 해 봐야 드러난다.** 단위 테스트는 가짜 localStorage 를 넣고
 * 부르는 함수 하나를 보지만, 실제로 확인해야 하는 것은 디바운스(400ms)와 pagehide 플러시,
 * 그리고 다시 부팅한 앱이 그 글자를 읽어 같은 화면을 세우는가 하는 한 줄기다.
 *
 * 공유 코드도 여기서 본다. 브라우저에서 코드를 굽고 그 코드를 다시 읽어 같은 규칙표가
 * 서면, 코드가 기기 사이를 건널 수 있다는 뜻이다 (파이썬과의 상호운용은 vitest·pytest 가
 * 골든으로 따로 본다).
 */
import { expect, test } from '@playwright/test'

import { attachDiagnostics, checkNoBrowserErrors, openFreshApp, saveShot } from './fixtures'

/** 저장 디바운스(400ms)보다 넉넉히 기다린다. */
const SAVE_SETTLE_MS = 900

test.describe('저장', () => {
  test('h 편집한 규칙표·방·시드가 새로고침 뒤에도 남는다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await openFreshApp(page)

    // 규칙 하나를 더하고, 첫 규칙의 임계값을 알아볼 수 있는 수로 바꾼다.
    await page.getByRole('button', { name: '주변 8칸 중 이동 가능 칸 수' }).click()
    await expect(page.locator('.rule-row')).toHaveCount(5)
    await page.locator('.rule-row').nth(0).getByLabel('조건 1 우변 값').fill('42')
    await page.selectOption('#launch-room', 'pillars')
    await page.fill('#launch-seed', '7')

    await page.waitForTimeout(SAVE_SETTLE_MS)
    await page.reload()

    await expect(page.getByRole('heading', { name: '규칙 에디터' })).toBeVisible()
    await expect(page.locator('.rule-row')).toHaveCount(5)
    await expect(page.locator('.rule-row').nth(0).getByLabel('조건 1 우변 값')).toHaveValue('42')
    await expect(page.locator('.rule-row').nth(4)).toContainText('주변 8칸 중 이동 가능 칸 수')
    await expect(page.locator('#launch-room')).toHaveValue('pillars')
    await expect(page.locator('#launch-seed')).toHaveValue('7')

    checkNoBrowserErrors(diagnostics)
  })

  test('프리셋 슬롯과 공유 코드가 브라우저에서 왕복한다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await openFreshApp(page)

    await page.fill('#library-name', '근접 압박 사본')
    await page.getByRole('button', { name: '저장' }).click()
    await expect(page.getByText('1 / 8')).toBeVisible()

    // 코드를 굽는다. 규칙표를 부순 뒤 그 코드로 되살린다.
    await page.getByRole('button', { name: '내보내기' }).click()
    const code = await page.locator('#library-code').inputValue()
    expect(code.startsWith('v2:'), `공유 코드 형식: ${code.slice(0, 12)}`).toBe(true)

    await page.locator('.rule-row').first().getByTitle('삭제 (Alt+Backspace)').click()
    await page.locator('.rule-row').first().getByTitle('삭제 (Alt+Backspace)').click()
    await expect(page.locator('.rule-row')).toHaveCount(2)

    await page.fill('#library-code', code)
    await page.getByRole('button', { name: '읽어 오기' }).click()
    await expect(page.locator('.rule-row')).toHaveCount(4)
    await expect(page.getByText('코드를 읽어 편집기에 실었다')).toBeVisible()
    await saveShot(page, '05-library')

    // 슬롯은 새로고침을 건넌다.
    await page.waitForTimeout(SAVE_SETTLE_MS)
    await page.reload()
    await expect(page.getByText('근접 압박 사본')).toBeVisible()
    await page.getByRole('button', { name: '불러오기' }).click()
    await expect(page.locator('.rule-row')).toHaveCount(4)

    checkNoBrowserErrors(diagnostics)
  })
})
