"""그림자 자리의 정원 — 누가 서고 누가 비켜 주는가 (개정 2026-09-15).

`doppels.py` 에서 갈라 나왔다. 저쪽은 **그림자를 만드는 일**이고 여기는 **자리가 남는가,
안 남으면 누가 나가는가**다. 파일이 400줄 상한에 닿은 것이 계기였을 뿐, 가르는 선은
책임이다 (§4).

**정원을 셋으로 잰다.** 예전에는 「세계에 스물」하나였고, 그 하나가 깊이로 줄을 세웠다 —
실측으로 스물 중 열아홉이 9장에 몰렸고 **주인은 셋뿐**이었다. 9장에 닿은 사람은 다섯
방이 전부 그림자였고, 2~8장에서는 하나도 못 만났다.

1. **한 원천은 한 장에 하나** — 같은 사람의 그림자가 한 장에 둘 서지 않는다.
2. **한 원천은 세계에 둘까지** (`DOPPELS_PER_SOURCE`) — 세계 상한이 **원천 수에 비례**
   하는 것은 이 규칙의 결과다. 총량에만 걸면 계정 둘이 아홉 장을 나눠 차지해도 통과한다.
3. **한 장에 둘까지** (`MAX_DOPPELS_PER_FLOOR`) — 한 장이 도는 방이 다섯이므로 이것이
   곧 「다섯 방 중 몇 방에서 만나는가」다.

**자리를 찾는 일도 여기 있다** (`find_free_slot`·`find_oldest_doppel_on_floor`). 정원이
남았는지와 앉을 자리가 있는지는 같은 질문의 두 면이다 — 실측으로 둘을 갈라 두었더니
한쪽만 보고 죽음을 버리는 길이 생겼다 (Z10).
"""

from psycopg_pool import ConnectionPool


def count_doppel_sources(pool: ConnectionPool) -> int:
    """그림자를 세울 수 있는 계정 수.

    **`apply_doppel_from_death` 의 통과 조건과 같은 식이어야 한다** — 봇이거나 동의를 켠
    사람이다. 여기만 넓게 세면 상한이 허수가 되고(판을 안 내는 계정까지 자리를 늘린다),
    좁게 세면 실제로 죽는 사람들이 서로를 밀어낸다.

    Args:
        pool: 연결 풀.

    Returns:
        원천 수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM account WHERE is_bot OR doppel_opt_in"
        ).fetchone()
    return int(row[0]) if row else 0


def count_doppels_on_floor(pool: ConnectionPool, floor: int) -> int:
    """그 장에 선 그림자 수.

    Args:
        pool: 연결 풀.
        floor: 볼 층.

    Returns:
        마릿수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive AND zone_floor = %s",
            (floor,),
        ).fetchone()
    return int(row[0]) if row else 0


def find_own_doppel_on_floor(
    pool: ConnectionPool, origin_account_id: int, floor: int
) -> tuple[int, str]:
    """그 사람이 그 장에 이미 세워 둔 그림자.

    **한 원천은 한 장에 하나다** (2026-09-15). 없으면 한 사람이 그 장의 정원을 통째로
    가져갈 수 있고, 그러면 다섯 방을 돌며 **같은 빌드를 두 번 만난다** — 「누구의
    그림자인가」가 뜻을 잃는다.

    새로 죽은 쪽이 이긴다. 같은 사람의 더 최근 빌드가 더 그 사람다우므로, 부르는 쪽은
    이것을 지우고 **그 자리를 물려받는다**.

    Args:
        pool: 연결 풀.
        origin_account_id: 누구의 그림자인가.
        floor: 볼 층.

    Returns:
        (개체 id, 자리 이름). 없으면 (0, "").
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, coalesce(entity_slot, '') FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive"
            " AND origin_account_id = %s AND zone_floor = %s"
            " ORDER BY id ASC LIMIT 1",
            (origin_account_id, floor),
        ).fetchone()
    return (int(row[0]), str(row[1])) if row else (0, "")


def find_crowded_doppel(pool: ConnectionPool) -> int:
    """가장 붐비는 장의 가장 오래된 그림자.

    **세계 상한에 닿았을 때 비켜 줄 하나를 고른다.** 예전에는 「가장 얕은 것」을 골랐고,
    그래서 얕은 장이 영원히 졌다 — 남는 것이 「가장 깊은 스물」이 되어 실제로 열아홉이
    9장에 몰렸다. 붐비는 쪽에서 빼면 장마다 고르게 퍼진다.

    **같은 수면 깊은 장에서 뺀다.** 깊은 장은 닿는 사람이 적어 거기 선 그림자는 아무도
    안 만나는 채로 자리만 차지한다.

    Args:
        pool: 연결 풀.

    Returns:
        개체 id. 하나도 없으면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive AND zone_floor = ("
            "  SELECT zone_floor FROM entity_record"
            "  WHERE kind = 'MONSTER' AND is_doppel AND alive"
            "  GROUP BY zone_floor ORDER BY count(*) DESC, zone_floor DESC LIMIT 1"
            " ) ORDER BY id ASC LIMIT 1"
        ).fetchone()
    return int(row[0]) if row else 0


