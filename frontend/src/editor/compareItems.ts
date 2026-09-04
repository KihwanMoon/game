/**
 * 고른 물건을 지금 낀 것과 견준다.
 *
 * **점수 하나로 접지 않는다.** 「이게 더 좋다」를 한 숫자로 말하려면 어느 스탯이 얼마나
 * 값한지를 코드가 정해야 하고, 그 기준이 틀리면 화면이 **틀린 답을 자신 있게** 말한다.
 * 봇의 장비 교체는 그 기준을 감수하고 만들었지만(`bots/upgrade.py`), 저쪽은 봇의 취향이
 * 정해져 있고 이쪽은 사람이 고른다 — 사람의 취향을 코드가 정하면 안 된다.
 *
 * 그래서 **스탯별 차이만 낸다.** 「공격 +3 · 사거리 +2 · 체력 −8」 까지가 화면의 몫이고,
 * 그것이 좋은 거래인지는 보는 사람이 정한다.
 *
 * 퍼센트와 고정값은 **합치지 않는다.** 합치려면 기준값이 필요하고 그것이 다시 기준을
 * 정하는 일이 된다 — 둘을 따로 적고 어느 쪽인지 화면이 말한다.
 */
import balanceFile from '@resources/balance/balance.json'

import type { AffixView } from '../storage'

/** 한 스탯의 견줌 한 줄. */
export interface CompareRow {
  readonly stat: string
  /** 화면에 적을 이름. 서버가 준 것을 그대로 쓴다. */
  readonly label: string
  /** 고른 것의 고정값·퍼센트. */
  readonly pickedFlat: number
  readonly pickedPercent: number
  /** 지금 낀 것의 고정값·퍼센트. */
  readonly wornFlat: number
  readonly wornPercent: number
  /** 차이. 양수면 고른 쪽이 높다. */
  readonly flatDelta: number
  readonly percentDelta: number
}

/**
 * 접사들을 스탯별로 합친다.
 *
 * 같은 스탯에 접사가 둘 붙을 수 있다 — 굴림과 봉인 해제가 각각 붙는 경우다.
 *
 * @param affixes 접사들.
 * @returns 스탯에서 (고정 합계, 퍼센트 합계, 이름) 으로.
 */
export function mergeAffixes(
  affixes: readonly AffixView[],
): Map<string, { flat: number; percent: number; label: string }> {
  const totals = new Map<string, { flat: number; percent: number; label: string }>()
  for (const affix of affixes) {
    const found = totals.get(affix.stat)
    totals.set(affix.stat, {
      flat: (found?.flat ?? 0) + affix.flat,
      percent: (found?.percent ?? 0) + affix.percent,
      label: found?.label ?? (affix.statLabel || affix.stat),
    })
  }
  return totals
}

/**
 * 고른 것과 지금 낀 것의 스탯별 차이를 낸다.
 *
 * **접사만 받는다.** 아이템 전체를 받으면 매물처럼 아이템이 아닌 것을 견줄 때 가짜
 * 아이템을 지어내야 하고, 그 가짜가 다른 필드에서 거짓말을 하게 된다.
 *
 * **양쪽에 없는 스탯도 낸다.** 고른 쪽에만 있으면 지금은 0 이고, 지금 쪽에만 있으면
 * 고른 것이 0 이다 — 빠뜨리면 「끼면 사라지는 것」이 화면에서 안 보인다.
 *
 * **정렬은 스탯 이름 순이다.** 접사 순서에 기대면 같은 물건이 볼 때마다 다른 순서로
 * 나오고, 그러면 두 칸을 번갈아 볼 수 없다.
 *
 * @param picked 고른 것의 접사들.
 * @param worn 그 자리에 지금 낀 것의 접사들. 빈 자리면 빈 배열이다.
 * @returns 차이가 있는 줄들. 같으면 빈 배열.
 */
export function compareToWorn(
  picked: readonly AffixView[],
  worn: readonly AffixView[],
): readonly CompareRow[] {
  const left = mergeAffixes(picked)
  const right = mergeAffixes(worn)
  const rows: CompareRow[] = []
  for (const stat of [...new Set([...left.keys(), ...right.keys()])].sort()) {
    const one = left.get(stat)
    const two = right.get(stat)
    const pickedFlat = one?.flat ?? 0
    const pickedPercent = one?.percent ?? 0
    const wornFlat = two?.flat ?? 0
    const wornPercent = two?.percent ?? 0
    if (pickedFlat === wornFlat && pickedPercent === wornPercent) {
      continue
    }
    rows.push({
      stat,
      label: one?.label ?? two?.label ?? stat,
      pickedFlat,
      pickedPercent,
      wornFlat,
      wornPercent,
      flatDelta: pickedFlat - wornFlat,
      percentDelta: pickedPercent - wornPercent,
    })
  }
  return rows
}

