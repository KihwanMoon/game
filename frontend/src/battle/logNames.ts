/**
 * 실행 로그를 사람의 말로 — **누가 · 누구에게 · 무엇을 · 얼마나** (2026-09-15 요청).
 *
 * 코어의 로그 레코드는 id 로 적힌다. 그것이 옳다 — `entity_id` 는 두 코어가 대조하는
 * 열쇠이고(G3), 이름으로 적으면 이름을 고칠 때마다 골든이 갈린다. **바꾸는 자리는
 * 화면이다.**
 *
 * 고치기 전 로그는 이렇게 읽혔다.
 *
 *     T012 ▸ [3] 대상 거리[NEAREST](1) <= 1  → ATTACK @goblin_rusher_0
 *     T012 ▸     ATTACK @goblin_rusher_0     → goblin_rusher_0 HP 28/40   -12
 *
 * **누가 한 것인지가 아예 없었다.** 한 틱에 여러 개체가 줄을 남기는데 행위자 칸이 없으니
 * 전부 한 덩어리로 읽힌다 — 실제 신고가 그것이다.
 *
 * 이름은 **상태에서 만든다.** id 를 잘라 붙이면(`goblin_rusher_0` → `goblin_rusher`)
 * 소환물(`_s3`)·추격자(`_h4`)에서 어긋나고, 그 어긋남은 조용하다.
 */
import type { LogEntry } from '../core/eventLog'
import type { BlockCatalog } from '../core/schemas'
import type { WorldState } from '../core/sim/state'
import { FACTION_PLAYER } from '../core/sim/state'

/** 화면에 쓸 이름 하나. 내 편인지 함께 담는다 — 색이 그것을 가른다. */
export interface ActorName {
  readonly name: string
  readonly isMine: boolean
}

/** 로그 한 줄의 결. 색·글리프·말 셋이 같은 것을 가리킨다 (design/README D-1). */
export type LogTone = 'decide' | 'damage' | 'heal' | 'waste' | 'death' | 'world' | 'act'

/** 같은 종이 여럿일 때 붙이는 번호. 열을 넘으면 그냥 숫자로 적는다. */
const CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'

/** 나를 가리키는 말. id 는 `player` 지만 화면에서 나는 나다. */
export const MY_NAME = '나'

/** 세계가 남기는 줄의 행위자 id (추격자 등장·압력). */
const WORLD_ID = 'world'

/** 세계가 남기는 줄에 적을 이름. */
const WORLD_NAME = '비각'

/** 틱을 버린 줄에 들어 있는 말. 셋 다 「아무 일도 안 일어났다」다. */
const WASTE_MARK = '틱 낭비'

/** 쓰러진 줄에 들어 있는 말. */
const DEATH_MARK = '사망'

/**
 * 같은 종이 여럿이면 번호를 붙인다.
 *
 * @param index 그 종 안에서의 차례 (0부터).
 * @param total 그 종이 몇인가.
 * @returns 번호. 하나뿐이면 빈 문자열.
 */
function formatOrdinal(index: number, total: number): string {
  if (total <= 1) {
    return ''
  }
  return ` ${CIRCLED[index] ?? String(index + 1)}`
}

/**
 * 이 판에 선 개체들의 이름표를 만든다.
 *
 * **`entityId` 순으로 번호를 매긴다.** 자리(좌표)로 매기면 움직일 때마다 ①과 ②가
 * 뒤바뀌어, 같은 개체를 두 줄에서 다른 이름으로 부르게 된다.
 *
 * @param state 지금 세계 상태.
 * @param labels 종 id 에서 한글 이름으로. balance.json 의 `enemies[].label_ko` 다.
 * @returns 엔티티 id 에서 이름표로.
 */
