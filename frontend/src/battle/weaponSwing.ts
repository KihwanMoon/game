/**
 * 무기 꼴과 휘두르는 모션 — 순수 기하 (설계/10_외형과_모션).
 *
 * **자유도가 사는 자리다.** 꼴(칼·굽은칼·도끼)과 모션(내려베기·횡베기·찌르기)을 갈라
 * 두었으므로, 자산 3+3 으로 조합 9 가 나온다 (계약 C7). 무기에 모션을 박으면 새 무기마다
 * 모션을 그려야 한다.
 *
 * **말은 안 움직인다.** 여기서 만드는 것은 **때린 자리에 지나가는 자국**이고, 말의 좌표는
 * 그대로다 — 도면이 흔들리면 눈이 좌표를 다시 잡아야 하고, 관전자가 읽어야 하는 것은
 * 궤적이 아니라 어느 틱에 어느 칸이다 (`planRenderer` 머리말).
 *
 * **무작위가 없다.** 위상과 방향에서만 나온다 — 같은 리플레이를 두 번 보면 같아야 한다
 * (계약 C4). 코어 밖이라 R5 가 강제하지는 않지만, 「같은 시드면 같은 판」이 이 게임이
 * 파는 것이라 화면도 그래야 한다.
 */

/** 무기 꼴. **닫힌 집합이다** (계약 C6) — 임의 값을 열면 도면이 무너진다. */
export type WeaponShape = 'straight' | 'curved' | 'axe'

/** 휘두르는 모션. 꼴과 **곱해진다.** */
export type SwingMotion = 'chop' | 'slash' | 'thrust'

/** 기본 꼴·모션. 무기가 아무것도 안 말하면 이것으로 그린다. */
export const DEFAULT_SHAPE: WeaponShape = 'straight'
export const DEFAULT_MOTION: SwingMotion = 'chop'

/** 아는 값인지 본다 — 서버가 모르는 값을 보내도 도면이 안 깨져야 한다. */
const SHAPES: ReadonlySet<string> = new Set<WeaponShape>(['straight', 'curved', 'axe'])
const MOTIONS: ReadonlySet<string> = new Set<SwingMotion>(['chop', 'slash', 'thrust'])

/** 칼날 길이. 셀 한 변에 대한 비율이며, 1 을 넘으면 옆 칸을 침범해 누가 때렸는지가 흐려진다. */
const BLADE_RATIO = 0.62

/** 굽은 칼의 휨. 칼날 길이에 대한 비율이다. */
const CURVE_RATIO = 0.26

/** 도끼 날의 폭·자리. 자루 끝에서 이만큼 앞에 이 폭으로 붙는다. */
const AXE_HEAD_AT = 0.72
const AXE_HEAD_WIDTH = 0.34

/** 호를 그리는 모션이 훑는 각도(라디안). 좁으면 안 보이고 넓으면 뒤를 친 것처럼 보인다. */
const ARC_SWEEP = Math.PI * 0.62

/** 찌르기가 나갔다 돌아오는 깊이. 셀 한 변에 대한 비율이다. */
const THRUST_REACH = 0.5

/** 평면 위의 점. */
export interface SwingPoint {
  readonly x: number
  readonly y: number
}

/** 한 위상에서의 무기 자국. 렌더러는 이것만 받아 선으로 긋는다. */
export interface SwingStroke {
  /** 자루에서 날 끝까지. 두 점이면 직선, 셋이면 굽은 날이다. */
  readonly blade: readonly SwingPoint[]
  /** 도끼 날. 없으면 빈 배열이다. */
  readonly head: readonly SwingPoint[]
}

/**
 * 아는 꼴로 접는다.
 *
 * @param raw 서버나 장비가 준 값.
 * @returns 아는 꼴. 모르면 기본값.
 */
export function resolveShape(raw: string): WeaponShape {
  return SHAPES.has(raw) ? (raw as WeaponShape) : DEFAULT_SHAPE
}

/**
 * 아는 모션으로 접는다.
 *
 * @param raw 서버나 장비가 준 값.
 * @returns 아는 모션. 모르면 기본값.
 */
export function resolveMotion(raw: string): SwingMotion {
  return MOTIONS.has(raw) ? (raw as SwingMotion) : DEFAULT_MOTION
}

