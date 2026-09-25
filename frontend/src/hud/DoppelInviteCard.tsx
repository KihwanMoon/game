/**
 * 둔갑 권유 — 첫 장을 깬 뒤 한 번만 묻는다 (2026-09-25).
 *
 * **기본은 꺼 둔 채다.** 둔갑은 내 내력으로 싸우므로 관전하는 사람이 내 해답을 어느 정도
 * 읽게 된다 — 켜는 사람이 그 대가를 알고 켜야 한다(`schema.sql` 의 `doppel_opt_in`). 그런데
 * 스위치가 서생 탭 깊숙이 있어서 아무도 켜지 않았다. 그래서 끄는 기본은 두고, **대가와 얻는
 * 것을 한 장에 적어 한 번 묻는다.** 고르면 다시 안 묻는다 — 두 번째부터는 방해다.
 *
 * **저절로 안 닫힌다.** 장 카드는 읽는 글이라 저절로 닫히지만, 이것은 고르는 일이다. 자리를
 * 비운 사이에 닫히면 고른 적 없는 선택이 「안 세운다」로 남는다.
 */
import { Button } from '../ds'

/** 이 기기에서 이미 물었는가. **계정이 아니라 기기에 둔다** — 서버에 칸을 늘릴 일이 아니다. */
export const DOPPEL_INVITE_KEY = 'doppel.invite.asked.v1'

export interface DoppelInviteCardProps {
  /** 고른 쪽. 참이면 세운다. */
  readonly onChoose: (isOn: boolean) => void
}

/** 무엇을 얻고 무엇을 내주는가. 한 장에 둘을 같이 적는다. */
const TRADE_TEXT =
  '깊은 장에서 쓰러지면 내 내력이 남의 판에 둔갑으로 선다. 그 둔갑이 이긴 만큼 물러날 때 활자가 들어오고, 둔갑 순위표에 이름이 선다.'
const COST_TEXT = '대신 둔갑은 내 내력 그대로 싸우므로, 관전하는 사람이 내 해답을 어느 정도 읽게 된다.'
const LATER_TEXT = '서생 탭에서 언제든 바꿀 수 있다.'

/**
 * 둔갑 권유 카드를 그린다.
 *
 * @param props 고른 쪽을 받는 처리기.
 * @returns 카드 요소.
 */
export function DoppelInviteCard(props: DoppelInviteCardProps): React.JSX.Element {
  return (
    <div className="story-card" role="dialog" aria-label="내 내력을 남의 장에 세울까">
      <div className="story-card__sheet">
        <header className="story-card__head">
          <span className="ds-label">둔갑</span>
          <h2 className="story-card__title">내 내력을 남의 장에 세울까</h2>
        </header>
        <p>{TRADE_TEXT}</p>
        <p>{COST_TEXT}</p>
        <p>{LATER_TEXT}</p>
        <div className="story-card__foot">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              props.onChoose(false)
            }}
          >
            안 세운다
          </Button>
          <Button
            size="sm"
            variant="secondary"
            glyph="◉"
            onClick={() => {
              props.onChoose(true)
            }}
          >
            세운다
          </Button>
        </div>
      </div>
    </div>
  )
}
