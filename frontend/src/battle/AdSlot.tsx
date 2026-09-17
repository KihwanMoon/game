/**
 * 배너 자리 — **지금은 우리 것이 서 있다** (2026-09-17).
 *
 * 광고망을 붙일지는 아직 안 정했고 트래픽도 모자란다(월 484, EthicalAds 기준 5만).
 * 그래도 자리를 먼저 잡는 이유는 **나중에 어느 망을 고르든 화면을 다시 안 짜기 위해서**다.
 * 비워 두면 그때 높이가 바뀌고, 높이가 바뀌면 도면과 로그의 배분이 흔들린다.
 *
 * **왜 하단인가.** 구글 정책이 「게임 창 가장자리에서 최소 150px」을 요구한다. 실측으로
 * 상단은 도면까지 52px 뿐이라 **구글을 영영 못 쓰는 자리**이고, 하단은 268px 이라 셋
 * (구글·EthicalAds·직접 스폰서) 다 통과한다.
 *
 * **왜 세로에서만인가.** 가로 배치는 높이가 559px 이하라(`--layout-mode:landscape`)
 * 내줄 158px 이 없다. 이 부품이 세로 전용 화면 안에 있어서 그 조건이 저절로 지켜진다.
 *
 * 채워 두는 것은 **우리 각인과 「광고문의」**다. 빈 상자를 두면 고장으로 읽히고, 남의
 * 스크립트를 들이지 않고도 자리가 무엇인지 말한다 — 직접 스폰서로 가는 길이기도 하다.
 */

/** 문의가 갈 곳. 약관·방침의 연락처와 같아야 한다 — 두 곳이 갈리면 어느 쪽이 맞는지 모른다. */
const CONTACT = 'mkihwan.dev@gmail.com'

/** 자리에 적는 말. */
const LABEL = '광고문의'

/**
 * 배너 자리를 그린다.
 *
 * @returns 자리 요소.
 */
export function AdSlot(): React.JSX.Element {
  return (
    <aside className="battle__ad" aria-label={LABEL}>
      <a className="battle__ad-link" href={`mailto:${CONTACT}?subject=${LABEL}`}>
        <img className="battle__ad-mark" src="/brand/mark-head.webp" alt="" width="160" height="80" />
        <span className="battle__ad-text">{LABEL}</span>
      </a>
    </aside>
  )
}
