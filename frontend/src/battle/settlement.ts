/**
 * 층별 정산 — 무엇을 벌었는지 쌓아 둔다.
 *
 * **한 줄짜리 알림이 화면을 흔들었다.** 층을 깰 때마다 상단 바에 정산 문구가 나타났다
 * 사라졌고, 그 줄이 생길 때마다 아래 전부가 밀렸다 — 도면도 규칙표도 로그도. 정산은
 * 사라지는 알림이 아니라 **쌓이는 기록**이다. 로그와 같은 급의 탭으로 옮긴다.
 *
 * 서버가 만든 문자열을 화면이 다시 짜지 않는다. 무엇을 줬는지는 서버만 알고, 화면이
 * 짜 맞추면 실제로 들어온 것과 다른 말을 하게 된다. 여기서 하는 것은 **끊는 것**
 * 하나뿐이다 — 한 줄에 정보 하나여야 눈이 훑을 수 있다.
 */

/** 서버가 보상 항목을 잇는 글자. `apply_run_rewards` 가 이것으로 join 한다. */
const NOTE_SEPARATOR = '·'

/** 층 하나의 정산. */
export interface FloorSettlement {
  readonly floor: number
  /** 항목 하나가 한 줄. 서버 문구를 끊기만 한 것이다. */
  readonly lines: readonly string[]
}

/**
 * 서버가 준 보상 한 줄을 항목별로 끊는다.
 *
 * @param reward 서버가 확정한 보상 문자열.
 * @returns 항목들. 빈 항목은 버린다.
 */
export function splitRewardNotes(reward: string): readonly string[] {
  return reward
    .split(NOTE_SEPARATOR)
    .map((note) => note.trim())
    .filter((note) => note !== '')
}

/**
 * 정산 목록에 한 층을 더한다.
 *
 * **같은 층은 덮어쓴다.** 판을 다시 돌리면 그 층이 다시 정산되는데, 두 번 쌓이면
 * 같은 벌이를 두 번 번 것처럼 읽힌다.
 *
 * @param list 지금까지의 정산.
 * @param floor 방금 정산한 층.
 * @param reward 서버가 확정한 보상 문자열.
 * @returns 새 목록. 적을 것이 없으면 원래 목록 그대로다.
 */
export function appendSettlement(
  list: readonly FloorSettlement[],
  floor: number,
  reward: string,
): readonly FloorSettlement[] {
  const lines = splitRewardNotes(reward)
  if (floor <= 0 || lines.length === 0) {
    return list
  }
  const kept = list.filter((item) => item.floor !== floor)
  // 층 오름차순으로 둔다. 하강한 순서와 같아서 위에서 아래로 읽으면 그대로 이야기가 된다.
  return [...kept, { floor, lines }].sort((left, right) => left.floor - right.floor)
}

/**
 * 정산 탭에 적을 카운트.
 *
 * @param list 정산 목록.
 * @returns `3층` 꼴. 정산한 층이 없으면 빈 문자열.
 */
export function formatSettlementTabCount(list: readonly FloorSettlement[]): string {
  return list.length === 0 ? '' : `${String(list.length)}층`
}
