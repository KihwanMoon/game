"""익명 계정과 기기 토큰 (docs/설계/1_통합시스템설계 §5).

가입 절차 없이 첫 실행에 계정이 생기고, 토큰이 기기에 저장된다. G1 판정 전이라 붙잡을
자산이 아직 없고, 재미가 검증되기 전에 가입을 요구하면 이탈만 는다.

**토큰 평문을 저장하지 않는다.** 해시만 두므로 저장소가 새도 계정이 넘어가지 않는다.
다만 익명 계정이라 복구 수단이 없다 — 기기를 잃으면 계정을 잃는다. 아이템과 거래가
붙기 전에 승격 경로(이메일·OAuth)가 필요하다.
"""

import hashlib
import secrets
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

# 토큰 바이트 수. 32바이트면 추측이 성립하지 않는다.
TOKEN_BYTES = 32

# 핸들에 붙일 무작위 꼬리의 길이. 같은 이름이 겹쳐도 계정이 갈리게 한다.
HANDLE_SUFFIX_BYTES = 4


@dataclass(frozen=True)
class Account:
    """계정 하나."""

    account_id: int
    handle: str


def build_token_hash(token: str) -> str:
    """토큰을 저장 형태로 바꾼다.

    Args:
        token: 평문 토큰.

    Returns:
        16진 해시 문자열.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_account(pool: ConnectionPool) -> tuple[Account, str]:
    """익명 계정과 토큰을 새로 만든다.

    `secrets` 를 쓰는 것은 R5 위반이 아니다 — 게임 난수가 아니라 예측 불가능해야 하는
    값이다. 코어 안에서 썼다면 위반이지만 여기는 코어 밖이다.

    Args:
        pool: 연결 풀.

    Returns:
        만들어진 계정과 **평문 토큰**. 평문은 여기서만 나오고 저장되지 않으므로,
        호출한 쪽이 그대로 돌려주지 않으면 영영 사라진다.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    handle = f"user_{secrets.token_hex(HANDLE_SUFFIX_BYTES)}"
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO account (handle) VALUES (%s) RETURNING id", (handle,)
        ).fetchone()
        if row is None:
            raise RuntimeError("계정을 만들지 못했다")
        account_id = int(row[0])
        connection.execute(
            "INSERT INTO account_token (token_hash, account_id) VALUES (%s, %s)",
            (build_token_hash(token), account_id),
        )
    return Account(account_id=account_id, handle=handle), token


def find_account(pool: ConnectionPool, token: str) -> Account | None:
    """토큰으로 계정을 찾는다. 찾으면 마지막 접속 시각을 갱신한다.

    Args:
        pool: 연결 풀.
        token: 평문 토큰.

    Returns:
        찾은 계정. 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT a.id, a.handle FROM account_token t"
            " JOIN account a ON a.id = t.account_id"
            " WHERE t.token_hash = %s",
            (build_token_hash(token),),
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE account_token SET last_seen_at = now() WHERE token_hash = %s",
            (build_token_hash(token),),
        )
    return Account(account_id=int(row[0]), handle=str(row[1]))
