/**
 * PlanCanvas — 도면 한 장을 캔버스에 그리는 React 껍데기.
 *
 * 그리기 자체는 `planRenderer` 가 하고 여기서는 세 가지만 맡는다.
 *
 *   1. devicePixelRatio 반영. 백버퍼를 배율만큼 키우고 변환행렬로 되돌린다. 이걸 빼면
 *      1px 괘선이 흐려지는데, 기계 도면에서 괘선이 흐려지면 성격이 통째로 사라진다.
 *   2. 틱 경계의 명도 전환 140ms. 캔버스 내용은 보간할 수 없으므로 캔버스 **자체**에
 *      전환을 건다. 이동·스케일은 쓰지 않는다 — 도면은 흔들리지 않는다.
 *   3. 보조 기술용 텍스트. 캔버스는 그림이라 그 안의 말들이 읽히지 않는다.
 *
 * 셀마다 DOM 노드를 두지 않는 이유는 12x9 = 108칸이 매 틱 다시 그려지기 때문이다. 도면은
 * 정보 밀도가 높고 갱신이 잦은 면이라 캔버스가 맞다.
 */
import { useEffect, useRef, useState } from 'react'

import { ACTOR_NAMES } from '../ds'
import type { PlanScene } from './planScene'
import { renderPlan, resizePlanCanvas } from './planRenderer'
import type { PlanTheme } from './planTheme'
import { DEFAULT_LOOK } from './weaponLook'
import type { WeaponLook } from './weaponLook'

/** 틱이 바뀔 때 한 번 다시 도는 명도 전환 클래스. */
const SWAP_CLASS = 'battle-plan__canvas--swap'

/** 배율을 모를 때 쓰는 값. 서버 렌더에는 화면이 없다. */
const DEFAULT_PIXEL_RATIO = 1

/**
 * 무기 자국이 지나가는 시간(ms).
 *
 * **틱 하나(`--dur-tick` 140ms)를 안 넘는다** (설계/10_외형과_모션 C3). 넘으면 배속에서
 * 앞뒤 틱의 자국이 겹치고, 되감기에서 앞 틱의 것이 남는다.
 */
const SWING_MS = 130

/** PlanCanvas 가 받는 props. */
export interface PlanCanvasProps {
  readonly scene: PlanScene
  readonly theme: PlanTheme
  /**
   * 이 말이 무엇을 들고 휘두르는가 (설계/10_외형과_모션).
   *
   * **장면이 아니라 화면이 안다.** 겉모습은 시뮬 입력이 아니므로 엔진도 티켓도 안
   * 거친다 — 화면이 장착 무기의 `catalogId` 에서 골라 넘긴다 (계약 C1).
   */
  readonly lookOf?: (entityId: string) => WeaponLook
}

/**
 * 화면의 화소 배율을 따라간다. 창을 다른 배율의 모니터로 옮기면 값이 바뀐다.
 *
 * @returns 현재 배율.
 */
function usePixelRatio(): number {
  const [ratio, setRatio] = useState(DEFAULT_PIXEL_RATIO)

  useEffect(() => {
    const update = (): void => {
      setRatio(window.devicePixelRatio)
    }
    update()
    const query = window.matchMedia(`(resolution: ${String(window.devicePixelRatio)}dppx)`)
    query.addEventListener('change', update)
    return () => {
      query.removeEventListener('change', update)
    }
  }, [ratio])

  return ratio
}

/**
 * 이 장면에 휘두르는 자국이 있는가.
 *
 * @param scene 그릴 장면.
 * @returns 하나라도 있으면 참.
 */
function checkHasSwing(scene: PlanScene): boolean {
  return scene.pulses.some((pulse) => pulse.isStrike && pulse.from !== null)
}

