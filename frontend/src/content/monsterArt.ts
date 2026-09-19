/**
 * 몬스터 도트 — 어느 그림을 쓸지 정한다 (2026-09-19).
 *
 * **아이템과 규약이 다르다.** 저쪽은 `catalog_id` 의 **접두사**로 형태를 고른다
 * (`sword_short`·`sword_saber` → `sword`) — 아이템은 계속 늘고 같은 형태를 여럿이
 * 나눠 쓰기 때문이다. 적은 종이 스물셋으로 정해져 있고 **같은 그림을 나눠 쓸 종이
 * 없다.** 그래서 id 를 통째로 쓴다.
 *
 * `bestiaryCells.ts` 가 남겨 둔 경고가 이 파일의 이유다 — *"몬스터 id 를 아이템 그림표에
 * 넣지 않는다. 접두사가 겹치는 날 도깨비 칸에 칼이 그려지고, 지금 안 겹치는 것은
 * 우연이지 규칙이 아니다."* 표를 나눠 두면 그 날이 안 온다.
 *
 * **없으면 없는 대로 둔다.** 그림이 아직 없는 종은 `undefined` 를 돌려주고 화면은
 * 지금처럼 글자로 그린다.
 */

// **파일을 떨구면 바로 잡힌다.** 목록을 코드에 또 적으면 그림을 더할 때마다 두 곳을
// 고쳐야 하고, 한쪽만 고친 날 그림이 조용히 안 뜬다.
const FILES = import.meta.glob<string>('@design/art/monsters/*.svg', {
  query: '?url',
  import: 'default',
  eager: true,
})

/** 파일 이름(확장자 뺀 것) → 주소. 파일 이름이 곧 적 id 다. */
const BY_ID = new Map<string, string>(
  Object.entries(FILES).map(([path, url]) => [
    path.slice(path.lastIndexOf('/') + 1, -'.svg'.length),
    url,
  ]),
)

/**
 * 이 종이 쓸 그림의 주소.
 *
 * @param catalogId 적 종류 id (`balance.json` 의 `enemies[].id`).
 * @returns 그림 주소. 아직 없는 종이면 undefined.
 */
export function findMonsterArt(catalogId: string): string | undefined {
  return BY_ID.get(catalogId)
}

/** 이 코어가 들고 있는 그림의 이름 전부. 전수 검사가 카탈로그와 맞춰 본다. */
export function listMonsterArtIds(): readonly string[] {
  return [...BY_ID.keys()].sort()
}
