/**
 * 층 보상 선택 — 기획의 고리에서 빠져 있던 한 칸 (GDD §2.2).
 *
 * 고리는 `방 입장 → 전투 → 클리어 → **보상 선택** → 규칙 편집 → 다음 방` 인데, 제품에는
 * 보상 선택이 없었다 (2026-09-11 실제 신고: 「5층 이후에 보상이 안 들어온거같아」 —
 * 재 보니 층과 무관하게 원래 그랬다).
 *
 * **여기서 고른 것이 규칙 편집으로 이어진다.** 확장 슬롯을 고르면 줄이 하나 늘고, 그
 * 줄에 무엇을 적을지가 다시 질문이 된다 — 그것이 이 칸의 존재 이유다 (§6.2).
 *
 * 훅을 안 쓴다. 훅 안에 있으면 렌더 검사가 문구를 못 본다 — 이 저장소의 검사는 jsdom
 * 없이 돈다.
 */
import type { RewardOfferView } from '../storage'
import { ValueExpr } from '../ds/ValueExpr'

/** 축 이름을 사람이 읽는 말로. 서버가 보낸 id 를 그대로 적으면 화면 한 칸만 영문이 된다. */
const STAT_LABELS: ReadonlyMap<string, string> = new Map([
  ['rule_slots', '규칙 줄'],
  ['cpu_budget', 'cpu'],
  ['attack', '공격'],
  ['defense', '방어'],
  ['hp_max', '최대 체력'],
  ['POTION', '물약 충전'],
])

/** RewardChoice 가 받는 props. */
export interface RewardChoiceProps {
  /** 고를 층. 0 이면 고를 것이 없다. */
  readonly floor: number
  readonly offers: readonly RewardOfferView[]
  /** 고르는 중인가. 두 번 눌러 두 번 고르는 것을 막는다. */
  readonly isBusy?: boolean
  readonly onTake: (rewardId: string) => void
}

/**
 * 보상 후보 한 장의 효과를 적는다.
 *
 * @param offer 후보.
 * @returns `규칙 줄 +1` 꼴.
 */
export function formatRewardEffect(offer: RewardOfferView): string {
  const label = STAT_LABELS.get(offer.targetStat) ?? offer.targetStat
  return `${label} +${String(offer.amount)}`
}

/**
 * 층 보상 선택을 그린다.
 *
 * @param props 층·후보·처리기.
 * @returns 렌더 트리. 고를 것이 없으면 아무것도 안 그린다.
 */
export function RewardChoice(props: RewardChoiceProps): React.JSX.Element | null {
  if (props.floor <= 0 || props.offers.length === 0) {
    return null
  }
  return (
    <div className="reward">
      <div className="reward__head">{`${String(props.floor)}층 보상 — 하나를 고른다`}</div>
      <div className="reward__row">
        {props.offers.map((offer) => (
          <button
            className="reward__card"
            key={offer.rewardId}
            type="button"
            disabled={props.isBusy === true}
            onClick={() => {
              props.onTake(offer.rewardId)
            }}
          >
            <span className="reward__name">{offer.labelKo}</span>
            <span className="reward__effect">{formatRewardEffect(offer)}</span>
          </button>
        ))}
      </div>
      {/* **고르기 전에는 다음 층이 안 열린다는 사실을 적는다.** 안 적으면 카드가 장식으로
          읽히고, 그냥 지나친 사람은 보상이 또 안 들어왔다고 느낀다. */}
      <ValueExpr text="고르면 다음 층부터 붙는다" size="sm" dim />
    </div>
  )
}