/**
 * 움직임을 줄여 달라고 했는가.
 *
 * **물어보고 따른다.** 모션은 네 번째 채널이지 유일한 채널이 아니다 — 꺼도 고리와 수치가
 * 남으므로 판은 똑같이 읽힌다 (설계/10_외형과_모션 C5).
 *
 * @returns 줄여 달라고 했으면 참. 화면이 없는 자리(서버 렌더)에서도 참이다.
 */
function checkPrefersStill(): boolean {
  return (
    typeof window === 'undefined' ||
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/**
 * 장면을 사람이 읽는 한 줄로 적는다. 캔버스 대신 보조 기술이 읽는다.
 *
 * @param scene 그린 장면.
 * @returns 틱과 말들의 좌표가 적힌 한 줄.
 */
export function describeScene(scene: PlanScene): string {
  const actors = scene.actors
    .map((actor) => {
      const name = actor.isSelf ? '자신' : (ACTOR_NAMES.get(actor.kind) ?? actor.kind)
      // **캔버스는 읽히지 않는다.** 도면에 붙는 표시는 여기 글로도 남아야 화면을 안 보는
      // 사람에게 남는다 — 색·모양에 이어 세 번째 채널이다.
      const guard = actor.isGuarding ? ' 방어 태세' : ''
      return `${name} ${actor.label} (${String(actor.x)}, ${String(actor.y)})${guard}`
    })
    .join(', ')
  const hazards = scene.hazards
    .map((one) => `(${String(one.x)}, ${String(one.y)}) ${String(one.ticks)}틱 후 피격`)
    .join(', ')
  const parts = [`틱 ${String(scene.tick)}`, actors]
  if (hazards !== '') {
    parts.push(`예고 ${hazards}`)
  }
  return parts.join(' · ')
}

/**
 * 도면을 그린다.
 *
 * @param props 그릴 장면과 토큰에서 읽은 값들.
 * @returns 렌더 트리.
 */
export function PlanCanvas(props: PlanCanvasProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pixelRatio = usePixelRatio()
  const lookOf = props.lookOf ?? ((): WeaponLook => DEFAULT_LOOK)

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    const ctx = resizePlanCanvas(canvas, props.scene, props.theme, pixelRatio)
    if (ctx === undefined) {
      return
    }
    // **자국이 없으면 프레임을 안 돈다.** 틱마다 한 번 그리는 것이 이 캔버스의 기본이고
    // (12×9=108칸), 루프는 휘두르는 동안에만 돈다.
    if (!checkHasSwing(props.scene) || checkPrefersStill()) {
      // 모션을 끈 사람에게는 **다 끝난 자국**을 한 장 그린다 — 고리와 수치는 그대로
      // 남으므로 무슨 일이 있었는지는 똑같이 읽힌다 (계약 C5).
      renderPlan(ctx, props.scene, props.theme, 1, lookOf)
      return
    }
    let frame = 0
    let start = 0
    const step = (now: number): void => {
      start = start === 0 ? now : start
      const phase = Math.min((now - start) / SWING_MS, 1)
      renderPlan(ctx, props.scene, props.theme, phase, lookOf)
      if (phase < 1) {
        frame = requestAnimationFrame(step)
      }
    }
    frame = requestAnimationFrame(step)
    return () => {
      cancelAnimationFrame(frame)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- lookOf 는 매 렌더 새 함수라
    // 의존성에 넣으면 자국이 매 렌더 처음부터 다시 돈다. 장면이 바뀔 때만 다시 그린다.
  }, [props.scene, props.theme, pixelRatio])

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    // 클래스를 뗐다 붙이는 사이에 레이아웃을 한 번 읽어 애니메이션을 처음부터 다시 돌린다.
    canvas.classList.remove(SWAP_CLASS)
    void canvas.offsetWidth
    canvas.classList.add(SWAP_CLASS)
  }, [props.scene])

  return (
    <div className="battle-plan">
      <canvas className="battle-plan__canvas" ref={canvasRef} role="img" aria-label="전투 도면" />
      <span className="ds-sr">{describeScene(props.scene)}</span>
    </div>
  )
}
