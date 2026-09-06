/**
 * 도면 렌더러 — 장면 하나를 캔버스에 그린다.
 *
 * 기계 도면의 규칙을 그대로 따른다. 그림자 없음, 층위는 명도차와 1px 괘선, 모든 표현은
 * 선과 해칭이고, 색은 정보의 유일한 채널이 아니다 — 타일 열 종은 **꼴이 서로 다르다**.
 * 흑백으로 인쇄해도 벽·파괴 가능 벽·엄폐물·용암·함정이 구분되어야 한다.
 *
 * **움직임이 없다.** 말은 칸에서 칸으로 순간 이동하고 보간하지 않는다. 도면이 흔들리면
 * 눈이 좌표를 다시 잡아야 하고, 관전자가 읽어야 하는 것은 궤적이 아니라 **어느 틱에 어느
 * 칸에 있었는가** 다. 틱 경계의 140ms 명도 전환은 캔버스 위가 아니라 캔버스 자체의 CSS
 * transition 이 맡는다 (battle.css).
 *
 * **자국은 다르다** (2026-09-06, 설계/10_외형과_모션). 무기를 휘두르는 자국은 **말을 안
 * 옮긴다** — 때린 칸에 날이 한 번 지나갈 뿐이고, 좌표도 수치도 그대로다. 위상(0→1)은
 * 그리는 쪽이 넘겨주며 안 넘기면 다 끝난 상태로 그린다.
 *
 * 좌표는 CSS px 로 계산하고, devicePixelRatio 는 `resizePlanCanvas` 가 변환행렬로만
 * 반영한다. 그래서 이 파일 어디에도 배율이 섞이지 않는다.
 */

import {
  TILE_BREAKABLE_WALL,
  TILE_COVER,
  TILE_DOOR,
  TILE_FLOOR,
  TILE_LAVA,
  TILE_SPRING,
  TILE_STAIRS,
  TILE_THORNS,
  TILE_TRAP,
  TILE_WALL,
} from '../core/schemas'
import { ACTOR_GLYPHS } from '../ds'
import { DEFAULT_LOOK } from './weaponLook'
import type { WeaponLook } from './weaponLook'
import { buildSwing } from './weaponSwing'
import type {
  PlanActorView,
  PlanHazardView,
  PlanLinkView,
  PlanPulseView,
  PlanScene,
} from './planScene'
import type { PlanTheme } from './planTheme'

/** 셀 하나가 차지하는 화면 사각형. 단위는 CSS px 다. */
export interface CellRect {
  readonly left: number
  readonly top: number
  readonly size: number
}

/** 셀 안쪽 여백. 타일 표현이 격자 괘선에 붙지 않게 한다. */
const CELL_INSET_RATIO = 0.125

/** 바닥 점의 반지름. */
const FLOOR_DOT_RATIO = 0.05

/** 파괴 가능 벽은 해칭 간격을 넓혀 성긴 단면으로 그린다. */
const BREAKABLE_GAP_MULTIPLIER = 2

/** 예고 타일의 해칭 간격. 벽 해칭과 겹쳐 보이지 않을 만큼 성기다. */
const HAZARD_GAP_MULTIPLIER = 2

/** 벽 해칭은 45도, 예고 해칭은 그 반대 방향이다. 방향이 곧 구분이다. */
const HATCH_DEGREES_WALL = 45
const HATCH_DEGREES_HAZARD = -45

/** 가시덤불 표시의 팔 길이와 개수. */
const THORN_ARM_RATIO = 0.09
const THORN_MARK_COUNT = 3

/** 문 여닫이 호의 반지름. */
const DOOR_ARC_RATIO = 0.34

/** 생명의 샘 동심원. */
const SPRING_OUTER_RATIO = 0.3
const SPRING_INNER_RATIO = 0.16

/** 계단의 단 수. */
const STAIR_STEP_COUNT = 4

/** 용암 물결의 줄 수. */
const LAVA_WAVE_COUNT = 3

/** 함정 사각형의 안쪽 여백. */
const TRAP_INSET_RATIO = 0.22

/** 엄폐물 모서리 표시의 길이. */
const COVER_TICK_RATIO = 0.16

/** 말 글리프를 셀 중앙에서 위로 올리는 양. */
const GLYPH_OFFSET_RATIO = 0.08

/** 두 글자 표기를 셀 중앙에서 아래로 내리는 양. */
const LABEL_OFFSET_RATIO = 0.24

/** 체력 막대의 폭과 위치. */
const HP_BAR_WIDTH_RATIO = 0.5
const HP_BAR_OFFSET_RATIO = 0.4

/** 체력 막대의 두께. 괘선 두께의 배수로 잡아 토큰과 연결을 끊지 않는다. */
const HP_BAR_LINE_UNITS = 2

