/**
 * 세로 모바일(390×844)에서 도면이 정말 고정인가, 시트만 바뀌는가 — 명세 A·D.
 *
 * 단위 테스트는 선언과 마크업을 읽을 뿐이다. **미디어쿼리를 평가하고 여섯 줄의 높이를
 * 실제로 재는 것은 브라우저**다. 이 배치에서 가장 쉽게 깨지는 것은 도면이 밀려 나가는
 * 것이고, 그것이 깨지면 "규칙을 보면서 유닛 위치를 계속 읽는다" 는 배치의 존재 이유가
 * 사라진다 — 화면은 여전히 그럴듯해 보이므로 눈으로는 잘 안 걸린다.
 *
 * 세로 골격은 44 + 44 + (270 + 14×2 + 테두리 2) + 34 + 시트 + 48 이고, 844 안에서
 * 시트가 남는 자리를 전부 가져간다.
 */
import { expect, test } from '@playwright/test'

import { attachDiagnostics, checkNoBrowserErrors, saveShot } from './fixtures'

/** 명세 A 가 기준으로 삼은 화면. */
const PORTRAIT = { width: 390, height: 844 } as const

/** 도면 격자와 셀. 토큰 표(design/README.md)와 같은 값이다. */
const PLAN_COLS = 12
const PLAN_ROWS = 9
const CELL = 30

/** 히트 영역의 하한. 손가락이 닿지 않는 조작부는 화면에 있어도 없는 것과 같다. */
const TAP_MIN = 44

test.describe('세로 모바일 전투 화면', () => {
  test.use({ viewport: PORTRAIT })

  test('도면은 고정이고 시트만 바뀐다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.selectOption('#launch-room', 'corridor')
    await page.fill('#launch-seed', '1')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle--portrait')).toBeVisible()

    // 문서는 어느 방향으로도 밀리지 않는다. 390×844 가 전부다.
    const doc = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
    }))
    expect(doc.scrollWidth).toBe(PORTRAIT.width)
    expect(doc.scrollHeight).toBe(PORTRAIT.height)

    // 도면은 12×9 전체를 유지하고 셀만 30 으로 줄어든다.
    const canvas = await page.locator('.battle__col--plan canvas').boundingBox()
    expect(Math.round(canvas?.width ?? 0)).toBe(PLAN_COLS * CELL)
    expect(Math.round(canvas?.height ?? 0)).toBe(PLAN_ROWS * CELL)

    // **도면 칸은 스크롤되지 않는다.** 내용이 칸을 넘지 않아야 성립한다.
    const planFits = await page.evaluate(() => {
      const el = document.querySelector('.battle--portrait .battle__col--plan')
      return el === null ? false : el.scrollHeight <= el.clientHeight && el.scrollWidth <= el.clientWidth
    })
    expect(planFits, '도면 칸이 스크롤된다').toBe(true)

    // 탭을 바꿔도 도면은 한 픽셀도 움직이지 않는다. 시트만 바뀐다.
    const tabs = page.getByRole('tab')
    await expect(tabs).toHaveCount(2)
    await tabs.nth(1).click()
    await expect(page.locator('.ds-log-row').first()).toBeVisible()
    await expect(page.locator('.ds-rule-table')).toHaveCount(0)
    expect(await page.locator('.battle__col--plan canvas').boundingBox()).toEqual(canvas)

    await tabs.nth(0).click()
    await expect(page.locator('.ds-rule-table')).toBeVisible()
    await expect(page.locator('.ds-log-row')).toHaveCount(0)
    expect(await page.locator('.battle__col--plan canvas').boundingBox()).toEqual(canvas)

    checkNoBrowserErrors(diagnostics)
  })

  test('규칙 행을 눌러 끄면 그 규칙 없이 판이 다시 돈다 (명세 D)', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.selectOption('#launch-room', 'corridor')
    await page.fill('#launch-seed', '1')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle--portrait')).toBeVisible()

    const rulesTab = page.getByRole('tab').first()
    const total = await page.locator('.ds-rule-row').count()
    await expect(rulesTab).toContainText(`${String(total)}/${String(total)}`)

    // 시계를 세우고 두 틱을 민다. 끄기가 판을 되돌리는 것을 보려면 0 이 아닌 틱이 필요하다.
    await page.getByRole('button', { name: '한 틱' }).click()
    await page.getByRole('button', { name: '한 틱' }).click()
    await expect(page.locator('.battle__tick')).toContainText('002')

    // 누르면 꺼진다 — 명도(0.4)와 글자(`· 꺼짐`) 두 채널이 함께 나간다.
    await page.locator('.ds-rule-row__hit').first().click()
    await expect(page.locator('.ds-rule-row--off')).toHaveCount(1)
    await expect(page.locator('.ds-rule-row--off')).toContainText('꺼짐')
    await expect(rulesTab).toContainText(`${String(total - 1)}/${String(total)}`)
    const dimmed = await page.evaluate(
      () => getComputedStyle(document.querySelector('.ds-rule-row--off') as Element).opacity,
    )
    expect(Number.parseFloat(dimmed)).toBeCloseTo(0.4)

    // **판이 처음부터 다시 돈다.** 끈 규칙은 판에 실리지 않으므로 판의 입력이 달라졌고,
    // 도는 판의 규칙표를 중간에 갈아 끼우면 같은 시드가 같은 결과를 내지 않는다 (R5).
    await expect(page.locator('.battle__tick')).toContainText('000')

    // 다시 누르면 켜진다.
    await page.locator('.ds-rule-row__hit').first().click()
    await expect(page.locator('.ds-rule-row--off')).toHaveCount(0)
    await expect(rulesTab).toContainText(`${String(total)}/${String(total)}`)

    checkNoBrowserErrors(diagnostics)
  })

  test('한 틱·처음부터가 손에 닿고 실제로 시계를 움직인다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.selectOption('#launch-room', 'corridor')
    await page.fill('#launch-seed', '1')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle--portrait')).toBeVisible()

    // 히트 영역은 44px 이상이다.
    for (const locator of [page.getByRole('tab').first(), page.getByRole('button', { name: '한 틱' })]) {
      const box = await locator.boundingBox()
      expect(Math.round(box?.height ?? 0)).toBeGreaterThanOrEqual(TAP_MIN)
    }

    // 한 틱은 정확히 한 틱만 민다. 시계를 세우므로 다음 틱이 값을 덮어쓰지 않는다.
    const step = page.getByRole('button', { name: '한 틱' })
    await step.click()
    await expect(page.locator('.battle__tick')).toContainText('001')
    await step.click()
    await expect(page.locator('.battle__tick')).toContainText('002')

    // 처음부터는 같은 방·같은 시드로 판을 다시 조립한다.
    await page.getByRole('button', { name: '처음부터' }).click()
    await expect(page.locator('.battle__tick')).toContainText('000')

    // 판정은 상태줄이 늘 적는다 — 진행 중에도 비워 두지 않는다.
    await expect(page.locator('.battle__verdict')).toHaveText('◆ 전투 중')

    await saveShot(page, '09-battle-portrait')
    checkNoBrowserErrors(diagnostics)
  })
})
