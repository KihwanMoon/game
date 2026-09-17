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
 * 광고 탭에 세우는 자리 수.
 *
 * **셋이다.** 하나면 탭을 따로 열 이유가 없고, 자리마다 152px 을 띄우므로 넷이면
 * 한 화면에 첫 자리밖에 안 들어온다 — 스크롤해야 보이는 배너는 없는 것과 같다.
 */
const PANEL_SLOTS = 3

/** 탭 머리에 적는 말. **이 탭이 무엇인지 먼저 말한다** — 안 적으면 내용으로 읽힌다. */
const PANEL_NOTE = '이 자리는 광고 자리다. 아래 문의로 연락하면 여기에 걸 수 있다.'

/**
 * 배너 자리를 그린다.
 *
 * @param props 어디에 서는가. `inline` 이면 탭 안에 그냥 선다 — 바닥에 안 붙는다.
 * @returns 자리 요소.
 */
export function AdSlot(props: { readonly inline?: boolean } = {}): React.JSX.Element {
  return (
    <aside
      className={`battle__ad${props.inline === true ? ' battle__ad--inline' : ''}`}
      aria-label={LABEL}
    >
      <a className="battle__ad-link" href={`mailto:${CONTACT}?subject=${LABEL}`}>
        <img className="battle__ad-mark" src="/brand/mark-head.webp" alt="" width="160" height="80" />
        <span className="battle__ad-text">{LABEL}</span>
      </a>
    </aside>
  )
}

/**
 * 광고 탭 본문 — 자리 여럿을 정책 여백만큼 띄워 세운다.
 *
 * **왜 탭인가** (2026-09-17 요청). 바닥 한 자리는 화면에서 빼 오는 높이라 하나가 한계다.
 * 탭은 **사람이 눌러서 오는 자리**라 여러 개를 세워도 판을 가리지 않는다 — 구글이 막는
 * 것은 「내용을 가로막는 배치」이지 광고가 여럿인 것이 아니다.
 *
 * **기본 탭이 아니다.** 순서는 맨 앞이지만 판이 열릴 때 뜨는 것은 상태 탭이다
 * (`portraitSheet.INITIAL_TAB`). 열자마자 광고가 펴지면 그것이 곧 가로막는 배치다.
 *
 * 여백은 자리끼리도, 위아래 가장자리에도 152px 이다 — 구글이 요구하는 150px 을 이
 * 저장소의 4px 눈금으로 올려 맞춘 값이다.
 *
 * @returns 탭 본문 요소.
 */
export function AdPanel(): React.JSX.Element {
  return (
    <div className="battle__ads">
      <p className="battle__ads-note">{PANEL_NOTE}</p>
      {Array.from({ length: PANEL_SLOTS }, (_unused, at) => (
        <AdSlot key={at} inline />
      ))}
    </div>
  )
}
