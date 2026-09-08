"""서버 오류를 남긴다 — 지킴이가 볼 수 있게 (설계/1_통합시스템설계 §6 H1).

**5xx 를 기록하는 곳이 없었다.** 그래서 `/api/run` 이 제출의 37%에서 500 을 내는 동안
지킴이 검사 여덟이 전부 OK 였고, 이틀 뒤에 사람이 컨테이너 로그를 보고서야 잡혔다.
검사들이 보던 것은 **상태 정합성**이지 요청이 성공했는가가 아니다.

**고아 제출을 세는 것으로는 안 된다.** `run_result` 없는 `run_submission` 은 저장 두
지점 *사이*에서 죽은 것만 잡는데, 그 500 은 둘 다 저장한 **뒤에** 터졌다.

**스스로 자란다.** 5xx 는 드물어야 하므로 넣을 때마다 오래된 줄을 지운다 — 드물지
않다면 그것이 곧 경보다. 검사 DB 가 안 비워져 개체 하나가 전리품 920개를 들고 있던
사고(Z8)를 여기서 되풀이하지 않는다.
"""

from psycopg_pool import ConnectionPool

# 이보다 오래된 줄은 지운다. 지킴이 창이 시간 단위이므로 하루면 넉넉하다.
RETAIN_HOURS = 24

# 한 줄에 담는 사유의 최대 길이. 역추적 전체를 넣으면 표가 로그가 된다 —
# 원인은 컨테이너 로그에 있고, 여기 있어야 하는 것은 「무엇이 몇 번」이다.
MAX_DETAIL = 300


def save_api_error(pool: ConnectionPool, path: str, method: str, status: int, detail: str) -> None:
    """오류 한 건을 남긴다.

    **여기서 절대 던지지 않는다.** 오류를 기록하다 오류를 내면 원래 응답까지 바뀐다 —
    부르는 쪽은 이미 실패를 처리하는 중이다.

    Args:
        pool: 연결 풀.
        path: 요청 경로.
        method: HTTP 메서드.
        status: 응답 상태.
        detail: 사유 한 줄. 길면 자른다.
    """
    try:
        with pool.connection() as connection:
            connection.execute(
                "INSERT INTO api_error (path, method, status, detail) VALUES (%s, %s, %s, %s)",
                (path[:200], method[:10], status, detail[:MAX_DETAIL]),
            )
            connection.execute(
                "DELETE FROM api_error WHERE happened_at < now() - make_interval(hours => %s)",
                (RETAIN_HOURS,),
            )
    except Exception:  # noqa: BLE001 — 기록 실패가 원래 응답을 바꾸면 안 된다
        return


def count_api_errors(pool: ConnectionPool, window_hours: int) -> tuple[int, str]:
    """창 안의 5xx 수와 가장 많은 경로를 센다.

    경로를 함께 내는 이유는 수만으로는 어디를 볼지 모르기 때문이다 — 「12건」과
    「12건, 전부 /api/run」은 다른 정보다.

    Args:
        pool: 연결 풀.
        window_hours: 몇 시간을 볼 것인가.

    Returns:
        (건수, 가장 많은 경로). 없으면 (0, "").
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*), coalesce(mode() WITHIN GROUP (ORDER BY path), '')"
            " FROM api_error WHERE happened_at > now() - make_interval(hours => %s)",
            (window_hours,),
        ).fetchone()
    return (0, "") if row is None else (int(row[0]), str(row[1]))
