/**
 * 도면 위 말의 종류 결정 — 적 유형 8종을 PlanActor 의 kind 4종에 접는다.
 *
 * **접는 지점이 정보 손실이라 여기에 규칙을 적어 둔다** (design/README.md D-1).
 * `PlanActorKind` 는 `self·charge·shoot·summon` 뿐인데 balance.json 의 적은 8종이고
 * 유형은 다섯이다 — MELEE·RANGED·SUMMONER·BOMBER·HEALER. 앞의 셋은 이름이 그대로
 * 맞고, 뒤의 둘은 다음과 같이 붙였다.
 *
 *   BOMBER → charge   접근해서 터진다. 이동 양상이 돌진형과 같고, 자폭형을 구분해 주는
 *                     정보는 글리프가 아니라 **예고 타일**이다 (GDD §4.2). 도면이 붉은
 *                     칸과 남은 틱을 함께 그리므로 글리프까지 나눌 필요가 없다.
 *   HEALER → summon   전열에 서지 않고 뒤에서 아군을 보조한다. 소환형과 같은 후열 지원
 *                     역할이라 접근 우선순위가 같다.
 *
 * 그래서 글리프만으로는 여덟 종이 구분되지 않는다. **색이 정보의 유일한 채널이 될 수
 * 없다는 규칙과 같은 이유로 글리프도 유일한 채널이 될 수 없어**, 도면은 글리프 아래에
 * 종류별 두 글자 표기를 함께 그린다. 색(황동/백묵) + 글리프 + 표기 세 채널이다.
 *
 * Phase 4 에서 kind 열거를 넓힐 때 이 표를 지우고 글리프를 새로 정하면 된다.
 */

import type { PlanActorKind } from '../ds'

/** 적 유형에서 도면 말의 종류로. 정본은 balance.json 의 `enemies[].type` 이다. */
export const KIND_BY_ENEMY_TYPE: ReadonlyMap<string, PlanActorKind> = new Map([
  ['MELEE', 'charge'],
  ['RANGED', 'shoot'],
  ['SUMMONER', 'summon'],
  ['BOMBER', 'charge'],
  ['HEALER', 'summon'],
])

/** 유형을 모를 때의 말. 근접으로 두는 편이 사거리를 과소평가하지 않는다. */
export const FALLBACK_ACTOR_KIND: PlanActorKind = 'charge'

/**
 * 종류별 두 글자 표기. 글리프가 겹치는 자리를 이것이 가른다.
 *
 * 두 글자인 것은 64px 셀 폭 안에 --fs-label 로 들어가는 한계이기 때문이다. 표에 없는
 * 종류는 kind_id 앞 두 글자를 쓴다 — 빈칸으로 두면 글리프만 남아 구분이 사라진다.
 */
export const SHORT_LABEL_BY_KIND_ID: ReadonlyMap<string, string> = new Map([
  ['goblin_rusher', '돌진'],
  ['goblin_archer', '사격'],
  ['goblin_summoner', '소환'],
  ['bomb_slime', '자폭'],
  ['mender_acolyte', '치유'],
  ['veteran_rusher', '정예'],
  ['longbow_archer', '장궁'],
  ['arch_summoner', '대소'],
])

/** 표에 없는 종류에서 잘라 쓸 글자 수. */
const FALLBACK_LABEL_LENGTH = 2

/**
 * 적 종류를 도면 말의 종류로 바꾼다.
 *
 * @param kindId 엔티티 종류 id.
 * @param kindTypes 종류에서 유형으로의 대응표 (`EngineConfig.kindTypes`).
 * @returns 그릴 말의 종류. 유형을 모르면 charge.
 */
export function resolveActorKind(
  kindId: string,
  kindTypes: ReadonlyMap<string, string>,
): PlanActorKind {
  const type = kindTypes.get(kindId)
  if (type === undefined) {
    return FALLBACK_ACTOR_KIND
  }
  return KIND_BY_ENEMY_TYPE.get(type) ?? FALLBACK_ACTOR_KIND
}

/**
 * 도면에 적을 두 글자 표기를 고른다.
 *
 * @param kindId 엔티티 종류 id.
 * @returns 두 글자 표기.
 */
export function resolveActorLabel(kindId: string): string {
  return SHORT_LABEL_BY_KIND_ID.get(kindId) ?? kindId.slice(0, FALLBACK_LABEL_LENGTH)
}
