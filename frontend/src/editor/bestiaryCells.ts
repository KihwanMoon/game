/**
 * 비각 도감(지속 몬스터) 격자의 셀 모델 (설계/6_몬스터 §8).
 *
 * **가방과 같은 형식이다.** 도감이 묻는 것은 「저것을 칠 수 있는가, 내 것을 들고 있는가」
 * 이고, 그것은 가방이 도면 격자로 답한 질문(「이게 뭐고 어느 게 더 좋은가」)과 같은 종류다.
 * 예전에는 여기만 줄 목록이라 개체 하나가 이름·스탯·접사·전리품·규칙표 버튼으로 다섯
 * 덩이였고, 열 마리가 살아 있으면 표적을 고르는 일이 스크롤이 됐다.
 *
 * **몬스터 그림은 0장이다.** `design/art/items` 에는 아이템 형태만 있으므로 칸은 코드
 * 글자로 떨어진다. 몬스터 id 를 아이템 그림표에 넣지 않는 이유는 이문록 재주 칸과 같다 —
 * 접두사가 겹치는 날 도깨비 칸에 칼이 그려지고, 지금 안 겹치는 것은 우연이지 규칙이 아니다.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 셀 배치를 볼 수 있어야 한다.
 */
import type { BestiaryEntry } from '../storage'

import type { CellFace } from './gridCell'
import { clipCellLabel } from './inventoryCells'

/**
 * 내 장비를 들고 있는 개체.
 *
 * 저잣거리의 「내 매물」과 같은 글리프다 — 둘 다 「내 것이 저기 있다」를 말하므로 표기를
 * 새로 만들지 않는다. 되찾으러 가는 동기가 이 한 글자에 걸려 있다.
 */
export const HOLDS_MINE_MARK = '◉'

/**
 * 도감 격자 칸 하나.
 *
 * 겉면(`CellFace`)은 가방·소모품·저잣거리와 함께 쓰고, 더하는 것은 알맹이 하나 —
 * 이 칸이 가리키는 개체다.
 */
export interface BestiaryCell extends CellFace {
  readonly entry: BestiaryEntry
}

/**
 * 도감 줄들을 격자 칸으로 만든다.
 *
 * **빈 칸을 덧대지 않는다.** 비각에 사는 개체 수는 정해져 있지 않다 — 없는 자리를 그리면
 * 「여기까지 찰 수 있다」로 읽힌다.
 *
 * @param entries 서버가 준 도감 줄들. 없으면 빈 배열.
 * @returns 서버가 준 순서 그대로의 칸들.
 */
export function buildBestiaryCells(
  entries: readonly BestiaryEntry[] | undefined,
): readonly BestiaryCell[] {
  return (entries ?? []).map((entry) => ({
    key: `bst:${String(entry.recordId)}`,
    // **자리는 층이다.** 가방 칸이 부위를 다는 자리에, 지속 몬스터는 「어디 있는가」가
    // 온다 — 되찾으러 갈 수 있는지를 가르는 것이 그것이다.
    code: `${String(entry.zoneFloor)}장`,
    label: clipCellLabel(entry.labelKo),
    // 등급 칠은 아이템 등급(COMMON·FINE·RELIC) 전용이다. 개체의 tier 를 여기 넣으면
    // 도감이 유물 색을 쓰게 되고, 그때부터 같은 색이 두 가지를 뜻한다.
    grade: '',
    marks: entry.holdsMine ? [HOLDS_MINE_MARK] : [],
    countText: `lv${String(entry.level)}`,
    // **등급은 글자로 적는다** — 의미색 셋은 이미 배정됐고, 색은 정보의 유일한 채널이
    // 될 수 없다. 실측 스탯(hp·공·방)은 칸이 70px 라 잘리므로 상세가 낸다.
    fact: entry.tier,
    isSealedSlot: false,
    entry,
  }))
}
