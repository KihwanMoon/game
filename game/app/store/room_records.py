"""방별 상시 기록 (2026-09-25) — 같은 방·같은 시드·같은 몸에서 가장 적게 쓰고 이긴 판.

**값은 서버가 정한 것만 들어온다** (설계/7_변조방지 §4). 이 모듈은 받은 값을 믿고 쓰며,
그 값이 재시뮬과 검증기에서 나왔는지는 부르는 쪽(`services/room_record`)이 책임진다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.app.store.display_name import build_display_name_sql

# 한 방의 기록판에 싣는 줄 수. 스무 줄이면 「어디쯤이 잘한 것인가」가 보이고, 그보다 길면
# 읽는 일이 아니라 훑는 일이 된다 — 데일리 판과 같은 눈금이다.
BOARD_LIMIT = 20


@dataclass(frozen=True)
class RoomRecord:
    """서버가 확정한 기록 하나."""

    room_id: str
    core_version: str
    account_id: int
    cpu: int
    ticks: int
    rule_count: int
    share_id: str
    submission_id: int


def save_room_record(pool: ConnectionPool, record: RoomRecord) -> bool:
    """기록을 적는다. 그 사람의 기존 기록보다 나을 때만 덮는다.

    **순서는 CPU → 틱 → 줄 수다.** CPU 가 이 게임의 정체성(「얼마나 적게 써서 풀었나」)이고,
    틱은 결정론이라 정확히 재지므로 동점을 가른다.

    Args:
        pool: 연결 풀.
        record: 적을 기록.

    Returns:
        새로 적었거나 더 나아져서 덮었으면 참.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO room_record"
            " (room_id, core_version, account_id, cpu, ticks, rule_count, share_id,"
            "  submission_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (room_id, core_version, account_id) DO UPDATE"
            " SET cpu = EXCLUDED.cpu, ticks = EXCLUDED.ticks,"
            "     rule_count = EXCLUDED.rule_count, share_id = EXCLUDED.share_id,"
            "     submission_id = EXCLUDED.submission_id, recorded_at = now()"
            " WHERE (EXCLUDED.cpu, EXCLUDED.ticks, EXCLUDED.rule_count)"
            "     < (room_record.cpu, room_record.ticks, room_record.rule_count)"
            " RETURNING account_id",
            (
                record.room_id,
                record.core_version,
                record.account_id,
                record.cpu,
                record.ticks,
                record.rule_count,
                record.share_id,
                record.submission_id,
            ),
        ).fetchone()
    return row is not None


# 기록판 한 줄의 열. 두 조회가 같은 줄 모양을 내야 「내 자리」와 윗자리가 한 표로 읽힌다.
_ROW_COLUMNS = (
    f"{build_display_name_sql('a')}, r.cpu, r.ticks, r.rule_count, r.share_id, r.account_id"
)
# 순위 식. 같은 기록이면 먼저 세운 쪽이 위다 — 늦게 같은 값에 닿았다고 앞서면 안 된다.
_RANK_ORDER = "r.cpu, r.ticks, r.rule_count, r.recorded_at"


def _build_row(rank: int, row: tuple) -> dict:
    """조회 한 줄을 기록판 한 줄로 옮긴다.

    Args:
        rank: 순위.
        row: `_ROW_COLUMNS` 순서의 값.

    Returns:
        기록판 한 줄.
    """
    return {
        "rank": rank,
        "handle": str(row[0]),
        "cpu": int(row[1]),
        "ticks": int(row[2]),
        "rule_count": int(row[3]),
        "share_id": str(row[4]),
        "account_id": int(row[5]),
    }


def list_room_records(
    pool: ConnectionPool, room_id: str, core_version: str, limit: int = BOARD_LIMIT
) -> tuple[dict, ...]:
    """한 방의 기록판을 읽는다.

    Args:
        pool: 연결 풀.
        room_id: 방 id.
        core_version: 지금 서버의 코어 버전.
        limit: 최대 줄 수.

    Returns:
        순위 순 줄들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            f"SELECT {_ROW_COLUMNS} FROM room_record r JOIN account a ON a.id = r.account_id"
            # 비활성 계정은 빠진다 — 검사가 만든 계정이 1위면 표가 실력이 아니라 탐침을 센다.
            " WHERE r.room_id = %s AND r.core_version = %s AND a.deactivated_at IS NULL"
            f" ORDER BY {_RANK_ORDER} LIMIT %s",
            (room_id, core_version, limit),
        ).fetchall()
    return tuple(_build_row(index + 1, row) for index, row in enumerate(rows))


def find_my_room_record(
    pool: ConnectionPool, room_id: str, core_version: str, account_id: int
) -> dict | None:
    """그 방에서 내 기록과 순위를 윗자리 밖에서도 찾는다.

    스무 줄 안에 없다고 내 기록을 안 보여 주면, 잘 못한 사람에게는 이 표가 남의 것만 적힌
    종이가 된다 — 데일리 판이 같은 이유로 내 자리를 따로 찾는다.

    Args:
        pool: 연결 풀.
        room_id: 방 id.
        core_version: 지금 서버의 코어 버전.
        account_id: 내 계정.

    Returns:
        기록판 한 줄. 기록이 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            f"SELECT {_ROW_COLUMNS},"
            " (SELECT count(*) FROM room_record o JOIN account oa ON oa.id = o.account_id"
            "   WHERE o.room_id = r.room_id AND o.core_version = r.core_version"
            "     AND oa.deactivated_at IS NULL"
            "     AND (o.cpu, o.ticks, o.rule_count, o.recorded_at)"
            "       < (r.cpu, r.ticks, r.rule_count, r.recorded_at))"
            " FROM room_record r JOIN account a ON a.id = r.account_id"
            " WHERE r.room_id = %s AND r.core_version = %s AND r.account_id = %s",
            (room_id, core_version, account_id),
        ).fetchone()
    if row is None:
        return None
    return _build_row(int(row[6]) + 1, row)


def count_room_players(pool: ConnectionPool, room_id: str, core_version: str) -> int:
    """그 방에 기록을 남긴 사람 수.

    Args:
        pool: 연결 풀.
        room_id: 방 id.
        core_version: 지금 서버의 코어 버전.

    Returns:
        사람 수. 비활성 계정은 뺀다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM room_record r JOIN account a ON a.id = r.account_id"
            " WHERE r.room_id = %s AND r.core_version = %s AND a.deactivated_at IS NULL",
            (room_id, core_version),
        ).fetchone()
    return int(row[0]) if row is not None else 0
