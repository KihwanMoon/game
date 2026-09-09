/**
 * 유물이 바꾸는 제약이 두 코어에서 같이 도는가 (게이트 G3, 설계/5_스킬 §10.7).
 *
 * **골든이 이 경로를 하나도 안 덮는다.** 유물 축은 로드아웃이 실어 오는 값이라 골든
 * 케이스에 등장하지 않고, 그래서 파이썬만 고치고 여기를 빠뜨리면 같은 티켓이 브라우저
 * 에서는 예고 3틱 · 서버 재시뮬에서는 1틱으로 돈다. 방어 태세가 정확히 그 틈으로
 * 조용히 갈려 있었다.
 *
 * 파이썬 짝은 `tests/test_cast_relics.py` 다 — 같은 값을 같은 이름으로 본다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { getManhattanDistance } from '../grid/geometry'
import { createPlannedAction } from './plan'
import { MIN_LEAD_TICKS } from './telegraph'
import type { Entity } from './state'

const METEOR = 'METEOR'
const BASE_TELEGRAPH = 3
const BASE_RADIUS = 3
const BASE_COOLDOWN = 16

/** 유물 축을 얹은 엔진과 플레이어. 파이썬 `build_probe` 와 같은 값을 세운다. */
function buildProbe(axes: Partial<Entity> = {}) {
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
    shape: { kind: 'AREA', radius: BASE_RADIUS, length: 0 },
    targetFaction: '',
    coefPct: 200,
    cooldown: BASE_COOLDOWN,
    reach: null,
    telegraph: BASE_TELEGRAPH,
    cancelOnAct: true,
    cancelOnHit: true,
    healPct: 0,
    guardPct: 0,
    guardTicks: 0,
    tags: [],
  })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  Object.assign(player, axes)
  return { engine, player }
}

function castPlan() {
  return createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'USE_SKILL', skillId: METEOR })
}

describe('시전 유물 이식', () => {
  it('예지의 홀이 예고를 줄인다 — 3 → 1틱', () => {
    const { engine } = buildProbe({ castLeadCut: 2 })
    engine.applyActions([castPlan()])
    expect(engine.telegraphs.listActive()[0]?.remainingTicks).toBe(1)
  })

  it('예고가 0 까지는 안 내려간다 — 0 이면 즉발이라 회피가 성립하지 않는다', () => {
    const { engine } = buildProbe({ castLeadCut: 99 })
    engine.applyActions([castPlan()])
    expect(engine.telegraphs.listActive()[0]?.remainingTicks).toBe(MIN_LEAD_TICKS)
  })

  it('확산의 핵이 반경을 넓힌다 — 3 → 5', () => {
    const { engine, player } = buildProbe({ blastRadius: 2 })
    engine.applyActions([castPlan()])
    const tiles = engine.telegraphs.listActive()[0]?.tiles ?? []
    const reach = Math.max(...tiles.map((tile) => getManhattanDistance(player.position, tile)))
    expect(reach).toBe(BASE_RADIUS + 2)
  })

  it('넓힌 값을 쿨타임으로 문다 — 대가가 없으면 상위 호환이다', () => {
    const { engine, player } = buildProbe({ blastRadius: 2, castCooldownAdd: 8 })
    engine.applyActions([castPlan()])
    expect(player.cooldowns.get(METEOR)).toBe(BASE_COOLDOWN + 8)
  })

  it('그 대가가 평타에는 안 붙는다 — 마법의 대가지 캐릭터의 벌이 아니다', () => {
    const { engine, player } = buildProbe({ castCooldownAdd: 8 })
    engine.applyActions([
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'ATTACK' }),
    ])
    expect(player.cooldowns.get('ATTACK') ?? 0).toBe(0)
  })

  it('정착의 인장은 행동 취소만 끈다', () => {
    const { engine, player } = buildProbe({ steadyCast: 1 })
    engine.applyActions([castPlan()])
    engine.applyActions([createPlannedAction({ entityId: player.entityId, actionId: 'HOLD' })])
    expect(engine.telegraphs.listActive().length).toBe(1)
  })

  it('피격 취소는 남는다 — 둘 다 끄면 「안전한 자리에서 쏘는가」가 사라진다', () => {
    const { engine, player } = buildProbe({ steadyCast: 1 })
    engine.applyActions([castPlan()])
    engine.actions.applyDamage(player, 5, 'ACT', '시험', 'e1')
    expect(engine.telegraphs.listActive().length).toBe(0)
  })

  it('유물이 없으면 아무것도 안 달라진다 — 마법은 유물 없이도 쓴다', () => {
    const { engine, player } = buildProbe()
    engine.applyActions([castPlan()])
    expect(engine.telegraphs.listActive()[0]?.remainingTicks).toBe(BASE_TELEGRAPH)
    expect(player.cooldowns.get(METEOR)).toBe(BASE_COOLDOWN)
  })
})
