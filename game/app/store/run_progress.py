"""런이 도는 동안 티켓에 쌓이는 것 (로드맵 W14, GDD §2.2).

`tickets.py` 에서 갈라 나왔다. 저쪽은 **티켓을 내주고 찾는 것**이고 여기는 **그 티켓이
런 도중에 어떻게 자라는가**다 — 어디까지 깼고, 무엇을 골랐고, 무엇을 썼는가. 파일이
400줄 상한을 넘은 것이 계기였을 뿐, 가르는 선은 책임이다 (§4).

셋 다 **한 번만 쓰이는 자리**라는 공통점이 있다. 같은 층을 두 번 청구하거나, 고른 보상을
바꾸거나, 쓴 충전을 두 번 세면 전부 같은 모양의 사고가 된다 — 그래서 조건이 SQL 안에
있다. 읽고 나서 쓰면 그 사이에 다른 요청이 끼어든다.
"""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


def apply_floor_claim(pool: ConnectionPool, ticket_id: str, floor: int) -> bool:
    """이 티켓으로 그 층까지 확정한 것으로 표시한다.

    **조건부 갱신이다** — 이미 그 층 이상을 확정했으면 아무 행도 안 바뀐다. 층 단위
    보상 때문에 한 티켓으로 여러 번 제출하는데, 같은 층을 두 번 제출해 보상을 두 번
    받는 길을 여기서 끊는다. T6 의 「한 티켓 한 제출」을 **「더 깊은 층으로만」**으로
    다시 세운 것이다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        floor: 이번에 확정한 층.

    Returns:
        이번 호출이 실제로 나아갔으면 True. 이미 지나온 층이면 False.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE run_ticket SET cleared_floor = %s"
            " WHERE id = %s AND consumed_at IS NULL AND cleared_floor < %s",
            (floor, ticket_id, floor),
        )
        return cursor.rowcount == 1


def apply_reward_choice(pool: ConnectionPool, ticket_id: str, floor: int, reward_id: str) -> bool:
    """그 층의 보상 선택을 티켓에 적는다.

    **이미 고른 층은 안 덮는다.** 덮을 수 있으면 층마다 다시 골라 최적을 맞출 수 있고,
    그러면 「그때 무엇을 골랐는가」가 이야기가 아니라 되돌릴 수 있는 설정이 된다.

    **닫힌 티켓에는 못 적는다.** 런이 끝난 뒤에 고르면 다음 런에 얹히거나 재시뮬이
    과거를 다르게 돈다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        floor: 고른 층.
        reward_id: 고른 보상.

    Returns:
        적었으면 True. 이미 고른 층이거나 닫힌 티켓이면 False.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE run_ticket SET rewards = rewards || %s"
            " WHERE id = %s AND consumed_at IS NULL AND NOT rewards ? %s"
            " RETURNING id",
            (Jsonb({str(floor): reward_id}), ticket_id, str(floor)),
        ).fetchone()
    return row is not None


def read_spent_charges(pool: ConnectionPool, ticket_id: str) -> dict[str, int]:
    """이 런이 이미 깎은 충전을 읽는다 (설계/4_아이템 §5).

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.

    Returns:
        쓰임새에서 이미 깎은 개수로. 없으면 빈 딕셔너리.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT spent_charges FROM run_ticket WHERE id = %s", (ticket_id,)
        ).fetchone()
    raw = row[0] if row else None
    if not isinstance(raw, dict):
        return {}
    return {str(key): int(value) for key, value in raw.items()}


def apply_spent_charges(pool: ConnectionPool, ticket_id: str, spent: dict[str, int]) -> None:
    """이 런이 깎은 충전을 적어 둔다.

    **덮어쓴다.** 부르는 쪽이 누적값을 넘긴다 — 서버가 층마다 처음부터 다시 돌려 내는
    수가 이미 누적이라, 여기서 더하면 두 번 더해진다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        spent: 쓰임새에서 누적 개수로. 정렬해서 담는다 (R5).
    """
    payload = {key: int(spent[key]) for key in sorted(spent)}
    with pool.connection() as connection:
        connection.execute(
            "UPDATE run_ticket SET spent_charges = %s WHERE id = %s",
            (Jsonb(payload), ticket_id),
        )
