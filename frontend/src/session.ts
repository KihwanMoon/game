/**
 * 앱 세션 — 탭이 살아 있는 동안의 상태 전부와, 그중 탭을 닫아도 남을 것.
 *
 * 화면(App.tsx)이 상태를 조각조각 들고 있으면 저장이 조각마다 붙는다. 조각 하나를 새로
 * 만들 때 저장에 넣는 것을 잊으면 그것만 사라지고, 그런 종류의 결함은 새로고침을 해 봐야
 * 드러난다. 그래서 **세션 하나가 저장의 모양과 같은 모양**을 갖고, 저장은 세션을 그대로
 * 굽는다 (`buildSessionSave`).
 *
 * 전이는 전부 순수 함수다. 되돌리기가 규칙표를 통째로 쌓는 방식이라(editor/history.ts)
 * 상태를 제자리에서 고치면 스택에 같은 객체가 여러 번 들어가 되돌려도 화면이 그대로다.
 *
 * **되돌리기 대상은 규칙표뿐이다.** 방·시드·직전 판 결과는 편집이 아니라 판의 조건이며,
 * `Ctrl+Z` 로 시드가 되돌아가면 사람은 자기가 무엇을 되돌렸는지 알 수 없다.
 */
import {
  type EditHistory,
  applyChange,
  applyRedo,
  applyUndo,
  createHistory,
} from './editor/history'
import type { MetaSave, RawRule, RuleSet, TutorialStage } from './core/schemas'
import { parseRuleSet } from './core/schemas'
import {
  MAX_PRESET_SLOTS,
  type EditorSave,
  type RulePreset,
  type RunResult,
  exportPresetCode,
  parsePresetCode,
} from './storage'

/** 지금 세션의 전부. */
export interface EditorSession {
  readonly history: EditHistory<RuleSet>
  readonly presets: readonly RulePreset[]
  readonly roomId: string
  readonly seed: number
  readonly lastResult: RunResult | undefined
}

/** 저장이 없을 때 세션을 세울 값. */
export interface SessionSeed {
  readonly ruleset: RuleSet
  readonly roomId: string
  readonly seed: number
}

/**
 * 저장에서 세션을 세운다. 저장이 없으면 기본값으로 시작한다.
 *
 * @param save 읽어 낸 저장. 없으면 undefined.
 * @param fallback 저장이 없을 때 쓸 값.
 * @returns 세션.
 */
export function createSession(save: EditorSave | undefined, fallback: SessionSeed): EditorSession {
  if (save === undefined) {
    return {
      history: createHistory(fallback.ruleset),
      presets: [],
      roomId: fallback.roomId,
      seed: fallback.seed,
      lastResult: undefined,
    }
  }
  return {
    history: createHistory(save.ruleset),
    presets: save.presets,
    roomId: save.roomId === '' ? fallback.roomId : save.roomId,
    seed: save.seed,
    lastResult: save.lastResult,
  }
}

/**
 * 지금 편집 중인 규칙표를 집는다.
 *
 * @param session 세션.
 * @returns 규칙표.
 */
export function getSessionRuleSet(session: EditorSession): RuleSet {
  return session.history.present
}

/**
 * 세션에서 저장할 것만 뽑는다.
 *
 * @param session 세션.
 * @returns 저장 내용.
 */
export function buildSessionSave(session: EditorSession): EditorSave {
  return {
    ruleset: getSessionRuleSet(session),
    presets: session.presets,
    roomId: session.roomId,
    seed: session.seed,
    lastResult: session.lastResult,
  }
}

/**
 * 규칙표 편집을 반영한다. 되돌리기 스택에 한 단계가 쌓인다.
 *
 * @param session 세션.
 * @param ruleset 편집 결과.
 * @returns 새 세션.
 */
export function applyRuleSetEdit(session: EditorSession, ruleset: RuleSet): EditorSession {
  return { ...session, history: applyChange(session.history, ruleset) }
}

