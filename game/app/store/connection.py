"""데이터베이스 연결과 스키마 적용.

연결 문자열은 환경변수에서 온다. 코드에 박으면 개발용 자격증명이 저장소에 남고, 그것은
지워도 히스토리에 남는다.

**연결이 없으면 서버가 시작되지 않아야 한다.** 연결을 지연시켜 "요청이 올 때 붙는" 구조로
두면, 설정이 틀린 채로 배포가 성공하고 첫 사용자가 그것을 발견한다.
"""

import os
from pathlib import Path

from psycopg_pool import ConnectionPool

# 연결 문자열 환경변수. `postgresql://user:pass@host:5432/db` 형식이다.
DATABASE_URL_ENV = "GAME_DATABASE_URL"

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# 이행 SQL. schema.sql 다음에 돈다 — 앞은 목표 형태를 만들고, 뒤는 옛 형태를 그리로 옮긴다.
MIGRATE_PATH = Path(__file__).resolve().parent / "migrate.sql"

# 풀 상한. 동기 검증이 요청 안에서 재시뮬을 돌리므로(런당 약 94ms) 연결이 그 시간만큼
# 잡힌다. 4코어 기준 동시 처리량을 넘겨 잡아 두면 대기가 DB 가 아니라 CPU 에서 생긴다.
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 8


def get_database_url() -> str | None:
    """환경변수에서 연결 문자열을 읽는다.

    Returns:
        연결 문자열. 설정돼 있지 않으면 None.
    """
    value = os.environ.get(DATABASE_URL_ENV, "").strip()
    return value or None


def create_pool(database_url: str | None = None) -> ConnectionPool:
    """연결 풀을 만들고 실제로 붙는지 확인한다.

    Args:
        database_url: 연결 문자열. 생략하면 환경변수를 쓴다.

    Returns:
        열린 연결 풀.

    Raises:
        RuntimeError: 연결 문자열이 없는 경우.
    """
    url = database_url or get_database_url()
    if url is None:
        raise RuntimeError(f"{DATABASE_URL_ENV} 가 설정되지 않았다")
    pool = ConnectionPool(url, min_size=POOL_MIN_SIZE, max_size=POOL_MAX_SIZE, open=True)
    # 여기서 기다린다. 붙지 못하면 서버가 시작되지 않아야 한다.
    pool.wait()
    return pool


def apply_schema(pool: ConnectionPool) -> None:
    """스키마를 적용한다. 이미 있으면 아무것도 하지 않는다.

    두 파일을 순서대로 돌린다. `schema.sql` 이 목표 형태를 만들고, `migrate.sql` 이
    옛 형태를 그리로 옮긴다. 신규 DB 에서는 뒤엣것이 전부 no-op 이 된다.

    마이그레이션 도구를 아직 들이지 않는다. 이행이 하나뿐이고, 그 하나를 명시적인 SQL 로
    두는 편이 도구의 자동 생성보다 읽기 쉽다 — **두 번째 이행이 이만큼 복잡하면 그때
    들인다.**

    Args:
        pool: 연결 풀.
    """
    with pool.connection() as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute(MIGRATE_PATH.read_text(encoding="utf-8"))
