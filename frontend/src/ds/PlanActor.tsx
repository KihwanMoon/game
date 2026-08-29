/**
 * PlanActor — 도면 위의 말 하나.
 *
 * `kind` 가 네 종뿐인 것은 Phase 1 범위(적 3종 + 플레이어)에 맞춘 것이다. GDD §5 의
 * 자폭·치유·보스는 도면에 그릴 글리프가 아직 없다(design/README.md D-1). Phase 4 에서
 * 열거를 넓힐 때 글리프도 함께 정해야 한다.
 *
 * 황동 예산: `kind="self"` 만 `--plan-actor-self`(황동)를 쓴다. 도면 위에 플레이어는
 * 하나뿐이므로 예산 한 자리다.
 */

/** 도면에 그릴 말의 종류. */
export type PlanActorKind = 'self' | 'charge' | 'shoot' | 'summon'

/** 종류별 글리프. 전부 유니코드 도형이며 이모지가 아니다. */
export const ACTOR_GLYPHS: ReadonlyMap<PlanActorKind, string> = new Map([
  ['self', '◉'],
  ['charge', '▲'],
  ['shoot', '◆'],
  ['summon', '■'],
])

/** 보조 기술이 읽을 종류 이름. */
export const ACTOR_NAMES: ReadonlyMap<PlanActorKind, string> = new Map([
  ['self', '플레이어'],
  ['charge', '돌진형'],
  ['shoot', '사격형'],
  ['summon', '소환형'],
])

/** PlanActor 가 받는 props. */
export interface PlanActorProps {
  /** 격자 열. 0 부터 센다. */
  readonly x: number
  /** 격자 행. 0 부터 센다. */
  readonly y: number
  readonly kind: PlanActorKind
  /** 글리프 아래 짧은 표기. */
  readonly label?: string
}

/**
 * 도면 위 말 하나를 그린다.
 *
 * @param props 좌표·종류·표기.
 * @returns 렌더 트리.
 */
export function PlanActor(props: PlanActorProps): React.JSX.Element {
  const glyph = ACTOR_GLYPHS.get(props.kind) ?? ACTOR_GLYPHS.get('charge')
  const name = ACTOR_NAMES.get(props.kind) ?? props.kind

  return (
    <div
      className={`ds-plan-actor ds-plan-actor--${props.kind}`}
      style={{
        left: `calc(var(--plan-cell) * ${String(props.x)})`,
        top: `calc(var(--plan-cell) * ${String(props.y)})`,
      }}
    >
      <span className="ds-plan-actor__glyph" aria-hidden="true">
        {glyph}
      </span>
      <span className="ds-sr">
        {name} ({props.x}, {props.y})
      </span>
      {props.label === undefined ? null : (
        <span className="ds-plan-actor__label">{props.label}</span>
      )}
    </div>
  )
}
