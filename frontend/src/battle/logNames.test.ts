/**
 * 실행 로그가 사람의 말로 적히는가 (2026-09-15 요청: 「누가 누구에게 무엇을 얼마나」).
 *
 * 고치기 전에는 이렇게 읽혔다 — **행위자 칸이 아예 없었다.**
 *
 *     T012 ▸ [3] 대상 거리[NEAREST](1) <= 1  → ATTACK @goblin_rusher_0
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../core/resources'
import { buildEngine, parseBalance } from '../core/services/runBattle'
import type { LogEntry } from '../core/eventLog'
import { buildActorNames, readLogTone, replaceIds } from './logNames'

const BALANCE_DATA = parseBalance(BALANCE)
const LABELS = new Map(BALANCE_DATA.enemies.map((kind) => [kind.id, kind.label_ko ?? kind.id]))

/** 적이 여럿인 방 하나. 번호가 붙는지 보려면 같은 종이 둘 이상이어야 한다. */
function buildNames() {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 가 없다')
  }
  const engine = buildEngine({ template, balance: BALANCE_DATA, seed: 3 })
  return buildActorNames(engine.state, LABELS)
}

/** 로그 한 줄을 짓는다. */
function buildEntry(over: Partial<LogEntry>): LogEntry {
  return {
    tick: 1,
    entityId: 'player',
    phase: 'ACT',
    expr: '',
    outcome: '',
    rule: null,
    delta: null,
    fired: true,
    targetId: null,
    ...over,
  } as LogEntry
}

describe('행위자 이름', () => {
  it('★ 나는 「나」다 — id 는 player 지만 화면에서 나는 나다', () => {
    expect(buildNames().get('player')?.name).toBe('나')
    expect(buildNames().get('player')?.isMine).toBe(true)
  })

  it('★ 적은 한글 이름으로 선다 — id 가 화면에 나오면 그것은 덤프다', () => {
    const names = buildNames()
    const goblin = names.get('goblin_rusher_0')
    expect(goblin?.name).toContain('몽둥이 도깨비')
    expect(goblin?.isMine).toBe(false)
  })

  it('★ 같은 종이 여럿이면 번호가 붙는다 — 안 붙으면 둘이 한 이름이 된다', () => {
    const names = buildNames()
    const first = names.get('goblin_rusher_0')?.name ?? ''
    const second = names.get('goblin_rusher_1')?.name ?? ''
    expect(second).not.toBe('')
    expect(first).not.toBe(second)
    expect(first).toContain('①')
  })

  it('세계가 남긴 줄에도 이름이 있다', () => {
    expect(buildNames().get('world')?.name).toBe('비각')
  })
})

describe('문구 안의 id', () => {
  it('★ 긴 id 부터 바꾼다 — 짧은 것부터 바꾸면 꼬리가 남는다', () => {
    const names = buildNames()
    const text = replaceIds('goblin_rusher_0 HP 28/40', names)
    expect(text).not.toContain('goblin_rusher')
    expect(text).toContain('HP 28/40')
  })

  it('대상 표기도 함께 바뀐다', () => {
    const names = buildNames()
    expect(replaceIds('ATTACK @goblin_rusher_0', names)).not.toContain('goblin_rusher_0')
  })
})

describe('줄의 결', () => {
  it('★ 판단과 행동을 가른다', () => {
    expect(readLogTone(buildEntry({ phase: 'DECIDE' }))).toBe('decide')
  })

  it('★ 피해와 회복을 증감의 부호로 가른다', () => {
    expect(readLogTone(buildEntry({ delta: -12 }))).toBe('damage')
    expect(readLogTone(buildEntry({ delta: 8 }))).toBe('heal')
  })

  it('★ 쓰러짐이 피해보다 앞선다 — 마지막 한 대는 다른 사건이다', () => {
    expect(readLogTone(buildEntry({ delta: -9, outcome: '나 HP 0/100 사망' }))).toBe('death')
  })

  it('★ 헛돈 줄을 따로 센다 — 수가 가장 많고 읽을 것이 가장 적다', () => {
    expect(readLogTone(buildEntry({ outcome: '길 막힘 — 틱 낭비' }))).toBe('waste')
  })

  it('세계가 남긴 줄은 세계다', () => {
    expect(readLogTone(buildEntry({ phase: 'UPKEEP' }))).toBe('world')
  })
})

describe('그림자의 이름', () => {
  /** 그림자 하나를 세운 상태. 여느 적 하나를 도플갱어로 바꿔 놓는다. */
  function buildShadowState() {
    const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
    if (template === undefined) {
      throw new Error('open_field 가 없다')
    }
    const engine = buildEngine({ template, balance: BALANCE_DATA, seed: 3 })
    const found = [...engine.state.entities.entries()].find(([id]) => id !== 'player')
    if (found === undefined) {
      throw new Error('적이 없다')
    }
    engine.state.entities.set('doppel_12', { ...found[1], kindId: 'doppelganger' })
    return engine.state
  }

  it('★ 주인 이름으로 부른다 — 「도플갱어①」이면 누구를 만난 것인지 모른다', () => {
    const names = buildActorNames(
      buildShadowState(),
      new Map([['doppelganger', '도플갱어']]),
      new Map([['doppel_12', '하윤']]),
    )

    expect(names.get('doppel_12')?.name).toBe('하윤의 도플갱어')
  })

  it('★ 주인을 모르면 종 이름으로 돌아간다 — 빈 이름표를 만들지 않는다', () => {
    const names = buildActorNames(
      buildShadowState(),
      new Map([['doppelganger', '도플갱어']]),
      new Map(),
    )

    expect(names.get('doppel_12')?.name).toContain('도플갱어')
  })
})
