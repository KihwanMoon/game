/**
 * 정비 규칙의 어휘·조립·검증 (설계/4_아이템 §5).
 *
 * **전투 규칙표의 형제이지 그 일부가 아니다.** 전투 규칙은 결정론 코어 안에서 돌고 두
 * 코어가 재현해야 하지만(R5·G3), 정비는 계정 상태를 만지는 서버의 일이다. 그래서 블록도
 * CPU 도 없다 — 대신 **조립의 규약은 같다**: 행 순서가 실행 순서이고, 위에서 아래로 돈다.
 *
 * 어휘는 닫혀 있다. 행동 일곱, 인자는 그 행동이 정한 목록 안에서만. 자유 조건식은 전투
 * DSL 의 자리다.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 문장과 검증을 볼 수 있어야 한다 — 저장 층
 * (`game/app/store/maintenance.py`) 의 `check_rows` 와 **같은 규칙을 본다.** 화면이
 * 통과시킨 것을 서버가 422 로 거절하면, 사람은 무엇이 틀렸는지 모른 채 저장을 잃는다.
 */
import type { MaintenanceRowView } from '../storage'

/** 행 수 상한. 서버 `MAX_ROWS` 와 같은 값이다 — 다르면 화면이 통과시킨 것을 서버가 막는다. */
export const MAX_MAINTENANCE_ROWS = 10

/** 버리기가 받는 등급. 유물은 없다 — 최상급을 자동으로 버리는 규칙은 오조작이 사고가 된다. */
export const DISCARD_ALL = 'ALL'

export const DISCARD_GRADES: readonly (readonly [string, string])[] = [
  ['COMMON', '보통'],
  ['FINE', '상급'],
  // **등급이 아니라 「등급을 안 본다」다.** 유물도 되찾은 것도 함께 버린다 — 등급으로
  // 버리면 되찾은 것이 남는데, 죽고 되찾기를 되풀이하면 가방 전체에 그 표시가 붙어
  // 가방이 영영 안 비워졌다. 고르는 것 자체가 그 보호를 내려놓겠다는 선언이다.
  [DISCARD_ALL, '전부'],
]

/** 인자 하나의 선택지. 값은 서버 어휘, 이름은 화면의 것이다. */
export type ArgChoice = readonly [string, string]

/** 정비 행동 하나의 뜻. */
export interface MaintenanceAction {
  readonly id: string
  /** 팔레트 버튼에 적을 짧은 이름. */
  readonly label: string
  /**
   * 이 행동이 받는 인자들. 비어 있으면 인자를 안 받는다.
   *
   * **표 하나로 둔다.** 서버의 `ACTION_ARGUMENTS` 와 짝이다 — 검증·화면·문장이 각자
   * 목록을 들면 셋이 갈린다.
   */
  readonly args: readonly ArgChoice[]
  /** 인자를 고르는 칸에 붙일 이름. 인자가 없으면 빈 문자열. */
  readonly argLabel: string
  /** 무엇을 하는가 한 줄. 팔레트가 버튼 아래에 적는다. */
  readonly note: string
  /** 돈이 나가는가(-1) 드는가(+1) 그대로인가(0). 검증의 순서 힌트가 이것을 본다. */
  readonly money: -1 | 0 | 1
}

/** 장비 교체가 받는 우선순위. 서버 `GEAR_PRIORITY_CHOICES` 와 같은 값이다. */
export const GEAR_PRIORITIES: readonly ArgChoice[] = [
  ['ATTACK', '공격'],
  ['DEFENSE', '방어'],
]

/**
 * 정비가 아는 행동들. **닫힌 목록이다** — 모르는 행동이 조용히 무시되면, 켰다고 믿은
 * 정비가 안 돈다. 서버 `MAINTENANCE_ACTIONS` 와 같은 순서·같은 id 다.
 */