/**
 * 차이 한 줄을 사람이 읽을 문구로.
 *
 * 고정값과 퍼센트를 따로 적는다 — 합치려면 기준값이 필요하고, 그것이 다시 기준을 정하는
 * 일이 된다.
 *
 * @param row 견줌 한 줄.
 * @returns `+3` · `−2%` · `+3 +5%` 꼴. 차이가 없으면 빈 문자열.
 */
export function formatDelta(row: CompareRow): string {
  const parts: string[] = []
  if (row.flatDelta !== 0) {
    parts.push(`${row.flatDelta > 0 ? '+' : '−'}${String(Math.abs(row.flatDelta))}`)
  }
  if (row.percentDelta !== 0) {
    parts.push(`${row.percentDelta > 0 ? '+' : '−'}${String(Math.abs(row.percentDelta))}%`)
  }
  return parts.join(' ')
}

/**
 * 사거리의 스탯 키.
 *
 * **접사가 아니라 필드다** (§2.2). 예전에는 접사였는데, 접사는 굴림에서 잘릴 수 있어
 * **활이 근접무기가 되는** 경로가 있었다. 필드로 올라간 뒤로는 견줌이 그것을 못 봤다 —
 * 활과 단검을 바꿔도 화면이 「달라지는 것이 없다」라고 적었다. 소모품의 충전 용량과
 * 같은 자리이고, 같은 방식으로 접사 줄에 끼워 넣는다.
 */
export const RANGE_STAT = 'attack_range'

/** 사거리 줄의 이름. 서버 접사가 아니므로 여기서 붙인다. */
export const RANGE_LABEL = '사거리'

/**
 * 캐릭터가 맨손일 때 닿는 거리.
 *
 * **밸런스 원본을 그대로 읽는다** — 사본을 두면 파이썬이 1 로 계산하는 동안 화면만 옛
 * 값으로 견주게 된다 (CLAUDE.md 의 `@resources` 규약, `SkillPanel` 과 같은 자리다).
 */
export const BASE_RANGE: number = Number(
  (balanceFile as { readonly player: { readonly attack_range: number } }).player.attack_range,
)

/**
 * 무기가 실제로 갖는 사거리.
 *
 * **0 은 「안 정한다」다** — 0 칸이 아니다. 주무기가 사거리를 정하지 않으면 캐릭터의
 * 기본값이 그대로 남는다 (`items/loadout.replace_range`). 그 규칙을 안 따르면 단검
 * (안 정함)과 견줄 때 활이 실제보다 한 칸 더 좋아 보인다.
 *
 * @param range 무기가 적은 사거리. 0 이면 안 정한 것이다.
 * @param base 캐릭터 기본 사거리. 생략하면 밸런스 원본의 값이다.
 * @returns 실제로 닿는 거리.
 */
export function resolveRange(range: number, base: number = BASE_RANGE): number {
  return range > 0 ? range : base
}

/**
 * 사거리 차이를 접사 줄과 같은 모양으로 만든다.
 *
 * **주무기끼리만 부른다.** 사거리를 대체하는 것은 주무기 하나이므로, 투구를 견주면서
 * 이 줄을 내면 아무 뜻이 없는 숫자가 선다.
 *
 * @param pickedRange 고른 것이 적은 사거리.
 * @param wornRange 지금 낀 것이 적은 사거리.
 * @param base 캐릭터 기본 사거리. 생략하면 밸런스 원본의 값이다.
 * @returns 견줌 한 줄. 같으면 undefined.
 */
export function buildRangeRow(
  pickedRange: number,
  wornRange: number,
  base: number = BASE_RANGE,
): CompareRow | undefined {
  const picked = resolveRange(pickedRange, base)
  const worn = resolveRange(wornRange, base)
  if (picked === worn) {
    return undefined
  }
  return {
    stat: RANGE_STAT,
    label: RANGE_LABEL,
    pickedFlat: picked,
    pickedPercent: 0,
    wornFlat: worn,
    wornPercent: 0,
    flatDelta: picked - worn,
    percentDelta: 0,
  }
}
