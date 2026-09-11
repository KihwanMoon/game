/**
 * 주문서 셋이 두 코어에서 같이 도는가 (게이트 G3, 2026-09-11 결정).
 *
 * **골든이 이 경로를 하나도 안 덮는다.** 골든 규칙표 중 `USE_ITEM[BLINK]` 를 쓰는 것이
 * 없고, 소모품은 로드아웃이 실어 오는 값이라 골든 케이스에 등장하지 않는다. 그래서
 * 파이썬만 고치고 여기를 빠뜨리면 같은 티켓이 브라우저에서는 순간이동을 하고 서버
 * 재시뮬에서는 「쓸 줄 모른다」로 떨어진다 — 마법이 정확히 그 틈으로 갈려 있었다.
 *
 * 파이썬 짝은 `tests/test_scrolls.py` 다 — 같은 값을 같은 이름으로 본다.
 */
import { describe, expect, it } from 'vitest'

import { TRIGGER_LABELS } from '../../content/consumableTags'
import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { getManhattanDistance } from '../grid/geometry'
import { GUARD_STATUS, ITEM_SCROLL } from './abilities'
import { FREE_ITEMS, createPlannedAction } from './plan'
import {
  FOCUS_RANGE_BONUS,
  TRIGGERS,
  FOCUS_TICKS,
  ITEM_BLINK,
  ITEM_FLAME,
  ITEM_FOCUS,
  STATUS_FOCUS,
  checkAlreadyHeld,
  readReach,
} from './scrolls'

/** 주문서 한 종류를 들린 플레이어와 엔진. 파이썬 `build_probe` 와 같은 값을 세운다. */
function buildProbe(tag: string, charges = 1) {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  player.consumables.set(tag, charges)
  return { engine, player }
}

function useScroll(engine: ReturnType<typeof buildProbe>['engine'], tag: string, ruleIndex = 1) {
  engine.applyActions([
    createPlannedAction({
      entityId: PLAYER_ENTITY_ID,
      actionId: 'USE_ITEM',
      itemKind: tag,
      ruleIndex,
      expr: `USE_ITEM[${tag}]`,
    }),
  ])
}

describe('주문서 이식', () => {
  it('부릅은 규칙표가 셀 수 있는 틱만큼 간다 — 유지시간이 상수다', () => {
    const { engine, player } = buildProbe(ITEM_FOCUS)
    useScroll(engine, ITEM_FOCUS)
    expect(player.statuses.get(STATUS_FOCUS)).toBe(FOCUS_TICKS)
  })

  it('부릅이 사거리를 한 칸 늘린다 — 읽는 자리가 하나다', () => {
    const { engine, player } = buildProbe(ITEM_FOCUS)
    const base = readReach(player)
    useScroll(engine, ITEM_FOCUS)
    expect(readReach(player)).toBe(base + FOCUS_RANGE_BONUS)
  })

  it('걸어 둔 것은 반드시 풀린다 — 안 풀리면 한 장이 판 전체를 산다', () => {
    const { engine, player } = buildProbe(ITEM_FOCUS)
    useScroll(engine, ITEM_FOCUS)
    for (let tick = 0; tick <= FOCUS_TICKS; tick += 1) {
      engine.runUpkeep()
    }
    expect(readReach(player)).toBe(player.attackRange)
  })

  it('이미 걸려 있으면 겹쳐 쓰기가 막힌다 — 즉발은 안 막힌다', () => {
    const { player } = buildProbe(ITEM_FOCUS, 2)
    player.statuses.set(STATUS_FOCUS, FOCUS_TICKS)
    expect(checkAlreadyHeld(player, ITEM_FOCUS)).toBe(true)
    expect(checkAlreadyHeld(player, ITEM_BLINK)).toBe(false)
    expect(checkAlreadyHeld(player, ITEM_FLAME)).toBe(false)
  })

  it('보호 주문서는 틱을 안 쓴다 — 같은 기제면 같은 규칙이다', () => {
    const { engine, player } = buildProbe(ITEM_SCROLL, 2)
    engine.actions.applyItem(
      player,
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'HOLD' }),
      ITEM_SCROLL,
    )
    // 공짜인 것은 틱이지 장수가 아니다 — 충전이 안 타면 한 장이 판 전체를 산다.
    expect(player.consumables.get(ITEM_SCROLL)).toBe(1)
    expect(player.statuses.get(GUARD_STATUS) ?? 0).toBeGreaterThan(0)
  })

  it('즉발 주문서는 그대로 틱을 낸다 — 공짜는 켜 두고 기다리는 것뿐이다', () => {
    expect(FREE_ITEMS.has(ITEM_SCROLL)).toBe(true)
    expect(FREE_ITEMS.has(ITEM_BLINK)).toBe(false)
    expect(FREE_ITEMS.has(ITEM_FLAME)).toBe(false)
    expect(FREE_ITEMS.has(ITEM_FOCUS)).toBe(false)
  })

  it('순간이동이 한 칸으로는 못 벌리는 거리를 연다', () => {
    const { engine, player } = buildProbe(ITEM_BLINK)
    const nearest = () =>
      Math.min(
        ...engine.state
          .listHostiles(player)
          .map((one) => getManhattanDistance(player.position, one.position)),
      )
    const before = nearest()
    useScroll(engine, ITEM_BLINK)
    expect(nearest()).toBeGreaterThan(before)
    expect(player.consumables.get(ITEM_BLINK)).toBe(0)
  })

  it('갈 곳이 없으면 충전을 안 태운다', () => {
    const { engine, player } = buildProbe(ITEM_BLINK)
    for (const other of engine.state.listHostiles(player)) {
      other.hp = 0
    }
    useScroll(engine, ITEM_BLINK)
    expect(player.consumables.get(ITEM_BLINK)).toBe(1)
  })

  it('화염은 예고 없이 둘레를 태운다 — 피해가 로그에 피격자별로 남는다', () => {
    const { engine, player } = buildProbe(ITEM_FLAME)
    const victim = engine.state.listHostiles(player)[0]
    if (victim === undefined) {
      throw new Error('적이 없다')
    }
    victim.position = { x: player.position.x + 1, y: player.position.y }
    const before = victim.hp
    useScroll(engine, ITEM_FLAME, 3)
    expect(victim.hp).toBeLessThan(before)
    expect(engine.telegraphs.listActive().length).toBe(0)
    const hits = engine.log.entries.filter(
      (one) => one.entityId === PLAYER_ENTITY_ID && one.outcome.includes(victim.entityId),
    )
    expect(hits.length, '피격자별 줄이 없다 — 피해 지도에서 화염이 안 보인다').toBeGreaterThan(0)
    expect(hits[hits.length - 1]?.rule).toBe(3)
  })

  it('반경 안에 적이 없으면 충전을 안 태운다', () => {
    const { engine, player } = buildProbe(ITEM_FLAME)
    for (const other of engine.state.listHostiles(player)) {
      other.position = { x: 0, y: 0 }
      other.hp = 0
    }
    useScroll(engine, ITEM_FLAME)
    expect(player.consumables.get(ITEM_FLAME)).toBe(1)
  })
})

