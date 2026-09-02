/**
 * 가방과 소모품 칸은 한 문으로만 읽는다 (설계/4_아이템 §5).
 *
 * **이 검사가 있는 이유는 같은 사고가 두 번 났기 때문이다.** 소모품 칸을 만들고 나서
 * 「끼울 수가 없다」는 신고를 받았는데, 원인은 부팅 경로가 **가방만 읽고 칸을 안 읽은**
 * 것이었다. 고쳤다고 하고 배포했는데 또 같은 신고를 받았다 — 치환이 `readInventory` 의
 * 한 가지 모양만 잡았고, 부팅 경로는 다른 모양(`await` 대입)이라 그대로 남아 있었다.
 *
 * 그래서 「빠뜨리지 않기」를 사람의 주의력에 맡기지 않는다. 문을 하나로 두고, **다른
 * 문이 생기지 않았는지를 검사가 본다.** 화면이 안 그리는 이유는 둘뿐이다 — 그릴 규칙이
 * 없거나, 그릴 값이 없거나. 이것은 두 번째를 막는 자리다.
 */
import { readFileSync } from 'node:fs'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { readBagState } from './consumableSync'

const APP_PATH = new URL('../App.tsx', import.meta.url).pathname

/**
 * 앱 본문을 주석을 걷어내고 읽는다.
 *
 * @returns 주석 없는 소스.
 */
function readAppSource(): string {
  return readFileSync(APP_PATH, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
}

describe('가방 읽기의 문', () => {
  it('★ `readInventory` 를 앱이 직접 안 부른다 — 부르면 칸을 빠뜨릴 자리가 다시 생긴다', () => {
    expect(readAppSource()).not.toContain('readInventory(')
  })

  it('★ `readConsumables` 도 직접 안 부른다 — 반대 방향으로 어긋나는 것도 막는다', () => {
    expect(readAppSource()).not.toContain('readConsumables(')
  })

  it('★ 문이 실제로 쓰이고 있다 — 아무것도 안 부르면 위의 둘이 저절로 통과한다', () => {
    expect(readAppSource()).toContain('readBagState(')
  })

  it('★ 한 번에 둘 다 돌려준다 — 하나만 담으면 부르는 쪽이 나머지를 또 찾아 나선다', async () => {
    const source = readFileSync(
      new URL('./consumableSync.ts', import.meta.url).pathname,
      'utf8',
    )
    expect(source).toContain('inventory')
    expect(source).toContain('consumables')
  })
})


afterEach(() => {
  vi.unstubAllGlobals()
})

describe('한 번에 둘 다 부른다', () => {
  it('★ 두 경로를 실제로 두드린다 — 문만 만들고 안 부르면 화면은 여전히 빈손이다', async () => {
    const paths: string[] = []
    vi.stubGlobal('fetch', (input: string) => {
      paths.push(String(input))
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            slots: [],
            equipment: [],
            options: [],
            balance: 0,
            repair_cost: 0,
            free_charges: 1,
            is_run_open: false,
          }),
      })
    })
    const bag = await readBagState('t')
    expect(paths.some((path) => path.endsWith('/inventory'))).toBe(true)
    expect(paths.some((path) => path.endsWith('/consumables'))).toBe(true)
    expect(bag.inventory).toBeDefined()
    expect(bag.consumables).toBeDefined()
  })
})