export const MAINTENANCE_ACTIONS: readonly MaintenanceAction[] = [
  {
    id: 'DISCARD',
    label: '버리기',
    args: DISCARD_GRADES,
    argLabel: '버릴 등급',
    note: '이 등급의 가방 장비를 버린다 (되찾은 것은 남긴다)',
    money: 0,
  },
  {
    id: 'REPAIR',
    label: '복구',
    args: [],
    argLabel: '',
    note: '파손된 착용 장비를 잔액 안에서 복구한다',
    money: -1,
  },
  {
    id: 'REFILL',
    label: '보충',
    args: [],
    argLabel: '',
    note: '끼운 소모품을 잔액 안에서 보충한다',
    money: -1,
  },
  {
    id: 'SELL_STOCK',
    label: '재고 팔기',
    args: [],
    argLabel: '',
    note: '가방의 소모품 재고를 전부 판다',
    money: 1,
  },
  {
    id: 'UNSEAL',
    label: '봉인 해제',
    args: [],
    argLabel: '',
    // **착용과 가방을 함께 본다.** 착용만 열면 가방에서 굴러 나온 유물이 영원히 안
    // 열린다 — 열어 봐야 갈아 낄 만한 물건인지 알 수 있다.
    note: '가진 장비의 봉인을 잔액 안에서 연다 (싼 칸부터)',
    money: -1,
  },
  {
    id: 'UPGRADE_GEAR',
    label: '장비 교체',
    args: GEAR_PRIORITIES,
    argLabel: '우선순위',
    note: '이 우선순위로 가방에 더 나은 것이 있으면 갈아 낀다',
    money: 0,
  },
  {
    id: 'UPGRADE_CONSUMABLE',
    label: '소모품 교체',
    args: [],
    argLabel: '',
    // 가득 찬 칸만 바꾼다 — 쓰던 칸을 갈면 남은 충전이 사라진다.
    note: '가득 찬 소모품 칸을 가방의 더 나은 것으로 갈아 낀다',
    money: 0,
  },
]

/**
 * 행동 하나를 찾는다.
 *
 * @param action 행동 id.
 * @returns 그 행동. 어휘 밖이면 undefined.
 */
export function findAction(action: string): MaintenanceAction | undefined {
  return MAINTENANCE_ACTIONS.find((entry) => entry.id === action)
}

/**
 * 인자의 한글 이름.
 *
 * @param action 그 인자를 받는 행동. 목록이 행동마다 다르다.
 * @param value 인자 값.
 * @returns 한글 이름. 모르면 받은 것을 그대로 — 영어 키라도 빈 칸보다 낫다.
 */
export function formatArgName(action: MaintenanceAction | undefined, value: string): string {
  return action?.args.find(([one]) => one === value)?.[1] ?? value
}

/**
 * 등급의 한글 이름. 버리기 행이 쓴다.
 *
 * @param grade 등급 id.
 * @returns 한글 이름.
 */
export function formatGradeName(grade: string): string {
  return DISCARD_GRADES.find(([value]) => value === grade)?.[1] ?? grade
}

/**
 * 행 하나를 사람이 읽는 문장으로 만든다.
 *
 * **문장이다.** 예전에는 이 자리가 드롭다운 둘이었고, 그래서 목록을 훑을 때 「무엇이
 * 언제 도는가」가 보이지 않았다 — 전투 규칙이 조건문을 문장으로 적는 것과 같은 이유다
 * (`ruleSentence`).
 *
 * @param row 볼 행.
 * @returns 한 문장. 어휘 밖이면 그 사실을 적는다 — 조용히 빈 줄로 두면 안 돈다는 것이
 *     화면 어디에도 안 남는다.
 */
export function formatMaintenanceSentence(row: MaintenanceRowView): string {
  const action = findAction(row.action)
  if (action === undefined) {
    return `모르는 행동이다: ${row.action || '(빈 값)'}`
  }
  if (action.args.length === 0) {
    return action.note
  }
  return `${formatArgName(action, row.grade)} ${action.note}`
}