/**
 * 때린 쪽에서 맞은 쪽을 보는 각도.
 *
 * **제자리를 때리면 위를 본다.** 방향이 없는 자해·장판은 각도가 0/0 이라 정의되지
 * 않는데, 그때 오른쪽을 기본으로 두면 늘 오른쪽으로 휘둘러 이상하다.
 *
 * @param from 때린 자리.
 * @param to 맞은 자리.
 * @returns 라디안 각도.
 */
export function resolveFacing(from: SwingPoint, to: SwingPoint): number {
  const dx = to.x - from.x
  const dy = to.y - from.y
  return dx === 0 && dy === 0 ? -Math.PI / 2 : Math.atan2(dy, dx)
}

/**
 * 모션이 이 위상에서 만드는 (각도, 뻗음).
 *
 * @param motion 모션.
 * @param phase 0 에서 1. 틱 하나 안에서 끝난다 (계약 C3).
 * @returns 바라보는 각도에 더할 각도와, 자루가 앞으로 나간 거리 비율.
 */
function resolveSweep(motion: SwingMotion, phase: number): { angle: number; reach: number } {
  if (motion === 'thrust') {
    // 나갔다 돌아온다. 위상 중앙에서 가장 깊다.
    return { angle: 0, reach: Math.sin(phase * Math.PI) * THRUST_REACH }
  }
  // 내려베기는 위에서 아래로, 횡베기는 뒤에서 앞으로 훑는다.
  const offset = motion === 'chop' ? -Math.PI / 2 : 0
  return { angle: offset + (phase - 0.5) * ARC_SWEEP, reach: 0 }
}

/**
 * 꼴 하나를 자루 기준 좌표로 만든다. 아직 회전하지 않은 상태다.
 *
 * @param shape 무기 꼴.
 * @param length 날 길이(px).
 * @returns 날과 도끼머리.
 */
function buildBlade(shape: WeaponShape, length: number): SwingStroke {
  if (shape === 'curved') {
    // 가운데를 옆으로 밀어 휘게 한다. 셋째 점이 곧 휨이다.
    return {
      blade: [
        { x: 0, y: 0 },
        { x: length * 0.5, y: -length * CURVE_RATIO },
        { x: length, y: 0 },
      ],
      head: [],
    }
  }
  const blade = [
    { x: 0, y: 0 },
    { x: length, y: 0 },
  ]
  if (shape !== 'axe') {
    return { blade, head: [] }
  }
  const at = length * AXE_HEAD_AT
  const half = length * AXE_HEAD_WIDTH * 0.5
  return {
    blade,
    head: [
      { x: at, y: -half },
      { x: length, y: 0 },
      { x: at, y: half },
    ],
  }
}

/**
 * 한 점을 돌리고 옮긴다.
 *
 * @param point 자루 기준 점.
 * @param angle 라디안.
 * @param origin 자루가 놓인 자리.
 * @returns 도면 좌표.
 */
function moveTo(point: SwingPoint, angle: number, origin: SwingPoint): SwingPoint {
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  return {
    x: origin.x + point.x * cos - point.y * sin,
    y: origin.y + point.x * sin + point.y * cos,
  }
}

/**
 * 이 위상의 무기 자국을 만든다.
 *
 * @param from 때린 자리(px).
 * @param to 맞은 자리(px).
 * @param cell 셀 한 변(px). 날 길이가 여기서 나온다.
 * @param shape 무기 꼴.
 * @param motion 모션.
 * @param phase 0 에서 1.
 * @returns 도면 좌표의 자국.
 */
export function buildSwing(
  from: SwingPoint,
  to: SwingPoint,
  cell: number,
  shape: WeaponShape,
  motion: SwingMotion,
  phase: number,
): SwingStroke {
  const held = Math.min(Math.max(phase, 0), 1)
  const facing = resolveFacing(from, to)
  const sweep = resolveSweep(motion, held)
  const angle = facing + sweep.angle
  // 자루는 때린 말의 자리에서 바라보는 쪽으로 조금 나가 있다. 말 위에 겹치면 글리프를
  // 가려서 **누가 때렸는지**가 안 읽힌다.
  const origin = {
    x: from.x + Math.cos(facing) * cell * (0.2 + sweep.reach),
    y: from.y + Math.sin(facing) * cell * (0.2 + sweep.reach),
  }
  const shaped = buildBlade(shape, cell * BLADE_RATIO)
  return {
    blade: shaped.blade.map((point) => moveTo(point, angle, origin)),
    head: shaped.head.map((point) => moveTo(point, angle, origin)),
  }
}