/** 물결의 제어점을 좌우 사분점에 둔다. */
const WAVE_CONTROL_RATIO = 0.25

/** 백분율의 밑. 부동소수를 피하려고 정수 퍼센트만 쓴다. */
const PERCENT_BASE = 100

/** 각도를 라디안으로 바꿀 때 쓰는 반바퀴. */
const HALF_TURN_DEGREES = 180

/** 원 한 바퀴. */
const FULL_TURN = Math.PI * 2

/** 사분원. 문 여닫이 호가 이만큼 돈다. */
const QUARTER_TURN = Math.PI / 2

/** 중앙을 가리키는 비율. */
const HALF = 0.5

/**
 * 셀 좌표를 화면 사각형으로 바꾼다.
 *
 * @param x 격자 열.
 * @param y 격자 행.
 * @param theme 토큰에서 읽은 값들.
 * @returns 셀이 차지하는 사각형.
 */
export function getCellRect(x: number, y: number, theme: PlanTheme): CellRect {
  return { left: x * theme.cell, top: y * theme.cell, size: theme.cell }
}

/**
 * 1px 선이 두 화소에 걸치지 않도록 좌표를 반 칸 민다.
 *
 * @param value 원래 좌표.
 * @param lineWidth 선 두께.
 * @returns 보정된 좌표.
 */
function alignToPixel(value: number, lineWidth: number): number {
  return Math.round(value) + (lineWidth % 2) * HALF
}

/**
 * 사각형 안을 평행선으로 채운다. 벽 단면과 예고 타일에만 쓴다.
 *
 * @param ctx 그릴 문맥.
 * @param rect 채울 사각형.
 * @param color 선 색.
 * @param gap 선 간격.
 * @param degrees 선의 기울기.
 * @param lineWidth 선 두께.
 */
function fillHatch(
  ctx: CanvasRenderingContext2D,
  rect: CellRect,
  color: string,
  gap: number,
  degrees: number,
  lineWidth: number,
): void {
  ctx.save()
  ctx.beginPath()
  ctx.rect(rect.left, rect.top, rect.size, rect.size)
  ctx.clip()
  ctx.strokeStyle = color
  ctx.lineWidth = lineWidth
  const slope = Math.tan((degrees * Math.PI) / HALF_TURN_DEGREES)
  const span = rect.size * (1 + Math.abs(slope))
  ctx.beginPath()
  for (let offset = -span; offset <= span; offset += gap) {
    ctx.moveTo(rect.left + offset, rect.top)
    ctx.lineTo(rect.left + offset + rect.size * slope, rect.top + rect.size)
  }
  ctx.stroke()
  ctx.restore()
}

/**
 * 셀 테두리를 그린다.
 *
 * @param ctx 그릴 문맥.
 * @param rect 테두리를 두를 사각형.
 * @param color 선 색.
 * @param theme 토큰 값들.
 * @param dashGap 점선 간격. 0 이면 실선이다.
 */
function strokeCell(
  ctx: CanvasRenderingContext2D,
  rect: CellRect,
  color: string,
  theme: PlanTheme,
  dashGap = 0,
): void {
  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = theme.lineWidth
  if (dashGap > 0) {
    ctx.setLineDash([dashGap, dashGap])
  }
  const left = alignToPixel(rect.left, theme.lineWidth)
  const top = alignToPixel(rect.top, theme.lineWidth)
  ctx.strokeRect(left, top, rect.size - theme.lineWidth, rect.size - theme.lineWidth)
  ctx.restore()
}

/**
 * 원 하나를 채운다.
 *
 * @param ctx 그릴 문맥.
 * @param cx 중심 x.
 * @param cy 중심 y.
 * @param radius 반지름.
 * @param color 색.
 */
function fillCircle(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  color: string,
): void {
  ctx.save()
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(cx, cy, radius, 0, FULL_TURN)
  ctx.fill()
  ctx.restore()
}

/**
 * 원 하나의 둘레를 그린다.
 *
 * @param ctx 그릴 문맥.
 * @param cx 중심 x.
 * @param cy 중심 y.
 * @param radius 반지름.
 * @param color 색.
 * @param lineWidth 선 두께.
 */
function strokeCircle(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  color: string,
  lineWidth: number,
): void {
  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = lineWidth
  ctx.beginPath()
  ctx.arc(cx, cy, radius, 0, FULL_TURN)
  ctx.stroke()
  ctx.restore()
}

/** 타일 한 종을 그리는 함수. */
export type TileDrawer = (ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme) => void

