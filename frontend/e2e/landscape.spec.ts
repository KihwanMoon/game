/**
 * 가로 모바일(844×390)에서 실제로 2열이 서고 도면이 잘리지 않는가 — 명세 B.
 *
 * 단위 테스트는 토큰과 선언을 읽을 뿐이다. **미디어쿼리를 평가하고 격자를 실제로 재는
 * 것은 브라우저**이고, 이 배치에서 가장 쉽게 깨지는 것이 높이(390px)라 실측이 필요하다.
 * 상단 40 + 하단 40 을 빼면 본문이 310px 이고 도면이 306px 를 쓴다 — 남는 자리가 4px 다.
 */
import { expect, test } from '@playwright/test'

import { attachDiagnostics, checkNoBrowserErrors, saveShot } from './fixtures'

/** 명세 B 가 기준으로 삼은 화면. */
const LANDSCAPE = { width: 844, height: 390 } as const

/** 도면 격자와 셀. 토큰 표(design/README.md)와 같은 값이다. */
const PLAN_COLS = 12
const PLAN_ROWS = 9
const CELL = 32

test.describe('가로 모바일 전투 화면', () => {
  test.use({ viewport: LANDSCAPE })

  test('2열이 서고 도면 12×9 가 잘리지 않는다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.selectOption('#launch-room', 'corridor')
    await page.fill('#launch-seed', '1')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle--landscape')).toBeVisible()

    // 2열이다 — 도면 열과 340px 시트 열. 세로의 배속바·상태줄은 없다.
    await expect(page.locator('.battle-ls__body')).toBeVisible()
    await expect(page.locator('.battle__speed-bar')).toHaveCount(0)
    await expect(page.locator('.battle__status')).toHaveCount(0)
    const panel = await page.locator('.battle-ls__panel').boundingBox()
    expect(Math.round(panel?.width ?? 0)).toBe(340)

    // 도면은 12×9 전체를 유지하고 셀만 32 로 줄어든다.
    const canvas = await page.locator('.battle__col--plan canvas').boundingBox()
    expect(Math.round(canvas?.width ?? 0)).toBe(PLAN_COLS * CELL)
    expect(Math.round(canvas?.height ?? 0)).toBe(PLAN_ROWS * CELL)

    // **도면 칸은 넘치지도 스크롤되지도 않는다.** 넘치면 도면의 아래가 잘린다.
    const planOverflow = await page.evaluate(() => {
      const node = document.querySelector('.battle__col--plan')
      if (node === null) {
        return { x: 1, y: 1 }
      }
      return { x: node.scrollWidth - node.clientWidth, y: node.scrollHeight - node.clientHeight }
    })
    expect(planOverflow, '도면 칸의 넘침(px)').toEqual({ x: 0, y: 0 })

    // 문서 자체도 가로·세로로 밀리지 않는다.
    const doc = await page.evaluate(() => ({
      x: document.documentElement.scrollWidth,
      y: document.documentElement.scrollHeight,
    }))
    expect(doc.x).toBe(LANDSCAPE.width)
    expect(doc.y).toBe(LANDSCAPE.height)

    // 시트 안도 넘치지 않는다. 스크롤하는 것은 본문 하나뿐이다.
    const sheetOverflow = await page.evaluate(() => {
      const node = document.querySelector('.battle__sheet')
      return node === null ? 1 : node.scrollHeight - node.clientHeight
    })
    expect(sheetOverflow, '시트의 세로 넘침(px)').toBe(0)

    // 규칙표와 로그가 한 시트를 나눠 쓴다 — 탭을 바꾸면 본문만 바뀌고 도면은 그대로다.
    await expect(page.locator('.ds-rule-table')).toBeVisible()
    await page.getByRole('tab', { name: /실행 로그/ }).click()
    await expect(page.locator('.ds-log')).toBeVisible()
    await expect(page.locator('.ds-rule-table')).toHaveCount(0)
    const after = await page.locator('.battle__col--plan canvas').boundingBox()
    expect(Math.round(after?.width ?? 0)).toBe(PLAN_COLS * CELL)

    await page.getByRole('tab', { name: /규칙표/ }).click()
    await saveShot(page, '08-battle-landscape')

    checkNoBrowserErrors(diagnostics)
  })
})
