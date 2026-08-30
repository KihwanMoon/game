"""관리자 권한을 주거나 뺏는다.

**승격의 유일한 경로다.** API 로 열지 않은 이유는 그 하나가 뚫리는 순간 세계 전체가
뚫리기 때문이다 — 이 저장소는 클라이언트를 적대적이라고 전제한다(CLAUDE.md). 이
스크립트는 DB 접속이 있어야 돌므로, 서버에 들어갈 수 있는 사람만 쓸 수 있다.

**가입한 계정만 관리자가 될 수 있다.** 익명 계정은 토큰만 있으면 되므로, 그 계정이
관리자면 토큰 하나가 곧 세계 전체다.

    GAME_DATABASE_URL=... uv run python -m scripts.grant_admin <로그인id>
    GAME_DATABASE_URL=... uv run python -m scripts.grant_admin <로그인id> --revoke
"""

import argparse
import os
import sys

from game.app.store.admin import set_admin
from game.app.store.connection import DATABASE_URL_ENV, create_pool


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="관리자 권한을 주거나 뺏는다")
    parser.add_argument("login_id", help="대상 계정의 로그인 id")
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
    pool = create_pool()
    is_admin = not arguments.revoke
    if not set_admin(pool, arguments.login_id, is_admin):
        print(f"그런 계정이 없다 (가입한 계정만 관리자가 될 수 있다): {arguments.login_id}")
        return 1
    print(f"{arguments.login_id} → 관리자 {'해제' if arguments.revoke else '부여'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
