/**
 * 런 티켓과 제출 계약 — `game/schemas/run_ticket.py` 의 이식이다.
 *
 * **시드는 런의 출처이지 플레이어의 선택이 아니다.** 클라이언트가 시드를 정하면 유리한
 * 시드가 나올 때까지 돌려 보고 그것만 제출할 수 있다. 지금 이음매를 만들어 두면 서버가
 * 붙을 때 발급처만 바뀌고, 나중에 고치면 그때까지의 기록이 전부 무효가 된다.
 *
 * 이 파일에서 가장 중요한 것은 `RunSubmission` 에 **없는 것**이다 — 결과·시드·스냅샷·
 * 아이템을 받을 자리가 없다. 자리가 생기는 순간 언젠가 그 값을 믿는 코드가 따라 들어온다.
 * 자세한 이유는 `docs/설계/7_변조방지` §4.
 */
import type { RuleSet } from './ruleset'

/** 엔진 로직 세대. 파이썬 `ENGINE_VERSION` 과 같은 값이어야 한다. */
export const ENGINE_VERSION = 1

/**
 * 시드 상한. `Number.MAX_SAFE_INTEGER` 이며, 이것은 밸런스가 아니라 **이식 제약**이다.
 *
 * 이 코어는 시드를 `number` 로 들고 다니다 RNG 진입점에서 `BigInt` 로 바꾼다. `number`
 * 는 53비트라 그 위의 값은 가장 가까운 짝수로 반올림되고, 같은 시드를 적어도 파이썬과
 * 다른 난수를 낸다 — 골든이 작은 시드만 쓰므로 G3 도 못 보는 구간이다.
 *
 * 서버가 이 상한을 넘는 시드를 발급하면 그 순간 클라이언트가 다른 판을 돈다. 64비트
 * 시드를 쓰려면 여기 `seed` 를 `bigint` 로 올리는 것이 선행이다.
 */
export const MAX_SEED = Number.MAX_SAFE_INTEGER

/** 로컬 티켓의 id 접두어. 서버가 발급한 것과 눈으로 구분되어야 한다. */
export const LOCAL_TICKET_PREFIX = 'local'

/** 런의 성격. 무엇을 신뢰할 수 있는지가 여기서 갈린다. */
export type RunMode = 'PRACTICE' | 'RANKED' | 'DAILY'

/** 서버가 발급해야만 성립하는 모드. 로컬 발급으로 만들 수 없다. */
export const SERVER_ONLY_MODES: readonly RunMode[] = ['RANKED', 'DAILY']

/**
 * 런 하나를 시작할 권한. 런의 입력 전부가 여기 얼려 있다.
 *
 * 지속 몬스터가 들어오면 `monsterSnapshot` 이 여기 붙는다. 그때도 등식은 유지된다 —
 * 스냅샷이 입력의 일부가 될 뿐이다.
 */
export interface RunTicket {
  readonly ticketId: string
  readonly seed: number
  readonly roomId: string
  readonly floor: number
  readonly mode: RunMode
  readonly coreVersion: string
}

/** 제출. 클라이언트가 서버에 보내는 것 전부다. */
export interface RunSubmission {
  readonly ticketId: string
  readonly ruleset: RuleSet
  readonly coreVersion: string
}

/**
 * 이 티켓의 결과가 순위에 반영되는가.
 *
 * @param ticket 볼 티켓.
 * @returns 순위 대상이면 true.
 */
export function checkRanked(ticket: RunTicket): boolean {
  return SERVER_ONLY_MODES.includes(ticket.mode)
}

/**
 * 런 결과를 바꿀 수 있는 자산들의 세대.
 *
 * **숫자 여섯 개를 위치 인자로 받지 않는다.** 전부 number 라 두 개를 바꿔 넣어도 타입이
 * 못 막는다. 이름을 붙이면 그 사고가 컴파일 전에 걸린다 — 파이썬 쪽과 같은 이유다.
 */
export interface ContentVersions {
  readonly blocks: number
  readonly balance: number
  readonly items: number
  readonly skills: number
  readonly rooms: number
  readonly enemies: number
}

