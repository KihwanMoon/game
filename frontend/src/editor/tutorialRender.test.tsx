/**
 * 튜토리얼 화면 검사 (W20).
 *
 * 파이썬 쪽 `tests/test_tutorial.py` 가 **스테이지가 무언가를 가르치는가**를 보고,
 * 여기서는 **그것이 화면과 세션까지 닿는가**를 본다. 데이터가 맞아도 배선이 없으면
 * 아무도 못 쓴다 — 도감에서 한 번 겪은 실수다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { checkTutorialCleared, readTutorialProgress, TUTORIAL_PROGRESS_KEY } from '../App'
import { TUTORIAL_STAGES } from '../core/resources'
import { applyTutorialStage, createSession, getSessionRuleSet } from '../session'
import { buildInitialRuleSet } from '../App'
import { TutorialPanel } from './TutorialPanel'

const FIRST = TUTORIAL_STAGES[0]
if (FIRST === undefined) {
  throw new Error('튜토리얼 스테이지가 비었다')
}

/** 빈 세션 하나. 튜토리얼이 방·시드·규칙표를 전부 덮으므로 시작값은 무엇이든 된다. */
function buildSession() {
  return createSession(undefined, {
    ruleset: buildInitialRuleSet(),
    roomId: 'corridor',
    seed: 1,
  })
}

/** 최소한의 기기 저장소 대역. */
function createMemoryStorage(seed: Record<string, string> = {}) {
  const map = new Map(Object.entries(seed))
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value)
    },
    removeItem: (key: string) => {
      map.delete(key)
    },
  }
}

describe('튜토리얼 데이터', () => {
  it('★ 단계가 다섯 이상 실려 있다 — 비면 아래가 전부 무의미하다', () => {
    expect(TUTORIAL_STAGES.length).toBeGreaterThanOrEqual(5)
  })

  it('★ 시작 규칙표와 해답이 다르다 — 같으면 고칠 이유가 없다', () => {
    for (const stage of TUTORIAL_STAGES) {
      expect(JSON.stringify(stage.startRules)).not.toBe(JSON.stringify(stage.solutionRules))
    }
  })

  it('★ 파이썬과 같은 파일을 읽는다 — 사본을 두면 화면만 조용히 갈라진다', () => {
    // 사본이면 stage_id 가 언젠가 어긋난다. 여기서는 vite 별칭이 원본을 가리키는지를
    // 스테이지 id 로 확인한다.
    expect(TUTORIAL_STAGES.map((stage) => stage.stageId)).toContain('flag_alternation')
  })
})

describe('튜토리얼 세션', () => {
  it('★ 단계를 열면 방·시드·규칙표가 한꺼번에 바뀐다', () => {
    // 셋 중 하나라도 남으면 단계가 의도한 판이 서지 않고, "시작으로는 진다" 가 깨진다.
    const opened = applyTutorialStage(buildSession(), FIRST, FIRST.startRules)
    expect(opened.roomId).toBe(FIRST.roomId)
    expect(opened.seed).toBe(FIRST.seed)
    expect(getSessionRuleSet(opened).rules).toHaveLength(FIRST.startRules.length)
  })

  it('★ 힌트는 해답을 싣는다 — 벽에 부딪힌 사람을 세워 두지 않는다', () => {
    const hinted = applyTutorialStage(buildSession(), FIRST, FIRST.solutionRules)
    expect(getSessionRuleSet(hinted).rules).toHaveLength(FIRST.solutionRules.length)
  })

  it('되돌리기가 살아 있다 — 단계를 열어도 앞 편집으로 돌아갈 수 있다', () => {
    const opened = applyTutorialStage(buildSession(), FIRST, FIRST.startRules)
    expect(opened.history.past.length).toBeGreaterThan(0)
  })
})

describe('튜토리얼 통과 판정', () => {
  it('★ 목표 판정과 같아야 통과다', () => {
    expect(checkTutorialCleared(FIRST, FIRST.goal.outcome, 100)).toBe(true)
    expect(checkTutorialCleared(FIRST, 'PLAYER_LOSS', 0)).toBe(false)
  })

  it('열린 단계가 없으면 통과할 것도 없다', () => {
    expect(checkTutorialCleared(undefined, 'PLAYER_WIN', 100)).toBe(false)
  })

  it('진행을 못 읽어도 앱은 뜬다 — 튜토리얼 진행은 게임을 막을 값이 아니다', () => {
    expect(readTutorialProgress(createMemoryStorage({ [TUTORIAL_PROGRESS_KEY]: '{' }))).toEqual([])
    expect(readTutorialProgress(undefined)).toEqual([])
  })

  it('저장된 진행을 읽는다', () => {
    const storage = createMemoryStorage({ [TUTORIAL_PROGRESS_KEY]: '["first_rule"]' })
    expect(readTutorialProgress(storage)).toEqual(['first_rule'])
  })
})

describe('튜토리얼 화면', () => {
  it('★ 목록에 단계 제목과 진행이 보인다', () => {
    const html = renderToStaticMarkup(
      <TutorialPanel
        stages={TUTORIAL_STAGES}
        cleared={['first_rule']}
        activeId={undefined}
        onOpen={() => undefined}
        onHint={() => undefined}
        onClose={() => undefined}
      />,
    )
    expect(html).toContain(FIRST.titleKo)
    expect(html).toContain('1 / 5')
  })

  it('★ 단계를 열면 무엇을 가르치는지 적혀 있다 — 없으면 퀴즈가 된다', () => {
    const stage = TUTORIAL_STAGES.find((item) => item.stageId === 'flag_alternation')
    const html = renderToStaticMarkup(
      <TutorialPanel
        stages={TUTORIAL_STAGES}
        cleared={[]}
        activeId="flag_alternation"
        onOpen={() => undefined}
        onHint={() => undefined}
        onClose={() => undefined}
      />,
    )
    expect(html).toContain(stage?.teachesKo ?? '__없음__')
    expect(html).toContain('힌트')
  })
})
