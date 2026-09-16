/**
 * 아이템 도트 — 어느 그림을 쓸지 정한다 (2026-09-16).
 *
 * **새 필드를 안 판다.** 설계 문서는 `items.json` 에 `art` 필드를 두기로 계획해 두었는데,
 * 실측해 보니 **`catalog_id` 의 접두사가 이미 형태를 말하고 있다** — 접두사 19종이 아이템
 * 49개를 정확히 덮는다(`sword_short`·`sword_saber` → `sword`). 서버에 열을 더하고 DB 를
 * 옮기는 값을 치를 이유가 없고, 새 아이템도 이름만 규약대로 지으면 그림이 따라온다.
 *
 * **두 곳만 보정한다.** 접두사만으로는 갈리지 않는 자리다.
 *
 * - `sword` 넷 중 **협도는 양손**이다(`hands = TWO`). 비수와 같은 그림을 쓰면 형태가
 *   거짓말을 한다.
 * - `scroll` 여섯은 쓰임새가 다르다(`use_tag`). 축지·눈밝이·불은 부적과 다른 일을 한다.
 *
 * 둘 다 화면이 이미 들고 있는 값이라, 서버를 안 건드린다.
 *
 * **없으면 없는 대로 둔다.** 그림이 아직 없는 형태는 `undefined` 를 돌려주고 화면은
 * 지금처럼 글자로 그린다 — 열아홉을 다 그리기 전에도 그린 것부터 쓸 수 있다.
 */

// **파일을 떨구면 바로 잡힌다.** 목록을 코드에 또 적으면 그림을 더할 때마다 두 곳을
// 고쳐야 하고, 한쪽만 고친 날 그림이 조용히 안 뜬다.
const FILES = import.meta.glob<string>('@design/art/items/*.svg', {
  query: '?url',
  import: 'default',
  eager: true,
})

/** 파일 이름(확장자 뺀 것) → 주소. */
const BY_NAME = new Map<string, string>(
  Object.entries(FILES).map(([path, url]) => [
    path.slice(path.lastIndexOf('/') + 1, -'.svg'.length),
    url,
  ]),
)

/** 양손무기는 같은 접두사라도 형태가 다르다. */
const TWO_HANDED = 'TWO'

/** 쓰임새가 부적과 다른 소모품들. 접두사가 전부 `scroll` 이라 이것으로 가른다. */
const BY_USE_TAG = new Map<string, string>([
  ['BLINK', 'blink'],
  ['FOCUS', 'focus'],
  ['FLAME', 'flame'],
])

/**
 * 이 아이템이 쓸 그림의 이름.
 *
 * @param catalogId 카탈로그 id. 접두사가 형태를 말한다.
 * @param hands 한 손인가 양손인가. 빈 값이면 안 본다.
 * @param useTag 소모품의 쓰임새. 빈 값이면 안 본다.
 * @returns 그림 이름. 카탈로그 id 가 비어 있으면 빈 문자열.
 */
export function readArtName(
  catalogId: string | undefined,
  hands = '',
  useTag = '',
): string {
  // **없을 수 있다.** 관리자의 봇 가방처럼 카탈로그 id 를 안 싣고 오는 화면이 있고,
  // 거기서 터지면 그림 하나 때문에 관리 화면 전체가 죽는다 (검사가 잡았다).
  if (typeof catalogId !== 'string' || catalogId === '') {
    return ''
  }
  const prefix = catalogId.split('_')[0] ?? ''
  if (prefix === 'sword' && hands === TWO_HANDED) {
    return 'glaive'
  }
  if (prefix === 'scroll') {
    return BY_USE_TAG.get(useTag) ?? 'scroll'
  }
  return prefix
}

/**
 * 그 아이템의 그림 주소.
 *
 * @param catalogId 카탈로그 id.
 * @param hands 한 손인가 양손인가.
 * @param useTag 소모품의 쓰임새.
 * @returns 주소. 아직 안 그린 형태면 undefined — 화면은 글자로 떨어진다.
 */
export function findItemArt(
  catalogId: string | undefined,
  hands = '',
  useTag = '',
): string | undefined {
  return BY_NAME.get(readArtName(catalogId, hands, useTag))
}

/** 지금 그려 둔 형태들. 검사가 무엇이 남았는지 셀 때 쓴다. */
export function listArtNames(): readonly string[] {
  return [...BY_NAME.keys()].sort()
}
