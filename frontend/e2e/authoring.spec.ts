/**
 * G3 관문 — **규칙 에디터로 규칙표 하나 짜는 데 3분 이내인가** (로드맵 W11~W12, 최대 리스크).
 *
 * 재는 방법을 먼저 밝힌다. 스크립트의 벽시계는 사람의 시간이 아니다 — 브라우저는 셀렉트
 * 하나를 40ms 에 바꾸지만 사람은 그 셀렉트를 **찾아야** 한다. 그래서 두 수를 따로 낸다.
 *
 *   1) 조작 수 — 규칙표 하나를 완성하는 데 필요한 클릭·선택·타이핑의 개수. 도구의 성질이다.
 *   2) 응답 시간 — 그 조작들에 UI 가 답하는 데 든 실제 시간. 도구가 사람을 기다리게 하는가.
 *
 * 사람의 시간은 (1) × 조작당 소요로 어림한다. `HUMAN_MS_PER_OP` 는 "화면에서 그 컨트롤을
 * 찾아 누르고 결과를 확인한다" 를 3초로 잡은 값이고, **측정값이 아니라 가정**이다. 가정을
 * 코드에 적어 두는 이유는 이 수가 관문 판정을 좌우하기 때문이다.
 *
 * 짜는 규칙표는 `g0_kite`(카이팅, 4규칙 7CPU)다. 기본으로 실려 있는 `g0_pressure` 가
 * `corridor` 에서 100% 지고 `g0_kite` 는 100% 이기므로(docs/05), **다 짜고 나서 이기는지**로
 * 규칙표가 진짜 만들어졌는지 확인할 수 있다. 화면만 보고 통과를 선언하지 않는다.
 */
import { expect, test, type Locator, type Page } from '@playwright/test'

import { attachDiagnostics, checkNoBrowserErrors, openFreshApp, runToOutcome, saveShot } from './fixtures'

/** G3 이 정한 상한. 3분. */
const GATE_BUDGET_MS = 180_000

/** 조작 하나에 사람이 쓴다고 가정한 시간. 측정값이 아니라 가정이다. */
const HUMAN_MS_PER_OP = 3_000

/**
 * 조작 수 상한. 지금 34 이고, 여기서 크게 늘면 3분 예산이 가정 하나로 무너진다.
 * 회귀 감시용이며 성능이 아니라 **설계 압력**으로 둔 수다.
 */
const MAX_OPS = 45

/** 카이팅이 이기는 방과 시드. 기본 규칙표로는 지는 판이다. */
const KITE_ROOM = 'corridor'
const KITE_SEED = '1'

/** 한 조작을 세면서 실행한다. */
class OpCounter {
  public count = 0

  /**
   * 조작 하나를 돌리고 센다.
   *
   * @param action 실행할 조작.
   */
  public async run(action: () => Promise<unknown>): Promise<void> {
    this.count += 1
    await action()
  }
}

/**
 * 규칙 행 하나를 집는다.
 *
 * @param page 에디터가 떠 있는 페이지.
 * @param at 0 부터 세는 자리.
 * @returns 그 행의 로케이터.
 */
function getRow(page: Page, at: number): Locator {
  return page.locator('.rule-row').nth(at)
}