/**
 * 행 하나를 바꾼 목록을 만든다.
 *
 * @param rows 지금 행들.
 * @param index 바꿀 자리.
 * @param row 새 행. undefined 면 지운다.
 * @returns 새 목록.
 */
export function replaceRow(
  rows: readonly MaintenanceRowView[],
  index: number,
  row: MaintenanceRowView | undefined,
): readonly MaintenanceRowView[] {
  const next = [...rows]
  if (row === undefined) {
    next.splice(index, 1)
  } else {
    next[index] = row
  }
  return next
}

/**
 * 행을 한 칸 옮긴 목록을 만든다. 순서가 실행 순서라 오르내리기가 조립의 반이다.
 *
 * **위로만 옮기던 것을 양쪽으로 열었다.** 아래로 못 내리면 세 번째 행을 맨 아래로
 * 보내려고 아래 둘을 각각 위로 올려야 했다 — 전투 규칙은 처음부터 양쪽이었다.
 *
 * @param rows 지금 행들.
 * @param from 옮길 자리.
 * @param to 옮겨 갈 자리. 범위 밖이면 그대로 둔다.
 * @returns 새 목록.
 */
export function moveRow(
  rows: readonly MaintenanceRowView[],
  from: number,
  to: number,
): readonly MaintenanceRowView[] {
  if (from < 0 || from >= rows.length || to < 0 || to >= rows.length || from === to) {
    return rows
  }
  const next = [...rows]
  const [row] = next.splice(from, 1)
  if (row !== undefined) {
    next.splice(to, 0, row)
  }
  return next
}

/**
 * 행 하나를 그 아래에 복제한 목록을 만든다.
 *
 * 전투 규칙의 복제(Alt+D)와 같은 자리다 — 「같은 것을 등급만 바꿔 하나 더」가 정비에서
 * 가장 흔한 편집이다 (보통 버리고, 상급도 버리고).
 *
 * @param rows 지금 행들.
 * @param index 복제할 자리.
 * @returns 새 목록. 범위 밖이면 그대로.
 */
export function duplicateRow(
  rows: readonly MaintenanceRowView[],
  index: number,
): readonly MaintenanceRowView[] {
  const row = rows[index]
  if (row === undefined) {
    return rows
  }
  const next = [...rows]
  next.splice(index + 1, 0, { ...row })
  return next
}

/**
 * 행동 하나를 새 행으로 만든다.
 *
 * @param action 행동 id.
 * @returns 새 행. 인자를 받는 행동이면 첫 등급으로 채운다 — 빈 인자는 서버가 거절한다.
 */
export function createRow(action: string): MaintenanceRowView {
  const found = findAction(action)
  return { action, grade: found?.args[0]?.[0] ?? '' }
}

/** 검증 한 줄. 막는 것과 일러 주는 것을 가른다. */
export interface MaintenanceProblem {
  /** 몇 번째 행의 일인가. 규칙표 전체의 일이면 -1. */
  readonly index: number
  /**
   * 저장이 막히는가.
   *
   * **막는 것과 일러 주는 것을 섞지 않는다.** 섞으면 「고쳐야 저장된다」와 「이래도
   * 저장은 된다」가 같아 보이고, 그러면 둘 다 무시된다.
   */
  readonly isBlocking: boolean
  readonly text: string
}

/**
 * 행 목록을 검증한다.
 *
 * **서버가 막는 것을 먼저 본다** (`check_rows`) — 화면이 통과시킨 것을 서버가 422 로
 * 거절하면 사람은 무엇이 틀렸는지 모른 채 저장을 잃는다.
 *
 * 그 위에 **화면만 아는 것**을 얹는다. 서버는 「돌긴 도는데 하는 일이 없는」 배치를 막지
 * 않는다 — 막으면 안 된다. 하지만 그것이 사람이 의도한 것인지는 물어봐 줄 수 있다.
 *
 * @param rows 검사할 행들.
 * @returns 문제들. 없으면 빈 배열.
 */
