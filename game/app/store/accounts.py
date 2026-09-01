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
from datetime import UTC, datetime

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
            # **비활성 계정의 토큰은 안 통한다.** 통계에서만 빼면 그 계정이 여전히
            # 게임을 돌리고 관리자 권한까지 쓴다 — 비활성화가 삭제를 대신하려면 여기서
            # 막혀야 한다.
            "SELECT a.id, a.handle FROM account_token t"
            " JOIN account a ON a.id = t.account_id"
            " WHERE t.token_hash = %s AND a.deactivated_at IS NULL",
            (build_token_hash(token),),
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE account_token SET last_seen_at = now() WHERE token_hash = %s",
            (build_token_hash(token),),
        )
    return Account(account_id=int(row[0]), handle=str(row[1]))


def find_player_entity(pool: ConnectionPool, account_id: int) -> int:
    """계정의 PLAYER 개체 id 를 준다. 없으면 만든다.

    아이템·인벤토리·장비가 계정이 아니라 **개체**를 가리키므로, 계정 하나에 개체 하나가
    반드시 있어야 한다 (docs/설계/6_몬스터 §7).

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        개체 id.

    Raises:
        RuntimeError: 개체를 만들지도 찾지도 못한 경우.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO entity_record (kind, owner_account_id) VALUES ('PLAYER', %s)"
            " ON CONFLICT (owner_account_id) DO NOTHING",
            (account_id,),
        )
        row = connection.execute(
            "SELECT id FROM entity_record WHERE owner_account_id = %s", (account_id,)
        ).fetchone()
    if row is None:
        raise RuntimeError(f"계정의 개체를 만들지 못했다: {account_id}")
    return int(row[0])


def apply_deactivation(pool: ConnectionPool, account_ids: tuple[int, ...], is_active: bool) -> int:
    """계정을 비활성화하거나 되살린다. 지우지 않는다.

    지우면 그 계정이 남긴 것(제출·원장·경매 이력)이 함께 사라지고, 그러면 "이 아이템이
    어디서 왔는가" 를 나중에 못 읽는다. 아이템 카탈로그를 폐기로 다루는 것과 같은
    규율이다 (설계/4_아이템 §15.7).

    비활성 계정은 **토큰이 안 통하고, 통계에서 빠지고, 매물이 안 보인다.** 통계에서만
    빼면 그 계정이 여전히 게임을 돌린다.

    Args:
        pool: 연결 풀.
        account_ids: 대상 계정들.
        is_active: 살릴지. False 면 비활성화한다.

    Returns:
        바뀐 계정 수.
    """
    if not account_ids:
        return 0
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE account SET deactivated_at = %s WHERE id = ANY(%s)",
            (None if is_active else datetime.now(UTC), list(account_ids)),
        )
    return cursor.rowcount


def check_is_active(pool: ConnectionPool, account_id: int) -> bool:
    """그 계정이 활성인지 본다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        활성이면 True. 없는 계정도 False.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT deactivated_at IS NULL FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return bool(row[0]) if row is not None else False


def apply_single_session(pool: ConnectionPool, account_id: int, keep_token: str) -> int:
    """이 토큰만 남기고 그 계정의 다른 기기 토큰을 지운다.

    **한 계정은 한 기기다** (2026-09-01 결정). 예전에는 로그인이 토큰을 하나 더 붙였고
    두 기기를 함께 쓸 수 있었는데, 그러면 같은 계정의 상태가 두 벌 돌면서 나중에 저장한
    쪽이 앞의 것을 덮는다 — 쓰는 사람에게 그것은 "규칙이 사라졌다" 로 보인다.

    지워진 토큰을 든 기기는 다음 요청에서 401 을 받는다. **그 기기가 그 사실을 말해야
    한다** — 조용히 익명으로 떨어지면 자기 것이 남의 것처럼 보인다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        keep_token: 남길 평문 토큰.

    Returns:
        지운 토큰 수.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "DELETE FROM account_token WHERE account_id = %s AND token_hash <> %s",
            (account_id, build_token_hash(keep_token)),
        )
    return cursor.rowcount


def remove_device_token(pool: ConnectionPool, token: str) -> bool:
    """이 기기의 토큰을 지운다 — 로그아웃이다.

    **계정은 안 지운다.** 로그아웃은 이 기기가 그 계정을 그만 보는 것이지 계정이
    사라지는 것이 아니다.

    Args:
        pool: 연결 풀.
        token: 평문 토큰.

    Returns:
        지웠으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "DELETE FROM account_token WHERE token_hash = %s", (build_token_hash(token),)
        )
    return cursor.rowcount == 1
