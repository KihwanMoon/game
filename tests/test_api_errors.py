"""서버가 낸 5xx 가 표에 남는가 (설계/1_통합시스템설계 §6 H1).

**기록하는 곳이 없어서 이틀이 걸렸다.** `/api/run` 이 제출의 37%에서 500 을 내는 동안
지킴이 검사 여덟이 전부 OK 였다 — 그것들이 보는 것은 상태 정합성이지 요청이 성공했는가가
아니다. 여기서 보는 것은 **기록이 남는가**와 **기록 장치가 응답을 안 바꾸는가** 둘이다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

PROBE_PATH = "/api/_probe_boom"


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    server = create_app()

    @server.get(PROBE_PATH)
    def raise_on_purpose():
        raise RuntimeError("일부러 터뜨린다")

    # 미들웨어가 다시 던지므로 클라이언트가 대신 받게 두면 응답을 못 본다.
    with fastapi_testclient.TestClient(server, raise_server_exceptions=False) as running:
        yield running


def count_probe_rows(pool):
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM api_error WHERE path = %s", (PROBE_PATH,)
        ).fetchone()
    return 0 if row is None else int(row[0])


def test_a_raised_error_lands_in_the_table(client):
    """★ 이것이 없으면 지킴이가 볼 것이 아무것도 없다."""
    from game.api.deps import get_pool

    pool = get_pool()
    before = count_probe_rows(pool)
    client.get(PROBE_PATH)
    assert count_probe_rows(pool) == before + 1


def test_the_response_is_unchanged(client):
    """★ **기록 장치가 응답을 바꾸면 안 된다.**

    예외 처리기가 아니라 미들웨어로 둔 이유가 이것이다 — 처리기는 응답을 대신 만들어야
    해서 지금의 본문이 바뀐다. 여기서는 다시 던져서 원래 경로로 흘려보낸다.
    """
    assert client.get(PROBE_PATH).status_code == 500


def test_the_reason_rides_along(client):
    """★ 「12건」만으로는 어디를 볼지 모른다. 예외 이름이라도 남아야 한다."""
    from game.api.deps import get_pool

    client.get(PROBE_PATH)
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT detail FROM api_error WHERE path = %s ORDER BY id DESC LIMIT 1",
            (PROBE_PATH,),
        ).fetchone()
    assert row is not None
    assert "RuntimeError" in str(row[0])


def test_a_good_request_leaves_nothing(client):
    """★ 4xx·2xx 까지 담으면 이 표가 접근 로그가 되고, 그러면 아무도 안 본다."""
    from game.api.deps import get_pool

    pool = get_pool()
    with pool.connection() as connection:
        before = connection.execute("SELECT count(*) FROM api_error").fetchone()
    client.get("/api/health")
    with pool.connection() as connection:
        after = connection.execute("SELECT count(*) FROM api_error").fetchone()
    assert after[0] == before[0]


def test_old_rows_do_not_pile_up(client):
    """★ 안 지우면 Z8 을 되풀이한다 — 검사 DB 가 안 비워져 개체 하나가 920개를 들었다.

    `client` 를 받는 이유는 풀의 수명이 앱 수명주기에 묶여 있기 때문이다 — 안 받으면
    닫힌 풀에 붙는다.
    """
    from game.api.deps import get_pool
    from game.app.store.api_errors import RETAIN_HOURS, save_api_error

    pool = get_pool()
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO api_error (path, method, status, detail, happened_at)"
            " VALUES (%s, 'GET', 500, '오래된 줄', now() - make_interval(hours => %s))",
            (PROBE_PATH, RETAIN_HOURS + 1),
        )
    save_api_error(pool, PROBE_PATH, "GET", 500, "새 줄")
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM api_error WHERE detail = '오래된 줄'"
        ).fetchone()
    assert int(row[0]) == 0, "보존 기간이 지난 줄이 안 지워졌다"
