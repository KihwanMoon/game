/**
 * 도면 위에 겹치는 HUD 층 (2026-09-21 요청).
 *
 * `BattleFrame` 에서 갈라 나왔다. 저쪽은 **무엇을 어떤 순서로 세우는가**이고 여기는
 * **귀퉁이 하나를 어떻게 그리는가**다.
 *
 * 값은 `planHud` 가 만든다 — 여기서 수치를 만들면 상태 탭과 갈린다.
 *
 * **눌리지 않는다.** 도면의 칸을 가리면 안 되므로 층 전체가 `pointer-events: none` 이다.
 *
 * 우상단은 **이번 틱에 발동한 내력의 번호**다 — 없어진 지시선을 대신한다(`HudArmed`).
 *
 * 아래 두 귀퉁이는 **도면의 칸을 세로로 쌓는다** (2026-09-21 요청). 가로로 이으면 종류가
 * 늘 때마다 줄이 길어져 도면 폭을 가로지르고 판정 줄과 겹쳤다 — 부적 넷을 다 들고 오면
 * 다섯 칸이다. 세로로 쌓으면 종류가 늘어도 도면의 한 열 안에 머문다.
 *
 * **수량을 숫자로 안 적는다** (같은 요청). 남은 비율만큼 밝게 두고 나머지를 그늘로
 * 덮는다 — 칸이 작아 숫자를 넣으면 그림이 설 자리가 없다. 정확한 값은 `title` 과
 * 보조 기술용 말이 늘 싣는다.
 */
import { formatRuleIndex } from '../ds'
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
 * 소모품 칸이 얼마나 줄었는가를 0~100 으로.
 *
 * 그늘이 덮는 높이다 — 밝게 남은 만큼이 지금 들고 있는 수다 (2026-09-21 요청:
 * 「남은 숫자 비율로 만들어서 음영으로 깎고」).
 *
 * @param item 소모품 칸.
 * @returns 퍼센트. 들고 온 적이 없으면 0 — 그 칸은 애초에 안 선다.
 */
