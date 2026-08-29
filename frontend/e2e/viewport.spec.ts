/**
 * 좁은 화면에서 무엇이 먼저 무너지는가, 그리고 반응형 토큰이 실제로 도는가.
 *
 *
 * 세 화면 모두 고정 폭 열(좌 320 / 우 300)에 가운데만 가변인 골격이다. 그 골격은 넓은
 * 데스크톱을 상정하고 그린 것이며, 흔한 노트북 폭 1280×720 에서 실제로 어떻게 보이는지는
 * 아무도 확인한 적이 없었다.
 *
 * 앞 절반은 **고쳐질 때까지 초록으로 두기 위한 테스트가 아니라 실측 기록이다.** 지금
 * 확실히 성립해야 하는 것(문서 자체는 가로로 스크롤되지 않는다, 닫기·되감기에 손이 닿는다,
 * 로그 줄이 잘리지 않는다)만 단언하고, 무너지는 수치는 주석에 적어 둔다.
 *
 * 뒤 절반은 반응형 토큰의 계약이다. `--plan-cell` 이 브레이크포인트마다 다른 값이 되었으므로
 * (64/30/32) 토큰 → 도면 테마 → 캔버스 백버퍼로 이어지는 사슬이 실제 브라우저에서 끊기지
 * 않는지 본다. 단위 테스트로는 볼 수 없다 — 미디어쿼리를 평가하는 것은 브라우저다.
 */
import { expect, test } from '@playwright/test'

import { attachDiagnostics, checkNoBrowserErrors, runToOutcome } from './fixtures'

/** 흔한 노트북 폭. */
const NARROW = { width: 1280, height: 720 }

test.describe('좁은 화면', () => {
  test.use({ viewport: NARROW })

  test('1280×720 에서 사후 분석의 조작부에 손이 닿는다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.selectOption('#launch-room', 'corridor')
    await page.fill('#launch-seed', '1')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle')).toBeVisible()
    expect(await runToOutcome(page)).toBe('쓰러짐')

    const post = page.getByRole('dialog', { name: '사후 분석' })
    await expect(post).toBeVisible()

    // 문서가 가로로 밀리지는 않는다.
    const docWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(docWidth).toBe(NARROW.width)

    // 그러나 대화상자 안쪽은 밀린다. 실측: scrollWidth 1307 vs clientWidth 1280 (27px),
    // 로그 열 폭이 117px 까지 눌려 모든 줄이 말줄임으로 잘린다. 1440 이상에서 277px 로
    // 회복한다. 고칠 때는 이 두 수를 기준으로 본다.
    const overflow = await page.evaluate(() => {
      const body = document.querySelector('.hud-post__body')
      return body === null ? 0 : body.scrollWidth - body.clientWidth
    })
    expect(overflow, '사후 분석 본문의 가로 넘침(px) — 0 이 되면 이 단언을 조여라').toBeLessThan(
      64,
    )

    // 열이 눌려도 로그 줄은 **잘리지 않는다.** 실측값 병기가 로그의 존재 이유이므로
    // (GDD §8.2, P1) 끝이 사라지면 기능이 죽는다. 넘치면 자르지 않고 접는다.
    // 열 폭 자체(위의 27px)는 아직 남은 문제이고, 이 단언은 그와 무관하게 성립해야 한다.
    const clipped = await page.evaluate(() =>
      [...document.querySelectorAll('.ds-log-row__body')].filter(
        (node) => node.scrollWidth > node.clientWidth + 1,
      ).length,
    )
    expect(clipped, '가로로 잘린 로그 줄 수').toBe(0)

    // 눌려도 조작은 된다. 되감기와 닫기가 이 화면의 전부다.
    await post.getByLabel('되감기').fill('21')
    await post.getByRole('button', { name: '닫기' }).click()
    await expect(post).toBeHidden()

    checkNoBrowserErrors(diagnostics)
  })
})

/** 명세가 기준으로 삼은 두 모바일 화면과 데스크톱 기준 해상도. */
const SIZES = {
  desktop: { width: 1440, height: 900 },
  portrait: { width: 390, height: 844 },
  landscape: { width: 844, height: 390 },
} as const

/** 배치별로 도면 셀이 몇 px 이어야 하는가. 토큰 표(design/README.md)와 같은 값이다. */
const CELLS = { desktop: 64, portrait: 30, landscape: 32 } as const

/** 도면 격자. 셀 수는 토큰 `--plan-cols`·`--plan-rows` 와 같다. */
const PLAN_COLS = 12

test.describe('반응형 토큰', () => {
  test.use({ viewport: SIZES.desktop })

  test('배치 이름과 도면 셀이 화면 크기를 따라간다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await page.goto('/')
    await page.selectOption('#launch-room', 'corridor')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle__col--plan canvas')).toBeVisible()

    const readMode = async (): Promise<string> =>
      (
        await page.evaluate(() =>
          getComputedStyle(document.documentElement).getPropertyValue('--layout-mode'),
        )
      ).trim()

    const readCanvasWidth = async (): Promise<number> => {
      const box = await page.locator('.battle__col--plan canvas').boundingBox()
      return box === null ? 0 : Math.round(box.width)
    }

    // 데스크톱은 전과 같다. 12×64 = 768.
    expect(await readMode()).toBe('desktop')
    expect(await readCanvasWidth()).toBe(PLAN_COLS * CELLS.desktop)

    // 세로 모바일 — 도면은 12×9 전체를 유지하고 셀만 30 으로 줄어든다. 12×30 = 360 이라
    // 390px 화면 안에 들어간다. 창을 바꾼 뒤 **다시 읽는지**도 여기서 걸린다.
    await page.setViewportSize(SIZES.portrait)
    await expect.poll(readMode).toBe('portrait')
    await expect.poll(readCanvasWidth).toBe(PLAN_COLS * CELLS.portrait)
    expect(PLAN_COLS * CELLS.portrait).toBeLessThanOrEqual(SIZES.portrait.width)

    // 가로 모바일 — 셀 32. 12×32 = 384 이고 우측 시트 340 과 함께 844 에 들어간다.
    await page.setViewportSize(SIZES.landscape)
    await expect.poll(readMode).toBe('landscape')
    await expect.poll(readCanvasWidth).toBe(PLAN_COLS * CELLS.landscape)

    // 되돌리면 데스크톱으로 돌아온다. 한 방향으로만 도는 전환이 아니다.
    await page.setViewportSize(SIZES.desktop)
    await expect.poll(readMode).toBe('desktop')
    await expect.poll(readCanvasWidth).toBe(PLAN_COLS * CELLS.desktop)

    checkNoBrowserErrors(diagnostics)
  })
})
