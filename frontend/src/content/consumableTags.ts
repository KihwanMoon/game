/**
 * 소모품 태그와 칸 계열 — `game/schemas/consumable.py` 의 짝 (2026-09-11).
 *
 * **칸은 계열이고 태그는 끼운 물건이다.** 부적 칸은 하나인데 거기 무엇을 끼웠느냐가
 * `USE_ITEM[태그]` 를 정한다 — 순간이동을 끼우면 `USE_ITEM[BLINK]` 가 돌고
 * `USE_ITEM[SCROLL]` 은 「불가」가 된다. 그래서 칸을 안 늘리고도 「무엇을 들고 갈까」가
 * 선택이 된다.
 *
 * **표시명은 탕약과 부적이고 열쇠는 `POTION`·`SCROLL` 그대로다** (기획/5_설정집 §5.6,
 * 4_세계관 §5.5). 열쇠는 코드의 것이라 개명이 저장된 규칙표·골든을 건드리지 않고,
 * 화면에 뜨는 말만 정본을 따른다 (2026-09-18).
 *
 * **화면 셋이 이 표를 함께 본다** — 규칙 편집기의 블록 인자, 소모품 칸 격자, 전투 화면의
 * 잔량 줄. 사본을 두면 새 부적이 어느 한 곳에서만 이름 없이 뜬다.
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
 * **칸 계열**의 한글 이름. 칸은 둘뿐이다 — 탕약 칸과 부적 칸.
 *
 * 태그 이름표와 갈라 둔 이유가 있다. 칸은 「여기에 무엇이 들어가는가」라 계열 이름이고,
 * 태그는 「지금 무엇이 들었는가」라 물건 이름이다 — 부적 칸의 이름은 넷 중 무엇을
 * 끼우든 「부적 1」이어야 한다.
 */
export const SLOT_LABELS: ReadonlyMap<string, string> = new Map([
  ['POTION', '탕약'],
  ['SCROLL', '부적'],
])

/**
 * 태그의 한글 이름. 규칙 편집기의 인자와 전투 잔량 줄이 함께 쓴다.
 *
 * `SCROLL` 에만 수식어가 붙는다 — 넷이 전부 부적이라 그냥 「부적」이면 어느 것을
 * 가리키는지 알 수 없다. 칸 이름(`SLOT_LABELS`)은 계열이라 수식어가 없다.
 */
export const USE_TAG_LABELS: ReadonlyMap<string, string> = new Map([
  ['POTION', '탕약'],
  ['SCROLL', '보호 부적'],
  ['BLINK', '순간이동'],
  ['FLAME', '화염'],
  ['FOCUS', '부릅'],
])

/**
 * 태그의 두 글자 도식 코드.
 *
 * 장비 칸이 부위 코드(`WM`·`HD`)를 다는 것과 같은 자리다 — 칸 구석은 **어디에 들어가는
 * 것인가**를 말한다. 그래서 부적 넷이 전부 `SC` 다: 셋 다 같은 칸에 들어간다.
 */
export const USE_TAG_CODES: ReadonlyMap<string, string> = new Map([
  ['POTION', 'PO'],
  ['SCROLL', 'SC'],
  ['BLINK', 'SC'],
  ['FLAME', 'SC'],
  ['FOCUS', 'SC'],
])
