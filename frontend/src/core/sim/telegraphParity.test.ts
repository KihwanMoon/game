/**
 * 스킬이 거는 예고가 두 코어에서 같이 도는가 (게이트 G3).
 *
 * **덫이었다가 대조가 됐다 (2026-09-09).** 파이썬이 `skills.json` 의 `telegraph` 를 읽어
 * 예고를 걸기 시작했을 때 TS 는 스킬 표조차 없었고, 그래서 「예고를 쓰는 스킬이 생기면
 * 운다」는 덫만 놓아 두었다. 이제 TS 도 같은 표를 읽으므로 실제로 대조한다.
 *
 * 골든에 안 기대는 이유는 골든이 이 경로를 하나도 안 덮기 때문이다 — 방어 태세가
 * 정확히 그 틈으로 조용히 갈려 있었다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { createPlannedAction } from './plan'
import { CANCEL_BY_HIT } from './telegraph'

const METEOR = 'METEOR'

function buildProbe(telegraph: number, switches: Record<string, boolean> = {}) {
  const balance = parseBalance(BALANCE)
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const engine = buildEngine({ template, balance, seed: 3 })
  const skills = engine.config.skills as Map<string, unknown>
  skills.set(METEOR, {
    skillId: METEOR,
    family: '',
    shape: { kind: 'AREA', radius: 2, length: 0 },
    targetFaction: '',
    coefPct: 200,
    cooldown: 0,
    reach: null,
    telegraph,
    cancelOnAct: switches.act ?? false,
    cancelOnHit: switches.hit ?? false,
    healPct: 0,
    guardPct: 0,
    guardTicks: 0,
    tags: [],
  })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  return { engine, player }
}

function castPlan() {
  return createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'USE_SKILL', skillId: METEOR })
}

describe('스킬 예고 이식', () => {
  it('예고를 쓰는 스킬은 즉발 대신 붉은 칸을 띄운다', () => {
    const { engine } = buildProbe(3)
    engine.applyActions([castPlan()])
    const active = engine.telegraphs.listActive()
    expect(active.length).toBe(1)
    expect(active[0]?.skillId).toBe(METEOR)
    expect(active[0]?.remainingTicks).toBe(3)
  })

  it('피해가 시전 시점에 얼어붙는다 — 파이썬과 같은 셈이다', () => {
    const { engine, player } = buildProbe(2)
    const before = player.attack
    engine.applyActions([castPlan()])
    const frozen = engine.telegraphs.listActive()[0]?.damage
    expect(frozen).toBe(before * 2)
  })

  it('예고를 안 쓰는 스킬은 지금대로 즉발이다', () => {
    const { engine } = buildProbe(0)
    engine.applyActions([castPlan()])
    expect(engine.telegraphs.listActive().length).toBe(0)
  })

  it('켜 둔 예고만 다른 행동에 끊긴다', () => {
    const on = buildProbe(3, { act: true })
    on.engine.applyActions([castPlan()])
    on.engine.applyActions([
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'APPROACH' }),
    ])
    expect(on.engine.telegraphs.listActive().length).toBe(0)

    const off = buildProbe(3)
    off.engine.applyActions([castPlan()])
    off.engine.applyActions([
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'APPROACH' }),
    ])
    expect(off.engine.telegraphs.listActive().length).toBe(1)
  })

  it('버티기는 시전을 안 끊는다 — 파이썬 `KEEP_CAST_ACTIONS` 와 같다', () => {
    // 「포기하지 않는다」를 적을 칸이 규칙표에 있어야 §10.3 의 선택이 성립한다.
    // 이것이 갈리면 브라우저에서 터진 마법이 서버 재시뮬에서는 취소된다 (G3).
    for (const actionId of ['HOLD', 'SET_FLAG']) {
      const { engine } = buildProbe(3, { act: true })
      engine.applyActions([castPlan()])
      engine.applyActions([createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId })])
      expect(engine.telegraphs.listActive().length, actionId).toBe(1)
    }
  })

  it('막아 낸 피해로는 안 끊긴다 — 그러면 방어가 벌이 된다', () => {
    const { engine, player } = buildProbe(3, { hit: true })
    engine.applyActions([castPlan()])
    engine.telegraphs.applyCancel(engine.state, engine.log, player.entityId, CANCEL_BY_HIT)
    expect(engine.telegraphs.listActive().length).toBe(0)
  })

  it('시전자가 자기 시전을 읽는다 — self_is_casting', () => {
    const { engine, player } = buildProbe(3)
    engine.applyActions([castPlan()])
    engine.state.tick = 1
    engine.runTelegraph()
    expect(engine.telegraphs.isCasting(player.entityId)).toBe(true)
  })
})

describe('마법 셋 이식', () => {
  function buildReal() {
    const balance = parseBalance(BALANCE)
    const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
    if (template === undefined) {
      throw new Error('open_field 템플릿이 없다')
    }
    const engine = buildEngine({ template, balance, seed: 3 })
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const target = engine.state.listHostiles(player)[0]
    if (target === undefined) {
      throw new Error('적이 없다')
    }
    return { engine, player, target }
  }

  function cast(skillId: string, targetId: string) {
    return createPlannedAction({
      entityId: PLAYER_ENTITY_ID,
      actionId: 'USE_SKILL',
      skillId,
      targetId,
    })
  }

  it('메테오는 반경 3 · 3틱 예고로 선다 — 파이썬 실측과 같다', () => {
    // 17 → 21 은 **중심이 시전자 발밑에서 겨눈 곳으로 옮겨 갔기 때문이다**. 예전에는
    // 자폭형에서 물려받은 자리라 10칸 밖 적에게 던진 메테오가 제 발밑에서 터졌다.
    const { engine, player, target } = buildReal()
    engine.applyActions([cast('METEOR', target.entityId)])
    const one = engine.telegraphs.listActive()[0]
    expect(one?.tiles.length).toBe(21)
    expect(one?.remainingTicks).toBe(3)
    const onSelf = (one?.tiles ?? []).some(
      (tile) => tile.x === player.position.x && tile.y === player.position.y,
    )
    expect(onSelf, '제 발밑에서 터지면 마법이 자해가 된다').toBe(false)
  })

  it('연쇄 번개는 대상 쪽으로 뻗는 직선이다', () => {
    const { engine, target } = buildReal()
    engine.applyActions([cast('CHAIN_BOLT', target.entityId)])
    const one = engine.telegraphs.listActive()[0]
    expect(one?.tiles.length).toBeGreaterThan(0)
    expect(one?.tiles.length).toBeLessThanOrEqual(4)
    expect(one?.remainingTicks).toBe(1)
  })

  it('서리 장판은 SLOW 를 걸고 이제 물기도 한다 — 자기 오사 포함', () => {
    // **피해 0 이었다 (§10.10).** 활 카이팅 기준선 84% 위에서 한 줄만 서리 장판으로
    // 바꾸면 61% 였고, 기준선을 넘는 유일한 변형이 「피해 60%」였다. SLOW 가 이동만
    // 늦춰서 사격형에게 효과가 없었기 때문이다. 화력 스킬은 여전히 아니다 —
    // 메테오의 220% 에 견주면 3분의 1 이다.
    const { engine, player, target } = buildReal()
    target.position = { x: player.position.x + 1, y: player.position.y }
    engine.applyActions([cast('FROST_FIELD', target.entityId)])
    const frozen = engine.telegraphs.listActive()[0]?.damage ?? -1
    expect(frozen).toBe(Math.floor((player.attack * 60) / 100))
    const beforeHp = target.hp
    for (const tick of [1, 2, 3]) {
      engine.state.tick = tick
      engine.runTelegraph()
    }
    expect(target.hp).toBe(beforeHp - frozen)
    expect(target.statuses.get('SLOW')).toBe(3)
    expect(player.statuses.get('SLOW')).toBe(3)
  })

  it('둔화는 두 틱에 한 칸이다 (GDD §211)', () => {
    const { engine, player, target } = buildReal()
    player.statuses.set('SLOW', 9)
    let moved = 0
    for (let tick = 0; tick < 6; tick += 1) {
      engine.state.tick = tick
      const before = { ...player.position }
      engine.applyActions([
        createPlannedAction({
          entityId: PLAYER_ENTITY_ID,
          actionId: 'APPROACH',
          targetId: target.entityId,
        }),
      ])
      if (player.position.x !== before.x || player.position.y !== before.y) {
        moved += 1
      }
    }
    expect(moved).toBe(3)
  })
})
