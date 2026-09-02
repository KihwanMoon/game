/**
 * 세션 검사 — **탭을 닫아도 남고, 지운 규칙은 되돌아온다** (M3).
 *
 * 여기서 도는 것이 에디터 담당이 지목한 구멍 셋이다.
 *
 * 1. 새로고침하면 규칙표가 G0 예시로 돌아가고 직전 판 결과도 사라진다.
 * 2. Alt+Backspace 로 지운 규칙은 돌아오지 않는다.
 * 3. 이름 붙여 둘 곳이 없어 규칙표를 한 벌밖에 들 수 없다.
 *
 * 새로고침은 **세션을 버리고 저장소만 들고 다시 세우는 것**으로 흉내 낸다. 그것이 새 탭이
 * 하는 일 그대로다.
 */
import { describe, expect, it } from 'vitest'

import { buildInitialRuleSet } from './App'
import { BLOCK_CATALOG, G0_RULESETS } from './core/resources'
import type { RuleSet } from './core/schemas'
import {
  HISTORY_LIMIT,
  addRule,
  checkTextEntry,
  removeRule,
  resolveHistoryCommand,
  updateRule,
} from './editor'
import {
  applyPresetImport,
  applyPresetLoad,
  applyPresetRemove,
  applyPresetSave,
  applyRedoStep,
  applyRoomChoice,
  applyRuleSetEdit,
  applyRunResult,
  applySeedChoice,
  applySeedPin,
  applyUndoStep,
  buildSessionSave,
  createSession,
  exportSessionCode,
  exportSlotCode,
  getSessionRuleSet,
  type EditorSession,
} from './session'
import { MAX_PRESET_SLOTS, readSave, writeSave, type StorageLike } from './storage'

/**
 * 대역 저장소를 만든다.
 *
 * @returns 메모리에만 남는 저장소.
 */
function createFakeStorage(): StorageLike {
  const entries = new Map<string, string>()
  return {
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => {
      entries.set(key, value)
    },
    removeItem: (key: string) => {
      entries.delete(key)
    },
  }
}

const SEED_VALUES = { ruleset: buildInitialRuleSet(), roomId: 'open_field', seed: 1 }

/**
 * 빈 세션을 만든다.
 *
 * @returns 저장이 없을 때의 세션.
 */
function createFresh(): EditorSession {
  return createSession(undefined, SEED_VALUES)
}

/**
 * 새로고침을 흉내 낸다 — 세션을 버리고 저장소만 들고 다시 세운다.
 *
 * @param session 저장할 세션.
 * @returns 새 탭이 세운 세션.
 */
function createReloaded(session: EditorSession): EditorSession {
  const storage = createFakeStorage()
  writeSave(storage, buildSessionSave(session))
  return createSession(readSave(storage), SEED_VALUES)
}

describe('새로고침', () => {
  it('저장이 없으면 G0 예시로 시작한다', () => {
    expect(getSessionRuleSet(createFresh()).rulesetId).toBe('g0_pressure')
  })

  it('고친 규칙표가 새 탭에 그대로 있다', () => {
    const edited = applyRuleSetEdit(
      createFresh(),
      addRule(getSessionRuleSet(createFresh()), BLOCK_CATALOG, 0),
    )
    const reloaded = createReloaded(edited)
    expect(getSessionRuleSet(reloaded).rules).toEqual(getSessionRuleSet(edited).rules)
  })

  it('직전 판 결과도 남는다 — 무엇을 고쳐야 하는지의 출발점이다', () => {
    const played = applyRunResult(createFresh(), {
      outcome: 'PLAYER_LOSS',
      ticks: 37,
      playerHp: 0,
    })
    expect(createReloaded(played).lastResult).toEqual({
      outcome: 'PLAYER_LOSS',
      ticks: 37,
      playerHp: 0,
    })
  })

  it('방과 시드도 남는다', () => {
    const chosen = applySeedChoice(applyRoomChoice(createFresh(), 'pillars'), 99)
    const reloaded = createReloaded(chosen)
    expect(reloaded.roomId).toBe('pillars')
    expect(reloaded.seed).toBe(99)
  })

  it('라이브러리 슬롯이 남는다', () => {
    const stored = applyPresetSave(createFresh(), '근접 압박')
    const reloaded = createReloaded(stored)
    expect(reloaded.presets).toHaveLength(1)
    expect(reloaded.presets[0]?.name).toBe('근접 압박')
    expect(reloaded.presets[0]?.ruleset.rules).toEqual(getSessionRuleSet(stored).rules)
  })

  it('되돌리기 스택은 남기지 않는다 — 새 탭에서 되돌릴 것은 이번 세션의 편집이다', () => {
    const edited = applyRuleSetEdit(createFresh(), removeRule(getSessionRuleSet(createFresh()), 0))
    const reloaded = createReloaded(edited)
    expect(reloaded.history.past).toEqual([])
    expect(applyUndoStep(reloaded)).toBe(reloaded)
  })
})

