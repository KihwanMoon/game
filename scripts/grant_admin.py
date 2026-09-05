"""관리자 등급을 주거나 뺏는다.

**승격의 유일한 경로다.** API 로 열지 않은 이유는 그 하나가 뚫리는 순간 세계 전체가
뚫리기 때문이다 — 이 저장소는 클라이언트를 적대적이라고 전제한다(CLAUDE.md). 이
스크립트는 DB 접속이 있어야 돌므로, 서버에 들어갈 수 있는 사람만 쓸 수 있다.

**가입한 계정만 관리자가 될 수 있다.** 익명 계정은 토큰만 있으면 되므로, 그 계정이
관리자면 토큰 하나가 곧 세계 전체다.

**등급을 골라야 한다** (2026-09-05, 설계/9_에이전트_운영 §3.1). 예전에는 주거나 뺏거나
둘뿐이라 관리자면 발행까지 전부 할 수 있었고, 그래서는 에이전트를 붙일 수 없다.

    observer  읽기 전량. 쓰기 없음
    author    콘텐츠 초안. 발행 불가
    operator  계정·세계 개입(회수·봇 멈춤·테스터 표시). 콘텐츠 불가
    owner     전부. **사람만** — 발행과 카탈로그 즉시 반영이 여기 있다

`owner` 를 에이전트 계정에 주지 않는다. 발행은 시즌을 가르는 행위이고, 되돌려도 흔적이
남는다 (§8).

    GAME_DATABASE_URL=... uv run python -m scripts.grant_admin <로그인id> --role operator
    GAME_DATABASE_URL=... uv run python -m scripts.grant_admin <로그인id> --revoke
"""

import argparse
import os
import sys

from game.app.store.admin import ADMIN_ROLES, ROLE_OWNER, set_admin_role
from game.app.store.connection import DATABASE_URL_ENV, create_pool


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="관리자 등급을 주거나 뺏는다")
    parser.add_argument("login_id", help="대상 계정의 로그인 id")
    # **기본값을 넓은 쪽에 두지 않는다.** 손이 미끄러져 owner 가 되면 그 계정이 발행까지
    # 할 수 있고, 그 사실은 아무 화면에도 안 뜬다. 고르게 해서 한 번 더 보게 한다.
    parser.add_argument("--role", choices=ADMIN_ROLES, help="세울 등급")
    parser.add_argument("--revoke", action="store_true", help="주는 대신 뺏는다")
    return parser.parse_args(argv)


def main() -> int:
    """스크립트 진입점.

    Returns:
        종료 코드. 연결이 없거나 계정을 못 찾으면 1.
    """
    arguments = parse_arguments(sys.argv[1:])
    if not os.environ.get(DATABASE_URL_ENV, "").strip():
        print(f"{DATABASE_URL_ENV} 가 없다")
        return 1
    if not arguments.revoke and arguments.role is None:
        print(f"등급을 골라야 한다: --role {{{'|'.join(ADMIN_ROLES)}}}")
        return 1
    pool = create_pool()
    role = "" if arguments.revoke else str(arguments.role)
    if not set_admin_role(pool, arguments.login_id, role):
        print(f"그런 계정이 없다 (가입한 계정만 관리자가 될 수 있다): {arguments.login_id}")
        return 1
    if role == ROLE_OWNER:
        # 사람에게만 준다는 규율이 코드에 안 박히므로 (§8), 줄 때 말이라도 한다.
        print("owner 는 사람만 받는다 — 에이전트 계정이면 좁은 등급으로 다시 세운다")
    print(f"{arguments.login_id} → {role or '권한 해제'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
