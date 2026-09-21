/**
 * 도면 위에 겹치는 HUD 층 (2026-09-21 요청).
 *
 * `BattleFrame` 에서 갈라 나왔다. 저쪽은 **무엇을 어떤 순서로 세우는가**이고 여기는
 * **귀퉁이 하나를 어떻게 그리는가**다.
 *
 * 값은 `planHud` 가 만든다 — 여기서 수치를 만들면 상태 탭과 갈린다.
 *
 * **눌리지 않는다.** 도면의 칸을 가리면 안 되므로 층 전체가 `pointer-events: none` 이다.
 */
import type { HudItem, HudSkill, HudStatus, PlanHud } from './planHud'

/** 게이지 칸 수. 4px 모듈에 맞춘 열 칸이다 — 한 칸이 곧 10% 다. */
const GAUGE_CELLS = 10
const PERCENT_BASE = 100

/**
 * 체력 게이지의 찬 칸 수.
 *
 * **0 이 아니면 최소 한 칸은 남긴다.** 내림만 하면 1% 가 0칸이 되어 「죽은 것」과
 * 「거의 죽은 것」이 같은 그림이 된다.
 *
 * @param hp 지금 체력.
 * @param hpMax 최대 체력.
 * @returns 찬 칸 수.
 */
export function countGaugeCells(hp: number, hpMax: number): number {
  if (hpMax <= 0 || hp <= 0) {
    return 0
  }
  return Math.max(1, Math.floor((hp * GAUGE_CELLS) / hpMax))
}

/**
 * 쿨타임이 얼마나 남았는가를 0~100 으로.
 *
 * 칸을 덮는 그늘의 높이가 된다 — 다 차면 0 이고, 막 쓴 직후가 100 이다.
 *
 * @param skill 재주 칸.
 * @returns 퍼센트. 쿨이 없는 재주는 0.
 */
export function readCooldownPercent(skill: HudSkill): number {
  if (skill.total <= 0 || skill.left <= 0) {
    return 0
  }
  return Math.min(PERCENT_BASE, Math.round((skill.left * PERCENT_BASE) / skill.total))
}

/**
 * 좌상단 — 체력과 걸린 상태이상.
 *
 * @param props 체력과 상태이상들.
 * @returns 렌더 트리.
 */
function HudVitals(props: {
  readonly hp: number
  readonly hpMax: number
  readonly isLow: boolean
  readonly statuses: readonly HudStatus[]
}): React.JSX.Element {
  const filled = countGaugeCells(props.hp, props.hpMax)
  return (
    <div className="hud-pin hud-pin--tl">
      <div className={`hud-hp${props.isLow ? ' hud-hp--low' : ''}`}>
        {/* **칸이 정보이고 숫자가 정본이다.** 색을 못 봐도 찬 칸 수로 읽히고,
            정확한 값은 옆의 숫자가 말한다 (design/README D-1). */}
        <span className="hud-hp__bar" aria-hidden="true">
          {Array.from({ length: GAUGE_CELLS }, (_unused, at) => (
            <i className={at < filled ? 'on' : undefined} key={at} />
          ))}
        </span>
        <span className="hud-hp__num">
          {props.hp} / {props.hpMax}
        </span>
      </div>
      {props.statuses.length === 0 ? null : (
        <div className="hud-stat">
          {props.statuses.map((one) => (
            <span className="hud-stat__one" key={one.label}>
              {one.label} {one.ticks}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * 좌하단 — 들고 온 소모품과 남은 수.
 *
 * @param props 칸들.
 * @returns 렌더 트리. 들고 온 것이 없으면 안 그린다.
 */
function HudItems(props: { readonly items: readonly HudItem[] }): React.JSX.Element | null {
  if (props.items.length === 0) {
    return null
  }
  return (
    <div className="hud-pin hud-pin--bl">
      {props.items.map((one) => (
        // **다 쓴 칸도 남는다.** 사라지면 「원래 없었다」로 읽히는데, 규칙표가 그것을
        // 쓰려다 「불가」로 떨어진 이유가 바로 0 이기 때문이다.
        <span
          className={`hud-item${one.held === 0 ? ' hud-item--empty' : ''}`}
          key={one.label}
          title={one.label}
        >
          <span className="hud-item__code" aria-hidden="true">
            {one.code}
          </span>
          <span className="hud-item__num">{one.held}</span>
          <span className="ds-sr">
            {one.label} {one.held} / {one.carried}
          </span>
        </span>
      ))}
    </div>
  )
}

/**
 * 우하단 — 재주 칸과 남은 쿨타임.
 *
 * **그늘이 유일한 채널이 아니다.** 남은 틱을 숫자로 함께 적는다 — 색과 명도만으로
 * 말하면 「거의 찼다」와 「막 썼다」가 같은 그림이 된다 (design/README D-1).
 *
 * @param props 칸들.
 * @returns 렌더 트리. 쓰는 재주가 없으면 안 그린다.
 */
function HudSkills(props: { readonly skills: readonly HudSkill[] }): React.JSX.Element | null {
  if (props.skills.length === 0) {
    return null
  }
  return (
    <div className="hud-pin hud-pin--br">
      {props.skills.map((one) => {
        const left = readCooldownPercent(one)
        return (
          <span
            className={`hud-skill${left > 0 ? ' hud-skill--cooling' : ''}`}
            key={one.label}
          >
            {/* 그늘이 위에서 내려와 남은 만큼을 덮는다. 다 차면 0 이라 사라진다. */}
            <i className="hud-skill__shade" aria-hidden="true" style={{ blockSize: `${left}%` }} />
            <span className="hud-skill__name">{one.label}</span>
            <span className="hud-skill__left">{one.left === 0 ? '' : one.left}</span>
            <span className="ds-sr">
              {one.label} {one.left === 0 ? '준비됨' : `${one.left}틱 남음`}
            </span>
          </span>
        )
      })}
    </div>
  )
}

/**
 * 도면 위 HUD 를 그린다.
 *
 * @param props 겹칠 값 전부.
 * @returns 렌더 트리.
 */
export function PlanHudLayer(props: { readonly hud: PlanHud }): React.JSX.Element {
  return (
    <div className="hud-layer">
      <HudVitals
        hp={props.hud.hp}
        hpMax={props.hud.hpMax}
        isLow={props.hud.isLow}
        statuses={props.hud.statuses}
      />
      <HudItems items={props.hud.items} />
      <HudSkills skills={props.hud.skills} />
    </div>
  )
}
