/**
 * 핵심 루프를 실제 브라우저에서 클릭한다 (GDD §2.2, 로드맵 M3 — JSON 없이 플레이 가능).
 *
 * 여기까지 이 앱을 검증한 것은 jsdom 렌더 테스트와 마크업 문자열 대조뿐이었다. 그것은
 * "컴포넌트가 이 마크업을 낸다" 를 말할 뿐 **"플레이된다" 를 말하지 않는다.** 이 파일이
 * 확인하는 것은 한 사람이 앱을 열어 규칙을 짜고 내보내고 죽은 이유를 보고 고쳐서 다시
 * 보내는 한 바퀴가 브라우저 안에서 실제로 도는가 하나다.
 *
 * 방은 `corridor`, 시드는 1 로 고정한다. 이 조합이 기본 규칙표 `g0_pressure` 로는 지는
 * 판이라(docs/05 — corridor 승률 0%) **사후 분석이 저절로 뜨는 경로**를 지나간다. 이겨
 * 버리면 그 화면을 클릭으로 밟을 수 없다.
 */
import { expect, test } from '@playwright/test'

import {
  WATCH_MS,
  attachDiagnostics,
  checkNoBrowserErrors,
  openFreshApp,
  runToOutcome,
  saveShot,
} from './fixtures'

/** 지는 판. 사후 분석이 저절로 뜬다. */
const LOSS_ROOM = 'corridor'
const LOSS_SEED = '1'

/**
 * 실측값이 양변에 병기된 조건문. `대상 거리[NEAREST](1) <= 사거리(1)` 를 잡는다.
 *
 * P1(실패는 정보다)의 실현 수단이 이 서식이다 — 참/거짓만 적힌 로그는 왜 그렇게
 * 판정됐는지 알려 주지 않는다 (design/README.md §5, GDD §8.2).
 */
const MEASURED_BOTH_SIDES = /\(\d+\)\s*(<=|<|>=|>|==|!=)\s*[^\s]*\(\d+\)/

/** 적어도 한 항에 실측값이 붙은 조건문. */
const MEASURED_ANY = /\(\S+\)\s*(<=|<|>=|>|==|!=)/

