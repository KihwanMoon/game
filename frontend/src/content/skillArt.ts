/**
 * 재주 도트 — 어느 그림을 쓸지 정한다 (2026-09-21 요청).
 *
 * **몬스터와 같은 규약이다** (`content/monsterArt.ts`): 파일 이름이 곧 재주 id 이며,
 * 소문자로 내린 것 하나만 다르다. 아이템처럼 접두사를 쓰지 않는 이유도 같다 — 재주는
 * 열일곱으로 정해져 있고 **같은 그림을 나눠 쓸 재주가 없다.** 접두사로 고르면
 * `hex_fire` 와 `hex_frost` 가 한 그림이 된다.
 *
 * **팩을 안 본다.** 재주 **이름**은 발행된 팩이 정본이지만(`content/skills.ts`), 그림은
 * 저장소가 구워 들고 있는 자산이라 발행과 무관하다 — 이름을 고쳐 발행해도 그림은 그대로
 * 그 재주의 것이다.
 *
 * **없으면 없는 대로 둔다.** 아직 안 그린 재주는 `undefined` 를 돌려주고 화면은 글자로
 * 떨어진다. 전수 검사가 빠진 장을 잡으므로 조용히 비지 않는다.
 */

// **파일을 떨구면 바로 잡힌다.** 목록을 코드에 또 적으면 그림을 더할 때마다 두 곳을
// 고쳐야 하고, 한쪽만 고친 날 그림이 조용히 안 뜬다.
const FILES = import.meta.glob<string>('@design/art/skills/*.svg', {
  query: '?url',
  import: 'default',
  eager: true,
})

/** 파일 이름(확장자 뺀 것) → 주소. 파일 이름이 곧 소문자로 내린 재주 id 다. */
const BY_ID = new Map<string, string>(
  Object.entries(FILES).map(([path, url]) => [
    path.slice(path.lastIndexOf('/') + 1, -'.svg'.length),
    url,
  ]),
)

/**
 * 이 재주가 쓸 그림의 주소.
 *
 * @param skillId 재주 id (`skills.json` 의 `skills[].id`). 대소문자를 안 가린다.
 * @returns 그림 주소. 아직 안 그린 재주면 undefined.
 */
export function findSkillArt(skillId: string): string | undefined {
  return BY_ID.get(skillId.toLowerCase())
}

/** 이 코어가 들고 있는 재주 그림의 이름 전부. 전수 검사가 정본과 맞춰 본다. */
export function listSkillArtIds(): readonly string[] {
  return [...BY_ID.keys()].sort()
}
