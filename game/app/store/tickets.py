"""런 티켓 발급과 소비 — **시드의 유일한 출처** (docs/설계/7_변조방지 T2·T6).

클라이언트가 시드를 정하면 유리한 시드가 나올 때까지 돌려 보고 그것만 제출할 수 있다.
그래서 시드는 여기서만 나오고, 예측 불가능해야 하며(`secrets`), 티켓 하나는 한 번만
쓰인다.

만료를 두는 이유는 골라 담기를 좁히기 위해서다. 티켓을 여러 개 받아 유리한 것만 완주하고
나머지를 버리는 것까지는 막지 못하지만(§5 의 남는 문제), 무한히 쌓아 두는 것은 막는다.
"""

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.schemas.run_ticket import MAX_SEED, RunMode

# 티켓 유효 기간. 짧으면 정상 플레이가 끊기고 길면 골라 담기가 열린다.
# 런 목표 시간이 15~25분이므로(GDD §1) 그 두 배로 잡았다 (결정/1_결정대기목록 #46).
TICKET_TTL = timedelta(minutes=50)

# 한 티켓이 도는 방 수 (로드맵 W3). 발급 시점의 값을 티켓에 **적어 둔다** — 여기를
# 고쳐도 이미 발급한 티켓은 그대로여야 서버가 그 판을 다시 계산할 수 있다.
CHAIN_LENGTH = 3

# 티켓 id 의 무작위 길이. 서버 발급 티켓은 로컬 것(`local:` 접두어)과 구분된다.
TICKET_ID_BYTES = 12


@dataclass(frozen=True)
class IssuedTicket:
    """발급된 티켓 하나."""

    ticket_id: str
    seed: int
    room_id: str
    floor: int
    mode: str
    core_version: str
    # 장비·레벨이 확정한 전투 입력. 없으면 기본 스탯으로 선다.
    loadout: dict | None = None
    # 이 티켓이 도는 방들 (로드맵 W3). 비어 있으면 `room_id` 한 방짜리다 — 구버전
    # 티켓이 그 경우다.
    room_ids: tuple[str, ...] = ()
    # 층 하나에 드는 방 수 (로드맵 W14). **티켓에 얼린다** — 상수를 바꾸면 이미 발급한
    # 티켓의 방 목록이 조용히 다른 층 배치로 읽힌다. 0 은 구버전 티켓이며 전체가 한 층이다.
    rooms_per_floor: int = 0
    # 어디까지 확정했는가. 0 은 아직 한 층도 못 깬 것이다.
    cleared_floor: int = 0


def create_seed() -> int:
    """예측 불가능한 시드를 만든다.

    상한은 `MAX_SEED` 다. 넘기면 TypeScript 코어가 그 값을 담지 못해 클라이언트가 다른
    판을 돈다 (docs/설계/3 §10-2 의 이식 제약).

    Returns:
        0 이상 MAX_SEED 이하의 정수.
    """
    return secrets.randbelow(MAX_SEED + 1)


def create_ticket(
    pool: ConnectionPool,
    account_id: int,
    room_id: str,
    core_version: str,
    floor: int = 1,
    mode: RunMode = RunMode.PRACTICE,
    wanted_seed: int | None = None,
    forced_seed: int | None = None,
    ttl: timedelta = TICKET_TTL,
    loadout: dict | None = None,
    room_ids: tuple[str, ...] = (),
    rooms_per_floor: int = 0,
) -> IssuedTicket:
    """티켓을 발급한다.

    Args:
        pool: 연결 풀.
        account_id: 발급 대상 계정.
        room_id: 방 id.
        core_version: 이 서버가 도는 코어 버전.
        floor: 층.
        mode: 런 모드.
        wanted_seed: **클라이언트가** 제안한 시드. 연습 모드에서만 반영한다 — 순위에
            반영되는 판에서 받으면 유리한 시드를 골라 담을 수 있다 (T2).
        forced_seed: **서버가** 정한 시드. 모드와 무관하게 그대로 쓴다. 데일리가 이것을
            쓴다 — 모두가 같은 시드를 받아야 성립하는데, 그것은 클라이언트가 고른 것이
            아니라 서버가 날짜에서 파생한 값이므로 T2 와 무관하다. 둘을 한 인자로 두면
            "누가 정했는가" 가 흐려지고, 그 구분이 이 게이트의 전부다.
        ttl: 유효 기간. 데일리는 짧게 잡는다 — "받아 두고 연습한 뒤 제출" 을 좁힌다.
        loadout: 장비·레벨이 확정한 전투 입력. 얼려 두지 않으면 화면과 서버가 다른
            캐릭터로 싸운다.
        room_ids: 이 티켓이 도는 방들. 비우면 `room_id` 를 `CHAIN_LENGTH` 번 잇는다.
        rooms_per_floor: 층 하나에 드는 방 수. 0 이면 전체가 한 층이다.

    Returns:
        발급된 티켓.

    Raises:
        RuntimeError: 삽입이 실패한 경우.
    """
    ticket_id = secrets.token_urlsafe(TICKET_ID_BYTES)
    if forced_seed is not None:
        seed = forced_seed
    elif mode is RunMode.PRACTICE and wanted_seed is not None:
        seed = wanted_seed
    else:
        seed = create_seed()
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"시드가 이식 범위를 벗어났다: {seed}")
    # **방 목록을 저장한다.** 길이를 서버 상수로 두면 상수를 고치는 순간 이미 발급한
    # 티켓이 소급해 달라지고, 그 티켓으로 돈 판을 서버가 다시 계산할 수 없다.
    rooms = tuple(room_ids) if room_ids else (room_id,) * CHAIN_LENGTH
    expires_at = datetime.now(UTC) + ttl
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO run_ticket"
            " (id, account_id, seed, room_id, floor, mode, core_version, expires_at,"
            " loadout, room_ids, rooms_per_floor)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                ticket_id,
                account_id,
                seed,
                room_id,
                floor,
                str(mode),
                core_version,
                expires_at,
                Jsonb(loadout) if loadout is not None else None,
                Jsonb(list(rooms)),
                rooms_per_floor,
            ),
        )
    return IssuedTicket(
        ticket_id=ticket_id,
        seed=seed,
        room_id=room_id,
        floor=floor,
        mode=str(mode),
        core_version=core_version,
        loadout=loadout,
        room_ids=rooms,
        rooms_per_floor=rooms_per_floor,
    )