/**
 * 바닥 — 모눈 교점을 짚는 점 하나.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawFloorTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  fillCircle(
    ctx,
    rect.left + rect.size * HALF,
    rect.top + rect.size * HALF,
    rect.size * FLOOR_DOT_RATIO,
    theme.floorDot,
  )
}

/**
 * 벽 — 45도 해칭에 실선 테두리. 도면의 단면 표기 그대로다.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawWallTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  fillHatch(ctx, rect, theme.wall, theme.hatchGap, HATCH_DEGREES_WALL, theme.lineWidth)
  strokeCell(ctx, rect, theme.wall, theme)
}

/**
 * 파괴 가능 벽 — 같은 해칭을 성기게, 테두리는 점선.
 *
 * 벽과 색이 같은 것은 의도다. 다른 것은 밀도와 테두리이며, 그 둘은 흑백에서도 읽힌다.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawBreakableTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  fillHatch(
    ctx,
    rect,
    theme.wall,
    theme.hatchGap * BREAKABLE_GAP_MULTIPLIER,
    HATCH_DEGREES_WALL,
    theme.lineWidth,
  )
  strokeCell(ctx, rect, theme.wall, theme, theme.hatchGap)
}

/**
 * 가시덤불 — 작은 갈고리 세 개.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawThornsTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const arm = rect.size * THORN_ARM_RATIO
  const inset = rect.size * CELL_INSET_RATIO
  const span = rect.size - inset * 2
  ctx.save()
  ctx.strokeStyle = theme.dim
  ctx.lineWidth = theme.lineWidth
  ctx.beginPath()
  for (let index = 0; index < THORN_MARK_COUNT; index += 1) {
    const ratio = (index + 1) / (THORN_MARK_COUNT + 1)
    const cx = rect.left + inset + span * ratio
    const cy = rect.top + inset + span * (index % 2 === 0 ? ratio : 1 - ratio)
    ctx.moveTo(cx - arm, cy - arm)
    ctx.lineTo(cx + arm, cy + arm)
    ctx.moveTo(cx + arm, cy - arm)
    ctx.lineTo(cx - arm, cy + arm)
  }
  ctx.stroke()
  ctx.restore()
}

/**
 * 문 — 양쪽 문설주와 여닫이 호.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawDoorTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const inset = rect.size * CELL_INSET_RATIO
  ctx.save()
  ctx.strokeStyle = theme.door
  ctx.lineWidth = theme.lineWidth
  ctx.beginPath()
  ctx.moveTo(rect.left + inset, rect.top + inset)
  ctx.lineTo(rect.left + rect.size - inset, rect.top + inset)
  ctx.moveTo(rect.left + inset, rect.top + rect.size - inset)
  ctx.lineTo(rect.left + rect.size - inset, rect.top + rect.size - inset)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(
    rect.left + inset,
    rect.top + inset,
    rect.size * DOOR_ARC_RATIO,
    0,
    QUARTER_TURN,
  )
  ctx.stroke()
  ctx.restore()
}

/**
 * 생명의 샘 — 동심원 둘과 중심점.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawSpringTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const cx = rect.left + rect.size * HALF
  const cy = rect.top + rect.size * HALF
  strokeCircle(ctx, cx, cy, rect.size * SPRING_OUTER_RATIO, theme.spring, theme.lineWidth)
  strokeCircle(ctx, cx, cy, rect.size * SPRING_INNER_RATIO, theme.spring, theme.lineWidth)
  fillCircle(ctx, cx, cy, rect.size * FLOOR_DOT_RATIO, theme.spring)
}

/**
 * 계단 — 평행한 단 넷.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawStairsTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const inset = rect.size * CELL_INSET_RATIO
  const span = rect.size - inset * 2
  ctx.save()
  ctx.strokeStyle = theme.door
  ctx.lineWidth = theme.lineWidth
  ctx.beginPath()
  for (let step = 0; step <= STAIR_STEP_COUNT; step += 1) {
    const y = rect.top + inset + (span * step) / STAIR_STEP_COUNT
    const shrink = (span * step) / (STAIR_STEP_COUNT * 2)
    ctx.moveTo(rect.left + inset + shrink, y)
    ctx.lineTo(rect.left + inset + span, y)
  }
  ctx.moveTo(rect.left + inset + span, rect.top + inset)
  ctx.lineTo(rect.left + inset + span, rect.top + inset + span)
  ctx.stroke()
  ctx.restore()
}

/**
 * 용암 — 물결 셋과 실선 테두리.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawLavaTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const inset = rect.size * CELL_INSET_RATIO
  const span = rect.size - inset * 2
  ctx.save()
  ctx.strokeStyle = theme.hazard
  ctx.lineWidth = theme.lineWidth
  ctx.beginPath()
  for (let wave = 1; wave <= LAVA_WAVE_COUNT; wave += 1) {
    const y = rect.top + inset + (span * wave) / (LAVA_WAVE_COUNT + 1)
    const hump = span / (LAVA_WAVE_COUNT + 1)
    ctx.moveTo(rect.left + inset, y)
    ctx.quadraticCurveTo(
      rect.left + inset + span * WAVE_CONTROL_RATIO,
      y - hump * HALF,
      rect.left + rect.size * HALF,
      y,
    )
    ctx.quadraticCurveTo(
      rect.left + inset + span * (1 - WAVE_CONTROL_RATIO),
      y + hump * HALF,
      rect.left + inset + span,
      y,
    )
  }
  ctx.stroke()
  ctx.restore()
  strokeCell(ctx, rect, theme.hazard, theme)
}

/**
 * 함정 — 점선 사각형 안의 대각선 둘.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawTrapTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const inset = rect.size * TRAP_INSET_RATIO
  const span = rect.size - inset * 2
  ctx.save()
  ctx.strokeStyle = theme.hazard
  ctx.lineWidth = theme.lineWidth
  ctx.setLineDash([theme.hatchGap, theme.hatchGap])
  ctx.strokeRect(rect.left + inset, rect.top + inset, span, span)
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.moveTo(rect.left + inset, rect.top + inset)
  ctx.lineTo(rect.left + inset + span, rect.top + inset + span)
  ctx.moveTo(rect.left + inset + span, rect.top + inset)
  ctx.lineTo(rect.left + inset, rect.top + inset + span)
  ctx.stroke()
  ctx.restore()
}

/**
 * 엄폐물 — 한 단 밝은 면과 모서리 표시. 유일하게 면을 채우는 타일이라 벽과 헷갈리지 않는다.
 *
 * @param ctx 그릴 문맥.
 * @param rect 셀 사각형.
 * @param theme 토큰 값들.
 */
