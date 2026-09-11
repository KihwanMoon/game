"""검사·탐침이 만든 계정을 비활성화한다.

**왜 필요했나.** `deploy/docker-compose.yml` 의 `test` 서비스가 프로덕션과 같은 DB 를
쓰고 있었다. 그래서 검사가 만든 계정·아이템·매물이 실제 서비스에 쌓였고, 검사용 계정
하나가 **관리자 권한까지 갖고 있었다** — 검사는 관리자 경로를 확인해야 하므로 스스로를
승격시킨다. 원인은 끊었고(검사는 이제 `game_test` 를 쓴다), 이 스크립트는 이미 쌓인
것을 치운다.

**지우지 않고 비활성화한다.** 지우면 그 계정이 남긴 것(제출·원장·경매 이력)이 함께
사라지고, 그러면 "이 아이템이 어디서 왔는가" 를 나중에 못 읽는다. 비활성 계정은 토큰이
안 통하고, 통계에서 빠지고, 매물이 안 보인다 — 지웠을 때와 게임상 결과가 같으면서
기록은 남는다.

**남길 것을 적는다.** "끌 것" 을 고르는 방식이면 새 계정이 생길 때마다 목록을 고쳐야
하고, 한 번 빠뜨리면 남의 계정이 꺼진다. 남길 것을 적으면 빠뜨렸을 때 꺼지는 쪽이
아니라 남는 쪽으로 실패한다.

**남길 것이 이름 하나가 아니게 됐다 (2026-09-11).** 이 스크립트를 쓸 때는 세계에
`sinindra` 하나뿐이었는데, 그 뒤로 봇 열과 둘째 테스터와 관리자가 생겼다. 이름 목록만
보고 돌렸으면 **봇 열이 통째로 꺼졌다.** 그래서 남길 조건을 넷으로 적는다.

    봇             세계를 혼자 두지 않으려고 도는 것들이다
    테스터 표시    G1 의 분모다 — 끄면 게이트 판정이 바뀐다
    관리자         끄면 그 사람이 세계에 못 들어온다
    제출이 있음    한 판이라도 논 계정은 기록이다

여기 하나도 안 걸리는 계정이 **한 번도 안 논 익명**이고, 그것이 개발·탐침이 남긴 것이다.

기본은 **미리보기**다. 실제로 끄려면 `--apply` 를 붙이고, 되살리려면 `--restore` 를 쓴다.

    docker compose run --rm ops uv run python -m scripts.purge_test_accounts
    docker compose run --rm ops uv run python -m scripts.purge_test_accounts --apply
    docker compose run --rm ops uv run python -m scripts.purge_test_accounts --apply --restore
"""

import argparse

from psycopg_pool import ConnectionPool

from game.app.store.accounts import apply_deactivation
from game.app.store.connection import create_pool

# 이름으로 지킬 계정. **조건 넷에 더해지는 것이지 그것을 대신하지 않는다** — 아직 안
# 놀았고 표시도 안 된 사람을 부르기로 했을 때 여기 적는다.
KEEP_LOGIN_IDS: tuple[str, ...] = ("sinindra",)

# 미리보기에 적는 줄 수. 전부 적으면 화면이 넘쳐 정작 무엇을 지우는지가 안 보인다.
PREVIEW_LIMIT = 10


def list_targets(
    pool: ConnectionPool, is_active: bool = True
) -> tuple[tuple[int, str, bool, int], ...]:
    """비활성화할 계정을 읽는다.

    **봇·테스터·관리자·논 적 있는 계정은 안 고른다.** 조건은 머리말에 적혀 있다 —
    여기 안 걸리는 것이 「한 번도 안 논 익명」이고 그것이 개발·탐침이 남긴 것이다.

    **티켓이 아니라 제출로 센다.** 티켓은 출격 버튼을 누르면 생기고 제출은 판을 끝내야
    생긴다 — 발급만 받고 떠난 것은 논 것이 아니다.

    Args:
        pool: 연결 풀.
        is_active: 지금 활성인 것을 찾을지. 되살리기는 False 로 부른다.

    Returns:
        (id, 계정 이름, 관리자 여부, 티켓 수) 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "WITH played AS ("
            "  SELECT t.account_id FROM run_ticket t"
            "  JOIN run_submission s ON s.ticket_id = t.id GROUP BY t.account_id"
            ")"
            " SELECT a.id, coalesce(a.login_id, ''), a.admin_role IS NOT NULL,"
            " (SELECT count(*) FROM run_ticket t WHERE t.account_id = a.id)"
            " FROM account a"
            " WHERE (a.login_id IS NULL OR lower(a.login_id) <> ALL(%s))"
            "   AND NOT a.is_bot"
            "   AND NOT a.is_tester"
            "   AND a.admin_role IS NULL"
            "   AND a.id NOT IN (SELECT account_id FROM played)"
            "   AND (a.deactivated_at IS NULL) = %s"
            " ORDER BY a.id",
            ([name.lower() for name in KEEP_LOGIN_IDS], is_active),
        ).fetchall()
    return tuple((int(row[0]), str(row[1]), bool(row[2]), int(row[3])) for row in rows)


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="검사·탐침 계정을 지운다")
    parser.add_argument("--apply", action="store_true", help="실제로 끈다")
    parser.add_argument("--restore", action="store_true", help="끈 것을 되살린다")
    args = parser.parse_args()

    pool = create_pool()
    try:
        targets = list_targets(pool, is_active=not args.restore)
        verb = "되살릴" if args.restore else "비활성화할"
        print(f"남길 계정: {', '.join(KEEP_LOGIN_IDS)}")
        print(f"{verb} 계정 {len(targets)}개")
        for account_id, name, is_admin, tickets in targets[:PREVIEW_LIMIT]:
            label = name or "(익명)"
            mark = " [관리자]" if is_admin else ""
            print(f"  #{account_id} {label}{mark} · 티켓 {tickets}")
        if len(targets) > PREVIEW_LIMIT:
            print(f"  … 외 {len(targets) - PREVIEW_LIMIT}개")
        if not args.apply:
            print("\n미리보기다. 실제로 바꾸려면 --apply 를 붙인다.")
            return
        changed = apply_deactivation(
            pool, tuple(item[0] for item in targets), is_active=args.restore
        )
        print(f"\n{verb[:-1]}했다: {changed}개")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
