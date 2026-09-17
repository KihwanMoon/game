/**
 * 관리 페이지의 목록이 공용 틀을 쓰는가.
 *
 * **관리 페이지만 딴 길로 가 있었다** (2026-09-17). 게임 안 관리 탭(`editor/AdminPanel`)은
 * `DataList` 를 쓰는데, 별도 관리 페이지(`/admin.html`)의 목록은 **전부 손으로 짠 것**이었다 —
 * 봇 표·둔갑·지킴이·테스터·봇 상세의 다섯 줄 목록까지.
 *
 * 그래서 찾기도 페이지도 없었고, 빈 경우를 화면마다 바깥에서 갈라 적고 있었다. 한 곳을
 * 고쳐도 나머지는 옛 모양으로 남는 자리다 — 이 저장소가 가방·격자에서 이미 겪은 병이다
 * (`gridCell` 머리말의 「봇 가방이 유저 가방과 다른 목록」).
 *
 * 소스를 읽어 본다. 화면 렌더 검사는 **그 화면이 있을 때만** 도는데, 새 관리 화면이
 * 손으로 짠 목록을 들고 들어오면 아무 검사도 안 빨개진다.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const HERE = fileURLToPath(new URL('.', import.meta.url))

/**
 * 관리 페이지의 화면 파일들.
 *
 * @returns 파일 이름과 내용.
 */
function listScreens(): readonly (readonly [string, string])[] {
  return readdirSync(HERE)
    .filter((name) => name.endsWith('.tsx') && !name.includes('.test.'))
    .map((name) => [name, readFileSync(`${HERE}${name}`, 'utf8')] as const)
}

/**
 * 목록을 손으로 짠 자리들.
 *
 * `<ul>` 안에서 `.map(` 을 도는 모양을 찾는다 — 그것이 곧 「줄을 손으로 편다」다.
 * 고정 배치(`<ul>` 안에 `<li>` 를 손으로 몇 개 적은 것)는 목록이 아니므로 안 센다.
 *
 * @param source 파일 내용.
 * @returns 걸린 자리 수.
 */
function countHandRolled(source: string): number {
  return [...source.matchAll(/<ul[^>]*>\s*\n\s*\{[^}]*\.map\(/g)].length
}

describe('관리 페이지 목록', () => {
  const SCREENS = listScreens()

  it('★ 화면을 실제로 읽었다 — 0개면 훑기가 깨진 것이다', () => {
    expect(SCREENS.length).toBeGreaterThan(8)
  })

  it('★ 손으로 짠 목록이 없다 — 찾기도 빈 경우도 화면마다 따로 적게 된다', () => {
    const hand = SCREENS.filter(([, source]) => countHandRolled(source) > 0).map(([name]) => name)
    expect(hand, '손으로 짠 목록이 남았다').toEqual([])
  })

  it('★ 줄을 도는 화면은 DataList 를 들여온다', () => {
    // `bots__grid` 는 관리 표의 줄 스택이다. 그것을 쓰면서 `DataList` 를 안 들여왔다면
    // 여전히 손으로 펴고 있다는 뜻이다.
    const stray = SCREENS.filter(
      ([, source]) => source.includes('bots__grid') && !source.includes('DataList'),
    ).map(([name]) => name)
    expect(stray, 'bots__grid 를 쓰면서 DataList 를 안 쓴다').toEqual([])
  })
})
