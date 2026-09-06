/**
 * 겉모습 — 누가 무엇을 어떻게 휘두르는가 (설계/10_외형과_모션).
 *
 * **정본을 복사하지 않는다.** `@resources` 별칭으로 원본을 그대로 읽는다 — 사본을 두면
 * 두 코어가 다른 데이터로 돌게 된다는 규율 그대로다 (CLAUDE.md).
 *
 * **`core_version` 에 안 낀다** (계약 C2). 이 파일에는 버전 키가 없고 여섯 축에도 없다 —
 * 겉모습을 고쳤다고 순위표 시즌이 갈리면 안 된다.
 *
 * **서버를 안 거친다** (계약 C1). 화면이 이미 장착 무기의 `catalogId` 를 알고 있으므로,
 * 겉모습이 티켓이나 로드아웃을 타고 올 이유가 없다 — 그것을 태우면 시뮬 입력처럼 보인다.
 *
 * **적도 제 무장으로 휘두른다** (2026-09-06). 표가 플레이어 것뿐이던 때는 늑대도 골렘도
 * 사거리 여섯 궁수도 전부 같은 직검을 내려쳤다 — 고리와 수치가 맞아도 자국이 거짓이면
 * 판이 틀리게 읽힌다. 적의 무장은 아이템이 아니라 **종**에 붙으므로 표가 둘이다.
 */
import rawLooks from '@resources/balance/looks.json'

import { PLAYER_ENTITY_ID } from '../core/services/runBattle'

import { resolveMotion, resolveShape } from './weaponSwing'
import type { SwingMotion, WeaponShape } from './weaponSwing'

/** 무기 하나의 겉모습. `shape` 가 `none` 이면 자국을 안 그린다. */
export interface WeaponLook {
  readonly shape: WeaponShape | 'none'
  readonly motion: SwingMotion
}

/** 정본 절의 모양. */
interface RawLooks {
  default: { shape: string; motion: string }
  /** 아이템 카탈로그 id 로 건다 — 플레이어가 낀 것. */
  looks: Record<string, { shape: string; motion: string }>
  /** 몬스터 종 id 로 건다 — 적의 무장은 아이템이 아니라 종에 붙는다. */
  monsters: Record<string, { shape: string; motion: string }>
}

const SOURCE = rawLooks as unknown as RawLooks

/**
 * 절 하나를 아는 값으로 접는다.
 *
 * @param raw 정본이 준 절.
 * @returns 겉모습.
 */
function parseLook(raw: { shape: string; motion: string }): WeaponLook {
  return {
    // **`none` 은 오타가 아니라 뜻이다.** 활은 휘두르지 않는다 — 사거리 넷 다섯에서
    // 칼자국이 뜨면 무슨 일이 있었는지가 거짓으로 읽힌다.
    shape: raw.shape === 'none' ? 'none' : resolveShape(raw.shape),
    motion: resolveMotion(raw.motion),
  }
}

/** 아무것도 안 꼈거나 모르는 무기일 때. 맨몸도 적도 이것으로 휘두른다. */
export const DEFAULT_LOOK: WeaponLook = parseLook(SOURCE.default)

/**
 * 몇 칸을 건너가면 「난 것」으로 본다.
 *
 * **표가 모르는 것에 칼자국을 씌우지 않기 위한 안전망이다.** 새 몬스터가 밸런스에
 * 들어와도, 남의 빌드를 입은 그림자가 장궁을 들었어도, 자국이 사거리를 거짓말하지
 * 않는다 — `arrow` 를 만든 이유 그대로다.
 */
const FLY_CELLS = 3

/** 표가 모르는데 멀리 닿았을 때. 화살로 날린다 — 훑는 자국은 그 자리에서 거짓이다. */
const FLYING_LOOK: WeaponLook = { shape: 'arrow', motion: 'fly' }

/**
 * 이 판에서 누가 무엇을 휘두르는가. 화면이 도면에 넘긴다.
 *
 * `cells` 는 이 한 방이 **실제로** 건너간 칸 수다. 선언된 사거리가 아니라 실측이라,
 * 사거리 다섯짜리가 코앞을 쳤으면 코앞을 친 것으로 그린다.
 */
export type LookTable = (entityId: string, kindId: string, cells: number) => WeaponLook

/**
 * 이 무기가 어떻게 휘둘러지는가.
 *
 * @param catalogId 무기의 카탈로그 id. 빈 문자열이면 맨몸이다.
 * @returns 겉모습. 표에 없으면 기본값 — 새 무기가 들어와도 도면이 안 깨진다.
 */
export function resolveWeaponLook(catalogId: string): WeaponLook {
  const found = SOURCE.looks[catalogId]
  return found === undefined ? DEFAULT_LOOK : parseLook(found)
}

/**
 * 모르는 것이 이만큼 멀리 닿았으면 무엇으로 그리는가.
 *
 * @param cells 이 한 방이 건너간 칸 수.
 * @returns 멀면 나는 것, 가까우면 기본 자국.
 */
function resolveUnknownLook(cells: number): WeaponLook {
  return cells >= FLY_CELLS ? FLYING_LOOK : DEFAULT_LOOK
}

/**
 * 이 몬스터가 무엇으로 치는가.
 *
 * **무장이 종에 붙는다.** 적은 아이템을 낀 것이 아니라 그 종이 곧 무장이다 — 늑대는
 * 엄니, 골렘은 덩이, 궁수는 활이다.
 *
 * **도플갱어는 표에 없다. 일부러다.** 그림자의 무장은 종의 것이 아니라 죽은 빌드의
 * 것이라 종으로는 못 정한다 — 실측 거리가 대신 답한다. 장궁 든 그림자가 사거리
 * 다섯에서 칼을 휘두르면 그것도 거짓이다.
 *
 * @param kindId 몬스터 종 id.
 * @param cells 이 한 방이 건너간 칸 수.
 * @returns 겉모습. 표에 없으면 거리가 정한다 — 새 적이 들어와도 도면이 안 거짓말한다.
 */
export function resolveActorLook(kindId: string, cells: number): WeaponLook {
  const found = SOURCE.monsters[kindId]
  return found === undefined ? resolveUnknownLook(cells) : parseLook(found)
}

/**
 * 이 판의 겉모습 표를 만든다.
 *
 * **화면 둘이 같은 표를 봐야 한다.** 관전과 사후 분석이 각자 만들면 되감기가 방금 본
 * 것과 다른 칼을 그린다 — 실제로 그랬다. 사후 분석이 표를 아예 안 받아 **리플레이만
 * 기본 자국 하나로** 돌았다(실제 신고).
 *
 * @param weaponCatalogId 플레이어가 낀 무기의 카탈로그 id. 빈 문자열이면 맨몸이다.
 * @returns entityId 를 겉모습으로 바꾸는 함수.
 */
export function buildLookOf(weaponCatalogId: string): LookTable {
  const found = SOURCE.looks[weaponCatalogId]
  return (entityId: string, kindId: string, cells: number) => {
    if (entityId !== PLAYER_ENTITY_ID) {
      return resolveActorLook(kindId, cells)
    }
    // **모르는 무기도 사거리는 거짓말하면 안 된다.** 카탈로그에 새 활이 들어오고
    // 표가 아직 모르면, 기본 직검이 아니라 거리가 답한다.
    return found === undefined ? resolveUnknownLook(cells) : parseLook(found)
  }
}