/**
 * 코어 버전 문자열을 만든다.
 *
 * **파이썬 `build_core_version` 과 글자 하나까지 같아야 한다.** 갈리면 서버가 티켓을
 * 못 알아본다.
 *
 * 여섯 자산을 전부 넣는다. 예전에는 블록과 밸런스 둘만 봉인했는데, 스킬 계수나 방
 * 배치를 고치면 과거 리플레이가 달라지는데도 시즌이 안 갈렸다.
 *
 * 팩 세대가 축 하나를 더 갖는다. 발행으로 콘텐츠가 바뀌면 파일 세대는 그대로인데 실제로
 * 도는 데이터가 달라지므로, 그 사실이 문자열에 남아야 한다.
 *
 * @param versions 자산별 세대.
 * @param pack 발행 세대. 발행한 적이 없으면 0.
 * @returns `b6.v2.i1.s2.r1.a1.p0.e1` 형태의 문자열.
 */
export function buildCoreVersion(versions: ContentVersions, pack = 0): string {
  return (
    `b${String(versions.blocks)}.v${String(versions.balance)}.i${String(versions.items)}` +
    `.s${String(versions.skills)}.r${String(versions.rooms)}.a${String(versions.enemies)}` +
    `.p${String(pack)}.e${String(ENGINE_VERSION)}`
  )
}

/**
 * 로컬에서 연습용 티켓을 만든다.
 *
 * **연습 모드만 만들 수 있다.** 순위·데일리는 서버가 발급해야 성립하며, 로컬이 그것을
 * 만들 수 있으면 시드 서버 발급이 아무것도 막지 못한다.
 *
 * 티켓 id 는 입력에서 그대로 파생한다. 시간이나 난수를 쓰면 같은 시드가 같은 티켓을
 * 내지 않아 리플레이가 깨진다 (R5).
 *
 * @param seed 이 런의 시드.
 * @param roomId 방 id.
 * @param coreVersion 코어 버전 문자열.
 * @param floor 층.
 * @param mode 런 모드. 연습이 아니면 거부한다.
 * @returns 만들어진 티켓.
 * @throws 서버 발급이 필요한 모드를 로컬로 만들려는 경우이거나, 시드가 이식 가능한
 *   범위를 벗어난 경우.
 */
export function createLocalTicket(
  seed: number,
  roomId: string,
  coreVersion: string,
  floor = 1,
  mode: RunMode = 'PRACTICE',
): RunTicket {
  if (!Number.isInteger(seed) || seed < 0 || seed > MAX_SEED) {
    throw new Error(`시드가 이식 범위를 벗어났다: ${String(seed)} (상한 ${String(MAX_SEED)})`)
  }
  if (SERVER_ONLY_MODES.includes(mode)) {
    throw new Error(`${mode} 티켓은 서버가 발급해야 한다 — 로컬 발급은 순위를 거짓으로 만든다`)
  }
  return {
    ticketId: `${LOCAL_TICKET_PREFIX}:${mode}:${roomId}:${String(floor)}:${String(seed)}`,
    seed,
    roomId,
    floor,
    mode,
    coreVersion,
  }
}

/**
 * 제출을 만든다. 티켓이 시드와 방을 이미 들고 있으므로 다시 넣지 않는다.
 *
 * @param ticket 이 런의 티켓.
 * @param ruleset 이 런에 쓴 규칙표.
 * @returns 만들어진 제출.
 */
export function buildSubmission(ticket: RunTicket, ruleset: RuleSet): RunSubmission {
  return { ticketId: ticket.ticketId, ruleset, coreVersion: ticket.coreVersion }
}

/**
 * 제출이 실제로 담는 열쇠 이름.
 *
 * 검사가 이 목록을 본다. 결과·시드·스냅샷이 늘어나면 그 자리에서 붉어진다.
 *
 * @param submission 볼 제출.
 * @returns 정렬된 열쇠 이름.
 */
export function listSubmissionKeys(submission: RunSubmission): readonly string[] {
  return Object.keys(submission).sort()
}
