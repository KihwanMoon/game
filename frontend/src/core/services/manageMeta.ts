/**
 * 메타 세이브 유스케이스 — 런이 끝났을 때 무엇이 남는가 (GDD §2.3, TDD §9).
 *
 * `game/app/services/manage_meta.py` 의 이식이다. 저장 파일 형식만이 아니라 **결산
 * 규칙도 같아야 한다** — 파이썬 헤드리스 러너로 만든 세이브를 브라우저가 그대로 읽고
 * 이어서 쓰기 때문이다.
 *
 * 결산이 남기는 것이 왜 이 셋인지가 설계의 핵심이다. 해금 블록과 도감은 **다음 런의
 * 규칙표를 더 잘 쓰게 하는 것**이지 캐릭터를 세게 만드는 것이 아니다. 스탯이 아니라
 * 정보가 누적되므로, 진 런도 "적을 카운터하는 규칙" 이라는 자산을 남긴다 (P1).
 */
import { FIRST_FLOOR, MAX_SLOT_BONUS } from '../schemas/metaSave'
import type { BestiaryRecord, MetaSave } from '../schemas/metaSave'
import type { BlockCatalog } from '../schemas/blocks'
import type { RuleSet } from '../schemas/ruleset'

/**
 * 런 하나가 남긴 것. 결산의 입력이다.
 *
 * 조우·처치 목록은 **항목 하나가 1회**다. 같은 종을 두 번 만났으면 두 번 적는다.
 * 처치 목록은 조우 목록의 부분집합으로 넘긴다 — 잡았으면 만난 것이다.
 */
export interface RunSummary {
  readonly floorReached: number
  readonly isCleared: boolean
  readonly seenPerceptions: readonly string[]
  readonly seenActions: readonly string[]
  readonly encounteredKinds: readonly string[]
  readonly defeatedKinds: readonly string[]
}

/**
 * 층 도달 기록이 주는 시작 규칙 슬롯 보너스 (GDD §2.3).
 *
 * @param bestFloor 지금까지 도달한 가장 깊은 층.
 * @returns 더해지는 슬롯 수. 층 1 까지는 0 이고 최대 +4 에서 멈춘다.
 */
export function getSlotBonus(bestFloor: number): number {
  if (bestFloor <= FIRST_FLOOR) {
    return 0
  }
  return Math.min(MAX_SLOT_BONUS, bestFloor - FIRST_FLOOR)
}

/**
 * 이 세이브로 시작하는 런의 규칙 슬롯 상한.
 *
 * @param meta 현재 메타 세이브.
 * @param baseSlots balance.json 의 기본 슬롯 수.
 * @returns 기본값에 층 기록 보너스를 더한 값.
 */
export function getRuleSlotCap(meta: MetaSave, baseSlots: number): number {
  return baseSlots + getSlotBonus(meta.bestFloor)
}

/**
 * 규칙표가 쓰는 인지 변수와 행동을 모은다.
 *
 * 도감이 적의 규칙표를 그대로 보여주므로, 적을 만나는 것이 곧 그 규칙표가 쓰는
 * 블록을 "접하는" 것이다. 결산이 해금 목록을 만들 때 이 함수를 쓴다.
 *
 * @param ruleset 훑을 규칙표.
 * @returns 인지 변수와 행동. 둘 다 정렬돼 있다.
 */
export function listRulesetBlocks(ruleset: RuleSet): {
  readonly perceptions: readonly string[]
  readonly actions: readonly string[]
} {
  const perceptions = new Set<string>()
  const actions = new Set<string>()
  for (const rule of ruleset.rules) {
    actions.add(rule.action)
    for (const term of rule.conditions.terms) {
      perceptions.add(term.lhs)
    }
  }
  return { perceptions: [...perceptions].sort(), actions: [...actions].sort() }
}

/**
 * 이미 해금된 것과 이번 런에 접한 것을 합친다.
 *
 * @param current 지금까지 해금된 블록 id.
 * @param seen 이번 런에 접한 블록 id.
 * @param allowed 카탈로그가 아는 id 목록. undefined 면 거르지 않는다.
 * @returns 정렬된 해금 목록.
 */