describe('조건 발동 이식', () => {
  it('규칙 줄 없이 터진다 — 포위되면 순간이동', () => {
    const { engine, player } = buildProbe(ITEM_BLINK)
    const hostiles = engine.state.listHostiles(player).slice(0, 2)
    expect(hostiles.length).toBe(2)
    for (const one of hostiles) {
      one.position = { ...player.position }
    }
    engine.actions.applyAutoScrolls(
      player,
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'HOLD' }),
    )
    expect(player.consumables.get(ITEM_BLINK)).toBe(0)
  })

  it('왜 터졌는지가 로그에 남는다 — 규칙 번호는 안 붙는다', () => {
    const { engine, player } = buildProbe(ITEM_BLINK)
    for (const one of engine.state.listHostiles(player).slice(0, 2)) {
      one.position = { ...player.position }
    }
    engine.actions.applyAutoScrolls(
      player,
      createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'HOLD' }),
    )
    const lines = engine.log.entries.filter((one) => one.expr.includes('인접 적'))
    expect(lines.length, '발동 사유가 로그에 없다').toBeGreaterThan(0)
    expect(lines[lines.length - 1]?.rule).toBe(null)
  })

  it('규칙표가 그 태그를 쓰면 자동은 물러난다 — 내가 적은 줄이 세다', () => {
    const { engine, player } = buildProbe(ITEM_BLINK)
    for (const one of engine.state.listHostiles(player).slice(0, 2)) {
      one.position = { ...player.position }
    }
    engine.actions.applyAutoScrolls(
      player,
      createPlannedAction({
        entityId: PLAYER_ENTITY_ID,
        actionId: 'HOLD',
        managedItems: [ITEM_BLINK],
      }),
    )
    expect(player.consumables.get(ITEM_BLINK)).toBe(1)
  })

  it('★ 저절로 터지는 태그는 전부 화면에 적을 말이 있다', () => {
    // **안 보이면 없는 것이다.** 규칙 줄 없이 터지므로, 조건을 화면이 못 적으면 들고 가는
    // 사람에게는 「언젠가 사라지는 물건」이 된다.
    for (const useTag of TRIGGERS.keys()) {
      expect(TRIGGER_LABELS.get(useTag), `${useTag} 의 발동 조건을 적을 말이 없다`).toBeDefined()
    }
  })

  it('물약에는 기본 트리거가 없다 — 언제 마실지가 이 게임의 질문이다', () => {
    expect(TRIGGERS.has('POTION')).toBe(false)
    expect([...TRIGGERS.keys()]).toEqual(['SCROLL', ITEM_BLINK, ITEM_FLAME, ITEM_FOCUS])
  })
})
