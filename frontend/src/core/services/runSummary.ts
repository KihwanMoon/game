/**
 * 판 하나에서 결산 입력을 뽑아낸다 (GDD §2.3).
 *
 * 전투가 끝난 세계 상태를 읽어 "무엇을 만났고 무엇을 잡았고 어떤 블록을 접했는가" 를
 * 만든다. `manageMeta` 의 `applyRunSummary` 가 그것을 받아 세이브에 누적한다.
 *
 * 시뮬레이션과 메타 세이브를 엮으므로 `services/` 에 있다. 어느 한쪽에 두면 그쪽이
 * 반대쪽을 알게 된다.
 */
import { FACTION_ENEMY, type WorldState } from '../sim/state'
import type { RawEnemyKind } from '../sim/plan'
import { FIRST_FLOOR } from '../schemas/room'
import type { RuleSet } from '../schemas/ruleset'
import { listRulesetBlocks, type RunSummary } from './manageMeta'

/** 만난 적과 잡은 적. 항목 하나가 1회다 — 같은 종을 두 번 만났으면 두 번 들어 있다. */
export interface EnemyTally {
  readonly encountered: readonly string[]
  readonly defeated: readonly string[]
}

/** 층을 밟지 못한 런. 층 사슬이 붙기 전까지 패배가 여기 해당한다. */
const NO_FLOOR = 0

/**
 * 세계에 나타났던 적을 종류별로 센다.
 *
 * **죽은 개체도 센다.** 상태에서 지우지 않고 남기므로 소환물까지 빠짐없이 잡히며,
 * 그것이 도감을 정직하게 만든다 — 소환된 졸개를 잡은 것도 잡은 것이다.
 *
 * 정렬해서 돌려주는 것은 R5 다. Map 순회 순서가 세이브 파일에 새어 나가면 안 된다.
 *
 * @param state 전투가 끝난 세계 상태.
 * @returns 만난 종류와 잡은 종류. 둘 다 정렬돼 있고 항목 하나가 1회다.
 */
export function countEnemyKinds(state: WorldState): EnemyTally {
  const encountered: string[] = []
  const defeated: string[] = []
  for (const entity of state.entities.values()) {
    if (entity.faction !== FACTION_ENEMY) {
      continue
    }
    encountered.push(entity.kindId)
    if (entity.hp <= 0) {
      defeated.push(entity.kindId)
    }
  }
  return { encountered: encountered.sort(), defeated: defeated.sort() }
}

/**
 * 만난 적 종류의 규칙표를 모은다.
 *
 * 같은 종을 여러 번 만나도 규칙표는 하나다. 해금은 누적이라 중복이 뜻이 없다.
 *
 * @param kindIds 만난 적 종류 id. 중복이 들어와도 된다.
 * @param enemies 밸런스의 적 목록. kindId 에서 ruleset_id 를 찾는 데 쓴다.
 * @param enemyRulesets ruleset_id 에서 규칙표로의 대응표.
 * @returns 찾아낸 규칙표들. 대응표에 없는 id 는 조용히 건너뛴다.
 */
export function listEncounteredRulesets(
  kindIds: readonly string[],
  enemies: readonly RawEnemyKind[],
  enemyRulesets: ReadonlyMap<string, RuleSet>,
): readonly RuleSet[] {
  const rulesetIdByKind = new Map(enemies.map((kind) => [kind.id, kind.ruleset_id]))
  const found = new Map<string, RuleSet>()
  for (const kindId of kindIds) {
    const rulesetId = rulesetIdByKind.get(kindId)
    if (rulesetId === undefined) {
      continue
    }
    const ruleset = enemyRulesets.get(rulesetId)
    if (ruleset !== undefined) {
      found.set(rulesetId, ruleset)
    }
  }
  // 정렬해서 꺼낸다. 해금 목록이 Map 순회 순서에 기대면 안 된다 (R5).
  return [...found.entries()].sort((left, right) => (left[0] < right[0] ? -1 : 1)).map(([, r]) => r)
}

/**
 * 판 하나의 결산 입력을 만든다.
 *
 * 해금 목록에 **적의 규칙표가 쓰는 블록도 넣는다.** 도감이 적의 규칙표를 그대로
 * 보여주므로, 적을 만나는 것이 곧 그 블록을 접하는 것이다 (GDD §2.3).
 *
 * `floorReached` 는 지금 0 아니면 1 이다. 프런트가 아직 방 하나만 돌리기 때문이며,
 * 층 사슬(W14 절차적 생성)이 붙으면 그 깊이가 들어온다. 슬롯 보너스는 층 2부터
 * 붙으므로 지금은 보너스가 나오지 않는 것이 맞다.
 *
 * @param tally 만난 적과 잡은 적.
 * @param playerRuleset 이번 판에 쓴 플레이어 규칙표.
 * @param isCleared 플레이어가 이겼는가.
 * @param enemyRulesets 만난 적의 규칙표들. 없으면 플레이어 것만 센다.
 * @returns 결산 입력.
 */
export function buildRunSummary(
  tally: EnemyTally,
  playerRuleset: RuleSet,
  isCleared: boolean,
  enemyRulesets: readonly RuleSet[] = [],
): RunSummary {
  const { encountered, defeated } = tally
  const perceptions = new Set<string>()
  const actions = new Set<string>()
  for (const ruleset of [playerRuleset, ...enemyRulesets]) {
    const blocks = listRulesetBlocks(ruleset)
    for (const id of blocks.perceptions) {
      perceptions.add(id)
    }
    for (const id of blocks.actions) {
      actions.add(id)
    }
  }
  return {
    floorReached: isCleared ? FIRST_FLOOR : NO_FLOOR,
    isCleared,
    seenPerceptions: [...perceptions].sort(),
    seenActions: [...actions].sort(),
    encounteredKinds: encountered,
    defeatedKinds: defeated,
  }
}
