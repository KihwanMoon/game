"""테스트 공통 준비.

**검사가 운영 DB 를 쓰지 않게 한다.** 컴포즈가 DB 하나만 띄우므로, 연결 문자열을 그대로
쓰면 검사가 만든 계정·티켓·제출이 실제 데이터와 같은 테이블에 쌓인다. 지금은 사용자가
없어 무해하지만, 생긴 뒤에 알아차리면 어느 행이 검사 것인지 가릴 수 없다.

여기서 데이터베이스 이름만 바꿔 붙는다. 없으면 만든다 — 컴포즈의 `POSTGRES_DB` 는 볼륨을
처음 만들 때만 적용되므로 나중에 추가할 방법이 이것뿐이다.
"""

import os

import psycopg

from game.app.store.connection import DATABASE_URL_ENV

# 검사 전용 데이터베이스 이름. 운영과 한 글자도 겹치지 않아야 한다.
TEST_DATABASE_NAME = "game_test"

# 데이터베이스를 만들 때 붙는 관리용 데이터베이스. postgres 이미지가 항상 갖고 있다.
ADMIN_DATABASE_NAME = "postgres"


def build_sibling_url(url: str, database: str) -> str:
    """같은 서버의 다른 데이터베이스를 가리키는 연결 문자열을 만든다.

    Args:
        url: 원래 연결 문자열.
        database: 붙을 데이터베이스 이름.

    Returns:
        경로만 바뀐 연결 문자열.
    """
    head, _, tail = url.rpartition("/")
    query = tail.partition("?")[2]
    return f"{head}/{database}" + (f"?{query}" if query else "")


def ensure_test_database(url: str) -> str:
    """검사 전용 데이터베이스를 확보한다.

    Args:
        url: 컴포즈가 준 연결 문자열.

    Returns:
        검사 전용 데이터베이스를 가리키는 연결 문자열.
    """
    admin_url = build_sibling_url(url, ADMIN_DATABASE_NAME)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        found = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DATABASE_NAME,)
        ).fetchone()
        if found is None:
            # 식별자는 매개변수로 넘길 수 없다. 이름이 상수라 주입 경로가 없다.
            connection.execute(f'CREATE DATABASE "{TEST_DATABASE_NAME}"')
    return build_sibling_url(url, TEST_DATABASE_NAME)


def pytest_configure() -> None:
    """검사가 도는 동안 연결 문자열을 검사 전용으로 바꾼다."""
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url or f"/{TEST_DATABASE_NAME}" in url:
        return
    try:
        os.environ[DATABASE_URL_ENV] = ensure_test_database(url)
    except psycopg.Error:
        # 붙지 못하면 DB 검사는 어차피 건너뛴다. 여기서 죽으면 나머지 검사까지 막힌다.
        os.environ.pop(DATABASE_URL_ENV, None)