function drawCoverTile(ctx: CanvasRenderingContext2D, rect: CellRect, theme: PlanTheme): void {
  const inset = rect.size * CELL_INSET_RATIO
  const span = rect.size - inset * 2
  ctx.save()
  ctx.fillStyle = theme.coverFill
  ctx.fillRect(rect.left + inset, rect.top + inset, span, span)
  ctx.strokeStyle = theme.coverEdge
  ctx.lineWidth = theme.lineWidth
  ctx.strokeRect(rect.left + inset, rect.top + inset, span, span)
  const tick = rect.size * COVER_TICK_RATIO
  ctx.beginPath()
  ctx.moveTo(rect.left + inset, rect.top + inset + tick)
  ctx.lineTo(rect.left + inset + tick, rect.top + inset)
  ctx.moveTo(rect.left + inset + span - tick, rect.top + inset + span)
  ctx.lineTo(rect.left + inset + span, rect.top + inset + span - tick)
  ctx.stroke()
  ctx.restore()
}

/**
 * 타일 ID 에서 그리는 함수로. 열 종이 전부 다른 꼴을 갖는다.
 *
 * `Record` 가 아니라 `Map` 인 이유는 저장소 전체와 같다 — 객체 키 순회 순서에 기대지
 * 않는다 (R5).
 */
export const TILE_DRAWERS: ReadonlyMap<number, TileDrawer> = new Map([
  [TILE_FLOOR, drawFloorTile],
  [TILE_WALL, drawWallTile],
  [TILE_BREAKABLE_WALL, drawBreakableTile],
  [TILE_THORNS, drawThornsTile],
  [TILE_DOOR, drawDoorTile],
  [TILE_SPRING, drawSpringTile],
  [TILE_STAIRS, drawStairsTile],
  [TILE_LAVA, drawLavaTile],
  [TILE_TRAP, drawTrapTile],
  [TILE_COVER, drawCoverTile],
])

/**
 * 격자 괘선을 그린다. 셀마다 사각형을 그리지 않고 선만 긋는다.
 *
 * @param ctx 그릴 문맥.
 * @param scene 그릴 장면.
 * @param theme 토큰 값들.
 */
function drawGrid(ctx: CanvasRenderingContext2D, scene: PlanScene, theme: PlanTheme): void {
  const width = scene.cols * theme.cell
  const height = scene.rows * theme.cell
  ctx.save()
  ctx.strokeStyle = theme.grid
  ctx.lineWidth = theme.lineWidth
  ctx.beginPath()
  for (let col = 0; col <= scene.cols; col += 1) {
    const x = alignToPixel(col * theme.cell, theme.lineWidth)
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
  }
  for (let row = 0; row <= scene.rows; row += 1) {
    const y = alignToPixel(row * theme.cell, theme.lineWidth)
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
  }
  ctx.stroke()
  ctx.restore()
}

