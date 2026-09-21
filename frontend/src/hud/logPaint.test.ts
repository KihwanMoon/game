/**
 * 두 화면이 로그를 같은 말로 적는가.
 *
 * **전투 화면만 덧칠하고 있었다** (2026-09-20 신고). 같은 판을 이어서 보는데 관전에서는
 * 「큰 도깨비가 일격」이고 사후 분석에서는 「goblin_rusher_0 이 SKILL_1」이었다 —
 * **로그가 id 로 말하면 그것은 로그가 아니라 덤프다.**
 *
 * 덧칠을 `battle/logNames` 한 곳으로 모으고 세 화면(관전·되감기·사후 분석)이 그것을
 * 부른다. 여기서 보는 것은 **그 함수가 실제로 한글로 바꾸는가**와 **기록이 이름표를
 * 들고 오는가** 둘이다. 판이 끝나면 세계 상태가 없어서, 그때 안 담아 두면 사후 분석은
 * 이름을 되살릴 방법이 없다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { buildLogRow } from '../battle'
import { readActivePack } from '../content/pack'
import { G0_RULESETS } from '../core/resources'
import { formatParamText } from '../editor/blockOptions'
import { recordBattle } from './battleRecorder'

const HERE = fileURLToPath(new URL('.', import.meta.url))

const RECORDING = recordBattle(
  { roomId: 'hazard_field', rulesetId: 'g0_cover', seed: 99 },
  G0_RULESETS,
)

/**
 * 기록의 로그를 화면이 그리는 모양으로 덧칠한다.
 *
 * @returns 덧칠된 줄들.
 */
function paint() {
  return RECORDING.entries.map((entry) =>
    buildLogRow(entry, RECORDING.actorNames, readActivePack().catalog, formatParamText),
  )
}

describe('기록이 이름표를 들고 온다', () => {
  it('★ 판이 끝나면 세계 상태가 없다 — 그때 안 담으면 되살릴 수 없다', () => {
    expect(RECORDING.actorNames.size).toBeGreaterThan(0)
  })

  it('플레이어도 이름표를 갖는다', () => {
    expect(RECORDING.actorNames.get(RECORDING.playerId)?.isMine).toBe(true)
  })
})

describe('로그 덧칠', () => {
  const rows = paint()

  it('줄 수는 그대로다 — 덧칠이 줄을 지우거나 더하지 않는다', () => {
    expect(rows).toHaveLength(RECORDING.entries.length)
  })

  it('★ 개체 id 가 이름표로 바뀐다', () => {
    const raw = RECORDING.entries.map((one) => `${one.expr} ${one.outcome}`).join(' ')
    expect(raw, '표본에 id 가 없으면 이 검사가 아무것도 안 본다').toMatch(/goblin_\w+_\d/)
    const shown = rows.map((one) => `${one.expr} ${one.outcome}`).join(' ')
    expect(shown).not.toMatch(/goblin_\w+_\d/)
  })

  it('★ 행동 id 가 한글로 바뀐다 — 그 칸만 다른 언어가 되면 안 된다', () => {
    const shown = rows.map((one) => one.outcome).join(' ')
    expect(shown).not.toMatch(/\b(MOVE_TO_COVER|APPROACH|RETREAT|SKILL_[12])\b/)
  })

  it('★ 왼쪽도 칠한다 (2026-09-21 신고) — 한 줄 안에서 언어가 갈리면 안 된다', () => {
    // 예고가 터진 줄은 `CHAIN_BOLT 예고 발동 (2칸)` 이고 실행 줄은 `APPROACH @player` 다.
    // 오른쪽만 칠하던 때는 같은 낱말이 한 줄 안에서 한쪽만 한글이었다.
    const raw = RECORDING.entries.map((one) => one.expr).join(' ')
    expect(raw, '표본 왼쪽에 행동 코드가 없으면 이 검사가 아무것도 안 본다').toMatch(
      /\b(MOVE_TO_COVER|APPROACH)\b/,
    )
    const shown = rows.map((one) => one.expr).join(' ')
    expect(shown).not.toMatch(/\b(MOVE_TO_COVER|APPROACH|RETREAT|SKILL_[12])\b/)
  })

  it('행위자 칸이 비지 않는다 — 이름표가 없으면 id 라도 적는다', () => {
    for (const row of rows) {
      expect(row.actor).not.toBe('')
    }
  })
})

describe('세 화면이 그 덧칠을 실제로 부른다', () => {
  /**
   * **여기가 회귀를 잡는 자리다.** `buildLogRow` 는 처음부터 잘 칠했고, 문제는 사후
   * 분석이 **그것을 안 부르고** 날것을 그대로 넘긴 것이었다 — 그래서 함수만 시험하면
   * 고치기 전에도 초록이다.
   *
   * `BattleFrame.entries` 가 구조적으로 날것도 받아 주기 때문에(`LogEntry` 가
   * `LogRowProps` 를 만족한다) **타입 검사도 안 잡는다.** 소스를 본다.
   */
  const SCREENS = ['PostMortem.tsx', 'HudScreen.tsx'] as const

  it.each(SCREENS)('%s 가 날것을 그대로 안 넘긴다', (name) => {
    const source = readFileSync(`${HERE}${name}`, 'utf8')
    expect(source).toContain('buildLogRow')
    // `entries={recording.entries...}` 가 바로 들어가면 덧칠을 건너뛴 것이다.
    expect(source).not.toMatch(/entries=\{recording\.entries/)
  })

  it('전투 화면도 같은 것을 부른다 — 사본을 두면 둘이 갈린다', () => {
    const source = readFileSync(`${HERE}../battle/BattleView.tsx`, 'utf8')
    expect(source).toContain('buildLogRow')
  })

  it('★ 리플레이는 제 로그를 안 그린다 — 전투 화면에 맡겨야 덧칠이 따라온다', () => {
    // 재생은 `BattleView` 를 그대로 쓴다. 그래서 로그 덧칠을 여기서 또 하지 않아도
    // 따라오는데, 언젠가 제 로그를 그리기 시작하면 그 순간 이 화면만 날것이 된다.
    const source = readFileSync(`${HERE}../admin/ReplayView.tsx`, 'utf8')
    expect(source).toContain('<BattleView')
    expect(source, '제 로그를 그리기 시작했다면 덧칠을 함께 가져가야 한다').not.toMatch(
      /entries=\{/,
    )
  })
})

describe('시트가 전투 화면과 같은 것을 받는다', () => {
  /**
   * **탭이 있는데 비면 고장으로 읽힌다** (2026-09-21). 「정산」 탭은 `settlements` 를
   * 펴는데, 전투 화면만 그것을 넘기고 사후 분석·되감기는 안 넘겼다 — 방금까지 차
   * 있던 자리가 판이 끝나자 빈 채로 섰다.
   *
   * 값이 비는 것과 **넘기지 않는 것**은 다르다. 확인용 페이지처럼 층 개념이 없어
   * 비는 것은 맞고, 있는데 안 주는 것이 틀린 것이다.
   */
  it.each(['PostMortem.tsx', 'HudScreen.tsx'] as const)('%s 가 정산을 넘긴다', (name) => {
    expect(readFileSync(`${HERE}${name}`, 'utf8')).toMatch(/settlements=\{/)
  })

  it('App 이 두 화면에 같은 정산을 준다', () => {
    const source = readFileSync(`${HERE}../App.tsx`, 'utf8')
    expect(source.match(/settlements=\{settlements\}/g) ?? []).toHaveLength(2)
  })
})
