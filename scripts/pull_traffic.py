"""Cloudflare 가 이미 센 트래픽을 받아 적는다 (U2).

**우리가 세지 않는 이유.** 스택이 Cloudflare Tunnel 뒤라 모든 요청이 엣지를 지나고,
CF 는 그것을 세고 있다. JS beacon(Web Analytics)을 안 고른 이유는 둘이다 — 광고
차단기가 beacon 을 막고, 계측을 브라우저에 맡기면 그 수도 조작 대상이 된다
(`설계/7_변조방지` 의 전제와 같은 자리).

**의존성이 0개다.** 표준 라이브러리의 `urllib` 로 POST 한 번이면 된다. 이 스크립트가
지킴이와 같은 자리에서 돌 수 있는 이유이기도 하다.

**받아 온 뒤 다시 지우지 않는다.** 무료 플랜의 보존 기간이 얼마인지 아직 모르고(존을
2026-09-16 에 옮겨서 그 이전 데이터가 없다), 어느 날 창이 닫히면 그때부터는 우리 표가
유일한 기록이 된다.

    GAME_DATABASE_URL=… CF_ZONE_ID=… CF_API_TOKEN=… uv run python -m scripts.pull_traffic
    … --days 14      # 며칠치를 받아올지 (기본 7)
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta

from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.traffic import save_traffic_day

# CF 자격. 값은 `deploy/.env` 에 있고 커밋되지 않는다.
ZONE_ENV = "CF_ZONE_ID"
TOKEN_ENV = "CF_API_TOKEN"

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

# 한 번에 받아올 최대 일수. CF 는 날짜 묶음을 주므로 창이 커도 왕복은 한 번이다.
DEFAULT_DAYS = 7

# 얼마나 자주 받아오는가(초). **자주 받을 이유가 없다** — 화면이 보는 것은 7일 창이고,
# CF 의 일별 묶음은 하루 단위로 자란다. 30분이면 오늘치가 자라는 것을 충분히 따라간다.
TICK_SEC = 1800

# 응답을 기다릴 시간(초). 지킴이 안에서 돌 수 있으므로 오래 매달리면 안 된다 —
# 트래픽 수치는 다음 차례에 다시 받아도 되는 값이다.
TIMEOUT_SEC = 20

# 일별 묶음 질의. `uniq.uniques` 는 고유 방문, `sum.pageViews` 는 사람이 연 화면 수다.
# 무료 플랜에서 셋 다 온다 (2026-09-18 실측).
QUERY = (
    "query($z:String!,$f:Date!,$t:Date!){viewer{zones(filter:{zoneTag:$z}){"
    "httpRequests1dGroups(limit:100,filter:{date_geq:$f,date_leq:$t},orderBy:[date_ASC])"
    "{dimensions{date} uniq{uniques} sum{requests pageViews}}}}}"
)


def fetch_traffic_days(zone: str, token: str, days: int) -> list[dict]:
    """CF 에서 일별 트래픽을 받아온다.

    Args:
        zone: 존 id.
        token: 읽기 전용 Analytics 토큰.
        days: 오늘을 포함해 며칠을 받아올지.

    Returns:
        날짜 순의 묶음들. 각 원소는 `dimensions`·`uniq`·`sum` 을 든다.

    Raises:
        RuntimeError: CF 가 `errors` 를 돌려주거나 응답 모양이 다를 때. 부르는 쪽이
            다음 차례에 다시 시도할 수 있게 올려 보낸다.
        urllib.error.URLError: 그물이 끊겼을 때.
    """
    # **UTC 로 잡는다.** CF 의 날짜 경계가 UTC 이고, 컨테이너 TZ 가 다르면 창이 하루
    # 밀려 가장 이른 날을 통째로 빠뜨린다.
    today = datetime.now(UTC).date()
    body = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "z": zone,
                "f": str(today - timedelta(days=days - 1)),
                "t": str(today),
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310  고정 https 상수라 스킴 검사가 무의미하다
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"CF 가 거절했다: {payload['errors']}")
    zones = payload.get("data", {}).get("viewer", {}).get("zones", [])
    if not zones:
        # 존이 안 보이는 것과 트래픽이 0 인 것은 다르다. 토큰 권한이 좁거나 존 id 가
        # 틀린 쪽이므로, 조용히 0 으로 적으면 「아무도 안 왔다」로 굳는다.
        raise RuntimeError("존을 못 읽었다 — 토큰 권한이나 CF_ZONE_ID 를 확인한다")
    return list(zones[0].get("httpRequests1dGroups", []))


def save_traffic_rows(pool: ConnectionPool, rows: list[dict]) -> int:
    """받아온 묶음을 표에 적는다.

    Args:
        pool: 연결 풀.
        rows: `fetch_traffic_days` 가 낸 묶음들.

    Returns:
        적은 날 수.
    """
    written = 0
    for row in rows:
        day_text = row.get("dimensions", {}).get("date", "")
        if not day_text:
            continue
        save_traffic_day(
            pool,
            date.fromisoformat(day_text),
            visits=int(row.get("uniq", {}).get("uniques", 0)),
            views=int(row.get("sum", {}).get("pageViews", 0)),
            requests=int(row.get("sum", {}).get("requests", 0)),
        )
        written += 1
    return written


def run_pull(pool: ConnectionPool, zone: str, token: str, days: int) -> int:
    """받아와 적는 한 차례.

    Args:
        pool: 연결 풀.
        zone: 존 id.
        token: 토큰.
        days: 며칠치.

    Returns:
        적은 날 수. 못 받아 왔으면 0.
    """
    try:
        rows = fetch_traffic_days(zone, token, days)
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        # **막지 않는다.** 이 값은 다음 차례에 받아도 되는 것이고, 여기서 예외를 올리면
        # 같은 자리에서 도는 지킴이가 함께 죽는다.
        print(f"[트래픽] 못 받았다: {error}", file=sys.stderr, flush=True)
        return 0
    return save_traffic_rows(pool, rows)


def main() -> int:
    """명령행 진입점.

    Returns:
        종료 코드. 자격이 없으면 2, 그 밖에는 0.
    """
    parser = argparse.ArgumentParser(description="Cloudflare 트래픽을 받아 적는다")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="며칠치를 받아올지")
    parser.add_argument("--loop", action="store_true", help=f"{TICK_SEC}초마다 계속 받는다")
    args = parser.parse_args()

    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    zone = os.environ.get(ZONE_ENV, "").strip()
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 2
    if not zone or not token:
        print(f"{ZONE_ENV} 나 {TOKEN_ENV} 가 없다 — deploy/.env 를 본다", file=sys.stderr)
        return 2

    pool = create_pool(url)
    if not args.loop:
        written = run_pull(pool, zone, token, args.days)
        print(f"[트래픽] {written}일치를 적었다", flush=True)
        return 0

    # **못 받아도 안 죽는다.** `run_pull` 이 예외를 삼키고 0 을 돌려주므로, CF 가
    # 잠깐 안 뜨거나 토큰이 만료돼도 다음 차례에 다시 시도한다 — 죽으면 그 뒤로
    # 아무도 안 받아 오는데, 그 사실이 화면에는 「사람이 안 온다」로 보인다.
    print(f"[트래픽] 시작 — {TICK_SEC}초마다 받는다", flush=True)
    while True:
        written = run_pull(pool, zone, token, args.days)
        print(f"[트래픽] {written}일치", flush=True)
        time.sleep(TICK_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
