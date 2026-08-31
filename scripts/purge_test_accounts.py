"""검사·탐침이 만든 계정을 지운다.

**왜 필요했나.** `deploy/docker-compose.yml` 의 `test` 서비스가 프로덕션과 같은 DB 를
쓰고 있었다. 그래서 검사가 만든 계정·아이템·매물이 실제 서비스에 쌓였고, 검사용 계정
하나가 **관리자 권한까지 갖고 있었다** — 검사는 관리자 경로를 확인해야 하므로 스스로를
승격시킨다. 원인은 끊었고(검사는 이제 `game_test` 를 쓴다), 이 스크립트는 이미 쌓인
것을 치운다.

**남길 계정을 이름으로 적는다.** "지울 것" 을 고르는 방식이면 새 계정이 생길 때마다
목록을 고쳐야 하고, 한 번 빠뜨리면 남의 계정이 지워진다. 남길 것을 적으면 빠뜨렸을 때
지워지는 쪽이 아니라 남는 쪽으로 실패한다.

기본은 **미리보기**다. 지우려면 `--apply` 를 붙인다.

    docker compose run --rm dev uv run python -m scripts.purge_test_accounts
    docker compose run --rm dev uv run python -m scripts.purge_test_accounts --apply
"""

import argparse

from psycopg_pool import ConnectionPool

from game.app.store.connection import create_pool

# 지우지 않을 계정. 여기 없는 계정은 전부 지워진다.
KEEP_LOGIN_IDS: tuple[str, ...] = ("sinindra",)

# 미리보기에 적는 줄 수. 전부 적으면 화면이 넘쳐 정작 무엇을 지우는지가 안 보인다.
PREVIEW_LIMIT = 10


def list_targets(pool: ConnectionPool) -> tuple[tuple[int, str, bool, int], ...]:
    """지울 계정을 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        (id, 계정 이름, 관리자 여부, 티켓 수) 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT a.id, coalesce(a.login_id, ''), a.is_admin,"
            " (SELECT count(*) FROM run_ticket t WHERE t.account_id = a.id)"
            " FROM account a"
            " WHERE a.login_id IS NULL OR lower(a.login_id) <> ALL(%s)"
            " ORDER BY a.id",
            ([name.lower() for name in KEEP_LOGIN_IDS],),
        ).fetchall()
    return tuple((int(row[0]), str(row[1]), bool(row[2]), int(row[3])) for row in rows)


def apply_purge(pool: ConnectionPool, account_ids: tuple[int, ...]) -> int:
    """계정을 지운다. 딸린 것은 외래키가 함께 지운다.

    **세계 몬스터는 안 지워진다.** `entity_record` 중 `owner_account_id` 가 비어 있는
    줄이 그것이며, 계정에 걸려 있지 않다.

    Args:
        pool: 연결 풀.
        account_ids: 지울 계정들.

    Returns:
        지운 수.
    """
    if not account_ids:
        return 0
    with pool.connection() as connection:
        cursor = connection.execute("DELETE FROM account WHERE id = ANY(%s)", (list(account_ids),))
    return cursor.rowcount


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="검사·탐침 계정을 지운다")
    parser.add_argument("--apply", action="store_true", help="실제로 지운다")
    args = parser.parse_args()

    pool = create_pool()
    try:
        targets = list_targets(pool)
        print(f"남길 계정: {', '.join(KEEP_LOGIN_IDS)}")
        print(f"지울 계정 {len(targets)}개")
        for account_id, name, is_admin, tickets in targets[:PREVIEW_LIMIT]:
            label = name or "(익명)"
            mark = " [관리자]" if is_admin else ""
            print(f"  #{account_id} {label}{mark} · 티켓 {tickets}")
        if len(targets) > PREVIEW_LIMIT:
            print(f"  … 외 {len(targets) - PREVIEW_LIMIT}개")
        if not args.apply:
            print("\n미리보기다. 실제로 지우려면 --apply 를 붙인다.")
            return
        removed = apply_purge(pool, tuple(item[0] for item in targets))
        print(f"\n지웠다: {removed}개")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