/**
 * 예고 칸 하나를 그린다 (GDD §4.2).
 *
 * 세 채널로 적는다 — 색(rust), 꼴(역방향 해칭), 그리고 **남은 틱 수**. 아직 인지 폭에
 * 들어오지 않은 예고는 테두리를 점선으로 둔다.
 *
 * @param ctx 그릴 문맥.
 * @param hazard 그릴 예고 칸.
 * @param theme 토큰 값들.
 */
function drawHazard(
  ctx: CanvasRenderingContext2D,
  hazard: PlanHazardView,
  theme: PlanTheme,
): void {
  const rect = getCellRect(hazard.x, hazard.y, theme)
  fillHatch(
    ctx,
    rect,
    theme.hazard,
    theme.hatchGap * HAZARD_GAP_MULTIPLIER,
    HATCH_DEGREES_HAZARD,
    theme.lineWidth,
  )
  strokeCell(ctx, rect, theme.hazard, theme, hazard.isSensed ? 0 : theme.hatchGap)
  ctx.save()
  ctx.fillStyle = theme.hazard
  ctx.font = `${String(theme.labelSize)}px ${theme.font}`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  const inset = rect.size * CELL_INSET_RATIO
  ctx.fillText(String(hazard.ticks), rect.left + inset, rect.top + inset)
  ctx.restore()
}

/**
 * 말 하나를 그린다.
 *
 * 글리프 + 두 글자 표기 + 체력 막대. 글리프만으로는 적 여덟 종이 구분되지 않으므로
 * 표기를 함께 적는다 (actorKind.ts).
 *
 * @param ctx 그릴 문맥.
 * @param actor 그릴 말.
 * @param theme 토큰 값들.
 */
/** 등급이 두르는 고리의 굵기(선 굵기 배수). 일반은 안 두른다 — 대부분이 일반이다. */
const TIER_RING_UNITS: ReadonlyMap<string, number> = new Map([
  ['ELITE', 1],
  ['BOSS', 2],
])

/** 고리 반지름. 칸 크기에 대한 비율이라 셀이 커져도 글리프를 안 가린다. */
const TIER_RING_RATIO = 0.34

/**
 * 방어 태세 호의 반지름. 등급 고리(0.34)보다 밖이라 둘이 겹쳐도 각각 읽힌다.
 *
 * **고리가 아니라 호다.** 등급은 닫힌 원이고 방어는 아래로 열린 호라, 모양만으로 갈린다 —
 * 색을 못 가르는 사람에게도 「등급이 붙었다」와 「지금 단단하다」가 달라야 한다.
 */
const GUARD_ARC_RATIO = 0.46

/** 호가 도는 각도. 아래쪽만 감싼다 — 받쳐 주는 모양이 「막는다」로 읽힌다. */
const GUARD_ARC_START = Math.PI * 0.18
const GUARD_ARC_END = Math.PI * 0.82

/**
 * 등급이 정하는 색을 고른다.
 *
 * @param tier 등급 코드.
 * @param theme 토큰에서 읽은 값들.
 * @returns 칠할 색. 일반이거나 모르는 등급이면 기본 적 색이다.
 */
export function resolveTierColor(tier: string, theme: PlanTheme): string {
  if (tier === 'ELITE') {
    return theme.actorElite
  }
  if (tier === 'BOSS') {
    return theme.actorBoss
  }
  return theme.actorEnemy
}

/**
 * 이 말을 칠할 색을 고른다.
 *
 * **도플갱어가 등급을 이긴다.** ELITE 로 서지만 다른 정예와 같은 것이 아니라서다 —
 * 사람의 빌드가 그대로 서 있고, 전리품을 안 떨어뜨리며, 그 규칙표가 나를 읽는다.
 * 노랑으로 두면 「한 단 위의 고블린」으로 읽힌다.
 *
 * @param actor 그릴 말.
 * @param theme 토큰에서 읽은 값들.
 * @returns 칠할 색.
 */
export function resolveActorColor(actor: PlanActorView, theme: PlanTheme): string {
  if (actor.isSelf) {
    return theme.actorSelf
  }
  if (actor.isDoppel) {
    return theme.actorDoppel
  }
  return resolveTierColor(actor.tier, theme)
}

/**
 * 방어 태세를 글리프 아래 호로 적는다.
 *
 * **모델에 있는데 화면에 없던 것이다.** `GUARD_BRACE` 는 받는 피해를 50% 깎고 2틱 가는데
 * 도면에도 로그에도 안 나왔다 — 보는 사람에게는 「왜 갑자기 덜 아프지」가 설명 없이
 * 일어났다. 설명 없는 것은 버그와 구별되지 않는다 (P1).
 *
 * @param ctx 캔버스 문맥.
 * @param cx 글리프 중심 x.
 * @param cy 글리프 중심 y.
 * @param size 칸 크기.
 * @param theme 토큰에서 읽은 값들.
 */
