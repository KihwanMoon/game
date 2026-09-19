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
import { CAST_CANCEL, CAST_FREE } from '../skills/catalog'
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
    castAct: switches.act === true ? CAST_CANCEL : CAST_FREE,
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

  it('취소로 적은 예고만 다른 행동에 끊긴다 — 파이썬 `cast_act` 와 같다', () => {
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
  function buildReal(templateId = 'open_field') {
    const balance = parseBalance(BALANCE)
    const template = ROOM_TEMPLATES.find((one) => one.templateId === templateId)
    if (template === undefined) {
      throw new Error(`${templateId} 템플릿이 없다`)
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

  it('★ 연쇄 번개는 적을 타고 튄다 — 직선이 아니다 (2026-09-17)', () => {
    // 예전에는 겨눈 대상 **뒤로** 뻗는 직선이라 적이 일렬로 설 때만 둘을 맞혔다.
    // 이제는 겨눈 대상에서 가까운 적으로 튄다 — 뭉친 적을 벌한다. 파이썬
    // `test_chain_bolt_hops_between_nearby_enemies` 와 같은 배치다.
    const { engine, player, target } = buildReal('chapel')
    const others = engine.state.listHostiles(player).filter((one) => one !== target)
    expect(others.length, '연쇄를 재려면 적이 셋은 있어야 한다').toBeGreaterThanOrEqual(2)
    const base = target.position
    // 두 칸씩 떨어뜨리되 **꺾어서** 놓는다. 일직선이면 예전 `LINE` 도 통과한다.
    ;(others[0] as { position: { x: number; y: number } }).position = {
      x: base.x + 2,
      y: base.y,
    }
    ;(others[1] as { position: { x: number; y: number } }).position = {
      x: base.x + 2,
      y: base.y + 2,
    }
    engine.applyActions([cast('CHAIN_BOLT', target.entityId)])
    const tiles = engine.telegraphs.listActive()[0]?.tiles ?? []
    const covers = (spot: { x: number; y: number }): boolean =>
      tiles.some((tile) => tile.x === spot.x && tile.y === spot.y)
    expect(covers(base)).toBe(true)
    expect(covers({ x: base.x + 2, y: base.y }), '두 칸 안의 적으로 튄다').toBe(true)
    expect(covers({ x: base.x + 2, y: base.y + 2 }), '튄 자리에서 또 튄다').toBe(true)
  })

  it('★ 겨눈 것이 없으면 안 튄다 — 자기 발밑을 지지지 않는다', () => {
    const { engine } = buildReal()
    engine.applyActions([cast('CHAIN_BOLT', '')])
    expect(engine.telegraphs.listActive()[0]?.tiles).toEqual([])
  })

  it('★ 서리 장판은 묶는다 — 둔화가 아니라 1틱 이동불가다 (2026-09-17)', () => {
    // 둔화는 「얼마나 느려지는가」를 물었고 그 답이 사격형에게는 아무것도 아니었다
    // (§10.10). 이제 묻는 것은 「어디에 묶이는가」다 — 이동만 막으므로 도망치려는
    // 쪽에만 걸린다. 자기 오사는 그대로다: 내가 밟으면 나도 묶인다.
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
    expect(target.statuses.get('ROOT')).toBe(1)
    expect(player.statuses.get('ROOT')).toBe(1)
    expect(target.statuses.get('SLOW'), '둔화는 더 이상 이 스킬의 것이 아니다').toBeUndefined()
  })

  it('★ 독이 적어 둔 틱 수만큼 정확히 문다 (2026-09-17)', () => {
    // `POISON` 은 인지 변수 목록에 처음부터 있었는데 거는 것도 깎는 것도 없었다 —
    // 물어볼 수는 있고 답은 영영 거짓인 항이었다. 파이썬
    // `test_poison_bites_every_tick_for_exactly_its_duration` 과 같은 배치다.
    const { engine, player } = buildReal()
    player.statuses.set('POISON', 3)
    const before = player.hp
    for (let tick = 1; tick <= 5; tick += 1) {
      engine.state.tick = tick
      engine.runUpkeep()
    }
    expect(before - player.hp).toBe(9)
    expect(player.statuses.get('POISON')).toBe(0)
  })

  it('★ 독은 방어력을 안 거치고 방벽은 거친다 — 용암과 같은 문이다', () => {
    const { engine, player } = buildReal()
    player.statuses.set('POISON', 1)
    player.statuses.set('GUARD', 5)
    const before = player.hp
    engine.state.tick = 1
    engine.runUpkeep()
    // 방벽 50% — 3 이 1 이 된다 (정수 내림, R5).
    expect(before - player.hp).toBe(1)
  })

  it('★ 이동불가는 발만 묶는다 — 손은 그대로다 (기절과 갈리는 자리)', () => {
    const { engine, player, target } = buildReal()
    target.position = { x: player.position.x + 1, y: player.position.y }
    player.statuses.set('ROOT', 1)
    const beforeSpot = { ...player.position }
    engine.applyActions([
      createPlannedAction({
        entityId: PLAYER_ENTITY_ID,
        actionId: 'APPROACH',
        targetId: target.entityId,
      }),
    ])
    expect(player.position, '묶였는데 움직였다').toEqual(beforeSpot)
    const beforeHp = target.hp
    engine.applyActions([
      createPlannedAction({
        entityId: PLAYER_ENTITY_ID,
        actionId: 'ATTACK',
        targetId: target.entityId,
      }),
    ])
    expect(target.hp, '묶였다고 손까지 묶으면 그것은 기절이다').toBeLessThan(beforeHp)
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

describe('둔화가 행동을 늦춘다 (2026-09-10 결정)', () => {
  it('★ 쉬는 틱에는 때리지도 못한다 — 이동만 막던 때는 사격형에 효과가 없었다', () => {
    const { engine, player } = buildProbe(0)
    const target = engine.state.listHostiles(player)[0]
    if (target === undefined) {
      throw new Error('적이 없다')
    }
    target.position = { x: player.position.x + 1, y: player.position.y }
    player.statuses.set('SLOW', 4)
    const before = target.hp

    engine.state.tick = 1 // 홀수 틱이 쉬는 틱이다
    engine.applyActions([
      createPlannedAction({
        entityId: PLAYER_ENTITY_ID,
        actionId: 'ATTACK',
        targetId: target.entityId,
      }),
    ])
    expect(target.hp, '쉬는 틱에 때렸다').toBe(before)

    engine.state.tick = 2
    engine.applyActions([
      createPlannedAction({
        entityId: PLAYER_ENTITY_ID,
        actionId: 'ATTACK',
        targetId: target.entityId,
      }),
    ])
    expect(target.hp, '쉬지 않는 틱에도 못 때렸다').toBeLessThan(before)
  })

  it('★ 쉬는 틱은 「다른 행동」이 아니다 — 둔화 한 번이 마법을 지우면 안 된다', () => {
    const { engine, player } = buildProbe(3, { act: true })
    engine.applyActions([castPlan()])
    player.statuses.set('SLOW', 4)
    engine.state.tick = 1
    engine.applyActions([
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'APPROACH' }),
    ])
    expect(engine.telegraphs.listActive().length).toBe(1)
  })
})
