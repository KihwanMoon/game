"""로그인 자격증명 — 익명 계정의 승격과 다른 기기에서의 로그인.

**익명 계정을 버리지 않고 승격시킨다.** 계정 행에 자격증명 컬럼을 비워 두었다가 가입할 때
채우므로, 계정 id 가 그대로이고 세이브·티켓·제출이 전부 따라온다. 계정을 새로 만들어
옮기는 구조였다면 그 이관 코드가 영원히 필요했을 것이다.

비밀번호는 `hashlib.scrypt` 로 늘린다. 표준 라이브러리에 있어 의존성이 늘지 않고, 계정당
소금이 달라 무지개표가 통하지 않으며, 메모리를 쓰는 함수라 GPU 로 밀어붙이기 어렵다.
SHA 계열을 그대로 쓰면 유출된 해시가 사실상 평문이다.

**모르는 아이디와 틀린 비밀번호를 같은 오류로 낸다.** 가르면 어느 아이디가 존재하는지
알려 주는 조회 도구가 된다.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.app.store.accounts import Account, build_token_hash

# scrypt 매개변수. n 이 작업량을 정한다 — 2**14 는 로그인 한 번에 수십 ms 를 쓰며,
# 사람은 못 느끼고 대량 시도는 느려진다. 올릴 때는 기존 해시를 다시 만들어야 하므로
# 저장 형식에 이 값을 함께 적는다.
SCRYPT_N = 1 << 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32

SALT_BYTES = 16
TOKEN_BYTES = 32

# 아이디·비밀번호 길이. 짧은 비밀번호는 늘리기가 무의미해진다.
MIN_LOGIN_ID = 3
MAX_LOGIN_ID = 32
MIN_PASSWORD = 8
MAX_PASSWORD = 128

# 아이디에 허용하는 문자. 대소문자를 가리지 않으므로 저장 전에 소문자로 접는다.
LOGIN_ID_ALPHABET = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")


@dataclass(frozen=True)
class CredentialProblem:
    """자격증명이 규칙을 어긴 사유. 화면이 그대로 보여준다."""

    field: str
    message: str


def normalize_login_id(login_id: str) -> str:
    """아이디를 저장·비교 형태로 접는다.

    Args:
        login_id: 사람이 입력한 아이디.

    Returns:
        앞뒤 공백을 없애고 소문자로 접은 아이디.
    """
    return login_id.strip().lower()


def check_credentials(login_id: str, password: str) -> CredentialProblem | None:
    """가입 전에 형식을 본다.

    Args:
        login_id: 정규화 전 아이디.
        password: 평문 비밀번호.

    Returns:
        어긴 규칙. 문제가 없으면 None.
    """
    folded = normalize_login_id(login_id)
    if not MIN_LOGIN_ID <= len(folded) <= MAX_LOGIN_ID:
        return CredentialProblem("login_id", f"아이디는 {MIN_LOGIN_ID}~{MAX_LOGIN_ID}자여야 한다")
    if not set(folded) <= LOGIN_ID_ALPHABET:
        return CredentialProblem("login_id", "아이디는 영문·숫자·밑줄·하이픈만 쓴다")
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        return CredentialProblem(
            "password", f"비밀번호는 {MIN_PASSWORD}자 이상 {MAX_PASSWORD}자 이하여야 한다"
        )
    return None


def build_password_hash(password: str, salt: str) -> str:
    """비밀번호를 저장 형태로 늘린다.

    Args:
        password: 평문 비밀번호.
        salt: 16진 소금.

    Returns:
        16진 해시 문자열.
    """
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return derived.hex()


def create_salt() -> str:
    """계정마다 다른 소금을 만든다.

    Returns:
        16진 소금 문자열.
    """
    return secrets.token_hex(SALT_BYTES)


def create_device_token(pool: ConnectionPool, account_id: int) -> str:
    """이 계정에 새 기기 토큰을 붙인다.

    기존 토큰을 지우지 않는다. 다른 기기에서 로그인했다고 이 기기가 튕기면, 사람은
    두 기기를 동시에 쓸 수 없다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        평문 토큰. 저장되지 않으므로 여기서만 나온다.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO account_token (token_hash, account_id) VALUES (%s, %s)",
            (build_token_hash(token), account_id),
        )
    return token


def find_login_owner(pool: ConnectionPool, login_id: str) -> int | None:
    """이 아이디를 이미 쓰는 계정을 찾는다.

    Args:
        pool: 연결 풀.
        login_id: 정규화 전 아이디.

    Returns:
        계정 id. 아무도 안 쓰면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id FROM account WHERE lower(login_id) = %s",
            (normalize_login_id(login_id),),
        ).fetchone()
    return int(row[0]) if row is not None else None


def check_account_has_login(pool: ConnectionPool, account_id: int) -> bool:
    """이 계정이 이미 가입돼 있는가.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        자격증명이 붙어 있으면 True.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT login_id FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return row is not None and row[0] is not None


def register_login(pool: ConnectionPool, account_id: int, login_id: str, password: str) -> None:
    """익명 계정에 자격증명을 붙인다 — 승격이다.

    계정 id 가 바뀌지 않으므로 세이브·티켓·제출이 전부 따라온다.

    Args:
        pool: 연결 풀.
        account_id: 승격할 계정.
        login_id: 정규화 전 아이디.
        password: 평문 비밀번호.
    """
    salt = create_salt()
    with pool.connection() as connection:
        connection.execute(
            "UPDATE account SET login_id = %s, password_salt = %s, password_hash = %s"
            " WHERE id = %s",
            (normalize_login_id(login_id), salt, build_password_hash(password, salt), account_id),
        )


def find_account_by_login(pool: ConnectionPool, login_id: str, password: str) -> Account | None:
    """아이디와 비밀번호로 계정을 찾는다.

    모르는 아이디와 틀린 비밀번호를 **가르지 않는다** — 부르는 쪽이 같은 오류를 내야
    아이디 존재 여부가 새지 않는다. 아이디가 없어도 해시를 한 번 계산해 응답 시간이
    갈리지 않게 한다.

    Args:
        pool: 연결 풀.
        login_id: 정규화 전 아이디.
        password: 평문 비밀번호.

    Returns:
        찾은 계정. 아이디가 없거나 비밀번호가 틀리면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, handle, password_salt, password_hash FROM account"
            " WHERE lower(login_id) = %s",
            (normalize_login_id(login_id),),
        ).fetchone()
    if row is None or row[2] is None or row[3] is None:
        # 없는 아이디에도 같은 일을 시킨다. 시간 차이로 존재 여부가 새면 안 된다.
        build_password_hash(password, create_salt())
        return None
    if not hmac.compare_digest(build_password_hash(password, str(row[2])), str(row[3])):
        return None
    return Account(account_id=int(row[0]), handle=str(row[1]))


def read_login_id(pool: ConnectionPool, account_id: int) -> str | None:
    """계정에 붙은 아이디를 읽는다. 화면이 가입 여부를 보여주는 데 쓴다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        아이디. 익명이면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT login_id FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return str(row[0]) if row is not None and row[0] is not None else None