function drawGuard(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  size: number,
  theme: PlanTheme,
): void {
  ctx.save()
  ctx.strokeStyle = theme.guard
  // 등급 고리보다 굵다. 등급은 오래 가는 성질이고 방어는 지금 이 순간이라, 굵기가
  // 「지금 일어나는 일」을 앞으로 당긴다.
  ctx.lineWidth = theme.lineWidth * 2
  ctx.beginPath()
  ctx.arc(cx, cy, size * GUARD_ARC_RATIO, GUARD_ARC_START, GUARD_ARC_END)
  ctx.stroke()
  ctx.restore()
}

function drawActor(ctx: CanvasRenderingContext2D, actor: PlanActorView, theme: PlanTheme): void {
  const rect = getCellRect(actor.x, actor.y, theme)
  const cx = rect.left + rect.size * HALF
  const cy = rect.top + rect.size * HALF
  const color = resolveActorColor(actor, theme)

  // **색이 유일한 채널이 아니다.** 등급 있는 적에게 고리를 두른다 — 색을 못 가르는
  // 사람에게도 정예와 보스가 달라 보여야 하고, 그것이 이 저장소가 참·거짓을 색·글리프·
  // 명도 셋으로 적는 것과 같은 규율이다.
  const ringUnits = TIER_RING_UNITS.get(actor.tier)
  if (ringUnits !== undefined && !actor.isSelf) {
    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = theme.lineWidth * ringUnits
    ctx.beginPath()
    ctx.arc(cx, cy - rect.size * GLYPH_OFFSET_RATIO, rect.size * TIER_RING_RATIO, 0, Math.PI * 2)
    ctx.stroke()
    ctx.restore()
  }

  if (actor.isGuarding) {
    drawGuard(ctx, cx, cy - rect.size * GLYPH_OFFSET_RATIO, rect.size, theme)
  }

  ctx.save()
  ctx.fillStyle = color
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.font = `${String(theme.glyphSize)}px ${theme.font}`
  ctx.fillText(ACTOR_GLYPHS.get(actor.kind) ?? '', cx, cy - rect.size * GLYPH_OFFSET_RATIO)
  ctx.fillStyle = theme.dim
  ctx.font = `${String(theme.labelSize)}px ${theme.font}`
  ctx.fillText(actor.label, cx, cy + rect.size * LABEL_OFFSET_RATIO)
  ctx.restore()

  const barWidth = rect.size * HP_BAR_WIDTH_RATIO
  const barLeft = cx - barWidth * HALF
  const barTop = cy + rect.size * HP_BAR_OFFSET_RATIO
  const filled = (barWidth * actor.hpPercent) / PERCENT_BASE
  ctx.save()
  ctx.fillStyle = theme.grid
  const thickness = theme.lineWidth * HP_BAR_LINE_UNITS
  ctx.fillRect(barLeft, barTop, barWidth, thickness)
  ctx.fillStyle = color
  ctx.fillRect(barLeft, barTop, filled, thickness)
  ctx.restore()
}

/**
 * 장면 한 장을 그린다.
 *
 * 순서가 곧 층위다 — 바탕, 격자, 타일, 예고, 말. 예고가 타일 위에 오는 것은 예고가
 * 지형이 아니라 **이번 틱의 사건**이기 때문이고, 말이 예고 위에 오는 것은 "그 칸에 누가
 * 서 있는가" 가 예고의 요점이기 때문이다.
 *
 * @param ctx 그릴 문맥. 변환행렬은 이미 배율이 반영된 상태여야 한다.
 * @param scene 그릴 장면.
 * @param theme 토큰에서 읽은 값들.
 */
/** 화살촉 길이를 셀 한 변의 몇 배로 둘지. */
const ARROW_RATIO = 0.22

/** 화살촉이 벌어지는 각(라디안). 도면 화살표의 관습대로 좁게 둔다. */
const ARROW_SPREAD = 0.42

/** 선을 말의 중심에서 얼마나 띄울지. 말 글리프를 덮으면 무엇인지 못 읽는다. */
const LINK_INSET = 0.34

