/**
 * 판에서 결산 입력을 뽑는 규칙을 본다 (GDD §2.3).
 *
 * 여기서 지키는 것은 셋이다 — **죽은 개체도 센다**(소환물을 빠뜨리면 도감이 거짓말을
 * 한다), **정렬해서 낸다**(Map 순회 순서가 세이브에 새면 안 된다, R5), **적의 규칙표가
 * 쓰는 블록도 해금된다**(적을 만나는 것이 곧 그 블록을 접하는 것이다).
 */
import { describe, expect, it } from 'vitest'

import { DeterministicRng } from '../rng'
import { ROOM_TEMPLATES } from '../resources'
import { parseRuleSet } from '../schemas/ruleset'
import type { RawEnemyKind } from '../sim/plan'
import { FACTION_ENEMY, FACTION_PLAYER, WorldState, createEntity } from '../sim/state'
import { buildRunSummary, countEnemyKinds, listEncounteredRulesets } from './runSummary'

/**
 * 빈 세계를 만든다. 방과 난수원은 집계에 쓰이지 않지만 생성자가 요구한다.
 *
 * @returns 개체가 없는 세계.
 */
function createWorld(): WorldState {
  const room = ROOM_TEMPLATES[0]
  if (room === undefined) {
    throw new Error('방 템플릿이 없다')
  }
  return new WorldState(room, new DeterministicRng(0n))
}

/**
 * 검사용 개체 하나를 세계에 넣는다.
 *
 * @param state 넣을 세계.
 * @param entityId 개체 id.
 * @param kindId 종류 id.
 * @param faction 진영.
 * @param hp 남은 HP. 0 이면 죽은 것이다.
 */
function addEntity(
  state: WorldState,
  entityId: string,
  kindId: string,
  faction: string,
  hp: number,
): void {
  state.entities.set(
    entityId,
    createEntity({
      entityId,
      kindId,
      faction,
      position: { x: 0, y: 0 },
      hp,
      hpMax: 10,
      attack: 1,
      defense: 0,
      attackRange: 1,
      initiative: 10,
    }),
  )
}

/**
 * 규칙 하나짜리 규칙표를 만든다.
 *
 * @param rulesetId 규칙표 id.
 * @param lhs 조건 좌변.
 * @param action 행동.
 * @returns 만들어진 규칙표.
 */
function buildRuleSet(rulesetId: string, lhs: string, action: string) {
  return parseRuleSet({
    ruleset_id: rulesetId,
    version: 1,
    rules: [
      {
        priority: 1,
        cpu_cost: 1,
        action,
        target: 'NEAREST',
        set_flag: null,
        conditions: { op: 'AND', terms: [{ lhs, cmp: '<=', rhs: 3 }] },
      },
    ],
  })
}

describe('적 집계', () => {
  it('죽은 개체도 조우에 센다', () => {
    // 상태에서 지우지 않으므로 소환된 졸개까지 빠짐없이 잡힌다.
    const state = createWorld()
    addEntity(state, 'player', 'hero', FACTION_PLAYER, 10)
    addEntity(state, 'e1', 'goblin_rusher', FACTION_ENEMY, 0)
    addEntity(state, 'e2', 'goblin_rusher', FACTION_ENEMY, 4)
    const tally = countEnemyKinds(state)
    expect(tally.encountered).toEqual(['goblin_rusher', 'goblin_rusher'])
    expect(tally.defeated).toEqual(['goblin_rusher'])
  })

  it('플레이어는 세지 않는다', () => {
    const state = createWorld()
    addEntity(state, 'player', 'hero', FACTION_PLAYER, 0)
    expect(countEnemyKinds(state).encountered).toEqual([])
  })

  it('정렬해서 낸다', () => {
    // 넣은 순서가 세이브 파일에 새어 나가면 안 된다 (R5).
    const state = createWorld()
    addEntity(state, 'e1', 'mender_acolyte', FACTION_ENEMY, 0)
    addEntity(state, 'e2', 'bomb_slime', FACTION_ENEMY, 0)
    addEntity(state, 'e3', 'arch_summoner', FACTION_ENEMY, 0)
    const tally = countEnemyKinds(state)
    expect(tally.encountered).toEqual(['arch_summoner', 'bomb_slime', 'mender_acolyte'])
    expect(tally.defeated).toEqual(tally.encountered)
  })
})

describe('만난 적의 규칙표', () => {
  const enemies = [
    { id: 'goblin_rusher', ruleset_id: 'ai_rusher' },
    { id: 'goblin_archer', ruleset_id: 'ai_archer' },
  ] as unknown as readonly RawEnemyKind[]
  const rulesets = new Map([
    ['ai_rusher', buildRuleSet('ai_rusher', 'target_distance', 'APPROACH')],
    ['ai_archer', buildRuleSet('ai_archer', 'self_hp_percent', 'RETREAT')],
  ])

  it('같은 종을 여러 번 만나도 규칙표는 하나다', () => {
    const found = listEncounteredRulesets(
      ['goblin_rusher', 'goblin_rusher', 'goblin_archer'],
      enemies,
      rulesets,
    )
    expect(found.map((item) => item.rulesetId)).toEqual(['ai_archer', 'ai_rusher'])
  })

  it('모르는 종은 조용히 건너뛴다', () => {
    expect(listEncounteredRulesets(['nope'], enemies, rulesets)).toEqual([])
  })
})

describe('결산 입력', () => {
  const player = buildRuleSet('player', 'target_distance', 'ATTACK')
  const enemy = buildRuleSet('ai_archer', 'self_hp_percent', 'RETREAT')
  const tally = { encountered: ['goblin_archer'], defeated: ['goblin_archer'] }

  it('적 규칙표가 쓰는 블록도 해금 목록에 들어간다', () => {
    // 도감이 적의 규칙표를 그대로 공개하므로, 만나는 것이 곧 접하는 것이다.
    const summary = buildRunSummary(tally, player, true, [enemy])
    expect(summary.seenPerceptions).toEqual(['self_hp_percent', 'target_distance'])
    expect(summary.seenActions).toEqual(['ATTACK', 'RETREAT'])
  })

  it('이기면 층 1 을 밟은 것이다', () => {
    expect(buildRunSummary(tally, player, true).floorReached).toBe(1)
  })

  it('지면 층을 밟지 못한 것이다', () => {
    // 층 사슬이 붙기 전까지는 이것이 방 하나의 성패를 그대로 뜻한다.
    expect(buildRunSummary(tally, player, false).floorReached).toBe(0)
  })

  it('진 판도 조우와 해금은 남긴다', () => {
    // 실패는 정보다 (P1). 이겼는지가 아니라 무엇을 접했는지로 쌓인다.
    const summary = buildRunSummary(tally, player, false, [enemy])
    expect(summary.encounteredKinds).toEqual(['goblin_archer'])
    expect(summary.seenActions).toContain('RETREAT')
  })
})