export function readSpentPercent(item: HudItem): number {
  if (item.carried <= 0) {
    return 0
  }
  const left = Math.max(0, Math.min(item.carried, item.held))
  return PERCENT_BASE - Math.round((left * PERCENT_BASE) / item.carried)
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
 * 칸 하나 — 도면의 한 칸만 한 네모에 그림 한 장과 그늘 하나.
 *
 * **소모품과 재주가 같은 칸을 쓴다.** 둘 다 답하는 질문이 하나이기 때문이다 — 지금
 * 이것을 쓸 수 있는가, 얼마나 남았는가.
 *
 * **못 쓰는 칸은 셋으로 말한다** (design/README D-1). 그늘이 덮고(명도), 그 그늘이
 * rust 이고(색), 구석에 `✕` 가 선다(글리프). 숫자를 뗀 뒤로 그늘만 남기면 「거의
 * 찼다」와 「못 쓴다」가 같은 그림이 되는데, `✕` 는 그 둘을 가르면서 자릿수를 안 먹는다.
 *
 * @param props 덮을 높이·표기·그림·못 쓰는 상태·읽어 줄 말.
 * @returns 렌더 트리.
 */
function HudCell(props: {
  readonly kind: string
  /** 그늘이 덮는 높이(%). 0 이면 안 덮는다. */
  readonly shade: number
  /** 그림이 없을 때 칸에 적는 글자. */
  readonly mark: string
  /** 그림 주소. 빈 문자열이면 글자로 떨어진다. */
  readonly art?: string
  /** 지금 쓸 수 없는가. */
  readonly isOut: boolean
  /** 손가락을 올렸을 때와 보조 기술이 읽을 말. 늘 온값이다. */
  readonly say: string
}): React.JSX.Element {
  return (
    <span
      className={`hud-cell hud-cell--${props.kind}${props.isOut ? ' hud-cell--out' : ''}`}
      title={props.say}
    >
      {/* 위에서 내려와 못 쓰는 만큼을 덮는다. 밝은 만큼이 지금 쓸 수 있는 것이다.
          **0 이면 안 그린다** — 밑동 괘선이 칸 꼭대기에 한 줄 남는다. */}
      {props.shade === 0 ? null : (
        <i className="hud-cell__shade" aria-hidden="true" style={{ blockSize: `${props.shade}%` }} />
      )}
      {props.art === undefined || props.art === '' ? (
        <span className="hud-cell__mark" aria-hidden="true">
          {props.mark}
        </span>
      ) : (
        <img className="hud-cell__art" src={props.art} alt="" />
      )}
      {props.isOut ? (
        <span className="hud-cell__x" aria-hidden="true">
          ✕
        </span>
      ) : null}
      <span className="ds-sr">{props.say}</span>
    </span>
  )
}

/**
 * 좌하단 — 들고 온 소모품을 한 칸씩 쌓는다.
 *
 * **가로로 잇지 않는다** (2026-09-21 요청). 부적 넷을 다 들고 오면 다섯 칸이 되는데,
 * 한 줄로 이으면 도면 폭을 가로지르고 판정 줄과 겹친다 — 세로로 쌓으면 종류가 늘어도
 * 도면 한 열 안에 머문다.
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
        <HudCell
          art={one.art}
          isOut={one.held === 0}
          key={one.tag}
          kind="item"
          mark={one.code}
          say={`${one.label} ${one.held} / ${one.carried}`}
          shade={readSpentPercent(one)}
        />
      ))}
    </div>
  )
}

/**
 * 우하단 — 이 규칙표가 쓰는 재주를 한 칸씩 쌓는다.
 *
 * 온이름은 `title` 과 보조 기술용 말이 싣는다 — 34px 칸에 「유성 낙하」가 안 들어간다.
 * 그림이 아직 없는 재주는 짧은 표기로 떨어진다.
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
      {props.skills.map((one) => (
        <HudCell
          art={one.art}
          isOut={one.left > 0}
          key={one.label}
          kind="skill"
          mark={one.mark}
          say={`${one.label} ${one.left === 0 ? '준비됨' : `${String(one.left)}틱 남음`}`}
          shade={readCooldownPercent(one)}
        />
      ))}
    </div>
  )
}

/**
 * 우상단 — 이번 틱에 발동한 내력의 번호.
 *
 * **없어진 지시선을 대신한다** (2026-09-21 요청). 데스크톱에는 규칙 줄과 도면 말을 잇는
 * 황동 지시선이 있었는데, 세로에서는 규칙 줄이 시트 탭 뒤로 숨을 수 있어 선의 한쪽 끝이
 * 사라져 함께 지웠다(`design/README.md`). 번호는 선이 아니라 **이름**이라 한쪽 끝이
 * 안 보여도 성립한다 — 로그 탭을 보는 동안에도 「지금 03번이 돌았다」가 남는다.
 *
 * 그래서 이 화면의 황동이 다시 셋이다: 도면의 플레이어 말 · 발동한 규칙 줄 · 이 번호.
 * 셋 중 둘은 **같은 사실의 두 끝**이고, 그 이음이 이 부품의 존재 이유다.
 *
 * **글자가 규칙 줄과 같아야 한다.** `formatRuleIndex` 를 함께 쓰는 이유다 — 한쪽이
 * `03` 이고 다른 쪽이 `3` 이면 눈이 두 값을 안 잇는다.
 *
 * @param props 발동한 우선순위. 아무 줄도 안 돌았으면 null.
 * @returns 렌더 트리.
 */
function HudArmed(props: { readonly armed: number | null }): React.JSX.Element {
  return (
    <div className="hud-pin hud-pin--tr">
      {/* **안 돌았어도 자리는 선다.** 사라지면 귀퉁이가 틱마다 깜빡이고, 「없다」와
          「이 화면에 그런 것이 없다」가 같은 그림이 된다. */}
      <span className={`hud-rule${props.armed === null ? ' hud-rule--idle' : ''}`}>
        <span className="hud-rule__tag">내력</span>
        <span className="hud-rule__num">
          {props.armed === null ? '——' : formatRuleIndex(props.armed)}
        </span>
        <span className="ds-sr">
          {props.armed === null
            ? '이번 틱에는 발동한 내력이 없다'
            : `${formatRuleIndex(props.armed)}번 내력이 발동했다`}
        </span>
      </span>
    </div>
  )
}

/**
 * 도면 위 HUD 를 그린다.
 *
 * @param props 겹칠 값 전부.
 * @returns 렌더 트리.
 */
export function PlanHudLayer(props: {
  readonly hud: PlanHud
  /**
   * 이번 틱에 발동한 내력의 우선순위. 아무 줄도 안 돌았으면 null.
   *
   * **없으면 귀퉁이를 비운다.** 추적 결과를 안 들고 있는 화면이 있고(확인용 페이지),
   * 거기서 「——」를 세우면 「안 돌았다」가 사실처럼 보인다 — 모르는 것과 없는 것은
   * 다른 말이고, 이 저장소는 그 구분으로 여러 번 다쳤다.
   */
  readonly armed?: number | null
}): React.JSX.Element {
  return (
    <div className="hud-layer">
      <HudVitals
        hp={props.hud.hp}
        hpMax={props.hud.hpMax}
        isLow={props.hud.isLow}
        statuses={props.hud.statuses}
      />
      {props.armed === undefined ? null : <HudArmed armed={props.armed} />}
      <HudItems items={props.hud.items} />
      <HudSkills skills={props.hud.skills} />
    </div>
  )
}
