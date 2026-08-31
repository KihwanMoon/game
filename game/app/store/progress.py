"""플레이어 성장과 랭킹 보관 (F단계).

**경험치는 검증된 런에서만 오른다.** 클라이언트 보고로 오르면 순위표가 곧 거짓이 된다.

랭킹은 **코어 버전별로 가른다** (결정 #06). 밸런스나 블록 목록이 바뀌면 과거 기록이
재현되지 않으므로, 한 표에 섞으면 검증할 수 없는 기록이 상위에 남는다.
"""

import json
from dataclasses import dataclass

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.progression.levels import (
    build_growth,
    compute_level,
    compute_required_xp,
    count_spent_points,
)

MODE_PRACTICE = "PRACTICE"
MODE_DAILY = "DAILY"


@dataclass(frozen=True)
class PlayerProgress:
    """플레이어 한 명의 성장 상태."""

    entity_id: int
    level: int
    total_xp: int
    remaining_xp: int
    next_xp: int
    stats: dict[str, int]
    bonus_rule_slots: int
    bonus_cpu: int
    bonus_flags: int
    stat_points: int
    spent_points: int


def read_progress(pool: ConnectionPool, entity_id: int) -> PlayerProgress:
    """개체의 성장 상태를 읽는다.

    Args:
        pool: 연결 풀.
        entity_id: PLAYER 개체 id.

    Returns:
        레벨·경험치·배분이 담긴 상태.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT total_xp, stat_json FROM entity_record WHERE id = %s", (entity_id,)
        ).fetchone()
    total_xp = int(row[0]) if row is not None else 0
    raw = row[1] if row is not None else {}
    stats = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    level, remaining = compute_level(total_xp)
    growth = build_growth(level)
    return PlayerProgress(
        entity_id=entity_id,
        level=level,
        total_xp=total_xp,
        remaining_xp=remaining,
        next_xp=compute_required_xp(level),
        stats={key: int(value) for key, value in stats.items()},
        bonus_rule_slots=growth.bonus_rule_slots,
        bonus_cpu=growth.bonus_cpu,
        bonus_flags=growth.bonus_flags,
        stat_points=growth.stat_points,
        spent_points=count_spent_points(stats),
    )


def add_player_xp(pool: ConnectionPool, entity_id: int, amount: int) -> int:
    """경험치를 더하고 레벨을 갱신한다. 상한이 없다.

    Args:
        pool: 연결 풀.
        entity_id: PLAYER 개체 id.
        amount: 더할 경험치.

    Returns:
        오른 뒤의 레벨.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE entity_record SET total_xp = total_xp + %s, updated_at = now()"
            " WHERE id = %s RETURNING total_xp",
            (amount, entity_id),
        ).fetchone()
        if row is None:
            return 1
        level, _ = compute_level(int(row[0]))
        connection.execute("UPDATE entity_record SET level = %s WHERE id = %s", (level, entity_id))
    return level


def save_allocation(pool: ConnectionPool, entity_id: int, stats: dict[str, int]) -> None:
    """능력치 배분을 저장한다. 검증은 부르는 쪽이 한다.

    Args:
        pool: 연결 풀.
        entity_id: PLAYER 개체 id.
        stats: 배분표.
    """
    with pool.connection() as connection:
        connection.execute(
            "UPDATE entity_record SET stat_json = %s, updated_at = now() WHERE id = %s",
            (Jsonb(stats), entity_id),
        )


def save_leaderboard(
    pool: ConnectionPool, mode: str, core_version: str, account_id: int, score: int, level: int
) -> None:
    """순위표를 갱신한다. 점수는 누적이므로 더 높을 때만 쓴다.

    Args:
        pool: 연결 풀.
        mode: 런 모드.
        core_version: 이 서버의 코어 버전. 시즌을 가르는 값이다.
        account_id: 계정 id.
        score: 누적 경험치.
        level: 레벨.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO leaderboard (mode, core_version, account_id, score, level)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (mode, core_version, account_id) DO UPDATE"
            " SET score = GREATEST(leaderboard.score, EXCLUDED.score),"
            "     level = GREATEST(leaderboard.level, EXCLUDED.level),"
            "     updated_at = now()",
            (mode, core_version, account_id, score, level),
        )


def list_leaderboard(
    pool: ConnectionPool, mode: str, core_version: str, limit: int = 50
) -> tuple[dict, ...]:
    """순위표를 읽는다.

    동점이면 먼저 도달한 쪽이 위다 — 늦게 같은 점수에 닿았다고 앞서면 안 된다.

    Args:
        pool: 연결 풀.
        mode: 런 모드.
        core_version: 시즌.
        limit: 최대 줄 수.

    Returns:
        순위 순 줄들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT a.handle, a.login_id, l.score, l.level, l.account_id"
            " FROM leaderboard l JOIN account a ON a.id = l.account_id"
            # 비활성 계정은 순위표에서 빠진다. 검사가 만든 계정이 1위에 있으면 순위표가
            # 말하는 것이 실력이 아니라 내 탐침 횟수가 된다.
            " WHERE l.mode = %s AND l.core_version = %s AND a.deactivated_at IS NULL"
            " ORDER BY l.score DESC, l.updated_at ASC LIMIT %s",
            (mode, core_version, limit),
        ).fetchall()
    return tuple(
        {
            "rank": index + 1,
            "handle": str(row[1]) if row[1] else str(row[0]),
            "score": int(row[2]),
            "level": int(row[3]),
            "account_id": int(row[4]),
        }
        for index, row in enumerate(rows)
    )
