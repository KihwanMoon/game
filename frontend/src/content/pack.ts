/**
 * 콘텐츠 팩 — 지금 도는 자산 (설계/4_아이템 §18).
 *
 * **번들이 폴백이다.** 서버에 못 닿으면 빌드에 박힌 것으로 돈다. 그것이 "서버가 없어도
 * 게임은 돈다" 를 지키는 자리이고, 그때는 팩 세대가 0 이라 코어 버전이 다르며, 그 판은
 * 로컬 티켓이라 제출되지 않는다.
 *
 * **받은 팩도 코어의 로더로 읽는다.** 서버가 보낸 것을 그냥 믿으면 깨진 절 하나가
 * 화면을 통째로 죽인다. 못 읽으면 번들로 떨어진다 — 콘텐츠 하나 잘못 발행했다고
 * 아무도 못 들어오는 상태가 되면 안 된다.
 *
 * 갈아 끼우는 것은 **렌더 전에 한 번**이다 (`main.tsx`). 도는 중에 바꾸면 같은 판이
 * 중간에 다른 데이터로 돌고, 그것이 R5 가 막으려는 것이다.
 */
import {
  BALANCE,
  BLOCK_CATALOG,
  CONTENT_VERSIONS,
  ENEMY_RULESETS,
  ROOM_TEMPLATES,
  type RawBalanceFile,
} from '../core/resources'
import { buildCoreVersion, loadBlockCatalog, loadRoomTemplates, loadRuleSets } from '../core/schemas'
import type {
  BlockCatalog,
  ContentVersions,
  RawBlockCatalog,
  RawRoomFile,
  RawRuleSetFile,
  RoomTemplate,
  RuleSet,
} from '../core/schemas'

/** 지금 도는 자산 한 벌. */
export interface ContentPack {
  readonly catalog: BlockCatalog
  readonly rooms: readonly RoomTemplate[]
  readonly enemies: ReadonlyMap<string, RuleSet>
  readonly balance: RawBalanceFile
  readonly versions: ContentVersions
  /** 발행 세대. 번들로 돌면 0 이다. */
  readonly generation: number
  readonly coreVersion: string
}

/** 서버가 보낸 팩의 원시 모양. */
export interface RawContentPack {
  readonly assets: Record<string, unknown>
  readonly generation: number
  readonly core_version: string
}

/** 빌드에 박힌 것. 서버에 못 닿을 때 이것으로 돈다. */
export const BUNDLED_PACK: ContentPack = {
  catalog: BLOCK_CATALOG,
  rooms: ROOM_TEMPLATES,
  enemies: ENEMY_RULESETS,
  balance: BALANCE,
  versions: CONTENT_VERSIONS,
  generation: 0,
  coreVersion: buildCoreVersion(CONTENT_VERSIONS),
}

let active: ContentPack = BUNDLED_PACK

/**
 * 지금 도는 팩을 준다.
 *
 * @returns 팩. 갈아 끼운 적이 없으면 번들이다.
 */
export function readActivePack(): ContentPack {
  return active
}

/**
 * 서버가 보낸 팩을 읽는다.
 *
 * @param raw 서버 응답.
 * @returns 읽어 낸 팩. 하나라도 못 읽으면 undefined.
 */
export function parseContentPack(raw: RawContentPack): ContentPack | undefined {
  try {
    const assets = raw.assets
    const catalog = loadBlockCatalog(assets.blocks as RawBlockCatalog)
    const balance = assets.balance as RawBalanceFile
    const skills = assets.skills as { skill_list_version: number }
    const rooms = assets.rooms as RawRoomFile & { room_list_version: number }
    const enemies = assets.enemies as RawRuleSetFile & { enemy_list_version: number }
    return {
      catalog,
      rooms: loadRoomTemplates(rooms),
      enemies: loadRuleSets(enemies),
      balance,
      versions: {
        blocks: catalog.version,
        balance: balance.balance_version,
        // 아이템은 브라우저 코어가 안 읽는다. 세대는 번들 값을 그대로 쓴다 — 서버가
        // 발급한 티켓의 코어 버전이 정본이고, 로컬 연습 티켓은 제출되지 않는다.
        items: CONTENT_VERSIONS.items,
        skills: skills.skill_list_version,
        rooms: rooms.room_list_version,
        enemies: enemies.enemy_list_version,
      },
      generation: raw.generation,
      coreVersion: raw.core_version,
    }
  } catch {
    return undefined
  }
}

/**
 * 팩을 갈아 끼운다. **렌더 전에 한 번만 부른다.**
 *
 * @param pack 새 팩.
 */
export function applyContentPack(pack: ContentPack): void {
  active = pack
}

/**
 * 서버에서 팩을 받아 갈아 끼운다.
 *
 * 실패는 조용히 넘어간다 — 번들로 돌면 되고, 그것이 폴백의 뜻이다.
 *
 * @param origin API 접두어.
 * @returns 갈아 끼웠으면 true.
 */
export async function loadContentPack(origin = '/api'): Promise<boolean> {
  try {
    const response = await fetch(`${origin}/content/pack`)
    if (!response.ok) {
      return false
    }
    const parsed = parseContentPack((await response.json()) as RawContentPack)
    if (parsed === undefined) {
      return false
    }
    applyContentPack(parsed)
    return true
  } catch {
    return false
  }
}