export function checkMaintenanceRows(
  rows: readonly MaintenanceRowView[],
): readonly MaintenanceProblem[] {
  const problems: MaintenanceProblem[] = []
  if (rows.length > MAX_MAINTENANCE_ROWS) {
    problems.push({
      index: -1,
      isBlocking: true,
      text: `행이 ${String(MAX_MAINTENANCE_ROWS)}개를 넘는다 — 서버가 저장을 거절한다`,
    })
  }
  const seen = new Set<string>()
  rows.forEach((row, index) => {
    const action = findAction(row.action)
    if (action === undefined) {
      problems.push({ index, isBlocking: true, text: `모르는 행동이다: ${row.action}` })
      return
    }
    if (action.args.length > 0 && !action.args.some(([value]) => value === row.grade)) {
      problems.push({
        index,
        isBlocking: true,
        text: `${action.label} 이 받을 수 없는 인자다: ${row.grade || '(빈 값)'}`,
      })
    }
    if (action.args.length === 0 && row.grade !== '') {
      problems.push({ index, isBlocking: true, text: `${action.label} 은 인자를 받지 않는다` })
    }
    // **같은 행이 두 번 있으면 뒤엣것은 할 일이 없다.** 앞의 행이 이미 다 했기 때문이다 —
    // 막지는 않는다. 사람이 알고 두는 경우(사이에 돈 버는 행을 끼워 두 번 시도)가 있다.
    const key = `${row.action}:${row.grade}`
    if (seen.has(key)) {
      problems.push({
        index,
        isBlocking: false,
        text: '위에 같은 행이 있다 — 앞의 것이 이미 다 하고 나면 이 행은 할 일이 없다',
      })
    }
    seen.add(key)
  })
  // **돈을 쓰는 행이 버는 행보다 앞이면 잔액이 모자랄 수 있다.** 복구·보충은 잔액 안에서만
  // 도는데(`maintenance_service`), 팔기를 뒤에 두면 그 돈을 못 쓴다.
  // **「전부 버리기」가 장비 교체보다 위면 고를 것을 먼저 없앤다.** 「남은 것은 잉여다」는
  // 위에서 최선을 끼운 뒤에만 참인 말이라, 순서가 뒤집히면 그 판에 주운 것이 통째로
  // 사라진다. 막지는 않는다 — 가방을 비우는 것이 목적인 배치도 있다.
  const dropAllAt = rows.findIndex(
    (row) => row.action === 'DISCARD' && row.grade === DISCARD_ALL,
  )
  const upgradeAt = rows.findIndex(
    (row) => row.action === 'UPGRADE_GEAR' || row.action === 'UPGRADE_CONSUMABLE',
  )
  if (dropAllAt >= 0 && upgradeAt >= 0 && dropAllAt < upgradeAt) {
    problems.push({
      index: dropAllAt,
      isBlocking: false,
      text: '전부 버리기가 교체보다 위에 있다 — 갈아 낄 후보를 먼저 버린다',
    })
  }
  const earnAt = rows.findIndex((row) => findAction(row.action)?.money === 1)
  const spendAt = rows.findIndex((row) => findAction(row.action)?.money === -1)
  if (earnAt >= 0 && spendAt >= 0 && spendAt < earnAt) {
    problems.push({
      index: earnAt,
      isBlocking: false,
      text: '파는 행이 쓰는 행보다 아래에 있다 — 판 돈은 이번 정비에서 못 쓴다',
    })
  }
  return problems
}

/**
 * 막는 문제가 있는가.
 *
 * @param problems 검증 결과.
 * @returns 하나라도 막으면 참.
 */
export function checkBlocked(problems: readonly MaintenanceProblem[]): boolean {
  return problems.some((problem) => problem.isBlocking)
}
