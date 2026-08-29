/**
 * 이벤트 로그 — `game/app/core/event_log.py` 의 이식 (TDD §2).
 *
 * 코어가 발행하고 UI 가 구독만 하는 단방향 스트림이다. 레코드의 필드는 디자인 시스템의
 * LogRow 계약에서 왔다 — `tick·rule·expr·outcome·delta·fired`.
 *
 * `expr` 이 조건문 문자열인 것이 핵심이다. GDD §8.2 는 매 틱 **평가된 조건의 실제 값**을
 * 노출하라고 요구한다. 참/거짓만 남기면 죽고 나서 어느 규칙이 왜 틀렸는지 특정할 수 없다.
 *
 * `formatLines` 는 파이썬의 f-string 서식을 글자 단위로 재현한다. 골든 대조가 이 문자열을
 * 그대로 비교하므로 자릿수 채움 하나가 달라도 게이트 G3 가 깨진다.
 */

/** 틱 번호를 0 으로 채울 자릿수. 파이썬 `{tick:03d}` 와 같다. */
const TICK_PAD_WIDTH = 3

/** 엔티티 id 를 왼쪽 정렬로 채울 폭. 파이썬 `{entity_id:<18s}` 와 같다. */
const ENTITY_PAD_WIDTH = 18

/** 규칙 번호가 없을 때 자리를 지키는 공백. 파이썬의 `"   "` 와 같은 길이다. */
const EMPTY_SLOT = '   '

/** 로그 한 줄. UI 의 LogRow 하나에 대응한다. */
export interface LogEntry {
  readonly tick: number
  readonly entityId: string
  readonly phase: string
  readonly expr: string
  readonly outcome: string
  /** 이 이벤트를 일으킨 규칙의 우선순위. 규칙이 없는 지형 피해 등은 null. */
  readonly rule: number | null
  /** 수치 변화. 없으면 null — 0 과 구분한다. */
  readonly delta: number | null
  readonly fired: boolean
  /**
   * 피해를 **받은** 쪽. entityId 는 행위자라 지형 피해가 아닌 한 둘이 다르다. 피해
   * 히트맵(GDD §8.3)이 "어느 칸에서 맞았는가" 를 세려면 피격자를 알아야 하는데,
   * outcome 문자열에서 되뽑으면 표시 문구를 고칠 때마다 집계가 조용히 틀린다.
   */
  readonly targetId: string | null
}

/** LogEntry 를 만들 때 기본값을 채워 주는 입력. 파이썬 dataclass 의 기본 인자에 대응한다. */
export interface LogEntryInput {
  readonly tick: number
  readonly entityId: string
  readonly phase: string
  readonly expr: string
  readonly outcome: string
  readonly rule?: number | null
  readonly delta?: number | null
  readonly fired?: boolean
  readonly targetId?: string | null
}

/**
 * 기본값을 채워 로그 레코드를 만든다.
 *
 * @param input 채워 넣을 값들. 생략한 항목은 파이썬 dataclass 의 기본값과 같다.
 * @returns 완성된 레코드.
 */
export function createLogEntry(input: LogEntryInput): LogEntry {
  return {
    tick: input.tick,
    entityId: input.entityId,
    phase: input.phase,
    expr: input.expr,
    outcome: input.outcome,
    rule: input.rule ?? null,
    delta: input.delta ?? null,
    fired: input.fired ?? false,
    targetId: input.targetId ?? null,
  }
}

/**
 * 부호를 반드시 붙여 정수를 적는다. 파이썬 `f"{value:+d}"` 와 같다.
 *
 * @param value 적을 정수.
 * @returns `+3` 이나 `-3` 형태의 문자열.
 */
export function formatSigned(value: number): string {
  return value < 0 ? String(value) : `+${value}`
}

/** 틱 진행 중 쌓이는 이벤트. 코어만 쓰고 UI 는 읽기만 한다. */
export class EventLog {
  readonly entries: LogEntry[] = []

  /**
   * 이벤트 한 건을 남긴다.
   *
   * @param entry 남길 레코드.
   */
  record(entry: LogEntry): void {
    this.entries.push(entry)
  }

  /**
   * 쌓인 이벤트 수.
   *
   * @returns 레코드 수.
   */
  count(): number {
    return this.entries.length
  }

  /**
   * 한 틱의 이벤트만 골라낸다.
   *
   * @param tick 고를 틱 번호.
   * @returns 그 틱에 남은 레코드들. 남긴 순서를 유지한다.
   */
  filterByTick(tick: number): readonly LogEntry[] {
    return this.entries.filter((entry) => entry.tick === tick)
  }

  /**
   * 터미널 출력용 문자열로 편다. 파이썬 `format_lines` 와 글자까지 같아야 한다.
   *
   * @returns `"T027 | player             [3] 조건 → 결과"` 형식의 줄들.
   */
  formatLines(): readonly string[] {
    return this.entries.map((entry) => {
      const slot = entry.rule === null ? EMPTY_SLOT : `[${entry.rule}]`
      const delta = entry.delta === null ? '' : ` (${formatSigned(entry.delta)})`
      const tick = String(entry.tick).padStart(TICK_PAD_WIDTH, '0')
      const actor = entry.entityId.padEnd(ENTITY_PAD_WIDTH, ' ')
      return `T${tick} | ${actor} ${slot} ${entry.expr} → ${entry.outcome}${delta}`
    })
  }
}