/**
 * 대상이 있는 행동 하나를 선으로 잇는다.
 *
 * **말만 봐서는 누가 누구를 때렸는지 알 수 없다.** 격자에 다섯이 서 있고 HP 가 줄면
 * 그것이 어느 말의 짓인지 화면 어디에도 없었다 — 로그를 눈으로 따라가야 했다.
 *
 * 색이 방향을 말한다. 황동은 이 화면에서 언제나 「이것이 너다」이고 녹슨 붉은색은 언제나
 * 「이것이 아프다」라, 새 뜻을 만들지 않고 있던 뜻을 그대로 쓴다.
 *
 * 양 끝을 말 중심에서 띄운다. 글리프를 덮으면 무엇이 서 있는지 못 읽는다.
 *
 * @param ctx 그리기 문맥.
 * @param link 이을 행동.
 * @param theme 토큰 값들.
 */
function drawLink(ctx: CanvasRenderingContext2D, link: PlanLinkView, theme: PlanTheme): void {
  const from = getCellRect(link.fromX, link.fromY, theme)
  const to = getCellRect(link.toX, link.toY, theme)
  const fromX = from.left + from.size / 2
  const fromY = from.top + from.size / 2
  const toX = to.left + to.size / 2
  const toY = to.top + to.size / 2
  const dx = toX - fromX
  const dy = toY - fromY
  const span = Math.hypot(dx, dy)
  if (span === 0) {
    return
  }
  const inset = theme.cell * LINK_INSET
  const unitX = dx / span
  const unitY = dy / span
  const startX = fromX + unitX * inset
  const startY = fromY + unitY * inset
  const endX = toX - unitX * inset
  const endY = toY - unitY * inset

  ctx.save()
  ctx.strokeStyle = link.isFromSelf ? theme.linkSelf : theme.linkEnemy
  ctx.lineWidth = theme.lineWidth
  ctx.beginPath()
  ctx.moveTo(startX, startY)
  ctx.lineTo(endX, endY)
  ctx.stroke()

  // 화살촉. **방향을 색만으로 말하지 않는다** — 색을 못 가르는 사람에게도 누가 누구에게
  // 하는지가 보여야 한다 (참·거짓을 색·글리프·명도 셋으로 적는 것과 같은 규율).
  const angle = Math.atan2(dy, dx)
  const head = theme.cell * ARROW_RATIO
  ctx.beginPath()
  ctx.moveTo(endX, endY)
  ctx.lineTo(
    endX - head * Math.cos(angle - ARROW_SPREAD),
    endY - head * Math.sin(angle - ARROW_SPREAD),
  )
  ctx.moveTo(endX, endY)
  ctx.lineTo(
    endX - head * Math.cos(angle + ARROW_SPREAD),
    endY - head * Math.sin(angle + ARROW_SPREAD),
  )
  ctx.stroke()
  ctx.restore()
}

/** 이펙트 고리의 반지름 비율. 지시선 고리보다 조금 크다 — 겹쳐도 구분된다. */
const PULSE_RATIO = 0.46

/**
 * 수치가 움직인 자리에 고리를 그린다 (간단한 이펙트).
 *
 * 피해는 붉게, 회복·방어는 초록으로 — 화면의 기존 뜻(rust=아프다, verdigris=참·회복)을
 * 그대로 쓴다. 채우지 않는 이유는 말 글리프를 덮으면 안 되기 때문이다.
 *
 * @param ctx 그리기 문맥.
 * @param pulse 그릴 자리.
 * @param theme 토큰 값들.
 */
function drawSwing(
  ctx: CanvasRenderingContext2D,
  pulse: PlanPulseView,
  theme: PlanTheme,
  phase: number,
  look: WeaponLook,
): void {
  // **활은 안 휘두른다.** 사거리 넷 다섯에서 칼자국이 뜨면 무슨 일이 있었는지가 거짓으로
  // 읽힌다 — 그래서 꼴에 `none` 이 있다.
  if (!pulse.isStrike || pulse.from === null || look.shape === 'none') {
    return
  }
  const fromRect = getCellRect(pulse.from.x, pulse.from.y, theme)
  const toRect = getCellRect(pulse.x, pulse.y, theme)
  const stroke = buildSwing(
    { x: fromRect.left + fromRect.size / 2, y: fromRect.top + fromRect.size / 2 },
    { x: toRect.left + toRect.size / 2, y: toRect.top + toRect.size / 2 },
    theme.cell,
    look.shape,
    look.motion,
    phase,
  )
  ctx.save()
  ctx.strokeStyle = theme.hazard
  ctx.lineWidth = theme.lineWidth * 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.beginPath()
  const [head, ...rest] = stroke.blade
  if (head !== undefined) {
    ctx.moveTo(head.x, head.y)
    for (const point of rest) {
      ctx.lineTo(point.x, point.y)
    }
    ctx.stroke()
  }
  if (stroke.head.length > 0) {
    ctx.beginPath()
    const [first, ...tail] = stroke.head
    if (first !== undefined) {
      ctx.moveTo(first.x, first.y)
      for (const point of tail) {
        ctx.lineTo(point.x, point.y)
      }
      ctx.stroke()
    }
  }
  ctx.restore()
}


