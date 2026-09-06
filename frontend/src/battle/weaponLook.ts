/**
 * 무기 겉모습 — 어느 칼이 어떻게 휘둘러지는가 (설계/10_외형과_모션).
 *
 * **정본을 복사하지 않는다.** `@resources` 별칭으로 원본을 그대로 읽는다 — 사본을 두면
 * 두 코어가 다른 데이터로 돌게 된다는 규율 그대로다 (CLAUDE.md).
 *
 * **`core_version` 에 안 낀다** (계약 C2). 이 파일에는 버전 키가 없고 여섯 축에도 없다 —
 * 겉모습을 고쳤다고 순위표 시즌이 갈리면 안 된다.
 *
 * **서버를 안 거친다** (계약 C1). 화면이 이미 장착 무기의 `catalogId` 를 알고 있으므로,
 * 겉모습이 티켓이나 로드아웃을 타고 올 이유가 없다 — 그것을 태우면 시뮬 입력처럼 보인다.
 */
import rawLooks from '@resources/balance/item_looks.json'

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
  looks: Record<string, { shape: string; motion: string }>
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
 * 이 무기가 어떻게 휘둘러지는가.
 *
 * @param catalogId 무기의 카탈로그 id. 빈 문자열이면 맨몸이다.
 * @returns 겉모습. 표에 없으면 기본값 — 새 무기가 들어와도 도면이 안 깨진다.
 */
export function resolveWeaponLook(catalogId: string): WeaponLook {
  const found = SOURCE.looks[catalogId]
  return found === undefined ? DEFAULT_LOOK : parseLook(found)
}
