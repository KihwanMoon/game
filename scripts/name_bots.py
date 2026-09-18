"""이미 서 있는 봇에게 한글 이름을 지어 준다 (2026-09-18).

**앞으로 서는 봇은 `store/bots.create_bot` 이 알아서 붙인다.** 이 스크립트는 그 규칙이
생기기 전에 만들어진 봇을 뒤늦게 맞추는 자리다 — 한 번 돌리면 끝이고, 다시 돌려도 같다.
`rename_bot_handles.py` 와 같은 결이다.

**왜 필요했나.** 봇의 성격 이름(「겨눔」·「문지기」)이 코드에는 있었는데
(`bots/personas.BOT_PERSONAS`) 화면까지 오지 않았다 — `list_persona_specs` 가 그 이름을
버리고 `bot1`·`bot2` 를 쓰고 있었고, 사유는 "화면에서 봇임을 알아보는 것이 먼저다" 였다.
그 판단을 뒤집으면서(§`play.list_persona_specs`) 이미 선 열 마리가 남았다.

**닉네임에 적는다.** 표시 이름이 `COALESCE(nickname, login_id, handle)` 이라 여기 적어야
순위표·경매·도감·둔갑이 전부 같은 이름을 쓴다. 자동 별명(`handle`)은 계정이 태어날 때
받는 내부 이름이라 안 건드린다 — 그것까지 바꾸면 계정을 가리키는 키가 움직인다.

**이미 이름이 있으면 안 건드린다.** 관리자가 지어 준 이름을 이 스크립트가 덮으면,
사람이 고친 것을 기계가 되돌리는 셈이다.

    GAME_DATABASE_URL=... uv run python -m scripts.name_bots
    ... --dry-run     # 무엇이 바뀌는지만 본다
"""

import argparse
import os
import sys

from psycopg_pool import ConnectionPool

from game.app.bots.personas import BOT_PERSONAS
from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.display_name import apply_nickname


def list_nameless_bots(pool: ConnectionPool) -> tuple[tuple[int, str, str], ...]:
    """이름이 없는 봇을 규칙표와 함께 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        (계정 id, 자동 별명, 규칙표 id) 들. 닉네임과 이름표가 이미 맞으면 빠진다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT a.id, a.handle, COALESCE(b.ruleset_id, '')"
            " FROM account a JOIN bot_profile b ON b.account_id = a.id"
            " WHERE a.deactivated_at IS NULL AND a.is_bot"
            " AND (a.nickname IS NULL OR a.nickname = '' OR b.label <> a.nickname)"
            " ORDER BY a.id"
        ).fetchall()
    return tuple((int(row[0]), str(row[1]), str(row[2])) for row in rows)


def find_persona_label(ruleset_id: str) -> str:
    """그 규칙표를 쓰는 성격의 이름.

    **규칙표로 잇는다.** 순번으로 이으면 봇이 지워졌다 다시 선 뒤에 이름이 밀린다 —
    같은 규칙표를 쓰는 봇이 곧 그 성격이다.

    Args:
        ruleset_id: 봇이 쓰는 규칙표.

    Returns:
        성격 이름. 아는 규칙표가 아니면 빈 문자열.
    """
    for persona in BOT_PERSONAS:
        if persona.ruleset_id == ruleset_id:
            return persona.label
    return ""


def apply_bot_names(pool: ConnectionPool, is_dry: bool) -> int:
    """이름 없는 봇에게 성격 이름을 붙인다.

    Args:
        pool: 연결 풀.
        is_dry: 참이면 적지 않고 보여만 준다.

    Returns:
        이름을 붙인 수.
    """
    named = 0
    for account_id, handle, ruleset_id in list_nameless_bots(pool):
        label = find_persona_label(ruleset_id)
        if not label:
            print(f"[봇이름] {handle}: 모르는 규칙표({ruleset_id}) — 건너뛴다", file=sys.stderr)
            continue
        if is_dry:
            print(f"[봇이름] {handle} → {label} (안 적음)")
            continue
        # `bot_profile.label` 도 같은 이름으로 맞춘다. 관리 화면이 그것을 따로 그리므로
        # 갈라 두면 한 화면에 「겨눔」과 「bot1」이 함께 선다.
        with pool.connection() as connection:
            connection.execute(
                "UPDATE bot_profile SET label = %s WHERE account_id = %s", (label, account_id)
            )
        if not apply_nickname(pool, account_id, label):
            # 겹치면 그대로 둔다. 자동 별명으로라도 서는 편이 낫고, 관리 화면에서
            # 사람이 다른 이름을 지어 줄 수 있다.
            print(f"[봇이름] {handle} → {label}: 이미 쓰는 이름이다", file=sys.stderr)
            continue
        print(f"[봇이름] {handle} → {label}")
        named += 1
    return named


def main() -> int:
    """명령행 진입점.

    Returns:
        종료 코드. 연결 문자열이 없으면 2, 그 밖에는 0.
    """
    parser = argparse.ArgumentParser(description="봇에게 한글 이름을 지어 준다")
    parser.add_argument("--dry-run", action="store_true", help="적지 않고 보여만 준다")
    args = parser.parse_args()

    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 2
    named = apply_bot_names(create_pool(url), args.dry_run)
    print(f"[봇이름] {named}마리에게 이름을 지었다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
