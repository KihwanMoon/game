/**
 * 메타 세이브의 **모양** — 사망해도 남는 것만 (GDD §2.3, TDD §9).
 *
 * `game/schemas/meta_save.py` 의 이식이되, JSON 직렬화는 여기 없다. 이 저장소의
 * TypeScript 는 `storage/ → core/` 한 방향으로만 의존하므로 파일 형식은 `storage/metaSave`
 * 가 맡는다. 파이썬은 둘이 한 파일에 있지만, 그쪽은 표준 라이브러리가 JSON 을 대므로
 * 층을 가를 이유가 없었다.
 *
 * 담는 것은 해금 블록, 층 도달 기록(규칙 슬롯 상한의 근거), 몬스터 도감, 프리셋 넷뿐이다.
 * 장비·임시 모듈·층 진행도·포션은 런 스냅샷 쪽이고 여기 들어오면 안 된다 — 들어오는
 * 순간 사망의 대가가 사라진다.
 */
import { FIRST_FLOOR } from './room'
import type { RuleSet } from './ruleset'

/** GDD §2.3 — 코드 라이브러리는 8슬롯이다. `meta_save.py` 의 MAX_PRESET_SLOTS 와 같은 값. */
export const MAX_PRESET_SLOTS = 8

/** GDD §2.3 — 시작 슬롯 보너스는 최대 +4 다. */
export const MAX_SLOT_BONUS = 4

// 층 1 도달은 시작 조건이라 보너스가 아니다. 보너스는 층 2부터 붙는다.
// FIRST_FLOOR 를 여기서 다시 선언하지 않고 room 에서 가져온다 — 파이썬은 meta_save.py 와
// room.py 양쪽에 같은 값을 두었지만, 값이 갈리면 슬롯 보너스와 방 배치가 서로 다른 "1층"
// 을 보게 된다.
export { FIRST_FLOOR }

/** 이 코어가 읽고 쓰는 세이브 형식 세대. `storage/metaSave` 의 태그와 같은 값이다. */
export const META_FORMAT_VERSION = 1

/**
 * 도감 한 줄. 이 적을 몇 번 만났고 몇 번 잡았는가.
 *
 * 조우만으로도 규칙표가 열린다 (GDD §2.3). 잡은 횟수를 따로 세는 것은 도감을
 * "읽었다" 와 "통했다" 로 나누기 위해서다.
 */
export interface BestiaryRecord {
  readonly kindId: string
  readonly encounters: number
  readonly defeats: number
}

/** 코드 라이브러리 한 슬롯. 이름 붙인 규칙표 하나다. */
export interface RulePreset {
  readonly name: string
  readonly ruleset: RuleSet
}

/** 사망해도 남는 것 전부. */
export interface MetaSave {
  readonly formatVersion: number
  readonly bestFloor: number
  readonly unlockedPerceptions: readonly string[]
  readonly unlockedActions: readonly string[]
  readonly bestiary: readonly BestiaryRecord[]
  readonly presets: readonly RulePreset[]
  /**
   * 편집 중인 규칙표. **이름 붙인 슬롯이 아니라 지금 손에 든 것**이다.
   *
   * 기기를 바꿔 로그인하면 이것이 없어서 규칙이 통째로 사라진 것처럼 보였다 — 슬롯은
   * 따라왔지만 사람이 실제로 짜고 있던 것은 이 초안이다.
   */
  readonly draft: RuleSet | undefined
}

/**
 * 아무것도 하지 않은 상태의 세이브.
 *
 * @returns 빈 메타 세이브.
 */
export function createEmptyMeta(): MetaSave {
  return {
    formatVersion: META_FORMAT_VERSION,
    bestFloor: 0,
    unlockedPerceptions: [],
    unlockedActions: [],
    bestiary: [],
    presets: [],
    draft: undefined,
  }
}
