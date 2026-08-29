/**
 * 좁은 화면에서 무엇이 먼저 무너지는가.
 *
 * 세 화면 모두 고정 폭 열(좌 320 / 우 300)에 가운데만 가변인 골격이다. 그 골격은 넓은
 * 데스크톱을 상정하고 그린 것이며, 흔한 노트북 폭 1280×720 에서 실제로 어떻게 보이는지는
 * 아무도 확인한 적이 없었다.
 *
 * 이 파일은 **고쳐질 때까지 초록으로 두기 위한 테스트가 아니라 실측 기록이다.** 지금
 * 확실히 성립해야 하는 것(문서 자체는 가로로 스크롤되지 않는다, 닫기·되감기에 손이 닿는다)만
 * 단언하고, 무너지는 수치는 주석에 적어 둔다. 고칠 때 이 수치를 기준으로 삼는다.
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
    expect(await runToOutcome(page)).toBe('패배')

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

    // 눌려도 조작은 된다. 되감기와 닫기가 이 화면의 전부다.
    await post.getByLabel('되감기').fill('21')
    await post.getByRole('button', { name: '닫기' }).click()
    await expect(post).toBeHidden()

    checkNoBrowserErrors(diagnostics)
  })
})
