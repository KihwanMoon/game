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
  // **주술형은 사격형과 같은 글리프다** (2026-09-17). 글리프를 하나 더 만들지 않는
  // 이유는 도면이 네 모양으로 끝나야 64px 칸에서 읽히기 때문이고, 겹치는 자리를
  // 가르는 것은 **두 글자 표기**라고 이 표가 이미 정해 두었다 (아래 `SHORT_LABEL`).
  // 실제로도 사격형과 같은 자리에서 같은 거리로 온다 — 다른 것은 오는 것의 정체다.
  ['CASTER', 'shoot'],
])

/**
 * 도플갱어의 종 id.
 *
 * **파이썬이 같은 값을 박아 두고 있다** (`game/app/bots/doppel.py`). 저쪽에서는 이 id
 * 하나에 드롭 굴림·전리품 강탈·되찾기 셋이 막혀 있어 바꾸면 셋이 함께 뚫린다. 여기서는
 * 화면 표시뿐이라 뚫릴 것은 없지만, 갈리면 **도면만 조용히 다른 것을 그린다.**
 */
export const DOPPEL_KIND_ID = 'doppelganger'

/**
 * 이 말이 도플갱어인가.
 *
 * 등급으로는 못 가른다 — ELITE 로 서지만 다른 정예와 같은 것이 아니다. 사람의 빌드가
 * 그대로 서 있고, 전리품을 안 떨어뜨리며, 그 규칙표가 나를 읽는다.
 *
 * @param kindId 엔티티 종류 id.
 * @returns 도플갱어면 참.
 */
export function checkDoppel(kindId: string): boolean {
  return kindId === DOPPEL_KIND_ID
}

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
  // **표기가 색과 함께 선다.** 색만으로 가르면 색을 못 가르는 사람에게 도플갱어가
  // 그냥 정예 하나로 남는다. 앞 두 글자를 자르는 기본값이면 「도플」인데, 그것은
  // 「돌진」과 한 글자 차이라 64px 칸에서 헷갈린다.
  [DOPPEL_KIND_ID, '분신'],
  // **다섯이 영문으로 서 있었다** (2026-09-17에 확인). 표에 없으면 id 앞 두 글자를
  // 자르므로 도면에 `di`·`sh`·`he`·`pl`·`st` 가 떴다 — 한글 화면에 영문 조각이 뜨는
  // 것은 고르개 값에서 이미 한 번 고친 병이고(2026-09-16 요청), 무엇보다 `plague_mender`
  // 와 `plague_shaman` 이 둘 다 `pl` 이라 **서로 구별되지 않았다.**
  ['dire_wolf', '주린'],
  ['shield_golem', '돌미'],
  ['hex_archer', '저주'],
  ['plague_mender', '역귀'],
  ['stone_gatekeeper', '장승'],
  // 주술형 여섯 (2026-09-17). 글리프가 사격형과 같으므로 **여기가 유일한 구별 채널이다.**
  ['bolt_shaman', '벼락'],
  ['frost_maiden', '서리'],
  ['snare_boy', '덫굿'],
  ['ember_shaman', '불티'],
  ['plague_shaman', '옴굿'],
  ['plate_wraith', '판각'],
  // 2막 후반 셋 (2026-09-18). 무당이 셋 더 늘어 「무당」으로는 못 가른다.
  ['dirge_shaman', '넋굿'],
  ['knell_shaman', '조종'],
  ['mimic_wraith', '입내'],
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
