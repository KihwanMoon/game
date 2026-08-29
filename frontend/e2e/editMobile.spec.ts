/**
 * 모바일에서 규칙을 실제로 고칠 수 있는가 — 명세 C (세로 390×844 · 가로 844×390).
 *
 * 단위 테스트는 마크업과 선언을 읽을 뿐이다. **미디어쿼리를 평가하고 세 조각이 390px 에
 * 실제로 들어가는지 재는 것은 브라우저**이고, 이 화면에서 가장 쉽게 깨지는 것이 그 폭이다.
 * 조건 한 줄이 `1fr 78px 1fr` 로 서지 못하면 우변이 화면 밖으로 밀리는데, 그때도 화면은
 * 그럴듯해 보이므로 눈으로는 잘 안 걸린다.
 *
 * 고른 값이 규칙표에 남는지까지 본다 — 편집 화면이 예뻐도 저장이 규칙표에 닿지 않으면
 * "고쳐서 다시 보낸다" 는 한 바퀴가 끊긴다 (GDD §2.1).
 */
import { expect, test } from '@playwright/test'

import { attachDiagnostics, checkNoBrowserErrors, saveShot } from './fixtures'

/** 명세 C 가 기준으로 삼은 화면. */
const PORTRAIT = { width: 390, height: 844 } as const

/** 히트 영역의 하한. 손가락이 닿지 않는 버튼은 화면에 있어도 없는 것과 같다. */
const TAP_MIN = 44

/** 카드 안의 조건·행동 칸과 우선순위 세그먼트 높이 (`--field-h`). */
const FIELD_H = 40

test.describe('세로 모바일 규칙 편집', () => {
  test.use({ viewport: PORTRAIT })

  test('규칙 줄을 눌러 조건 세 조각을 고치고 저장한다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')

    // 세로에서는 데스크톱 세 열이 아니라 규칙표 목록이 선다.
    await expect(page.locator('.edit-m--list')).toBeVisible()
    await expect(page.locator('.editor__col--palette')).toHaveCount(0)
    await saveShot(page, '12-edit-list-portrait')

    // 규칙 줄을 누르면 그 규칙 하나가 화면 전체를 쓴다.
    await page.getByRole('button', { name: '규칙 2 편집' }).click()
    await expect(page.locator('.edit-m--edit')).toBeVisible()
    await expect(page.locator('.edit-card')).toHaveCount(4)

    // 문서는 어느 방향으로도 밀리지 않는다. 390 이 전부다.
    const width = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(width).toBe(PORTRAIT.width)

    // 조건은 좌변 / 비교 / 우변 세 조각이고 셋 다 한 줄에 들어간다.
    const row = page.locator('.edit-cond__row').first()
    const cells = await row.evaluate((node) => getComputedStyle(node).gridTemplateColumns)
    expect(cells.split(' ')).toHaveLength(3)

    // 인자를 받는 인지 변수(대상 거리[셀렉터])는 인자 선택칸이 함께 뜬다.
    await expect(page.getByLabel('조건 1 selector 인자')).toBeVisible()

    // 실측 줄이 조건 아래에 선다. 아직 한 틱도 돌지 않았으므로 값 자리는 `–` 다.
    const measure = page.locator('.edit-measure').first()
    await expect(measure).toContainText('–')
    await expect(measure.locator('.ds-glyph--pending')).toBeVisible()

    // 취소·저장의 히트 영역은 44px 이상이다. 카드 안의 칸은 명세가 정한 40 이다.
    const save = await page.getByRole('button', { name: '저장' }).boundingBox()
    expect(Math.round(save?.height ?? 0)).toBeGreaterThanOrEqual(TAP_MIN)
    const segment = await page.locator('.edit-seg__cell').first().boundingBox()
    expect(Math.round(segment?.height ?? 0)).toBe(FIELD_H)

    // 세 조각을 고친다 — 비교와 우변.
    await page.getByLabel('조건 1 비교').selectOption('<')
    await page.getByLabel('조건 1 우변 값').fill('3')

    await saveShot(page, '10-edit-portrait')

    // 저장하면 목록으로 돌아오고, 고친 조건이 그 줄에 남아 있다.
    await page.getByRole('button', { name: '저장' }).click()
    await expect(page.locator('.edit-m--list')).toBeVisible()
    await expect(page.locator('.edit-m__rule').nth(1)).toContainText('대상 거리[NEAREST](–) < 3')

    checkNoBrowserErrors(diagnostics)
  })

  test('취소는 열었을 때의 규칙표로 되돌린다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.getByRole('button', { name: '규칙 4 편집' }).click()

    const before = await page.locator('.edit-measure').first().innerText()
    await page.getByLabel('조건 1 우변 값').fill('99')
    await expect(page.locator('.edit-measure').first()).not.toHaveText(before)

    await page.getByRole('button', { name: '취소' }).click()
    await expect(page.locator('.edit-m--list')).toBeVisible()
    await expect(page.locator('.edit-m__rule').nth(3)).not.toContainText('99')

    checkNoBrowserErrors(diagnostics)
  })
})

/** 명세 C 의 가로 배치가 기준으로 삼은 화면. */
const LANDSCAPE = { width: 844, height: 390 } as const

/** 가로 편집 화면의 우열 폭 (`--edit-col`). */
const EDIT_COL = 300

test.describe('가로 모바일 규칙 편집', () => {
  test.use({ viewport: LANDSCAPE })

  test('1fr 300px 두 열이 서고 취소·저장이 우열에 있다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.getByRole('button', { name: '규칙 2 편집' }).click()

    await expect(page.locator('.edit-ls__body')).toBeVisible()
    const side = await page.locator('.edit-ls__col--side').boundingBox()
    expect(Math.round(side?.width ?? 0)).toBe(EDIT_COL)

    // 취소·저장은 우열 안이다. 높이가 390px 뿐이라 하단바를 한 줄 더 쌓을 자리가 없다.
    await expect(page.locator('.edit-m__bar--edit')).toHaveCount(0)
    const save = await page.getByRole('button', { name: '저장' }).boundingBox()
    expect(save?.x ?? 0).toBeGreaterThan(LANDSCAPE.width - EDIT_COL)

    // 문서는 어느 방향으로도 밀리지 않는다. 스크롤하는 것은 두 열 안쪽뿐이다.
    const doc = await page.evaluate(() => ({
      x: document.documentElement.scrollWidth,
      y: document.documentElement.scrollHeight,
    }))
    expect(doc).toEqual({ x: LANDSCAPE.width, y: LANDSCAPE.height })

    await saveShot(page, '11-edit-landscape')
    checkNoBrowserErrors(diagnostics)
  })
})
