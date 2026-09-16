"""구글 계정을 계정 행에 붙이고, 일회용 논스를 낸다 (2026-09-16).

**자격증명이 사는 자리는 하나다.** 아이디·비밀번호가 `account` 의 빈 칸을 채우듯
구글의 식별자도 같은 행의 빈 칸을 채운다 — 계정 id 가 안 바뀌므로 세이브·티켓·둔갑·
활자가 전부 따라온다 (`credentials.register_login` 과 같은 규율).

**논스는 표에 둔다.** 서명한 문자열로 대신하면 만료 전까지 몇 번이고 다시 쓸 수 있는데,
논스의 일이 정확히 그것을 막는 것이다 — 가로챈 ID 토큰을 그대로 다시 보내는 공격은
서명이 여전히 맞으므로 **한 번 쓰면 사라지는 값**으로만 막힌다.
"""

import secrets

from psycopg_pool import ConnectionPool

# 논스가 사는 시간(분). 짧으면 느린 기기에서 로그인이 실패하고, 길면 가로챈 토큰이
# 그만큼 오래 산다. 구글 버튼을 누르고 돌아오는 데 드는 시간의 몇 배로 잡는다.
NONCE_MINUTES = 10

# 논스 길이. `secrets` 를 쓰는 것은 R5 위반이 아니다 — 게임 난수가 아니라 예측 불가능해야
# 하는 값이고, 여기는 코어 밖이다 (`accounts.create_account` 와 같은 자리).
NONCE_BYTES = 24


def create_auth_nonce(pool: ConnectionPool) -> str:
    """일회용 논스를 발급하고 남긴다.

    **낡은 것을 함께 치운다.** 따로 도는 청소가 없으면 이 표만 단조 증가한다 — 로그인
    시도마다 한 줄이고, 대부분은 쓰이지 않고 버려진다.

    Args:
        pool: 연결 풀.

    Returns:
        발급된 논스.
    """
    nonce = secrets.token_urlsafe(NONCE_BYTES)
    with pool.connection() as connection:
        connection.execute(
            "DELETE FROM auth_nonce WHERE created_at < now() - make_interval(mins => %s)",
            (NONCE_MINUTES,),
        )
        connection.execute("INSERT INTO auth_nonce (nonce) VALUES (%s)", (nonce,))
    return nonce


def apply_nonce_use(pool: ConnectionPool, nonce: str) -> bool:
    """논스를 한 번 쓴다 — 두 번째는 통과하지 않는다.

    지우면서 확인하므로 같은 논스로 두 번 들어오면 두 번째는 거짓이다 — 확인과 삭제를
    나누면 그 사이가 곧 재생 공격의 창이 된다.

    Args:
        pool: 연결 풀.
        nonce: 클라이언트가 돌려준 값.

    Returns:
        유효했으면 참. 없거나 이미 썼거나 만료됐으면 거짓.
    """
    if not nonce:
        return False
    with pool.connection() as connection:
        row = connection.execute(
            "DELETE FROM auth_nonce"
            " WHERE nonce = %s AND created_at >= now() - make_interval(mins => %s)"
            " RETURNING nonce",
            (nonce, NONCE_MINUTES),
        ).fetchone()
    return row is not None


def find_google_owner(pool: ConnectionPool, google_sub: str) -> int:
    """그 구글 계정이 붙어 있는 계정.

    Args:
        pool: 연결 풀.
        google_sub: 구글의 고정 식별자.

    Returns:
        계정 id. 아직 아무 데도 안 붙었으면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id FROM account WHERE google_sub = %s AND deactivated_at IS NULL",
            (google_sub,),
        ).fetchone()
    return int(row[0]) if row else 0


def check_account_has_google(pool: ConnectionPool, account_id: int) -> bool:
    """이 계정에 이미 구글이 붙어 있는가.

    Args:
        pool: 연결 풀.
        account_id: 볼 계정.

    Returns:
        붙어 있으면 참.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT google_sub FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return bool(row and row[0])


def apply_google_link(pool: ConnectionPool, account_id: int, google_sub: str) -> bool:
    """익명 계정에 구글을 붙인다 — 승격이다.

    **빈 칸일 때만 채운다.** 이미 붙어 있는 계정에 덮어쓰면 앞의 구글 계정이 조용히
    로그인 수단을 잃는다.

    Args:
        pool: 연결 풀.
        account_id: 승격할 계정.
        google_sub: 구글의 고정 식별자.

    Returns:
        붙였으면 참. 이미 붙어 있었으면 거짓.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE account SET google_sub = %s WHERE id = %s AND google_sub IS NULL RETURNING id",
            (google_sub, account_id),
        ).fetchone()
    return row is not None
