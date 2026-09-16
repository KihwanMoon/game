/**
 * AffixList — 옵션 줄 목록 하나. **네 화면이 베껴 쓰던 `invd__affixes` 를 한 곳으로 모은다.**
 *
 * 가방·재주·저잣거리·소모품이 각자 같은 `ul` 을 짓고 있었다. 모양이 같아도 집이 넷이면
 * 한 곳만 고친 날 화면마다 다른 줄이 서고, 「옵션 하나에 한 줄」이라는 약속이 화면마다
 * 다른 코드로 지켜지고 있었다 — 약속이 넷이면 그것은 이미 약속이 아니다.
 *
 * 바깥(컨테이너·키)은 `DataList` 가 지고, 여기서는 **접사 목록이라서 달라지는 셋**만
 * 박아 둔다. 셋 다 실제로 한 번씩 깨졌던 것이다.
 *
 * 1. **키에 자리(index)가 든다.** 접사는 값이 중복될 수 있다(서버에서 실제로 같은 줄이
 *    둘 나온다). 값만으로 키를 만들면 React 가 같은 줄로 보고 하나를 지운다.
 * 2. **비면 아무것도 안 그린다.** `DataList` 는 빈 목록 문구를 강제하지만, 옵션이 없는
 *    것은 「아직 안 왔다」가 아니라 **원래 없는 것**이다 — 「없다」를 적으면 상세에 아무
 *    뜻 없는 줄이 하나 늘어난다. 그래서 길이를 여기서 먼저 보고 null 을 돌려준다.
 * 3. **거르기·페이지를 안 켠다.** 줄 오른쪽 단추(가방의 「다시 찍기」)는 **접사의 자리**로
 *    서버에 말한다. 보이는 줄을 거르기나 페이지가 줄이면 누른 줄과 갈리는 줄이 어긋나
 *    **옆 줄을 갈아 버린다** — 활자를 내고 되돌릴 수 없는 사고다.
 *
 * **접사가 아닌 줄도 담는다.** 사거리는 접사가 아니라 필드라 다시 찍을 수 없고(단추가
 * 없다), 재주 상세는 계수·쿨타임을 같은 모양으로 적는다. 줄이 무엇인지는 부르는 쪽이
 * 정하고, 이 틀은 **줄의 모양**만 진다.
 */
import type { ReactNode } from 'react'

import { ValueExpr } from '../ds'

import { DataList } from './DataList'

/**
 * 빈 목록 문구. **화면에 안 나간다** — 비면 `AffixList` 가 그 위에서 null 을 돌려주기
 * 때문이다. `DataList` 가 문구를 강제하므로 자리만 채운다.
 */
const NEVER_EMPTY_TEXT = '옵션이 없다'

/** 옵션 줄 하나. */
export interface AffixLine {
  /** 적을 말. 실측값이 병기된 채로 온다 — 「예리함 · 공격력 +3」. */
  readonly text: string
  /**
   * 줄 오른쪽에 설 것. 「다시 찍기」처럼 **그 줄에만 붙는** 조작이다.
   *
   * 없으면 값만 선다 — 사거리처럼 접사가 아닌 줄이 그렇다.
   */
  readonly trail?: ReactNode
}

/** AffixList 가 받는 것. */
export interface AffixListProps {
  /** 그릴 줄들. 비면 목록 자체가 안 선다. */
  readonly lines: readonly AffixLine[]
  /**
   * 역할 이름. 주면 목록 왼쪽에 박힌다 — 「끼면」·「쓰면」.
   *
   * 소모품은 성격이 다른 셋(끼면 / 쓰면 / 자동)을 같은 모양으로 적으므로, 이름이 없으면
   * 어느 것이 끼고 있을 때의 값인지 읽는 사람이 짐작해야 한다.
   */
  readonly role?: string
}

/**
 * 옵션 줄 목록을 그린다.
 *
 * @param props 줄들과 역할 이름.
 * @returns 목록. 줄이 하나도 없으면 null — 빈 목록 문구를 대신 적지 않는다.
 */
export function AffixList(props: AffixListProps): React.JSX.Element | null {
  if (props.lines.length === 0) {
    return null
  }
  const list = (
    <DataList<AffixLine>
      items={props.lines}
      // 자리를 앞에 둔다. 같은 글자가 둘 와도 키가 갈리고, 사거리 줄이 접사 첫 줄과
      // 겹치지 않는다.
      rowKey={(line, index) => `${String(index)}:${line.text}`}
      renderRow={(line) => (
        <>
          <ValueExpr text={line.text} size="sm" />
          {line.trail}
        </>
      )}
      emptyText={NEVER_EMPTY_TEXT}
      listClass="invd__affixes"
      rowClass="invd__affix"
    />
  )
  if (props.role === undefined) {
    return list
  }
  return (
    <div className="invd__role">
      <span className="invd__role-name">{props.role}</span>
      {list}
    </div>
  )
}