describe('되돌리기', () => {
  it('지운 규칙이 되돌아온다', () => {
    const start = createFresh()
    const before = getSessionRuleSet(start)
    const deleted = applyRuleSetEdit(start, removeRule(before, 0))
    expect(getSessionRuleSet(deleted).rules).toHaveLength(before.rules.length - 1)
    expect(getSessionRuleSet(applyUndoStep(deleted)).rules).toEqual(before.rules)
  })

  it('되돌린 것을 다시 실행한다', () => {
    const deleted = applyRuleSetEdit(createFresh(), removeRule(getSessionRuleSet(createFresh()), 0))
    const back = applyRedoStep(applyUndoStep(deleted))
    expect(getSessionRuleSet(back).rules).toEqual(getSessionRuleSet(deleted).rules)
  })

  it('여러 단계를 순서대로 되돌린다', () => {
    let session = createFresh()
    const snapshots: RuleSet[] = [getSessionRuleSet(session)]
    for (let step = 0; step < 3; step += 1) {
      session = applyRuleSetEdit(session, removeRule(getSessionRuleSet(session), 0))
      snapshots.push(getSessionRuleSet(session))
    }
    for (let step = snapshots.length - 1; step > 0; step -= 1) {
      session = applyUndoStep(session)
      expect(getSessionRuleSet(session)).toEqual(snapshots[step - 1])
    }
  })

  it('되돌린 뒤 새로 고치면 앞길은 버린다', () => {
    const start = createFresh()
    const deleted = applyRuleSetEdit(start, removeRule(getSessionRuleSet(start), 0))
    const undone = applyUndoStep(deleted)
    const rewritten = applyRuleSetEdit(undone, addRule(getSessionRuleSet(undone), BLOCK_CATALOG, 0))
    expect(rewritten.history.future).toEqual([])
    expect(applyRedoStep(rewritten)).toBe(rewritten)
  })

  it('아무것도 바꾸지 않은 편집은 단계로 쌓지 않는다', () => {
    const start = createFresh()
    const same = applyRuleSetEdit(start, getSessionRuleSet(start))
    expect(same.history.past).toEqual([])
  })

  it('스택은 상한까지만 자란다', () => {
    let session = createFresh()
    for (let step = 0; step < HISTORY_LIMIT + 10; step += 1) {
      session = applyRuleSetEdit(
        session,
        updateRule(getSessionRuleSet(session), 0, { setFlag: `flag_${String(step)}` }),
      )
    }
    expect(session.history.past).toHaveLength(HISTORY_LIMIT)
  })

  it('되돌리기는 규칙표만 되돌린다 — 시드는 판의 조건이지 편집이 아니다', () => {
    const edited = applyRuleSetEdit(createFresh(), removeRule(getSessionRuleSet(createFresh()), 0))
    const seeded = applySeedChoice(edited, 77)
    expect(applyUndoStep(seeded).seed).toBe(77)
  })

  it('Ctrl+Z 와 Ctrl+Shift+Z 를 가른다', () => {
    const base = { ctrlKey: true, metaKey: false, shiftKey: false }
    expect(resolveHistoryCommand({ ...base, key: 'z' })).toBe('undo')
    expect(resolveHistoryCommand({ ...base, key: 'Z', shiftKey: true })).toBe('redo')
    expect(resolveHistoryCommand({ ...base, key: 'y' })).toBe('redo')
    expect(resolveHistoryCommand({ ...base, key: 'a' })).toBeUndefined()
    expect(resolveHistoryCommand({ key: 'z', ctrlKey: false, metaKey: false, shiftKey: false })).toBeUndefined()
    expect(resolveHistoryCommand({ key: 'z', ctrlKey: false, metaKey: true, shiftKey: false })).toBe('undo')
  })

  it('글자를 치는 칸에서는 브라우저의 되돌리기에 맡긴다', () => {
    expect(checkTextEntry('input')).toBe(true)
    expect(checkTextEntry('TEXTAREA')).toBe(true)
    expect(checkTextEntry('DIV')).toBe(false)
    expect(checkTextEntry('')).toBe(false)
  })
})

