/**
 * 메타 진행 패널 — **사망해도 남는 것**을 보여준다 (GDD §2.3).
 *
 * 이 게임에서 진 판이 자산이 되는 이유가 화면에 있어야 한다. 죽어도 해금과 도감이 남고,
 * 도감은 적의 규칙표를 그대로 열어 주므로 다음 런의 카운터가 된다 (P1).
 *
 * 도감 줄은 **만난 횟수와 잡은 횟수를 따로 적는다.** "읽었다" 와 "통했다" 는 다르고,
 * 그 차이가 곧 무엇을 아직 못 풀었는지다.
 */
import { Panel, ValueExpr } from '../ds'
import type { MetaSave } from '../core/schemas'
import { getSlotBonus } from '../core/services/manageMeta'

export interface MetaPanelProps {
  readonly meta: MetaSave
  /** 층 기록 보너스를 뺀 기본 규칙 슬롯 수. 상한을 `기본+보너스` 로 적기 위해 받는다. */
  readonly baseSlots: number
}

/** 아직 아무것도 없을 때 자리를 지키는 글. 빈 패널은 고장으로 읽힌다. */
const EMPTY_HINT = '아직 없다 — 판을 한 번 끝내면 쌓인다'

/**
 * 메타 진행 패널을 그린다.
 *
 * @param props 세이브와 기본 슬롯 수.
 * @returns 패널 요소.
 */
export function MetaPanel(props: MetaPanelProps): React.JSX.Element {
  const { meta, baseSlots } = props
  const bonus = getSlotBonus(meta.bestFloor)
  const unlocked = meta.unlockedPerceptions.length + meta.unlockedActions.length
  const isEmpty = meta.bestFloor === 0 && unlocked === 0 && meta.bestiary.length === 0

  return (
    <Panel title="영구 기록" meta="사망해도 남는다" tone="panel" padded scroll>
      <div className="meta">
        <div className="meta__row">
          <span className="meta__label">최고 층</span>
          <ValueExpr text={String(meta.bestFloor)} size="sm" />
        </div>
        <div className="meta__row">
          <span className="meta__label">규칙 슬롯</span>
          <ValueExpr
            text={bonus === 0 ? String(baseSlots) : `${String(baseSlots)} + ${String(bonus)}`}
            size="sm"
          />
        </div>
        <div className="meta__row">
          <span className="meta__label">해금 블록</span>
          <ValueExpr
            text={`인지 ${String(meta.unlockedPerceptions.length)} · 행동 ${String(meta.unlockedActions.length)}`}
            size="sm"
          />
        </div>

        <div className="meta__head">도감</div>
        {meta.bestiary.length === 0 ? (
          <div className="meta__empty">
            <ValueExpr text={isEmpty ? EMPTY_HINT : '만난 적이 없다'} size="sm" dim />
          </div>
        ) : (
          <ul className="meta__list">
            {meta.bestiary.map((record) => (
              <li className="meta__entry" key={record.kindId}>
                <span className="meta__kind">{record.kindId}</span>
                <ValueExpr
                  text={`조우 ${String(record.encounters)} · 처치 ${String(record.defeats)}`}
                  size="sm"
                  dim
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  )
}