def read_room_ids(raw: object) -> tuple[str, ...]:
    """티켓의 방 목록 절을 읽는다.

    Args:
        raw: JSONB 컬럼 값. 문자열이거나 리스트이거나 None 이다.

    Returns:
        방 id 들. 비어 있으면 빈 튜플.
    """
    if raw is None:
        return ()
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    return tuple(str(item) for item in parsed) if isinstance(parsed, list) else ()


def find_open_ticket(pool: ConnectionPool, ticket_id: str, account_id: int) -> IssuedTicket | None:
    """아직 쓰지 않았고 만료되지 않은 티켓을 찾는다.

    **계정을 함께 본다.** 남의 티켓으로 제출하는 것을 막는다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        account_id: 제출한 계정.

    Returns:
        쓸 수 있는 티켓. 없거나 이미 썼거나 만료됐으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, seed, room_id, floor, mode, core_version, loadout, room_ids,"
            " rooms_per_floor, cleared_floor"
            " FROM run_ticket"
            " WHERE id = %s AND account_id = %s"
            " AND consumed_at IS NULL AND expires_at > now()",
            (ticket_id, account_id),
        ).fetchone()
    if row is None:
        return None
    return IssuedTicket(
        ticket_id=str(row[0]),
        seed=int(row[1]),
        room_id=str(row[2]),
        floor=int(row[3]),
        mode=str(row[4]),
        core_version=str(row[5]),
        loadout=(json.loads(row[6]) if isinstance(row[6], str) else row[6]),
        # 구버전 티켓에는 목록이 없다. 그때는 방 하나짜리로 본다 — 없는 것을 길이 3으로
        # 채우면 그 티켓으로 돈 판과 서버 재시뮬이 갈린다.
        room_ids=tuple(read_room_ids(row[7]) or (str(row[2]),)),
        rooms_per_floor=int(row[8] or 0),
        cleared_floor=int(row[9] or 0),
    )


def mark_ticket_consumed(pool: ConnectionPool, ticket_id: str) -> bool:
    """티켓을 쓴 것으로 표시한다.

    조건부 갱신이다 — 이미 쓴 티켓이면 아무 행도 바뀌지 않는다. 같은 티켓으로 두 번
    제출하는 경쟁 상태를 여기서 끊는다 (T6).

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.

    Returns:
        이번 호출이 실제로 소비했으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE run_ticket SET consumed_at = now() WHERE id = %s AND consumed_at IS NULL",
            (ticket_id,),
        )
        return cursor.rowcount == 1


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


def count_open_tickets(pool: ConnectionPool, account_id: int) -> int:
    """아직 안 닫힌 티켓 수를 센다.

    **보충을 막는 데 쓴다** (설계/4_아이템 §5). 런 중에 채우면 이미 얼린 로드아웃은 안
    바뀌는데 층 정산은 새 충전에서 깎아, **낸 돈이 그 자리에서 사라진다.**

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        열린 티켓 수. 만료된 것은 세지 않는다 — 안 그러면 켜 두고 나간 티켓 하나가
        계정을 영원히 잠근다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM run_ticket"
            " WHERE account_id = %s AND consumed_at IS NULL AND expires_at > now()",
            (account_id,),
        ).fetchone()
    return int(row[0]) if row else 0


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
