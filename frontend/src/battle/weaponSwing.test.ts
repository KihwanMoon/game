/**
 * 무기 꼴과 모션 (설계/10_외형과_모션).
 *
 * **여기서 지키는 것은 계약이다.** 자유도를 외형에 두기로 했고, 그 축이 결정론·판독성과
 * 부딪히지 않는다는 것이 이 검사들이다.
 */
import { describe, expect, it } from 'vitest'

import {
  DEFAULT_MOTION,
  DEFAULT_SHAPE,
  buildSwing,
  resolveFacing,
  resolveMotion,
  resolveShape,
} from './weaponSwing'

const CELL = 40
const FROM = { x: 100, y: 100 }
const TO = { x: 140, y: 100 }

function swing(shape = 'straight', motion = 'chop', phase = 0.5) {
  return buildSwing(FROM, TO, CELL, resolveShape(shape), resolveMotion(motion), phase)
}

describe('resolveShape · resolveMotion', () => {
  it('★ 모르는 값이 와도 도면이 안 깨진다', () => {
    // 닫힌 집합이다 (계약 C6) — 임의 값을 열면 이모지·폭 다른 글자가 들어온다.
    expect(resolveShape('무엇이든')).toBe(DEFAULT_SHAPE)
    expect(resolveMotion('무엇이든')).toBe(DEFAULT_MOTION)
  })

  it('아는 값은 그대로 통과한다', () => {
    expect(resolveShape('axe')).toBe('axe')
    expect(resolveMotion('thrust')).toBe('thrust')
  })
})

describe('resolveFacing', () => {
  it('때린 쪽에서 맞은 쪽을 본다', () => {
    expect(resolveFacing({ x: 0, y: 0 }, { x: 10, y: 0 })).toBeCloseTo(0)
    expect(resolveFacing({ x: 0, y: 0 }, { x: 0, y: 10 })).toBeCloseTo(Math.PI / 2)
  })

  it('★ 제자리를 때리면 위를 본다', () => {
    // 방향이 없는 자해·장판에서 오른쪽을 기본으로 두면 늘 오른쪽으로 휘둘러 이상하다.
    expect(resolveFacing({ x: 5, y: 5 }, { x: 5, y: 5 })).toBeCloseTo(-Math.PI / 2)
  })
})

