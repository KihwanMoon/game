/**
 * 소모품 태그와 칸 계열 — `game/schemas/consumable.py` 의 짝 (2026-09-11).
 *
 * **칸은 계열이고 태그는 끼운 물건이다.** 주문서 칸은 하나인데 거기 무엇을 끼웠느냐가
 * `USE_ITEM[태그]` 를 정한다 — 순간이동을 끼우면 `USE_ITEM[BLINK]` 가 돌고
 * `USE_ITEM[SCROLL]` 은 「불가」가 된다. 그래서 칸을 안 늘리고도 「무엇을 들고 갈까」가
 * 선택이 된다.
 *
 * **화면 셋이 이 표를 함께 본다** — 규칙 편집기의 블록 인자, 소모품 칸 격자, 전투 화면의
 * 잔량 줄. 사본을 두면 새 주문서가 어느 한 곳에서만 이름 없이 뜬다.
 */

/** 소모품 태그에서 그것이 들어가는 칸 계열로. 서버 `SLOT_FAMILY` 와 같은 표다. */
export const SLOT_FAMILY: ReadonlyMap<string, string> = new Map([
  ['POTION', 'POTION'],
  ['SCROLL', 'SCROLL'],
  ['BLINK', 'SCROLL'],
  ['FLAME', 'SCROLL'],
  ['FOCUS', 'SCROLL'],
])

/**
 * 그 태그가 들어가는 칸 계열.
 *
 * @param useTag 소모품 태그.
 * @returns 칸 계열. 모르는 태그면 빈 문자열 — 그때는 어느 칸에도 안 맞는다.
 */
export function findSlotFamily(useTag: string | undefined): string {
  return SLOT_FAMILY.get(useTag ?? '') ?? ''
}

/**
 * 그 소모품이 이 칸에 들어가는가.
 *
 * @param useTag 소모품의 쓰임새 태그.
 * @param slotTag 칸의 계열.
 * @returns 맞으면 true.
 */
export function checkSlotFit(useTag: string | undefined, slotTag: string): boolean {
  return useTag !== undefined && useTag !== '' && findSlotFamily(useTag) === slotTag
}

/**
 * **칸 계열**의 한글 이름. 칸은 둘뿐이다 — 물약 칸과 주문서 칸.
 *
 * 태그 이름표와 갈라 둔 이유가 있다. 칸은 「여기에 무엇이 들어가는가」라 계열 이름이고,
 * 태그는 「지금 무엇이 들었는가」라 물건 이름이다 — 주문서 칸의 이름은 넷 중 무엇을
 * 끼우든 「주문서 1」이어야 한다.
 */
export const SLOT_LABELS: ReadonlyMap<string, string> = new Map([
  ['POTION', '물약'],
  ['SCROLL', '주문서'],
])

/** 태그의 한글 이름. 규칙 편집기의 인자와 전투 잔량 줄이 함께 쓴다. */
export const USE_TAG_LABELS: ReadonlyMap<string, string> = new Map([
  ['POTION', '물약'],
  ['SCROLL', '보호 주문서'],
  ['BLINK', '순간이동'],
  ['FLAME', '화염'],
  ['FOCUS', '부릅'],
])

/**
 * 태그의 두 글자 도식 코드.
 *
 * 장비 칸이 부위 코드(`WM`·`HD`)를 다는 것과 같은 자리다 — 칸 구석은 **어디에 들어가는
 * 것인가**를 말한다. 그래서 주문서 넷이 전부 `SC` 다: 셋 다 같은 칸에 들어간다.
 */
export const USE_TAG_CODES: ReadonlyMap<string, string> = new Map([
  ['POTION', 'PO'],
  ['SCROLL', 'SC'],
  ['BLINK', 'SC'],
  ['FLAME', 'SC'],
  ['FOCUS', 'SC'],
])

/**
 * 태그가 **언제 저절로 터지는가** (2026-09-11 개정). 코어의 `scrolls.TRIGGERS` 를 사람
 * 말로 옮긴 것이다.
 *
 * **화면에 반드시 적는다.** 주문서가 규칙 줄 없이 터지므로, 조건을 안 보여 주면 들고
 * 가는 사람에게는 「언젠가 사라지는 물건」이 된다 — 이 저장소가 여러 번 다친
 * 「안 보이면 없는 것」의 자리다.
 *
 * 여기 없는 태그(물약)는 규칙표로만 쓴다. 언제 마실지는 이 게임이 파는 판단 그 자체다.
 */
export const TRIGGER_LABELS: ReadonlyMap<string, string> = new Map([
  ['SCROLL', '체력 30% 아래에서 적이 붙어 있으면'],
  ['BLINK', '인접한 적이 둘 이상이면 (포위)'],
  ['FLAME', '인접한 적이 둘 이상이면 (포위)'],
  ['FOCUS', '적이 한 칸 차이로 안 닿으면'],
])
