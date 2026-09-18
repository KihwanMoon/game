/**
 * StatusBar — 전투 화면 하단 48px. 체력·탕약·현재 위협.
 *
 * 세 값 모두 색 말고 다른 채널을 함께 가진다 — 체력은 숫자, 탕약은 낱개 수, 위협은
 * 글리프와 문구다.
 *
 * **낱말은 화면 전체와 같은 것을 쓴다** (2026-09-18). 소모품 이름의 정본은
 * `content/consumableTags.SLOT_LABELS`(탕약·부적)이고 체력은 `HpGauge` 가 낭독하는
 * 「체력」이다. 여기가 `물약`·`주문서`·`hp` 라 한 화면에 두 이름이 섰다. 표를 가져다
 * 쓰지 않고 적어 두는 것은 의존 방향 때문이다 — 디자인 시스템은 도메인 표를 모른다.
 */
import { HpGauge } from './HpGauge'
import { ResourceCount } from './ResourceCount'
import { ThreatNotice } from './ThreatNotice'

/** 하단 바에서 체력 막대가 차지하는 폭(px). 4px 모듈의 배수다. */
const HP_BAR_WIDTH = 160

/** 소모품 칸의 글리프. */
const SCROLL_GLYPH = '▤'
const POTION_GLYPH = '◍'

/** StatusBar 가 받는 props. */
export interface StatusBarProps {
  readonly hp: number
  readonly hpMax: number
  readonly potions: number
  readonly potionsMax: number
  /** 남은 부적과 실은 수. 탕약과 같은 자리다 — 소모품 현황이 플레이 중에 보여야 한다. */
  readonly scrolls?: number
  readonly scrollsMax?: number
  /** 지금 걸린 위협 문구. 없으면 위협 칸을 그리지 않는다. */
  readonly threat?: string
}

/**
 * 하단 상태 바를 그린다.
 *
 * @param props 체력·탕약·위협.
 * @returns 렌더 트리.
 */
export function StatusBar(props: StatusBarProps): React.JSX.Element {
  return (
    <footer className="ds-statusbar">
      <span className="ds-label">체력</span>
      <HpGauge value={props.hp} max={props.hpMax} width={HP_BAR_WIDTH} />
      <ResourceCount
        label="탕약"
        count={props.potions}
        max={props.potionsMax}
        glyph={POTION_GLYPH}
      />
      {props.scrolls === undefined ? null : (
        <ResourceCount
          label="부적"
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