/**
 * 한 단계 되돌린다.
 *
 * 되돌릴 것이 없으면 **같은 객체**를 돌려준다. 새 객체를 내면 화면이 다시 그려지고
 * 저장이 한 번 더 예약된다 — 아무 일도 일어나지 않은 입력에 대해서는 아무 일도 하지 않는
 * 편이 낫다.
 *
 * @param session 세션.
 * @returns 새 세션. 되돌릴 것이 없으면 그대로.
 */
export function applyUndoStep(session: EditorSession): EditorSession {
  const history = applyUndo(session.history)
  return history === session.history ? session : { ...session, history }
}

/**
 * 한 단계 다시 실행한다.
 *
 * @param session 세션.
 * @returns 새 세션. 갈 곳이 없으면 그대로.
 */
export function applyRedoStep(session: EditorSession): EditorSession {
  const history = applyRedo(session.history)
  return history === session.history ? session : { ...session, history }
}

/**
 * 방을 고른다.
 *
 * @param session 세션.
 * @param roomId 방 id.
 * @returns 새 세션.
 */
export function applyRoomChoice(session: EditorSession, roomId: string): EditorSession {
  return { ...session, roomId }
}

/**
 * 시드를 고른다.
 *
 * @param session 세션.
 * @param seed 시드.
 * @returns 새 세션.
 */
export function applySeedChoice(session: EditorSession, seed: number): EditorSession {
  return { ...session, seed }
}

/**
 * 직전 판의 결과를 남긴다.
 *
 * @param session 세션.
 * @param result 판 결과.
 * @returns 새 세션.
 */
export function applyRunResult(session: EditorSession, result: RunResult): EditorSession {
  return { ...session, lastResult: result }
}

/**
 * 지금 규칙표를 이름 붙여 슬롯에 넣는다. 같은 이름이 있으면 그 슬롯을 덮는다.
 *
 * 덮어쓰는 쪽을 고른 이유는 같은 이름이 둘인 라이브러리가 더 나쁘기 때문이다 — 어느 것을
 * 불러야 하는지 이름으로 가릴 수 없게 된다.
 *
 * @param session 세션.
 * @param name 슬롯 이름. 앞뒤 공백은 버린다.
 * @returns 새 세션. 이름이 비었거나 슬롯이 가득 차 있으면 그대로.
 */
export function applyPresetSave(session: EditorSession, name: string): EditorSession {
  const trimmed = name.trim()
  if (trimmed === '') {
    return session
  }
  const preset: RulePreset = { name: trimmed, ruleset: getSessionRuleSet(session) }
  const at = session.presets.findIndex((item) => item.name === trimmed)
  if (at >= 0) {
    return { ...session, presets: session.presets.map((item, index) => (index === at ? preset : item)) }
  }
  if (session.presets.length >= MAX_PRESET_SLOTS) {
    return session
  }
  return { ...session, presets: [...session.presets, preset] }
}

/**
 * 슬롯의 규칙표를 편집기로 불러온다. 편집 한 단계로 쌓이므로 되돌릴 수 있다.
 *
 * @param session 세션.
 * @param index 슬롯 자리.
 * @returns 새 세션. 빈 슬롯이면 그대로.
 */
export function applyPresetLoad(session: EditorSession, index: number): EditorSession {
  const preset = session.presets[index]
  return preset === undefined ? session : applyRuleSetEdit(session, preset.ruleset)
}

/**
 * 슬롯을 지운다.
 *
 * @param session 세션.
 * @param index 슬롯 자리.
 * @returns 새 세션.
 */
export function applyPresetRemove(session: EditorSession, index: number): EditorSession {
  return { ...session, presets: session.presets.filter((_unused, at) => at !== index) }
}

