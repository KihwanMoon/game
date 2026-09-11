"""이미 있는 봇 계정의 이름을 봇 것으로 바꾼다.

**앞으로 만들어지는 봇은 `store/bots.create_bot` 이 알아서 붙인다.** 이 스크립트는
그 규칙이 생기기 전에 만들어진 계정을 뒤늦게 맞추는 자리다 — 한 번 돌리면 끝이고,
다시 돌려도 같다.

**왜 필요했나** (2026-09-11, 실제 신고). 봇은 사람과 같은 익명 계정으로 태어나므로
이름이 `user_xxxx` 였다. 그런데 순위표·경매·도감이 전부 이 이름만 적어서, 화면
어디에서도 봇인지 알 수 없었다. 표를 따로 두지 않고 이름에 싣는 이유가 그것이다.

**앞만 바꾼다.** 뒷자리는 이미 유일하므로 이름 충돌이 안 생기고, 같은 계정이 늘 같은
이름으로 남는다 — 순위표에 적힌 이름이 어느 날 통째로 달라지면 「누가 누구였지」가 된다.

    GAME_DATABASE_URL=... uv run python -m scripts.rename_bot_handles
    GAME_DATABASE_URL=... uv run python -m scripts.rename_bot_handles --apply
"""

import argparse
import os
import sys

from psycopg_pool import ConnectionPool

from game.app.store.accounts import BOT_HANDLE_PREFIX, apply_bot_handle
from game.app.store.connection import DATABASE_URL_ENV, create_pool


def list_stale_bots(pool: ConnectionPool) -> tuple[tuple[int, str], ...]:
    """아직 봇 이름이 아닌 봇들.

    Args:
        pool: 연결 풀.

    Returns:
        (계정 id, 지금 이름) 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, handle FROM account WHERE is_bot AND handle NOT LIKE %s ORDER BY id",
            (f"{BOT_HANDLE_PREFIX}%",),
        ).fetchall()
    return tuple((int(row[0]), str(row[1])) for row in rows)


def main(argv: list[str]) -> int:
    """스크립트 진입점.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        종료 코드. 0 이면 성공.
    """
    parser = argparse.ArgumentParser(description="봇 계정 이름을 봇 것으로 바꾼다")
    parser.add_argument("--apply", action="store_true", help="실제로 바꾼다")
    arguments = parser.parse_args(argv)
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    pool = create_pool(url)
    stale = list_stale_bots(pool)
    if not stale:
        print("바꿀 것이 없다 — 봇 이름이 전부 맞다")
        return 0
    for account_id, handle in stale:
        suffix = handle.partition("_")[2]
        print(f"  #{account_id} {handle} → {BOT_HANDLE_PREFIX}{suffix}")
    if not arguments.apply:
        print(f"\n미리보기다 ({len(stale)}개). 실제로 바꾸려면 --apply 를 붙인다.")
        return 0
    for account_id, _handle in stale:
        apply_bot_handle(pool, account_id)
    print(f"\n{len(stale)}개를 바꿨다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
