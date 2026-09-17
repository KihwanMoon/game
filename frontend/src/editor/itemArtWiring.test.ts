/**
 * 아이템을 그리는 화면이 전부 그림을 넘기는가.
 *
 * **`CatalogAdminPanel` 하나가 빠져 있었다** (2026-09-17 신고: 「여기 그림 없잖아」).
 * 부품(`ds/Thumb`)은 `art` 를 받는데 그 화면만 안 넘겨서, 칸에 자리 코드(`BD`)만
 * 그려지고 있었다 — 쓰는 사람에게는 「관리 페이지에는 그림이 없다」로 보인다.
 *
 * **서버도 파서도 멀쩡했다.** `catalog_id`·`hands` 를 싣고 있었고 클라이언트도 지키고
 * 있었다 — 마지막 한 칸에서 안 쓴 것뿐이다. 도감에서 겪은 것과 같은 모양이라(서버는
 * 싣는데 화면이 버림) 이번에는 **자리 전체**를 검사로 덮는다.
 *
 * 소스를 읽는다. 화면 렌더 검사는 그 화면이 있을 때만 도는데, 새 화면이 `Thumb` 을
 * 그림 없이 들고 들어오면 아무 검사도 안 빨개진다.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const HERE = fileURLToPath(new URL('.', import.meta.url))

/**
 * `Thumb` 을 쓰는 화면들.
 *
 * @returns 파일 이름과 내용.
 */
function listUsers(): readonly (readonly [string, string])[] {
  return readdirSync(HERE)
    .filter((name) => name.endsWith('.tsx') && !name.includes('.test.'))
    .map((name) => [name, readFileSync(`${HERE}${name}`, 'utf8')] as const)
    .filter(([, source]) => source.includes('<Thumb'))
}

describe('아이템 그림 배선', () => {
  const USERS = listUsers()

  it('★ `Thumb` 을 쓰는 화면을 실제로 찾았다 — 0개면 훑기가 깨진 것이다', () => {
    expect(USERS.length).toBeGreaterThan(2)
  })

  // **`findItemArt` 를 부르는지는 안 본다.** 그림을 제 손으로 찾는 화면도 있고, 칸이
  // 미리 담아 준 것(`cell.art`)을 그대로 넘기는 화면도 있다 — 둘 다 맞는 배선이다.
  // 처음엔 그것까지 걸었다가 멀쩡한 화면 셋을 잡았다.

  it('★ 넘기는 자리가 `Thumb` 수만큼 있다 — 둘 중 하나만 넘기면 반만 뜬다', () => {
    const short = USERS.filter(([, source]) => {
      const thumbs = [...source.matchAll(/<Thumb\b/g)].length
      const arts = [...source.matchAll(/\bart[:=]|\{ art \}|art \}/g)].length
      return arts < thumbs
    }).map(([name]) => name)
    expect(short, '그림을 안 넘기는 Thumb 이 남았다').toEqual([])
  })
})
