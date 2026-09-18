"""하루치 트래픽 원장 — 받아 적고, 창으로 읽는다 (U2).

**우리가 세지 않는다.** 스택이 Cloudflare Tunnel 뒤라 모든 요청이 엣지를 지나고 CF 가
이미 세고 있다. JS beacon 을 심는 쪽(Web Analytics)을 안 고른 이유는 둘이다 — 광고
차단기가 beacon 을 막고, 계측을 브라우저에 맡기면 그 수도 조작 대상이 된다
(`설계/7_변조방지` 의 전제와 같은 자리).

**출처를 값과 함께 저장한다.** 언젠가 계측을 갈아 끼울 때 같은 날에 두 출처가 나란히
남아야 한다. 덮어쓰면 그날을 기점으로 선이 점프하고, 몇 달 뒤에는 아무도 이유를 모른다.

**계정 수와 다른 것을 센다.** `account` 는 출격을 누른 사람이고 여기는 열어 본 사람이다.
둘을 나란히 놓아야 「오는데 안 한다」와 「아예 안 온다」가 갈린다.
"""

from dataclasses import dataclass
from datetime import date

from psycopg_pool import ConnectionPool

# 지금 쓰는 계측의 이름. 갈아 끼우면 이 값이 아니라 **새 값**을 쓴다 — 옛 행을 고치지
# 않아야 두 시대를 나란히 볼 수 있다.
CLOUDFLARE_SOURCE = "cloudflare"


@dataclass(frozen=True)
class TrafficWindow:
    """한 창(기간) 동안의 트래픽 합.

    `days` 를 함께 드는 이유는 **화면이 기간을 밝혀야 하기 때문**이다. 누적 절대값은
    출처를 바꾸는 순간 점프해 예전 값과 이어 붙일 수 없고, 기간이 적혀 있지 않으면
    보는 사람이 그것을 알아챌 방법이 없다.
    """

    days: int
    visits: int
    views: int
    requests: int
    source: str


def save_traffic_day(
    pool: ConnectionPool,
    day: date,
    visits: int,
    views: int,
    requests: int,
    source: str = CLOUDFLARE_SOURCE,
) -> None:
    """하루치를 적는다. 같은 날·같은 출처를 다시 적으면 덮어쓴다.

    **덮어쓰는 것이 맞다.** 오늘치는 하루가 끝나기 전까지 계속 자라므로, 한 번 적고 마는
    구조면 오늘이 늘 모자란 수로 남는다. 출처가 다르면 다른 행이라 서로를 안 덮는다.

    Args:
        pool: 연결 풀.
        day: 대상 날짜 (UTC 기준).
        visits: 고유 방문 수.
        views: 페이지뷰 수.
        requests: 요청 수.
        source: 계측 출처 이름.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO traffic_day (day, source, visits, views, requests)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (day, source) DO UPDATE SET"
            " visits = EXCLUDED.visits, views = EXCLUDED.views,"
            " requests = EXCLUDED.requests, at = now()",
            (day, source, visits, views, requests),
        )


def read_traffic_window(
    pool: ConnectionPool, days: int = 7, source: str = CLOUDFLARE_SOURCE
) -> TrafficWindow:
    """최근 며칠치를 합쳐 읽는다.

    **오늘을 넣는다.** 오늘치가 아직 자라는 중이라 어제보다 작은 것은 정상이고, 빼면
    「지금 사람이 오는가」에 하루 늦게 답하게 된다.

    Args:
        pool: 연결 풀.
        days: 오늘을 포함해 며칠을 볼 것인가.
        source: 계측 출처 이름.

    Returns:
        합. 행이 하나도 없으면 전부 0 이다 — 계측을 아직 안 붙였거나 못 받아 온 상태이며,
        그것과 「아무도 안 왔다」는 화면이 구별해야 한다(`visits` 0 이면 비율을 안 적는다).
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT coalesce(sum(visits), 0), coalesce(sum(views), 0),"
            " coalesce(sum(requests), 0)"
            " FROM traffic_day"
            # 같은 이유로 UTC 다 — 표에 적힌 날짜가 CF 의 UTC 날짜이므로,
            # 서버 TZ 로 창을 자르면 경계일이 들락거린다.
            " WHERE source = %s AND day > (now() AT TIME ZONE 'utc')::date - %s::int",
            (source, days),
        ).fetchone()
    if row is None:
        return TrafficWindow(days=days, visits=0, views=0, requests=0, source=source)
    return TrafficWindow(
        days=days,
        visits=int(row[0]),
        views=int(row[1]),
        requests=int(row[2]),
        source=source,
    )


def compute_conversion_pct(visits: int, played: int) -> int:
    """들른 사람 중 몇 %가 판을 냈는가.

    **정수로 센다.** 이 저장소는 부동소수를 피한다(TDD §1.1) — 화면에 적을 것은 한 자리
    정수이고, 백분율을 실수로 들고 다니면 같은 값이 기기마다 다르게 반올림된다.

    **비율이 절대수보다 오래 간다.** 계측을 갈아 끼우면 분모가 점프하지만 비율은 뜻이
    같다 — 「열 명 중 둘이 논다」는 출처가 어디든 같은 말이다.

    Args:
        visits: 들른 사람 수.
        played: 그중 판을 낸 사람 수.

    Returns:
        0~100 의 정수. 들른 사람이 0 이면 0 — 부르는 쪽이 「아직 모른다」와 「아무도 안
        했다」를 가르려면 `visits` 를 함께 봐야 한다.
    """
    if visits <= 0:
        return 0
    return played * 100 // visits