test.describe('G3 — 규칙표 하나 짜기', () => {
  test('빈 판에서 카이팅 규칙표를 짜고, 그것으로 이긴다', async ({ page }) => {
    const diagnostics = attachDiagnostics(page)
    await openFreshApp(page)

    const ops = new OpCounter()
    const startedAt = Date.now()

    // 0) 실려 있는 규칙표를 비운다. "처음부터 짠다" 의 출발점이다.
    for (let i = 0; i < 4; i += 1) {
      await ops.run(() => page.locator('.rule-row').first().getByTitle('삭제 (Alt+Backspace)').click())
    }
    await expect(page.locator('.rule-row')).toHaveCount(0)

    // 1) 내 HP% < 30 AND 내 포션 수 > 0 → 포션 사용
    await ops.run(() => page.getByRole('button', { name: '내 HP%' }).click())
    await ops.run(() => getRow(page, 0).getByLabel('조건 1 우변 값').fill('30'))
    await ops.run(() => getRow(page, 0).getByTitle('조건 항 추가 (Alt+T)').click())
    await ops.run(() => getRow(page, 0).getByLabel('조건 2 인지 변수').selectOption({ label: '내 포션 수' }))
    await ops.run(() => getRow(page, 0).getByLabel('조건 2 비교').selectOption('>'))
    await ops.run(() => getRow(page, 0).getByLabel('조건 2 우변 값').fill('0'))
    await ops.run(() => getRow(page, 0).getByLabel('규칙 1 행동').selectOption({ label: '포션 사용' }))

    // 2) 대상 거리[NEAREST] <= 1 → 후퇴 @가장 가까운 적, A=참
    await ops.run(() => page.getByRole('button', { name: '대상 거리' }).click())
    await ops.run(() => getRow(page, 1).getByLabel('조건 1 비교').selectOption('<='))
    await ops.run(() => getRow(page, 1).getByLabel('조건 1 우변 값').fill('1'))
    await ops.run(() => getRow(page, 1).getByLabel('규칙 2 행동').selectOption({ label: '후퇴' }))
    await ops.run(() => getRow(page, 1).getByLabel('규칙 2 플래그').selectOption('A'))

    // 3) 플래그[A] == 참 AND 쿨타임[SKILL_2] 완료 → 스킬 2, A=거짓
    await ops.run(() => page.getByRole('button', { name: '플래그 상태' }).click())
    await ops.run(() => getRow(page, 2).getByTitle('조건 항 추가 (Alt+T)').click())
    await ops.run(() => getRow(page, 2).getByLabel('조건 2 인지 변수').selectOption({ label: '내 쿨타임[스킬] 완료' }))
    await ops.run(() => getRow(page, 2).getByLabel(/조건 2 .*인자/).selectOption('SKILL_2'))
    await ops.run(() => getRow(page, 2).getByLabel('규칙 3 행동').selectOption({ label: '스킬 2' }))
    await ops.run(() => getRow(page, 2).getByLabel('규칙 3 플래그').selectOption('A'))
    await ops.run(() => getRow(page, 2).getByLabel('규칙 3 플래그 값').selectOption('false'))

    // 4) 대상 거리 <= 4 AND 쿨타임[SKILL_2] 완료 → 스킬 2
    await ops.run(() => page.getByRole('button', { name: '대상 거리' }).click())
    await ops.run(() => getRow(page, 3).getByLabel('조건 1 비교').selectOption('<='))
    await ops.run(() => getRow(page, 3).getByLabel('조건 1 우변 값').fill('4'))
    await ops.run(() => getRow(page, 3).getByTitle('조건 항 추가 (Alt+T)').click())
    await ops.run(() => getRow(page, 3).getByLabel('조건 2 인지 변수').selectOption({ label: '내 쿨타임[스킬] 완료' }))
    await ops.run(() => getRow(page, 3).getByLabel(/조건 2 .*인자/).selectOption('SKILL_2'))
    await ops.run(() => getRow(page, 3).getByLabel('규칙 4 행동').selectOption({ label: '스킬 2' }))

    const uiMs = Date.now() - startedAt
    const humanMs = ops.count * HUMAN_MS_PER_OP
    // 관문 판정에 쓰는 수라 실행 로그에 남긴다. reporter 가 그대로 찍는다.
    console.log(
      `[G3] 조작 ${String(ops.count)}회 · UI 응답 ${String(uiMs)}ms · ` +
        `사람 어림 ${String(Math.round(humanMs / 1000))}초 (조작당 ${String(HUMAN_MS_PER_OP / 1000)}초 가정)`,
    )

    // 다 짜인 규칙표가 실행 가능해야 한다. 화면이 그럴듯한 것과는 다른 사실이다.
    await expect(page.locator('.rule-row')).toHaveCount(4)
    await expect(page.locator('.editor__bottom')).toContainText('cpu 7 / 8')
    await expect(page.getByText('실행 가능한 규칙표다')).toBeVisible()
    await saveShot(page, '06-authoring-kite')

    expect(ops.count, '조작 수').toBeLessThanOrEqual(MAX_OPS)
    expect(uiMs, 'UI 응답 시간').toBeLessThan(GATE_BUDGET_MS)
    expect(humanMs, '조작 수 × 조작당 가정 시간').toBeLessThan(GATE_BUDGET_MS)

    // 짠 것이 실제로 이긴다. 같은 방·같은 시드에서 기본 규칙표는 진다(coreLoop.spec).
    await page.selectOption('#launch-room', KITE_ROOM)
    await page.fill('#launch-seed', KITE_SEED)
    await page.getByRole('button', { name: '출격' }).click()
    await expect(page.locator('.battle')).toBeVisible()
    expect(await runToOutcome(page), '카이팅으로 corridor 를 이겨야 한다').toBe('승리')
    await saveShot(page, '07-battle-win')

    checkNoBrowserErrors(diagnostics)
  })
})
