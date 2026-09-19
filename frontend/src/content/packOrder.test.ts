/**
 * 발행한 팩이 화면에 닿는가.
 *
 * **한 번도 안 닿고 있었다** (2026-09-19). 「재주 이름을 고쳐 발행했는데 그대로다」로
 * 드러났는데, 이름만의 일이 아니었다 — `App.tsx` 는 본문에서 `readActivePack()` 을
 * 불러 카탈로그·방·적·밸런스를 한꺼번에 잡아 두고, `main.tsx` 가 그 App 을 **정적으로**
 * 들이고 있었다. ESM 은 import 한 모듈의 본문을 먼저 돌리므로 그 잡기가
 * `loadContentPack()` 보다 앞섰고, 팩은 갈아 끼워졌지만 화면이 든 것은 번들이었다.
 *
 * 운영에서 여태 안 보인 이유는 발행한 적이 없어서다(`published=0`). 첫 발행이 곧
 * 첫 노출이었다.
 *
 * 두 가지를 본다 — 부팅 순서(소스)와 읽는 자리(동작)다. 순서만 보면 읽는 자리가
 * 번들로 돌아가는 것을 못 잡고, 동작만 보면 정적 import 가 다시 들어오는 것을 못 잡는다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { afterEach, describe, expect, it } from 'vitest'

import { applyContentPack, readActivePack } from './pack'
import { listAllSkillIds, readSkillName } from './skills'

import type { ContentPack } from './pack'
import type { RawBalanceFile } from '../core/resources'

const SRC = fileURLToPath(new URL('..', import.meta.url))

// 팩을 받아 그리는 진입점들. 개발 전용 화면(`battleMain`·`hudMain`·`galleryMain`)은
// 팩을 안 받으므로 대상이 아니다 — 번들로 도는 것이 그쪽의 정상이다.
const BOOTS = ['main.tsx', 'adminMain.tsx']

/**
 * 그 진입점이 정적으로 들이는 우리 모듈들.
 *
 * **CSS 와 node_modules 는 뺀다.** 스타일은 팩을 안 읽고, `react` 는 우리 것이 아니다.
 *
 * @param source 진입점 소스.
 * @returns 정적 import 경로들.
 */
function listStaticLocalImports(source: string): readonly string[] {
  // 부작용 import(`import './x'`)도 본다. `from` 만 보면 본문을 돌리는 것은 같은데
  // 검사만 못 보는 자리가 생긴다.
  const found = [...source.matchAll(/^import\s(?:[^\n]*?from\s+)?'([^']+)'/gm)].map(
    (one) => one[1] ?? '',
  )
  return found.filter((path) => /^[.@]/.test(path) && !path.endsWith('.css'))
}

describe('부팅 순서', () => {
  it('정적으로 들인 화면을 잡아낸다 — 검사 자신에 대한 검사', () => {
    const before = "import { App } from './App'\nimport './styles/app.css'\n"
    expect(listStaticLocalImports(before)).toEqual(['./App'])
  })

  it.each(BOOTS)('%s 는 팩을 갈아 끼운 뒤에 화면을 들인다', (name) => {
    const source = readFileSync(`${SRC}${name}`, 'utf8')
    expect(source).toContain('await loadContentPack()')
    // **팩 모듈 하나만 허용한다.** 「App 만 늦게 들이면 된다」가 아니다 — 팩을 읽는
    // 모듈은 앞으로도 늘어나고, 그중 하나를 위에서 정적으로 들이면 그 모듈의 본문이
    // 다시 `loadContentPack()` 을 앞선다. 허용 목록을 좁게 두는 편이 싸다.
    expect(listStaticLocalImports(source)).toEqual(['./content/pack'])
    expect(source).toContain('await import(')
  })
})

describe('발행한 이름', () => {
  const BUNDLED = readActivePack()

  afterEach(() => {
    applyContentPack(BUNDLED)
  })

  /**
   * 재주 절만 바꾼 팩을 만든다.
   *
   * @param skills 갈아 끼울 재주 목록.
   * @returns 그 절만 다른 팩.
   */
  function buildPack(skills: readonly unknown[]): ContentPack {
    const balance: RawBalanceFile = { ...BUNDLED.balance, skills }
    return { ...BUNDLED, balance }
  }

  it('갈아 끼운 팩의 한글 이름이 화면 쪽으로 나온다', () => {
    expect(readSkillName('HEAL')).toBe('수복')
    applyContentPack(buildPack([{ id: 'HEAL', label_ko: '회복', actor: 'BOTH' }]))
    expect(readSkillName('HEAL')).toBe('회복')
  })

  it('팩에만 있는 재주도 목록에 선다', () => {
    expect(listAllSkillIds()).not.toContain('NEW_TRICK')
    applyContentPack(buildPack([{ id: 'NEW_TRICK', label_ko: '새 재주', actor: 'BOTH' }]))
    expect(listAllSkillIds()).toContain('NEW_TRICK')
  })

  it('이름이 없으면 id 를 그대로 쓴다 — 빈 칸보다 낫다', () => {
    applyContentPack(buildPack([{ id: 'NAMELESS', actor: 'BOTH' }]))
    expect(readSkillName('NAMELESS')).toBe('NAMELESS')
  })
})