test.describe('핵심 루프', () => {
  test('a~d 규칙 에디터에서 규칙을 짜고 CPU 를 넘겨도 편집이 계속된다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await openFreshApp(page)

    // (a) 앱이 뜨고 규칙 에디터가 보인다.
    await expect(page.getByRole('heading', { name: '규칙 에디터' })).toBeVisible()
    await expect(page.getByText('블록 팔레트')).toBeVisible()
    await expect(page.locator('.rule-row')).toHaveCount(4)
    await expect(page.locator('.editor__bottom')).toContainText('cpu 6 / 8')
    await saveShot(page, '01-editor')

    // (b) 팔레트에서 인지 변수 → 행동 → 셀렉터를 골라 규칙을 한 줄 더 만든다.
    await page.getByRole('button', { name: '시야 내 적 수' }).click()
    await expect(page.locator('.rule-row')).toHaveCount(5)
    const added = page.locator('.rule-row').nth(4)
    await expect(added).toContainText('[5]')

    await page.getByRole('button', { name: '스킬 1', exact: true }).click()
    await expect(added.getByLabel('규칙 5 행동')).toHaveValue('SKILL_1')
    await page.getByRole('button', { name: '위협도가 가장 높은 적' }).click()
    await expect(added.getByLabel('규칙 5 대상')).toHaveValue('HIGHEST_THREAT')

    // (c) 인자를 받는 인지 변수를 고르면 인자 선택칸이 뜬다.
    await expect(added.getByLabel(/조건 1 .*인자/)).toHaveCount(0)
    await added.getByLabel('조건 1 인지 변수').selectOption({ label: '내 쿨타임[스킬] 완료' })
    const param = added.getByLabel(/조건 1 .*인자/)
    await expect(param).toBeVisible()
    await expect(param.locator('option')).toContainText(['SKILL_1', 'SKILL_2'])
    await param.selectOption('SKILL_2')
    await expect(param).toHaveValue('SKILL_2')

    // (d) CPU 예산을 넘겨도 편집은 계속된다 (GDD §3.6).
    // 3항 규칙의 비용은 4 다(항 수 → 비용은 1·2·4). 6 + 4 = 10 으로 예산 8 을 넘긴다.
    await added.getByTitle('조건 항 추가 (Alt+T)').click()
    await added.getByTitle('조건 항 추가 (Alt+T)').click()
    await expect(page.locator('.editor__bottom')).toContainText('cpu 10 / 8')
    await expect(added.locator('.rule-row__bar--over')).toHaveCount(1)
    // 넘긴 줄부터다 — 그 위의 줄들은 그대로 남는다.
    await expect(page.locator('.rule-row__bar--over')).toHaveCount(1)
    await expect(page.getByRole('button', { name: '출격' })).toBeDisabled()
    await saveShot(page, '02-editor-cpu-over')

    // 넘긴 상태에서 고쳐진다. 이것이 "오류가 아니라 수치" 의 뜻이다.
    await added.getByLabel('규칙 5 행동').selectOption({ label: '후퇴' })
    await expect(added.getByLabel('규칙 5 행동')).toHaveValue('RETREAT')
    await expect(page.locator('.editor__bottom')).toContainText('cpu 10 / 8')

    // 되돌리기로 예산 안으로 돌아온다.
    await page.getByTitle('되돌리기 (Ctrl+Z)').click()
    await page.getByTitle('되돌리기 (Ctrl+Z)').click()
    await page.getByTitle('되돌리기 (Ctrl+Z)').click()
    await expect(page.locator('.editor__bottom')).toContainText('cpu 7 / 8')
    await expect(page.getByRole('button', { name: '출격' })).toBeEnabled()

    checkNoBrowserErrors(diagnostics)
  })

  test('e~g 출격·사후 분석·재도전', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await openFreshApp(page)

    await page.selectOption('#launch-room', LOSS_ROOM)
    await page.fill('#launch-seed', LOSS_SEED)

    // (e) 출격하면 전투가 돌고, 로그에 실측값이 병기된 조건문이 쌓인다.
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle')).toBeVisible()
    await expect(page.locator('.battle__col--plan canvas')).toBeVisible()

    // 관전 배속 ×1 로 저절로 돈다. 사람이 아무것도 누르지 않아도 틱이 오른다.
    await page.waitForTimeout(WATCH_MS)
    const watchedTick = await page.locator('.ds-topbar__tick, .ds-topbar').first().textContent()
    expect(watchedTick ?? '').not.toBe('')
    await expect(page.locator('.ds-log-row')).not.toHaveCount(0)

    // 규칙표 열이 세 상태를 구분해 보여준다 — 참·발동 / 참·미발동 / 거짓 (P1).
    await expect(page.locator('.ds-rule-row--armed')).not.toHaveCount(0)
    await expect(page.locator('.ds-rule-row--false')).not.toHaveCount(0)
    await saveShot(page, '03-battle')

    const logText = await page.locator('.ds-log-row').allInnerTexts()
    const joined = logText.join('\n')
    expect(joined, '실측값이 붙은 조건문').toMatch(MEASURED_ANY)
    expect(joined, '양변에 실측값이 병기된 조건문').toMatch(MEASURED_BOTH_SIDES)

    // (f) 죽으면 사후 분석이 저절로 뜬다.
    expect(await runToOutcome(page)).toBe('패배')
    const post = page.getByRole('dialog', { name: '사후 분석' })
    await expect(post).toBeVisible()
    await expect(post.getByText('규칙별 발동')).toBeVisible()
    await expect(post.locator('.hud-stats tbody tr')).not.toHaveCount(0)
    await expect(post.getByText('피해 히트맵')).toBeVisible()
    await expect(post.locator('.hud-post__plan canvas')).toBeVisible()

    // 되감기 — 슬라이더를 옮기면 그 틱의 화면과 로그로 간다.
    const scrub = post.getByLabel('되감기')
    const endTick = await scrub.inputValue()
    const startTick = await scrub.getAttribute('min')
    await scrub.fill(startTick ?? '1')
    await expect(post.locator('.hud-post__meta, .ds-panel__meta').first()).toBeVisible()
    expect(startTick).not.toBe(endTick)
    await saveShot(page, '04-postmortem')

    const firstMeta = (await post.locator('.hud-post__meta').textContent()) ?? ''
    await post.getByRole('button', { name: '닫기' }).click()

    // (g) 규칙을 고쳐 재도전하면 결과가 달라진다.
    await page.getByRole('button', { name: '규칙 고치기' }).click()
    await expect(page.getByRole('heading', { name: '규칙 에디터' })).toBeVisible()
    // 같은 판정을 전투 화면은 `패배`, 에디터·사후 분석은 `사망` 이라 적는다. 라벨표가
    // 두 벌이기 때문이다(BattleView.OUTCOME_LABELS ↔ analysisText.OUTCOME_LABELS).
    // 여기서는 지금 화면에 실제로 적히는 말을 그대로 확인한다.
    await expect(page.locator('.launch')).toContainText('직전 판 사망')

    const firstRun = (await page.locator('.launch').innerText()).split('\n')[0] ?? ''
    // 포션을 훨씬 일찍 쓰게 한다. 같은 방·같은 시드인데 판이 달라져야 한다.
    await page.locator('.rule-row').nth(0).getByLabel('조건 1 우변 값').fill('90')
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle')).toBeVisible()
    await runToOutcome(page)
    const post2 = page.getByRole('dialog', { name: '사후 분석' })
    await expect(post2).toBeVisible()
    const secondMeta = (await post2.locator('.hud-post__meta').textContent()) ?? ''
    expect(secondMeta, '규칙을 고쳤는데 같은 판이 나왔다').not.toBe(firstMeta)
    expect(firstRun).toContain('직전 판')

    checkNoBrowserErrors(diagnostics)
  })

  test('키보드만으로 규칙을 더하고 옮기고 지운다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await openFreshApp(page)

    // 규칙 행은 tabIndex 0 이라 포커스를 받는다. 팔레트 설명이 못박은 요구 —
    // 키보드만으로 규칙 하나를 완성할 수 있어야 한다 (PalettePanel.tsx 머리주석).
    const first = page.locator('.rule-row').first()
    await first.focus()
    await expect(first).toBeFocused()

    await page.keyboard.press('Alt+Enter')
    await expect(page.locator('.rule-row')).toHaveCount(5)

    await page.keyboard.press('Alt+t')
    await expect(page.locator('.rule-row').nth(1).locator('.term')).toHaveCount(2)

    await page.keyboard.press('Alt+d')
    await expect(page.locator('.rule-row')).toHaveCount(6)
    // 슬롯이 5개라 6번째는 즉시 위반으로 잡힌다. 편집을 막지는 않는다.
    await expect(page.locator('.editor__col--check')).toContainText('규칙')

    await page.keyboard.press('Alt+Backspace')
    await page.keyboard.press('Alt+Backspace')
    await expect(page.locator('.rule-row')).toHaveCount(4)

    // Ctrl+Z 는 화면 어디서든 듣는다.
    await page.keyboard.press('Control+z')
    await expect(page.locator('.rule-row')).toHaveCount(5)

    checkNoBrowserErrors(diagnostics)
  })
})