describe('buildSwing', () => {
  it('★ 같은 입력이면 같은 자국이다 — 무작위가 없다', () => {
    // 같은 리플레이를 두 번 보면 같아야 한다 (계약 C4).
    expect(swing()).toEqual(swing())
  })

  it('★ 위상이 다르면 자국이 다르다 — 실제로 움직인다', () => {
    expect(swing('straight', 'chop', 0)).not.toEqual(swing('straight', 'chop', 1))
  })

  it('★ 위상은 0..1 을 벗어나지 않는다', () => {
    // 넘으면 배속에서 앞뒤 틱의 자국이 겹친다 (계약 C3).
    expect(swing('straight', 'chop', -5)).toEqual(swing('straight', 'chop', 0))
    expect(swing('straight', 'chop', 9)).toEqual(swing('straight', 'chop', 1))
  })

  it('★ 꼴과 모션이 서로 곱한다', () => {
    // 자산 3+3 으로 조합 9 다 (계약 C7). 꼴을 바꿔도 모션을 바꿔도 자국이 달라진다.
    expect(swing('straight')).not.toEqual(swing('axe'))
    expect(swing('straight', 'chop')).not.toEqual(swing('straight', 'thrust'))
  })

  it('굽은 칼은 곧은 칼보다 마디가 많다 — 휨이 곧 그 마디다', () => {
    expect(swing('curved').blade.length).toBeGreaterThan(swing('straight').blade.length)
  })

  it('도끼만 날을 얹는다 — 칼 셋 중에서', () => {
    expect(swing('axe').head.length).toBeGreaterThan(0)
    expect(swing('straight').head).toHaveLength(0)
  })

  it('★ 몸이 무기인 것들도 저마다 다르게 그려진다', () => {
    // 늑대에게 직검을 쥐여 주면 그것도 거짓이다. 일곱 꼴이 서로 겹치면 안 나뉜다.
    const drawn = ['straight', 'curved', 'axe', 'arrow', 'fang', 'bolt', 'fist'].map((shape) =>
      JSON.stringify(swing(shape, 'chop', 0.5)),
    )
    expect(new Set(drawn).size).toBe(drawn.length)
  })

  it('엄니는 두 짝이다 — 한 줄이면 그냥 칼이다', () => {
    const bite = swing('fang')
    expect(bite.blade.length).toBeGreaterThan(0)
    expect(bite.head.length).toBeGreaterThan(0)
  })

  it('술법 탄은 닫힌 마름모다 — 열린 선은 날붙이로 읽힌다', () => {
    const bolt = swing('bolt', 'fly').blade
    expect(bolt.length).toBeGreaterThan(3)
    expect(bolt.at(0)).toEqual(bolt.at(-1))
  })

  it('덩이는 뾰족한 데가 없다 — 네 귀가 닫혀 있다', () => {
    const fist = swing('fist').head
    expect(fist.length).toBe(5)
    expect(fist.at(0)).toEqual(fist.at(-1))
  })

  it('★ 자국이 때린 말의 칸을 크게 벗어나지 않는다', () => {
    // 옆 칸을 침범하면 **누가 때렸는지**가 흐려진다.
    for (const shape of ['axe', 'fang', 'fist']) {
      const drawn = swing(shape, 'slash', 0.5)
      for (const point of [...drawn.blade, ...drawn.head]) {
        expect(Math.hypot(point.x - FROM.x, point.y - FROM.y)).toBeLessThan(CELL * 1.5)
      }
    }
  })

  it('★ 나는 것은 자루가 옮겨 간다 — 훑는 것과 종류가 다르다', () => {
    // 훑는 모션은 자루가 때린 말에 붙어 있고 날이 그 둘레를 돈다. 화살은 반대다.
    const at = (phase: number) => {
      const tip = buildSwing(FROM, TO, CELL, 'arrow', 'fly', phase).blade.at(-1)
      return Math.hypot((tip?.x ?? 0) - FROM.x, (tip?.y ?? 0) - FROM.y)
    }
    expect(at(0)).toBeLessThan(at(0.5))
    expect(at(0.5)).toBeLessThan(at(1))
  })

  it('★ 화살은 위상 1 에 대상 칸에 꽂힌다', () => {
    // 고리와 수치가 뜨는 순간과 닿는 순간이 같아야 「맞았다」로 읽힌다.
    const far = { x: FROM.x + CELL * 4, y: FROM.y }
    const shaft = buildSwing(FROM, far, CELL, 'arrow', 'fly', 1).blade[0]
    expect(Math.hypot((shaft?.x ?? 0) - far.x, (shaft?.y ?? 0) - far.y)).toBeLessThan(CELL)
  })

  it('★ 화살은 쏜 말 위에서 출발하지 않는다 — 글리프를 가리면 누가 쐈는지 안 읽힌다', () => {
    const shaft = buildSwing(FROM, TO, CELL, 'arrow', 'fly', 0).blade[0]
    expect(Math.hypot((shaft?.x ?? 0) - FROM.x, (shaft?.y ?? 0) - FROM.y)).toBeGreaterThan(0)
  })

  it('화살은 촉을 단다 — 도끼보다 좁고 뾰족하다', () => {
    const arrow = swing('arrow', 'fly', 0.5)
    expect(arrow.head.length).toBeGreaterThan(0)
    const width = (stroke: { head: readonly { x: number; y: number }[] }) => {
      const ys = stroke.head.map((one) => one.y)
      return Math.max(...ys) - Math.min(...ys)
    }
    expect(width(arrow)).toBeLessThan(width(swing('axe', 'chop', 0.5)))
  })

  it('꼴과 모션이 여전히 곱한다 — 던진 칼도 표현된다', () => {
    // 4 꼴 × 4 모션이라 조합 16 이다. 나는 모션에 곧은 날을 태우면 던진 칼이 된다.
    expect(swing('straight', 'fly')).not.toEqual(swing('arrow', 'fly'))
  })

  it('찌르기는 중간에 가장 멀리 나갔다 돌아온다', () => {
    const reach = (phase: number) => {
      const tip = buildSwing(FROM, TO, CELL, 'straight', 'thrust', phase).blade.at(-1)
      return Math.hypot((tip?.x ?? 0) - FROM.x, (tip?.y ?? 0) - FROM.y)
    }
    expect(reach(0.5)).toBeGreaterThan(reach(0))
    expect(reach(0.5)).toBeGreaterThan(reach(1))
  })
})
