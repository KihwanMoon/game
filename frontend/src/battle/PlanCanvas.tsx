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

/** 틱이 바뀔 때 한 번 다시 도는 명도 전환 클래스. */
const SWAP_CLASS = 'battle-plan__canvas--swap'

/** 배율을 모를 때 쓰는 값. 서버 렌더에는 화면이 없다. */
const DEFAULT_PIXEL_RATIO = 1

/** PlanCanvas 가 받는 props. */
export interface PlanCanvasProps {
  readonly scene: PlanScene
  readonly theme: PlanTheme
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

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    const ctx = resizePlanCanvas(canvas, props.scene, props.theme, pixelRatio)
    if (ctx === undefined) {
      return
    }
    renderPlan(ctx, props.scene, props.theme)
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
