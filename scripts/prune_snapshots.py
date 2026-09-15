"""읽을 수 없게 된 몬스터 스냅샷을 지운다.

**티켓 하나가 스냅샷 서른 몇 개를 남기고, 봇은 쉬지 않고 돈다.** 두 주 만에 34만 개가
쌓여 `monster_snapshot` 이 DB 의 57%(184MB)를 차지했다 — 그중 **99.2%는 아무도 읽을 수
없는 것**이었다.

읽는 곳이 넷뿐이라 그렇다.

    제출 때  전리품 판정 (`api/loot_service`) · 몬스터 처치 (`api/monster_service`)
    나중에   리플레이 (`api/routes/replay`) · 봇 리플레이 (`api/routes/admin_bot_detail`)

앞의 둘은 **지금 제출하는 티켓**만 본다. 뒤의 둘은 `HISTORY_LIMIT`·`RECENT_RUN_LIMIT`
가 **계정당 최근 10판**으로 잘라 두었으므로, 열한 번째로 밀려난 판의 스냅샷은 어떤
경로로도 못 읽는다. 그래서 남길 것은 둘뿐이다.

    ① 아직 제출 안 된 티켓  — 지금 돌고 있는 판이다. 지우면 그 제출이 재시뮬에 실패한다
    ② 계정별 최근 10판      — 리플레이가 닿는 전부

**지우고 나면 `VACUUM FULL` 을 따로 돌려야** 디스크가 돌아온다. 이 스크립트는 안 돌린다 —
그 동안 표가 잠기고, 언제 잠글지는 사람이 정할 일이다.

    GAME_DATABASE_URL=... uv run python -m scripts.prune_snapshots
    GAME_DATABASE_URL=... uv run python -m scripts.prune_snapshots --apply
"""

import argparse
import os
import sys

from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool

# 리플레이가 닿는 판 수. **`api/routes/replay.HISTORY_LIMIT` 과 같은 값이어야 한다** —
# 저쪽이 늘면 여기가 먼저 지운 뒤에 목록이 그것을 찾게 된다.
KEEP_RUNS = 10

# 남길 티켓을 고르는 절. 두 갈래를 합친다 (아직 안 쓴 티켓 · 최근 10판).
KEEP_SQL = (
    "SELECT t.id FROM run_ticket t"
    " WHERE NOT EXISTS (SELECT 1 FROM run_submission s WHERE s.ticket_id = t.id)"
    " UNION"
    " SELECT ticket_id FROM ("
    "   SELECT s.ticket_id,"
    "          row_number() OVER (PARTITION BY t.account_id"
    "                             ORDER BY s.submitted_at DESC, s.id DESC) AS rn"
    "     FROM run_submission s JOIN run_ticket t ON t.id = s.ticket_id"
    " ) r WHERE r.rn <= %s"
)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="못 읽는 몬스터 스냅샷을 지운다")
    parser.add_argument("--apply", action="store_true", help="실제로 지운다. 없으면 세기만 한다")
    parser.add_argument("--keep", type=int, default=KEEP_RUNS, help="계정당 남길 판 수")
    return parser.parse_args(argv)


def count_targets(pool: ConnectionPool, keep: int) -> tuple[int, int]:
    """남길 것과 지울 것을 센다.

    Args:
        pool: 연결 풀.
        keep: 계정당 남길 판 수.

    Returns:
        (남길 스냅샷 수, 지울 스냅샷 수).
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FILTER (WHERE ticket_id IN (" + KEEP_SQL + ")),"
            "       count(*) FILTER (WHERE ticket_id NOT IN (" + KEEP_SQL + "))"
            " FROM monster_snapshot",
            (keep, keep),
        ).fetchone()
    if row is None:
        return (0, 0)
    return (int(row[0]), int(row[1]))


def apply_prune(pool: ConnectionPool, keep: int) -> int:
    """못 읽는 스냅샷을 지운다.

    Args:
        pool: 연결 풀.
        keep: 계정당 남길 판 수.

    Returns:
        지운 행 수.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "DELETE FROM monster_snapshot WHERE ticket_id NOT IN (" + KEEP_SQL + ")",
            (keep,),
        )
        return int(cursor.rowcount)


def main(argv: list[str]) -> int:
    """스크립트 진입점.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        종료 코드. 0 이면 성공.
    """
    arguments = parse_arguments(argv)
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    pool = create_pool(url)
    kept, doomed = count_targets(pool, arguments.keep)
    print(f"  남길 스냅샷 {kept}개 — 안 쓴 티켓과 계정당 최근 {arguments.keep}판")
    print(f"  지울 스냅샷 {doomed}개 — 어떤 화면도 못 읽는 것")
    if doomed == 0:
        print("  지울 것이 없다")
        return 0
    if not arguments.apply:
        print("  --apply 를 붙이면 지운다")
        return 0
    removed = apply_prune(pool, arguments.keep)
    print(f"  {removed}개를 지웠다. **디스크는 아직 안 돌아온다** —")
    print("  VACUUM (FULL, ANALYZE) monster_snapshot; 을 따로 돌린다 (그 동안 표가 잠긴다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