/**
 * 공유 코드를 읽어 라이브러리에 넣고 편집기로 불러온다.
 *
 * 라이브러리에도 넣는 이유는 받은 코드가 **이름을 달고 오기** 때문이다. 편집기에만 실으면
 * 그 이름이 다음 편집에서 사라지고, 남의 규칙표를 자기 것과 비교하려면 다시 받아야 한다.
 * 슬롯이 가득 차 있으면 편집기에만 싣는다 — 받은 코드를 열어 보는 일까지 막지는 않는다.
 *
 * @param session 세션.
 * @param code `v2:` 로 시작하는 공유 코드.
 * @returns 새 세션.
 * @throws 코드를 풀 수 없는 경우. 사유를 그대로 화면에 적는다.
 */
export function applyPresetImport(session: EditorSession, code: string): EditorSession {
  const preset = parsePresetCode(code)
  const stored = applyPresetSave({ ...session, history: createHistory(preset.ruleset) }, preset.name)
  return {
    ...session,
    presets: stored.presets,
    history: applyChange(session.history, preset.ruleset),
  }
}

/**
 * 튜토리얼 단계를 세션에 싣는다 (로드맵 W20).
 *
 * **방·시드·규칙표를 한꺼번에 바꾼다.** 셋 중 하나라도 남으면 단계가 의도한 판이 서지
 * 않고, 그러면 "시작 규칙표로는 진다" 는 대비가 성립하지 않는다.
 *
 * 실린 규칙표는 **틀린 것**이다. 실패한 판을 한 번 보고 나서 고치는 것이 이 게임의 학습
 * 방식이다 (P1 실패는 정보다).
 *
 * @param session 세션.
 * @param stage 열 단계.
 * @param rules 실을 규칙 목록. 시작 규칙표이거나 힌트로 여는 해답이다.
 * @returns 새 세션.
 */
export function applyTutorialStage(
  session: EditorSession,
  stage: TutorialStage,
  rules: readonly RawRule[],
): EditorSession {
  const ruleset = parseRuleSet({
    ruleset_id: stage.stageId,
    version: 1,
    rules: [...rules],
  })
  return {
    ...session,
    roomId: stage.roomId,
    seed: stage.seed,
    history: applyChange(session.history, ruleset),
  }
}

/**
 * 슬롯 하나를 공유 코드로 굽는다.
 *
 * @param session 세션.
 * @param index 슬롯 자리.
 * @returns `v2:` 공유 코드. 빈 슬롯이면 빈 문자열.
 */
export function exportSlotCode(session: EditorSession, index: number): string {
  const preset = session.presets[index]
  return preset === undefined ? '' : exportPresetCode(preset)
}

/**
 * 지금 규칙표를 공유 코드로 굽는다.
 *
 * @param session 세션.
 * @param name 코드에 실을 이름.
 * @returns `v2:` 공유 코드.
 */
export function exportSessionCode(session: EditorSession, name: string): string {
  return exportPresetCode({ name, ruleset: getSessionRuleSet(session) })
}

/**
 * 세션의 코드 라이브러리를 메타 세이브에 싣는다.
 *
 * **서버로 가는 것은 메타 세이브다.** `MetaSave.presets` 는 처음부터 있었지만 아무도
 * 채우지 않아 늘 빈 배열이었고, 그래서 슬롯에 저장한 규칙표가 계정을 따라오지 않았다 —
 * 기기를 바꾼 사람에게 그것은 "저장이 안 된다" 로 보인다.
 *
 * **편집 중인 규칙표도 싣는다.** 처음에는 "두 기기가 서로의 편집을 덮어쓴다" 를 걱정해
 * 안 올렸는데, 기기를 바꾸면 규칙이 통째로 사라진 것처럼 보였다 — **잃는 쪽이 훨씬
 * 나쁘다.** 받는 쪽에서 이 기기에 초안이 없을 때만 서버 것을 쓰므로, 덮어쓰기는 안
 * 일어난다 (`adoptServerMeta`).
 *
 * @param session 세션.
 * @param meta 지금 메타 세이브.
 * @returns 코드 라이브러리가 실린 메타 세이브.
 */
