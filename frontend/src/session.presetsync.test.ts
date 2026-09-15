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
  adoptAccount,
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

describe('로그인은 서버가 이긴다', () => {
  it('★ 이 기기에 있던 초안을 서버 것으로 갈아 끼운다', () => {
    // **여기가 마지막 구멍이었다.** 로컬을 지키는 규칙이 mount 에는 맞지만 로그인에는
    // 틀리다 — 모바일에서 짠 규칙이 컴퓨터에 안 보인 이유가 이것이다.
    const mine = buildSession()
    // **표본에 규칙을 넣어 둔다.** 예전에는 0줄짜리를 썼는데, 그것은 「서버가 이긴다」가
    // 아니라 **「빈 것이 이긴다」를 계약으로 굳히는 것**이었다 — 실제로 그 길로 사람의
    // 규칙이 두 번 지워졌다 (2026-09-15). 빈 초안의 몫은 아래 절이 따로 본다.
    const server = {
      ...createEmptyMeta(),
      draft: { ...getSessionRuleSet(mine), rulesetId: 'from_server' },
    }
    const adopted = adoptAccount(mine, server)
    expect(getSessionRuleSet(adopted).rulesetId).toBe('from_server')
  })

  it('★ 서버에 초안이 없으면 지금 것을 둔다 — 새로 가입한 계정이 그 경우다', () => {
    const mine = buildSession()
    const adopted = adoptAccount(mine, createEmptyMeta())
    expect(getSessionRuleSet(adopted).rulesetId).toBe(getSessionRuleSet(mine).rulesetId)
  })

  it('★ 슬롯도 계정 것으로 갈린다 — 앞 계정의 슬롯이 남으면 남의 것을 보게 된다', () => {
    const mine = applyPresetSave(buildSession(), '내 것')
    const server = {
      ...createEmptyMeta(),
      presets: applyPresetSave(buildSession(), '계정 것').presets,
    }
    expect(adoptAccount(mine, server).presets[0]?.name).toBe('계정 것')
  })
})

describe('빈 초안이 서버의 초안을 덮지 않는가 (2026-09-15, 실제 사고)', () => {
  /** 규칙이 한 줄도 없는 세션. 아무것도 안 짜 본 기기가 이 모양이다. */
  function buildEmptySession() {
    const first = ROOM_TEMPLATES[0]
    if (first === undefined) {
      throw new Error('룸 템플릿이 없다')
    }
    return createSession(undefined, {
      ruleset: { rulesetId: 'empty', version: 1, rules: [] },
      roomId: first.templateId,
      seed: 1,
    })
  }

  it('★ 0줄짜리 초안은 서버의 여러 줄을 안 덮는다', () => {
    // 실제로 이것이 일어났다 — 여섯 줄을 짜 둔 계정이 빈 기기에서 화면을 열자 서버
    // 초안이 0줄로 덮였고, 사람에게 그것은 「전투 규칙이 사라졌다」로 보였다.
    const stored = { ...createEmptyMeta(), draft: getSessionRuleSet(buildSession()) }
    expect(stored.draft?.rules.length).toBeGreaterThan(0)
    const merged = buildMetaFromSession(buildEmptySession(), stored)
    expect(merged.draft).toBe(stored.draft)
  })

  it('한 줄이라도 있으면 그것이 올라간다 — 지키기가 저장을 막으면 안 된다', () => {
    const stored = { ...createEmptyMeta(), draft: getSessionRuleSet(buildEmptySession()) }
    const session = buildSession()
    const merged = buildMetaFromSession(session, stored)
    expect(merged.draft?.rules.length).toBe(getSessionRuleSet(session).rules.length)
  })

  it('★ 이 기기의 초안이 비어 있으면 저장이 있어도 서버 것을 싣는다', () => {
    // 「저장이 있다」와 「짜 둔 것이 있다」는 다르다 — 시드나 방만 한 번 고른 기기에도
    // 저장은 생긴다.
    const fromServer = getSessionRuleSet(buildSession())
    const next = adoptDraft(buildEmptySession(), fromServer, true)
    expect(getSessionRuleSet(next).rules.length).toBe(fromServer.rules.length)
  })

  it('짜 둔 것이 있으면 서버 것이 안 덮는다 — 방금 한 편집이 사라지면 안 된다', () => {
    const session = buildSession()
    const next = adoptDraft(session, { rulesetId: 'other', version: 1, rules: [] }, true)
    expect(next).toBe(session)
  })
})

describe('빈 초안은 어디서도 이기지 않는다 (2026-09-15, 같은 사고 두 번째)', () => {
  /** 규칙이 없는 초안. 「다 지웠다」가 아니라 「아직 아무것도 없다」다. */
  const EMPTY_DRAFT = { rulesetId: 'first_rule', version: 1, rules: [] }

  it('★ 합칠 때 — 0줄짜리 이 기기 초안이 서버의 여러 줄을 못 이긴다', () => {
    // 여기가 두 번째 구멍이었다. `local.draft ?? server.draft` 는 **없을 때만** 서버
    // 것을 쓰는데, 0줄은 `undefined` 가 아니다. 그리고 합친 결과는 곧바로 서버로
    // 올라가므로 **화면을 여는 것만으로** 남의 기기에서 짠 규칙이 지워졌다.
    const full = getSessionRuleSet(buildSession())
    const merged = adoptServerMeta(
      { ...createEmptyMeta(), draft: full },
      { ...createEmptyMeta(), draft: EMPTY_DRAFT },
    )
    expect(merged.draft?.rules.length).toBe(full.rules.length)
  })

  it('짜 둔 것이 있으면 이 기기 것이 이긴다 — 방금 한 편집이 사라지면 안 된다', () => {
    const mine = getSessionRuleSet(buildSession())
    const merged = adoptServerMeta(
      { ...createEmptyMeta(), draft: EMPTY_DRAFT },
      { ...createEmptyMeta(), draft: mine },
    )
    expect(merged.draft).toBe(mine)
  })

  it('둘 다 비었으면 이 기기 것을 둔다 — 이름과 판을 지킨다', () => {
    const merged = adoptServerMeta(
      { ...createEmptyMeta(), draft: undefined },
      { ...createEmptyMeta(), draft: EMPTY_DRAFT },
    )
    expect(merged.draft).toBe(EMPTY_DRAFT)
  })

  it('★ 로그인할 때 — 계정 초안이 0줄이면 짜던 것을 안 지운다', () => {
    // 로그인은 서버가 이기지만, **이길 것이 없으면 이기지 않는다.**
    const session = buildSession()
    const next = adoptAccount(session, { ...createEmptyMeta(), draft: EMPTY_DRAFT })
    expect(getSessionRuleSet(next).rules.length).toBe(getSessionRuleSet(session).rules.length)
  })
})
