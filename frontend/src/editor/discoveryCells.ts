/**
 * 이문록(물건과 재주) 격자의 셀 모델.
 *
 * **가방과 같은 형식이다.** 이문록이 답하는 것은 「무엇이 있고 그중 무엇을 밝혔는가」
 * 이고, 밝힌 칸은 가방 칸과 같은 물건을 가리킨다 — 같은 것이 화면마다 다른 모양으로
 * 그려지면 한 곳을 고쳐도 나머지는 옛 모양으로 남는다 (`gridCell` 머리말).
 *
 * 지키는 것은 셋이다.
 *
 * 1. **미해금도 자리를 보여준다.** 빼면 도감이 「내가 가진 것 목록」이 되고 무엇을 더
 *    찾아야 하는지가 사라진다.
 * 2. **이름은 가리지 않는다.** 목표가 안 보이면 찾아갈 이유도 안 생긴다 — 그래서
 *    미해금은 `isOff` 다. 막힌 칸(`isSealedSlot`)은 이름을 지우므로 여기 쓸 수 없다.
 * 3. **미해금 표기는 「불가」와 같은 해칭이다.** 새 표기를 만들지 않는다 — 뜻이 같다.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 셀 배치를 볼 수 있어야 한다.
 */
import { findItemArt } from '../content/itemArt'
import type { DiscoveryRow } from '../storage'

import type { CellFace } from './gridCell'
import { clipCellLabel, EQUIP_CELL_CODES } from './inventoryCells'

/**
 * 아이템 줄의 `kind`. 서버의 `store.discovery.KIND_ITEM` 과 같은 값이다.
 *
 * **재주 줄에는 그림을 안 붙인다.** `refId` 가 거기서는 스킬 id(`HEAL`)이고, 그것을
 * 아이템 그림표에 넣으면 언젠가 같은 접두사를 가진 아이템이 생긴 날 재주 칸에 칼이
 * 그려진다 — 지금 안 맞는다는 것은 우연이지 규칙이 아니다.
 */
export const KIND_ITEM = 'ITEM'

/** 안 밝힌 칸. `ds/Thumb` 의 미해금 해칭과 같은 글리프다 — 뜻이 같으면 표기도 같다. */
export const LOCKED_MARK = '⧅'

/** 안 밝힌 칸의 한 줄. 칸이 70px 라 짧게 적고, 「얻으면 밝혀진다」는 상세가 낸다. */
export const LOCKED_FACT = '못 얻음'

/** 이문록 격자 칸 하나. */
export interface DiscoveryCell extends CellFace {
  readonly row: DiscoveryRow
}

/**
 * 도감 줄들을 칸으로 바꾼다.
 *
 * @param rows 도감 줄들.
 * @returns 격자에 넣을 칸들.
 */
export function buildDiscoveryCells(rows: readonly DiscoveryRow[]): readonly DiscoveryCell[] {
  return rows.map((row) => ({
    // 물건과 재주가 같은 id 를 쓸 수 있다. 계열을 키에 넣어야 탭을 옮겼을 때 엉뚱한
    // 칸이 골라진 채로 남지 않는다.
    key: `disc:${row.kind}:${row.refId}`,
    // **`ref_id` 가 곧 카탈로그 id 다** — 도감이 아이템을 그것으로 가리킨다. 분류는
    // 슬롯이라 장비 칸과 같은 코드를 쓴다.
    code: EQUIP_CELL_CODES.get(row.category) ?? (row.kind === KIND_ITEM ? 'IT' : 'SK'),
    label: clipCellLabel(row.labelKo),
    // **안 밝힌 것에는 그림을 안 준다.** 실루엣이 새면 해칭이 뜻을 잃는다. 예전에는
    // 주소를 그대로 넘기고 `Thumb` 이 가렸는데, 도면 격자의 칸은 가리는 상태를 모른다 —
    // 가리는 판단이 한 곳(여기)에 있는 것이 그때 적어 둔 규율이기도 하다.
    //
    // **접두사만으로는 둘이 안 갈린다.** 같은 `sword` 라도 양손이면 협도고, 부적 여섯은
    // 쓰임새로 갈린다 — 그래서 `hands`·`useTag` 를 함께 넘긴다 (`content/itemArt`).
    //
    // 한동안 여기 「그 둘이 응답에 없다」고 적혀 있었는데 **사실이 아니었다.** 서버는
    // 싣고 있었고(`view_schemas.DiscoveryRow`) 화면의 매핑이 버리고 있었다 — 주석이
    // 코드보다 오래 산 자리다.
    art:
      row.kind === KIND_ITEM && row.isFound
        ? findItemArt(row.refId, row.hands, row.useTag)
        : undefined,
    // 등급은 이 응답에 없다. 없는 것을 칠하지 않는다.
    grade: '',
    marks: row.isFound ? [] : [LOCKED_MARK],
    countText: '',
    // **밝힌 것은 「무엇을 해 주는가」를 칸에서 말한다.** 속살(`detail`)은 밝힌 줄에만
    // 채워져 오므로, 이 한 줄이 곧 해금의 보상이다.
    fact: row.isFound ? row.detail : LOCKED_FACT,
    isSealedSlot: false,
    // **미해금은 `isOff` 다** — 이름은 남고 명도가 죽는다(막힌 칸 `isSealedSlot` 은
    // 이름을 지우므로 여기 쓸 수 없다). 다만 공용 칸의 보조 기술 이름표는 이 상태를
    // 「끔」으로 읽어, 뜻이 「아직 못 얻음」인 자리에 정확하지 않다 — 고치려면
    // `GridCellView` 의 말을 늘려야 하고 그것은 다섯 화면이 함께 쥔 파일이다.
    isOff: !row.isFound,
    row,
  }))
}
