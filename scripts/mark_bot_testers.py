"""층이 깊은 봇 몇을 테스터로 표시한다.

**표시는 화면 순서를 위한 것이지 G1 의 분모가 아니다.** 표시된 줄은 테스터 화면 맨 위에
고정되므로, 층 깊이 간 봇을 지켜보려는 사람이 목록을 훑지 않아도 된다. G1 이 세는 것은
사람뿐이고(`store/testers.count_testers`, `scripts/report_g1`) 그 규율은 여기서도 안
바뀐다 — 게이트가 묻는 「첫 패배 후 규칙을 고쳐 재도전했는가」는 사람에게만 뜻이 있는
질문이라, 봇을 세면 그 수가 「러너가 몇 번 돌았는가」가 된다.

**층은 `meta_save` 의 `best_floor` 로 본다.** `entity_record.reached_floor` 는 개체의
기록이지 계정의 기록이 아니고, 봇 화면(`store/bot_view`)이 이미 이 값을 쓴다 — 두 곳이
다른 수를 보면 「왜 이 봇이 뽑혔지」에 답할 수 없다.

**되풀이해 돌리라고 만든 것이다.** 봇은 계속 돌아 층이 바뀌므로, 표시를 한 번 박아 두면
얼마 안 가 「깊은 봇」이 아니게 된다. 다시 돌리면 예전 표시를 지우고 지금 깊은 쪽에
붙인다 — 사람 계정의 표시는 건드리지 않는다.

    GAME_DATABASE_URL=... uv run python -m scripts.mark_bot_testers
    GAME_DATABASE_URL=... uv run python -m scripts.mark_bot_testers --count 3
    GAME_DATABASE_URL=... uv run python -m scripts.mark_bot_testers --clear
"""

import argparse
import os
import sys

from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.testers import apply_tester_mark

# 몇을 표시할지의 기본값. 로드맵의 테스터 수(5)와 **일부러 다르다** — 이 표시는 G1 의
# 분모가 아니므로 그 수를 따라갈 이유가 없고, 따라가면 화면에서 둘이 같은 것으로 읽힌다.
DEFAULT_COUNT = 3


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="층이 깊은 봇을 테스터로 표시한다")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="표시할 봇 수")
    parser.add_argument("--clear", action="store_true", help="봇 표시를 전부 지운다")
    return parser.parse_args(argv)


def list_deep_bots(pool: ConnectionPool, count: int) -> tuple[tuple[int, str, int], ...]:
    """층이 깊은 순으로 봇을 읽는다.

    **같은 층이면 계정 번호가 작은 쪽이다.** 순서를 안 박아 두면 같은 층이 여럿일 때
    돌릴 때마다 다른 봇이 뽑히고, 그러면 「어제 표시한 봇이 왜 빠졌지」에 답할 수 없다.

    Args:
        pool: 연결 풀.
        count: 읽을 수.

    Returns:
        (계정 id, 이름, 층) 튜플들. 봇이 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT b.account_id, b.label,"
            " COALESCE((SELECT (m.payload->>'best_floor')::int FROM meta_save m"
            "   WHERE m.account_id = b.account_id), 0) AS best_floor"
            " FROM bot_profile b"
            " ORDER BY best_floor DESC, b.account_id"
            " LIMIT %s",
            (count,),
        ).fetchall()
    return tuple((int(row[0]), str(row[1]), int(row[2])) for row in rows)


def list_marked_bots(pool: ConnectionPool) -> tuple[int, ...]:
    """지금 표시돼 있는 봇들.

    Args:
        pool: 연결 풀.

    Returns:
        계정 id 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id FROM account WHERE is_bot AND is_tester ORDER BY id"
        ).fetchall()
    return tuple(int(row[0]) for row in rows)


def apply_deep_bot_marks(pool: ConnectionPool, count: int) -> tuple[tuple[int, str, int], ...]:
    """깊은 봇만 표시로 남긴다.

    **먼저 지우고 붙인다.** 붙이기만 하면 예전에 깊었던 봇이 표시된 채로 남아, 화면
    맨 위가 「한때 깊었던 봇들」이 된다.

    Args:
        pool: 연결 풀.
        count: 표시할 수.

    Returns:
        표시한 (계정 id, 이름, 층) 튜플들.
    """
    picked = list_deep_bots(pool, count)
    stale = tuple(one for one in list_marked_bots(pool) if one not in {item[0] for item in picked})
    apply_tester_mark(pool, stale, is_tester=False)
    apply_tester_mark(pool, tuple(item[0] for item in picked), is_tester=True)
    return picked


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
    if arguments.clear:
        marked = list_marked_bots(pool)
        apply_tester_mark(pool, marked, is_tester=False)
        print(f"봇 표시 {len(marked)}개를 지웠다")
        return 0
    picked = apply_deep_bot_marks(pool, arguments.count)
    if not picked:
        print("표시할 봇이 없다")
        return 0
    for account_id, label, floor in picked:
        print(f"  {label} (#{account_id}) — {floor}층")
    print(f"봇 {len(picked)}개를 표시했다. **G1 에는 안 센다** — 세는 것은 사람뿐이다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