function mergeUnlocked(
  current: readonly string[],
  seen: readonly string[],
  allowed: ReadonlySet<string> | undefined,
): readonly string[] {
  const merged = new Set(current)
  // 오타 난 id 가 들어오면 영영 쓸 수 없는 해금이 세이브에 남는다. 카탈로그를 받은
  // 경우에만 거른다 — 카탈로그 없이 부르는 쪽이 판단을 미룰 수 있게.
  for (const blockId of seen) {
    if (allowed === undefined || allowed.has(blockId)) {
      merged.add(blockId)
    }
  }
  return [...merged].sort()
}

/**
 * 도감에 이번 런의 조우·처치를 더한다.
 *
 * @param records 기존 도감.
 * @param encountered 이번 런에 만난 적 종류 id.
 * @param defeated 이번 런에 잡은 적 종류 id.
 * @returns kindId 순으로 정렬된 도감.
 */
function mergeBestiary(
  records: readonly BestiaryRecord[],
  encountered: readonly string[],
  defeated: readonly string[],
): readonly BestiaryRecord[] {
  const counts = new Map<string, [number, number]>()
  for (const record of records) {
    counts.set(record.kindId, [record.encounters, record.defeats])
  }
  for (const kindId of encountered) {
    const tally = counts.get(kindId) ?? [0, 0]
    tally[0] += 1
    counts.set(kindId, tally)
  }
  for (const kindId of defeated) {
    const tally = counts.get(kindId) ?? [0, 0]
    tally[1] += 1
    counts.set(kindId, tally)
  }
  // 정렬해서 꺼낸다. Map 순회 순서가 세이브 파일에 새어 나가면 안 된다 (R5).
  return [...counts.entries()]
    .sort((left, right) => (left[0] < right[0] ? -1 : 1))
    .map(([kindId, tally]) => ({ kindId, encounters: tally[0], defeats: tally[1] }))
}

/**
 * 런 결산을 메타 세이브에 반영한다 (GDD §2.3).
 *
 * 해금과 도감은 누적이고 층 기록은 최대값이다. 이번 런이 더 얕게 죽었다고 해서 슬롯
 * 상한이 줄지 않는다 — 줄면 재도전이 벌이 되고 P1 이 무너진다.
 *
 * @param meta 지금까지의 세이브.
 * @param summary 이번 런의 결산 입력.
 * @param catalog 동결된 블록 카탈로그. 주면 모르는 블록 id 를 걸러낸다.
 * @returns 갱신된 새 세이브. 인자로 받은 세이브는 그대로 둔다.
 */
export function applyRunSummary(
  meta: MetaSave,
  summary: RunSummary,
  catalog?: BlockCatalog,
): MetaSave {
  const perceptionIds = catalog ? new Set(catalog.perceptions.keys()) : undefined
  const actionIds = catalog ? new Set(catalog.actions.keys()) : undefined
  return {
    ...meta,
    bestFloor: Math.max(meta.bestFloor, summary.floorReached),
    unlockedPerceptions: mergeUnlocked(
      meta.unlockedPerceptions,
      summary.seenPerceptions,
      perceptionIds,
    ),
    unlockedActions: mergeUnlocked(meta.unlockedActions, summary.seenActions, actionIds),
    bestiary: mergeBestiary(meta.bestiary, summary.encounteredKinds, summary.defeatedKinds),
  }
}

/**
 * 서버 세이브를 정본으로 받아들인다.
 *
 * **성취는 서버 것이 이긴다.** 해금·도감·최고 층은 서버가 재시뮬에서 뽑는 것이고, 기기에
 * 쌓인 값은 오프라인 연습이 만든 낙관적 표시일 뿐이다 — 서버가 뒷받침하지 않는 해금을
 * 화면이 계속 보여 주면, 그것이 순위에 반영되지 않는다는 사실이 나중에 드러난다.
 *
 * 오프라인 런은 원래 보상을 주지 않으므로(티켓이 없으면 제출도 없다) 여기서 잃는 것은
 * 표시뿐이다.
 *
 * **프리셋은 기기 것을 지킨다.** 편집 중인 것이 기기에 있고, 서버 것으로 덮으면 방금 짠
 * 규칙표가 사라진다.
 *
 * @param server 서버가 준 세이브.
 * @param local 이 기기의 세이브.
 * @returns 서버 성취 + 기기 프리셋.
 */
export function adoptServerMeta(server: MetaSave, local: MetaSave): MetaSave {
  return {
    ...server,
    presets: local.presets.length > 0 ? local.presets : server.presets,
  }
}