def count_own_doppels(pool: ConnectionPool, origin_account_id: int) -> int:
    """그 사람이 세계에 세워 둔 그림자 수.

    **비례가 걸리는 자리다.** 총량에만 상한을 걸면 계정 둘이 아홉 장을 하나씩 차지해도
    통과한다 — 세계는 안 덮였지만 만나는 빌드는 둘뿐이다.

    Args:
        pool: 연결 풀.
        origin_account_id: 누구의 그림자인가.

    Returns:
        마릿수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive AND origin_account_id = %s",
            (origin_account_id,),
        ).fetchone()
    return int(row[0]) if row else 0


def find_own_oldest_doppel(pool: ConnectionPool, origin_account_id: int) -> int:
    """그 사람의 그림자 중 가장 오래된 것.

    **제 상한을 넘으면 제 것이 물러난다.** 남의 것을 밀어내면 「내가 깊이 갔다」가 남의
    자리를 빼앗는 일이 되고, 그것은 이 정원이 막으려던 바로 그 쏠림이다.

    **깊이로 안 고른다.** 깊은 것을 남기면 한 번 9장에 닿은 사람이 거기를 영영 차지한다 —
    세계 상한 하나가 깊이로 줄을 세우던 때의 병이 사람 단위로 되풀이된다.

    Args:
        pool: 연결 풀.
        origin_account_id: 누구의 그림자인가.

    Returns:
        개체 id. 하나도 없으면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive AND origin_account_id = %s"
            " ORDER BY id ASC LIMIT 1",
            (origin_account_id,),
        ).fetchone()
    return int(row[0]) if row else 0


def find_oldest_doppel_on_floor(pool: ConnectionPool, floor: int) -> tuple[int, str]:
    """그 층에서 가장 오래된 그림자와 그 자리.

    **장 정원이 찼을 때 비켜 줄 하나를 고른다.** 세계 상한 하나로만 재던 때는 전체에서
    가장 얕은 것을 골랐는데, 그것이 다른 층에 있으면 지워 봐야 **이 층의 자리는 그대로
    차 있다.** 실측으로 4층 자리 열하나가 다 차자 그 사이 봇이 4층을 115번 깼는데 새
    그림자가 하나도 안 섰다 (알려진 이슈 Z10).

    **오래된 것이 나간다.** id 순이 곧 생성 순이다 — 그래야 한 장이 붐빌 때도 보토가
    돌고, 하루 종일 같은 그림자를 만나지 않는다.

    Args:
        pool: 연결 풀.
        floor: 볼 층.

    Returns:
        (개체 id, 자리 이름). 그 층에 그림자가 없으면 (0, "").
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, coalesce(entity_slot, '') FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive AND zone_floor = %s"
            " ORDER BY id ASC LIMIT 1",
            (floor,),
        ).fetchone()
    return (int(row[0]), str(row[1])) if row else (0, "")


def find_free_slot(pool: ConnectionPool, floor: int, slots: tuple[str, ...]) -> str:
    """그 층에서 아직 아무도 안 앉은 자리를 찾는다.

    **템플릿의 자리여야 한다.** 방 배치에 없는 이름으로 세우면 스냅샷이 아무에게도
    안 붙어서, 개체는 있는데 아무도 못 만나는 상태가 된다.

    Args:
        pool: 연결 풀.
        floor: 세울 층.
        slots: 그 층 방들의 스폰 자리 이름들. 순서가 곧 우선순위다.

    Returns:
        빈 자리 이름. 없으면 빈 문자열.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT entity_slot FROM entity_record"
            " WHERE kind = 'MONSTER' AND zone_floor = %s AND entity_slot IS NOT NULL",
            (floor,),
        ).fetchall()
    taken = {str(row[0]) for row in rows}
    return next((slot for slot in slots if slot not in taken), "")