export function buildMetaFromSession(session: EditorSession, meta: MetaSave): MetaSave {
  return { ...meta, presets: session.presets, draft: getSessionRuleSet(session) }
}

/**
 * 세션을 메타 세이브에 반영하되, 바뀐 것이 없으면 **같은 객체**를 돌려준다.
 *
 * **바뀐 것을 슬롯으로만 재면 초안이 영영 안 올라간다.** 실제로 그랬다 — 올리는 쪽이
 * `presets` 만 보고 있어서, 규칙을 아무리 고쳐도 서버에는 아무것도 안 갔다. 기기를
 * 바꾸면 규칙이 사라진 것처럼 보인 진짜 이유가 이것이다.
 *
 * @param session 세션.
 * @param meta 지금 메타 세이브.
 * @returns 새 메타 세이브. 바뀐 것이 없으면 받은 것 그대로.
 */
export function applySessionToMeta(session: EditorSession, meta: MetaSave): MetaSave {
  const merged = buildMetaFromSession(session, meta)
  if (merged.presets === meta.presets && merged.draft === meta.draft) {
    return meta
  }
  return merged
}

/**
 * 서버에서 받은 코드 라이브러리를 세션에 싣는다.
 *
 * **이 기기에 슬롯이 하나라도 있으면 손대지 않는다.** 덮어쓰면 방금 만든 것이 사라지고,
 * 그 손실은 되돌릴 수 없다 — 비어 있을 때만 채우는 쪽이 잃는 것이 없다.
 *
 * @param session 세션.
 * @param presets 서버가 준 슬롯들.
 * @returns 새 세션. 채울 것이 없으면 같은 객체.
 */
export function adoptPresets(
  session: EditorSession,
  presets: readonly RulePreset[],
): EditorSession {
  if (session.presets.length > 0 || presets.length === 0) {
    return session
  }
  return { ...session, presets: presets.slice(0, MAX_PRESET_SLOTS) }
}

/**
 * 서버에서 받은 편집 중인 규칙표를 세션에 싣는다.
 *
 * **이 기기에 저장이 없을 때만 싣는다.** 새 기기가 정확히 그 경우이고, 그때 안 실으면
 * 규칙이 통째로 사라진 것처럼 보인다 — 실제로 그렇게 보고됐다.
 *
 * 저장이 있으면 손대지 않는다. 덮어쓰면 방금 한 편집이 사라지고 그 손실은 되돌릴 수 없다.
 *
 * @param session 세션.
 * @param draft 서버가 준 초안.
 * @param hasLocalSave 이 기기에 저장이 있었는가.
 * @returns 새 세션. 실을 것이 없으면 같은 객체.
 */
/**
 * 로그인한 계정의 것으로 세션을 갈아 끼운다.
 *
 * **로그인은 서버가 이긴다.** 이 기기에 있던 초안·슬롯은 다른 계정의 것이거나 옛 것이고,
 * 로그인은 "이 기기를 그 계정으로 만든다" 는 명시적 행동이다 — 여기서 로컬을 지키면
 * 모바일에서 짠 규칙이 컴퓨터에 안 보인다. 실제로 그렇게 보고됐다.
 *
 * 서버에 초안이 없으면 지금 것을 둔다. 새로 가입한 계정이 그 경우이고, 그때 비우면
 * 방금까지 짜던 것이 사라진다.
 *
 * @param session 세션.
 * @param meta 그 계정의 메타 세이브.
 * @returns 새 세션.
 */
export function adoptAccount(session: EditorSession, meta: MetaSave): EditorSession {
  return {
    ...session,
    presets: meta.presets.slice(0, MAX_PRESET_SLOTS),
    history: meta.draft === undefined ? session.history : createHistory(meta.draft),
  }
}

export function adoptDraft(
  session: EditorSession,
  draft: RuleSet | undefined,
  hasLocalSave: boolean,
): EditorSession {
  if (draft === undefined || hasLocalSave) {
    return session
  }
  return { ...session, history: createHistory(draft) }
}
