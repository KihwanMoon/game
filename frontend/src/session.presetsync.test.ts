/**
 * 프리셋이 계정을 따라오는가.
 *
 * 계정은 익명으로 시작해 가입으로 승격되고, **세이브·티켓·제출이 전부 따라온다**
 * (CLAUDE.md). 코드 라이브러리만 안 따라오면 기기를 바꾼 사람은 자기가 만든 규칙표를
 * 잃는다 — 그리고 그것은 "저장이 안 된다" 로 보인다.
 */
import { describe, expect, it } from 'vitest'

import { createEmptyMeta } from './core/schemas'
import { adoptServerMeta } from './core/services/manageMeta'
import {
  adoptDraft,
  applyRuleSetEdit,
  applySessionToMeta,
  adoptPresets,
  applyPresetSave,
  buildMetaFromSession,
  buildSessionSave,
  createSession,
  getSessionRuleSet,
} from './session'
import { G0_RULESETS, ROOM_TEMPLATES } from './core/resources'

function buildSession() {
  const base = G0_RULESETS.get('g0_kite')
  if (base === undefined) {
    throw new Error('기준 규칙표가 없다')
  }
  const first = ROOM_TEMPLATES[0]
  if (first === undefined) {
    throw new Error('룸 템플릿이 없다')
  }
  return createSession(undefined, { ruleset: base, roomId: first.templateId, seed: 1 })
}

describe('코드 라이브러리가 계정을 따라온다', () => {
  it('★ 저장한 프리셋이 서버로 올라갈 절에 실린다', () => {
    const session = applyPresetSave(buildSession(), '내 규칙')
    expect(session.presets).toHaveLength(1)
    // 서버로 가는 것은 메타 세이브다. 세션의 프리셋이 거기 실리지 않으면 서버의
    // presets 필드는 영영 빈 채로 남는다.
    const meta = buildMetaFromSession(session, createEmptyMeta())
    expect(meta.presets).toHaveLength(1)
  })

  it('★ 서버에 있는 프리셋을 새 기기가 받는다', () => {
    const server = { ...createEmptyMeta(), presets: applyPresetSave(buildSession(), '내 규칙').presets }
    const merged = adoptServerMeta(server, createEmptyMeta())
    expect(merged.presets).toHaveLength(1)
  })

  it('저장 절에도 그대로 남는다 — 로컬은 지금도 된다', () => {
    expect(buildSessionSave(applyPresetSave(buildSession(), '내 규칙')).presets).toHaveLength(1)
  })

  it('★ 새 기기가 서버 슬롯을 세션으로 받는다 — 받아도 화면에 안 뜨면 없는 것과 같다', () => {
    const server = applyPresetSave(buildSession(), '내 규칙').presets
    expect(adoptPresets(buildSession(), server).presets).toHaveLength(1)
  })

  it('★ 이 기기에 슬롯이 있으면 서버 것으로 덮지 않는다 — 덮으면 되돌릴 수 없다', () => {
    const local = applyPresetSave(buildSession(), '이 기기')
    const server = applyPresetSave(buildSession(), '서버').presets
    expect(adoptPresets(local, server).presets[0]?.name).toBe('이 기기')
  })
})


describe('편집 중인 규칙표가 계정을 따라온다', () => {
  it('★ 새 기기가 서버의 초안을 받는다 — 안 받으면 규칙이 통째로 사라진 것처럼 보인다', () => {
    // 실제로 그렇게 보고됐다: "기기를 바꿔서 로그인했는데 규칙이 다 사라져있네".
    const source = buildSession()
    const meta = buildMetaFromSession(source, createEmptyMeta())
    expect(meta.draft).toBeDefined()
    const fresh = createSession(undefined, {
      ruleset: { rulesetId: 'empty', version: 1, rules: [] },
      roomId: 'x',
      seed: 1,
    })
    const adopted = adoptDraft(fresh, meta.draft, false)
    expect(getSessionRuleSet(adopted).rules.length).toBe(
      getSessionRuleSet(source).rules.length,
    )
  })

  it('★ 이 기기에 저장이 있으면 안 덮는다 — 방금 한 편집이 사라지면 되돌릴 수 없다', () => {
    const mine = buildSession()
    const server = { rulesetId: 'other', version: 1, rules: [] }
    expect(adoptDraft(mine, server, true)).toBe(mine)
  })

  it('서버에 초안이 없으면 그대로 둔다', () => {
    const mine = buildSession()
    expect(adoptDraft(mine, undefined, false)).toBe(mine)
  })
})


describe('규칙을 고치면 올릴 것이 생긴다', () => {
  it('★ 슬롯이 안 바뀌어도 초안이 바뀌면 새 메타다', () => {
    // **여기가 진짜 원인이었다.** 올리는 쪽이 슬롯만 보고 있어서, 규칙을 아무리 고쳐도
    // 서버에는 아무것도 안 갔다 — 기기를 바꾸면 규칙이 사라진 것처럼 보였다.
    const base = createEmptyMeta()
    const first = applySessionToMeta(buildSession(), base)
    expect(first).not.toBe(base)
    expect(first.draft).toBeDefined()
  })

  it('★ 아무것도 안 바뀌면 같은 객체다 — 매번 올리면 규칙 한 줄에 수십 번이 나간다', () => {
    const session = buildSession()
    const once = applySessionToMeta(session, createEmptyMeta())
    expect(applySessionToMeta(session, once)).toBe(once)
  })

  it('★ 규칙을 고치면 다시 올릴 것이 생긴다', () => {
    const session = buildSession()
    const once = applySessionToMeta(session, createEmptyMeta())
    const edited = applyRuleSetEdit(session, {
      ...getSessionRuleSet(session),
      version: getSessionRuleSet(session).version + 1,
    })
    expect(applySessionToMeta(edited, once)).not.toBe(once)
  })
})