describe('코드 라이브러리', () => {
  it('이름을 붙여 슬롯에 넣고 다시 불러온다', () => {
    const start = applyPresetSave(createFresh(), '근접 압박')
    const changed = applyRuleSetEdit(start, removeRule(getSessionRuleSet(start), 0))
    const restored = applyPresetLoad(changed, 0)
    expect(getSessionRuleSet(restored).rules).toEqual(getSessionRuleSet(start).rules)
  })

  it('불러오기도 되돌릴 수 있다', () => {
    const start = applyPresetSave(createFresh(), '근접 압박')
    const kite = G0_RULESETS.get('g0_kite') as RuleSet
    const swapped = applyRuleSetEdit(start, kite)
    const loaded = applyPresetLoad(swapped, 0)
    expect(getSessionRuleSet(applyUndoStep(loaded))).toEqual(kite)
  })

  it('같은 이름은 슬롯을 덮는다 — 이름이 둘인 라이브러리를 만들지 않는다', () => {
    const first = applyPresetSave(createFresh(), '같은 이름')
    const edited = applyRuleSetEdit(first, removeRule(getSessionRuleSet(first), 0))
    const second = applyPresetSave(edited, '같은 이름')
    expect(second.presets).toHaveLength(1)
    expect(second.presets[0]?.ruleset.rules).toEqual(getSessionRuleSet(edited).rules)
  })

  it('빈 이름은 저장하지 않는다', () => {
    expect(applyPresetSave(createFresh(), '   ').presets).toEqual([])
  })

  it('8슬롯을 넘겨 담지 않는다 (GDD §2.3)', () => {
    let session = createFresh()
    for (let step = 0; step < MAX_PRESET_SLOTS + 3; step += 1) {
      session = applyPresetSave(session, `슬롯 ${String(step)}`)
    }
    expect(session.presets).toHaveLength(MAX_PRESET_SLOTS)
  })

  it('슬롯을 지운다', () => {
    const two = applyPresetSave(applyPresetSave(createFresh(), '하나'), '둘')
    expect(applyPresetRemove(two, 0).presets.map((item) => item.name)).toEqual(['둘'])
  })
})

describe('공유 코드', () => {
  it('내보낸 코드를 읽으면 규칙표와 이름이 함께 온다', () => {
    const code = exportSessionCode(createFresh(), '남에게 줄 규칙표')
    const received = applyPresetImport(createFresh(), code)
    expect(received.presets[0]?.name).toBe('남에게 줄 규칙표')
    expect(getSessionRuleSet(received).rules).toEqual(getSessionRuleSet(createFresh()).rules)
  })

  it('읽어 온 코드도 되돌릴 수 있다', () => {
    const start = createFresh()
    const kite = G0_RULESETS.get('g0_kite') as RuleSet
    const code = exportSessionCode(applyRuleSetEdit(start, kite), '원거리 견제')
    const received = applyPresetImport(start, code)
    expect(getSessionRuleSet(received)).toEqual(kite)
    expect(getSessionRuleSet(applyUndoStep(received))).toEqual(getSessionRuleSet(start))
  })

  it('슬롯 코드는 그 슬롯의 규칙표를 낸다', () => {
    const stored = applyPresetSave(createFresh(), '근접 압박')
    expect(exportSlotCode(stored, 0)).toBe(exportSessionCode(stored, '근접 압박'))
    expect(exportSlotCode(stored, 7)).toBe('')
  })

  it('깨진 코드는 사유와 함께 던진다 — 화면이 그것을 그대로 적는다', () => {
    expect(() => applyPresetImport(createFresh(), '아무 글자')).toThrow(/v<버전>/)
  })
})

describe('시드 고정', () => {
  it('★ 기본은 꺼져 있다 — 판마다 새 시드가 나오는 것이 기본값이어야 한다', () => {
    expect(createFresh().isSeedPinned).toBe(false)
  })

  it('★ 저장에서 세워도 꺼져 있다 — 한 번 고정하면 영영 같은 판을 도는 사고를 막는다', () => {
    const pinned = applySeedPin(applySeedChoice(createFresh(), 777), true)
    const restored = createSession(buildSessionSave(pinned), {
      ruleset: getSessionRuleSet(pinned),
      roomId: 'corridor',
      seed: 1,
    })
    expect(restored.seed).toBe(777)
    expect(restored.isSeedPinned).toBe(false)
  })

  it('켜고 끌 수 있다', () => {
    const on = applySeedPin(createFresh(), true)
    expect(on.isSeedPinned).toBe(true)
    expect(applySeedPin(on, false).isSeedPinned).toBe(false)
  })
})