export function buildActorNames(
  state: WorldState,
  labels: ReadonlyMap<string, string>,
  ownerNames?: ReadonlyMap<string, string>,
): ReadonlyMap<string, ActorName> {
  const ids = [...state.entities.keys()].sort((left, right) => left.localeCompare(right))
  const counts = new Map<string, number>()
  for (const id of ids) {
    const kind = state.entities.get(id)?.kindId ?? ''
    counts.set(kind, (counts.get(kind) ?? 0) + 1)
  }
  const seen = new Map<string, number>()
  const names = new Map<string, ActorName>()
  for (const id of ids) {
    const entity = state.entities.get(id)
    if (entity === undefined) {
      continue
    }
    const isMine = entity.faction === FACTION_PLAYER
    if (isMine) {
      names.set(id, { name: MY_NAME, isMine: true })
      continue
    }
    const at = seen.get(entity.kindId) ?? 0
    seen.set(entity.kindId, at + 1)
    // **그림자는 주인 이름으로 부른다** (2026-09-16). 「도플갱어①」로 뜨면 누구를 만난
    // 것인지 모르고, 이 기제의 전제인 「거기까지 실제로 내려간 빌드」가 이름을 잃는다 —
    // 남는 것은 숫자 큰 정예 몹 하나다. 종 이름을 함께 두어 무엇인지도 안 잃는다.
    const owner = ownerNames?.get(id) ?? ''
    const base = labels.get(entity.kindId) ?? entity.kindId
    if (owner !== '') {
      names.set(id, { name: `${owner}의 ${base}`, isMine: false })
      continue
    }
    names.set(id, { name: `${base}${formatOrdinal(at, counts.get(entity.kindId) ?? 1)}`, isMine: false })
  }
  names.set(WORLD_ID, { name: WORLD_NAME, isMine: false })
  return names
}

/**
 * 문구 안의 id 를 이름으로 바꾼다.
 *
 * **긴 id 부터 바꾼다.** `goblin_rusher_0` 을 `goblin_rusher` 로 먼저 자르면 뒤의 `_0`
 * 이 남아 「몽둥이 도깨비_0」 이 된다.
 *
 * @param text 원문.
 * @param names 이름표.
 * @returns 이름으로 바뀐 문구.
 */
export function replaceIds(text: string, names: ReadonlyMap<string, ActorName>): string {
  const ids = [...names.keys()].sort((left, right) => right.length - left.length)
  let out = text
  for (const id of ids) {
    const name = names.get(id)?.name ?? id
    out = out.split(id).join(name)
  }
  return out
}

/**
 * 행동 코드를 팔레트와 같은 말로 바꾼다.
 *
 * **팔레트가 쓰는 낱말을 그대로 쓴다.** 로그가 다른 말로 적으면, 본 것을 자기 내력에
 * 옮겨 적을 수 없다 — 도감이 규칙표와 같은 표기를 쓰는 것과 같은 이유다.
 *
 * @param text 원문. 앞머리가 행동 코드일 수 있다.
 * @param catalog 블록 카탈로그.
 * @returns 한글 행동으로 바뀐 문구.
 */
export function translateActions(text: string, catalog: BlockCatalog): string {
  return text.replace(/^([A-Z][A-Z0-9_]*)/, (code) => catalog.actions.get(code)?.labelKo ?? code)
}

/**
 * 로그 한 줄의 결을 정한다.
 *
 * **색이 유일한 채널이 아니다.** 결마다 글리프와 말이 함께 붙으므로, 색을 못 봐도
 * 「헛돌았다」와 「쓰러졌다」가 갈린다 (design/README D-1).
 *
 * @param entry 로그 레코드.
 * @returns 그 줄의 결.
 */
export function readLogTone(entry: LogEntry): LogTone {
  if (entry.phase === 'DECIDE') {
    return 'decide'
  }
  if (entry.phase === 'UPKEEP') {
    return 'world'
  }
  if (entry.outcome.includes(DEATH_MARK)) {
    return 'death'
  }
  if (entry.outcome.includes(WASTE_MARK)) {
    return 'waste'
  }
  const delta = entry.delta ?? 0
  if (delta < 0) {
    return 'damage'
  }
  if (delta > 0) {
    return 'heal'
  }
  return 'act'
}