function drawPulse(
  ctx: CanvasRenderingContext2D,
  pulse: PlanPulseView,
  theme: PlanTheme,
  phase: number,
  look: WeaponLook,
): void {
  // **자국이 먼저, 고리가 나중이다.** 고리와 수치는 모션을 꺼도 남아야 하므로 위에
  // 그린다 (계약 C5).
  drawSwing(ctx, pulse, theme, phase, look)
  const rect = getCellRect(pulse.x, pulse.y, theme)
  const color = pulse.isGain ? theme.spring : theme.hazard
  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = theme.lineWidth * 2
  ctx.beginPath()
  ctx.arc(
    rect.left + rect.size / 2,
    rect.top + rect.size / 2,
    theme.cell * PULSE_RATIO,
    0,
    Math.PI * 2,
  )
  ctx.stroke()
  // **수치를 병기한다** (P1). 고리만으로는 얼마나였는지 모른다 — 맞은 자리에 -7,
  // 회복에 +12. 수치 없는 스킬(방어·소환)은 이름표가 그 자리를 맡는다.
  ctx.fillStyle = color
  ctx.font = `${String(theme.labelSize)}px ${theme.font}`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'bottom'
  const centerX = rect.left + rect.size / 2
  const top = rect.top - theme.lineWidth
  if (pulse.delta !== null) {
    const sign = pulse.delta > 0 ? '+' : ''
    const suffix = pulse.label === '' ? '' : ` ${pulse.label}`
    ctx.fillText(`${sign}${String(pulse.delta)}${suffix}`, centerX, top)
  } else if (pulse.label !== '') {
    ctx.fillText(pulse.label, centerX, top)
  }
  ctx.restore()
}

export function renderPlan(
  ctx: CanvasRenderingContext2D,
  scene: PlanScene,
  theme: PlanTheme,
  phase = 1,
  lookOf: (entityId: string) => WeaponLook = () => DEFAULT_LOOK,
): void {
  const width = scene.cols * theme.cell
  const height = scene.rows * theme.cell
  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = theme.surface
  ctx.fillRect(0, 0, width, height)
  drawGrid(ctx, scene, theme)

  for (let y = 0; y < scene.rows; y += 1) {
    const row = scene.tiles[y]
    if (row === undefined) {
      continue
    }
    for (let x = 0; x < scene.cols; x += 1) {
      const tile = row[x]
      const draw = tile === undefined ? undefined : TILE_DRAWERS.get(tile)
      if (draw !== undefined) {
        draw(ctx, getCellRect(x, y, theme), theme)
      }
    }
  }

  for (const hazard of scene.hazards) {
    drawHazard(ctx, hazard, theme)
  }
  // **말보다 먼저 긋는다.** 선이 글리프를 덮으면 무엇이 서 있는지 못 읽는다.
  for (const link of scene.links) {
    drawLink(ctx, link, theme)
  }
  for (const pulse of scene.pulses) {
    drawPulse(ctx, pulse, theme, phase, lookOf(pulse.byEntityId))
  }
  for (const actor of scene.actors) {
    drawActor(ctx, actor, theme)
  }
}

/**
 * 캔버스를 장면 크기에 맞추고 devicePixelRatio 를 변환행렬에 반영한다.
 *
 * CSS 크기는 **토큰의 배수**로 준다. `calc(var(--plan-cell) * 12)` 라고 적으면 셀 크기를
 * 토큰에서 고쳤을 때 화면도 함께 따라온다 — 여기서 px 수를 문자열로 만들면 그 연결이
 * 끊긴다. 반면 백버퍼 크기는 실제 화소 수라 수치일 수밖에 없다.
 *
 * @param canvas 그릴 캔버스.
 * @param scene 그릴 장면.
 * @param theme 토큰 값들.
 * @param pixelRatio 화면의 화소 배율.
 * @returns 배율이 반영된 그리기 문맥. 얻지 못하면 undefined.
 */
export function resizePlanCanvas(
  canvas: HTMLCanvasElement,
  scene: PlanScene,
  theme: PlanTheme,
  pixelRatio: number,
): CanvasRenderingContext2D | undefined {
  canvas.style.width = `calc(var(--plan-cell) * ${String(scene.cols)})`
  canvas.style.height = `calc(var(--plan-cell) * ${String(scene.rows)})`
  canvas.width = Math.round(scene.cols * theme.cell * pixelRatio)
  canvas.height = Math.round(scene.rows * theme.cell * pixelRatio)
  const ctx = canvas.getContext('2d')
  if (ctx === null) {
    return undefined
  }
  ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
  return ctx
}
