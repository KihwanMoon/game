/**
 * StatusBar — 전투 화면 하단 48px. 체력·물약·현재 위협.
 *
 * 세 값 모두 색 말고 다른 채널을 함께 가진다 — 체력은 숫자, 물약은 낱개 수, 위협은
 * 글리프와 문구다.
 */
import { HpGauge } from './HpGauge'
import { ResourceCount } from './ResourceCount'
import { ThreatNotice } from './ThreatNotice'

/** 하단 바에서 체력 막대가 차지하는 폭(px). 4px 모듈의 배수다. */
const HP_BAR_WIDTH = 160

/** 물약 칸의 글리프. */
const SCROLL_GLYPH = '▤'
const POTION_GLYPH = '◍'

/** StatusBar 가 받는 props. */
export interface StatusBarProps {
  readonly hp: number
  readonly hpMax: number
  readonly potions: number
  readonly potionsMax: number
  /** 남은 주문서와 실은 수. 물약과 같은 자리다 — 소모품 현황이 플레이 중에 보여야 한다. */
  readonly scrolls?: number
  readonly scrollsMax?: number
  /** 지금 걸린 위협 문구. 없으면 위협 칸을 그리지 않는다. */
  readonly threat?: string
}

/**
 * 하단 상태 바를 그린다.
 *
 * @param props 체력·물약·위협.
 * @returns 렌더 트리.
 */
export function StatusBar(props: StatusBarProps): React.JSX.Element {
  return (
    <footer className="ds-statusbar">
      <span className="ds-label">hp</span>
      <HpGauge value={props.hp} max={props.hpMax} width={HP_BAR_WIDTH} />
      <ResourceCount
        label="물약"
        count={props.potions}
        max={props.potionsMax}
        glyph={POTION_GLYPH}
      />
      {props.scrolls === undefined ? null : (
        <ResourceCount
          label="주문서"
          count={props.scrolls}
          max={props.scrollsMax ?? 0}
          glyph={SCROLL_GLYPH}
        />
      )}
      {props.threat === undefined ? null : (
        <span className="ds-statusbar__threat">
          <ThreatNotice text={props.threat} tone="danger" />
        </span>
      )}
    </footer>
  )
}
