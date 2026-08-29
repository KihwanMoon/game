/**
 * 판정 문구 — 전투 화면과 사후 분석이 **같은 말**을 쓰게 하는 한 곳.
 *
 * 전에는 `BattleView` 와 `hud/analysisText` 에 라벨표가 두 벌 있었고, 같은
 * `PLAYER_LOSS` 를 한쪽은 `패배`, 다른 쪽은 `사망` 이라 적었다. 사후 분석은 전투 화면을
 * **덮으며** 뜨므로 한 화면에 두 단어가 동시에 보였다 — 플레이어가 자기 규칙이 아니라
 * 화면의 말을 의심하게 되는 종류의 결함이다.
 *
 * 고른 말은 `쓰러짐` 이다. 모바일 명세의 판정 표시(`✕ 쓰러짐 · 규칙을 고쳐 다시`)가
 * 디자인 정본이고, 그 문구가 P1(실패는 정보다)에 맞기 때문이다 — `패배`·`사망` 은 판이
 * 끝났다는 통보에서 멈추지만 `쓰러짐 · 규칙을 고쳐 다시` 는 다음에 할 일을 가리킨다.
 *
 * 이 파일이 `battle/` 에 있는 이유는 의존 방향 때문이다. `hud/` 는 이미 `battle/` 을
 * 가져다 쓰므로(PostMortem 이 PlanCanvas 를 그린다) 반대 방향으로 두면 순환이 된다.
 * 코어(`core/sim/phases.ts`)는 파이썬 정본의 이식이라 화면 문구가 들어갈 자리가 아니다.
 */
import {
  OUTCOME_ONGOING,
  OUTCOME_PLAYER_LOSS,
  OUTCOME_PLAYER_WIN,
  OUTCOME_TIMEOUT,
} from '../core/sim/phases'

/** 판정 표기. 코어의 OUTCOME_* 를 화면 문구로 바꾼다. */
export const OUTCOME_LABELS: ReadonlyMap<string, string> = new Map([
  [OUTCOME_ONGOING, '진행 중'],
  [OUTCOME_PLAYER_WIN, '승리'],
  [OUTCOME_PLAYER_LOSS, '쓰러짐'],
  [OUTCOME_TIMEOUT, '시간 초과'],
])

/**
 * 판정 글리프. 색이 정보의 유일한 채널이 될 수 없으므로 문구 앞에 도형을 붙인다.
 * 전부 유니코드 도형이며 이모지가 아니다.
 */
export const OUTCOME_GLYPHS: ReadonlyMap<string, string> = new Map([
  [OUTCOME_ONGOING, '◆'],
  [OUTCOME_PLAYER_WIN, '✓'],
  [OUTCOME_PLAYER_LOSS, '✕'],
  [OUTCOME_TIMEOUT, '◈'],
])

/**
 * 판정 한 줄 — 글리프와 함께, 다음에 할 일까지 적는다. 모바일 상태줄이 쓰는 형태다.
 * 데스크톱은 자리가 좁지 않으므로 같은 문구를 그대로 쓸 수 있다.
 */
export const OUTCOME_NOTICES: ReadonlyMap<string, string> = new Map([
  [OUTCOME_ONGOING, '전투 중'],
  [OUTCOME_PLAYER_WIN, '방 클리어 · 다음 실로'],
  [OUTCOME_PLAYER_LOSS, '쓰러짐 · 규칙을 고쳐 다시'],
  [OUTCOME_TIMEOUT, '추격자 도착'],
])

/** 판정 한 줄의 색 계열. 토큰의 상태색과 짝이 맞는다 — dim·참·위험 셋뿐이다. */
export type OutcomeTone = 'dim' | 'true' | 'danger'

/**
 * 판정별 색 계열 (모바일 원본 D 의 판정 표시).
 *
 * `◆ 전투 중` 은 아직 아무 일도 없었다는 뜻이라 보조 명도로 두고, 방을 깼으면 녹청,
 * 쓰러졌거나 추격자가 도착했으면 위험색이다. 색은 언제나 세 번째 채널이다 — 글리프와
 * 문구가 먼저 말하고 색이 거든다.
 */
export const OUTCOME_TONES: ReadonlyMap<string, OutcomeTone> = new Map([
  [OUTCOME_ONGOING, 'dim'],
  [OUTCOME_PLAYER_WIN, 'true'],
  [OUTCOME_PLAYER_LOSS, 'danger'],
  [OUTCOME_TIMEOUT, 'danger'],
])

/**
 * 판정 한 줄의 색 계열.
 *
 * @param outcome 코어가 낸 OUTCOME_* 값.
 * @returns 색 계열. 모르는 값이면 보조 명도로 둔다 — 모르는 것을 위험색으로 칠하지 않는다.
 */
export function resolveOutcomeTone(outcome: string): OutcomeTone {
  return OUTCOME_TONES.get(outcome) ?? 'dim'
}

/**
 * 판정 문구.
 *
 * @param outcome 코어가 낸 OUTCOME_* 값.
 * @returns 화면에 적을 문구. 모르는 값이면 원문 그대로.
 */
export function formatOutcome(outcome: string): string {
  return OUTCOME_LABELS.get(outcome) ?? outcome
}

/**
 * 판정 한 줄 (`✕ 쓰러짐 · 규칙을 고쳐 다시`).
 *
 * @param outcome 코어가 낸 OUTCOME_* 값.
 * @returns 글리프와 문구. 모르는 값이면 판정 문구만 낸다.
 */
export function formatOutcomeNotice(outcome: string): string {
  const notice = OUTCOME_NOTICES.get(outcome)
  const glyph = OUTCOME_GLYPHS.get(outcome)
  if (notice === undefined || glyph === undefined) {
    return formatOutcome(outcome)
  }
  return `${glyph} ${notice}`
}
