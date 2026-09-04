"""봇과 도플갱어의 현황 조회 (관리 화면).

**성격만 보면 아무것도 모른다.** 규칙표와 실력은 우리가 정해 준 값이라 화면에 적어도
새 사실이 없다. 알아야 할 것은 **그래서 어떻게 됐는가** 다 — 몇 판을 돌았고, 어디까지
내려갔고, 무엇을 벌었는가. 그것이 「봇을 늘릴까 줄일까」를 정하는 근거다.

한 번의 조회로 낸다. 봇마다 따로 물으면 열 번이 되고, 화면 한 장을 그리는 데 열 번을
왕복하면 그 화면은 안 쓰이게 된다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class BotRow:
    """봇 하나의 현황."""

    account_id: int
    handle: str
    label: str
    ruleset_id: str
    cadence_sec: int
    skill_pct: int
    is_active: bool
    # 다음 출격까지 남은 초. 음수면 이미 차례다.
    due_in_sec: int
    # 제출 수와 그중 확정된 승리. **승리가 0이면 그 봇은 세계에 아무것도 안 남긴다.**
    runs: int
    wins: int
    best_floor: int
    balance: int
    items: int


@dataclass(frozen=True)
class DoppelRow:
    """도플갱어 하나의 현황."""

    record_id: int
    zone_floor: int
    level: int
    alive: bool
    entity_slot: str
    # 누구의 그림자인가. 봇이 지워졌으면 빈 문자열이다.
    origin_handle: str
    # 남은 목숨. 다 쓰면 세계에서 지워지므로 **여기 보이는 것은 늘 1 이상**이다.
    lives: int = 1


def list_bot_rows(pool: ConnectionPool) -> tuple[BotRow, ...]:
    """봇 현황을 한 번에 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        계정 id 순의 현황들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT b.account_id, a.handle, b.label, b.ruleset_id, b.cadence_sec,"
            " b.skill_pct, b.is_active,"
            " EXTRACT(EPOCH FROM (b.next_run_at - now()))::int,"
            # 제출은 계정을 직접 안 들고 티켓을 거친다. 티켓이 그 런의 입력 전부를
            # 쥔 정본이라 계정도 거기 있다 — 제출에 복사해 두면 둘이 갈릴 수 있다.
            " (SELECT count(*) FROM run_submission s JOIN run_ticket t ON t.id = s.ticket_id"
            "  WHERE t.account_id = b.account_id),"
            " (SELECT count(*) FROM run_submission s JOIN run_ticket t ON t.id = s.ticket_id"
            "  JOIN run_result r ON r.submission_id = s.id"
            "  WHERE t.account_id = b.account_id AND r.outcome = 'PLAYER_WIN'),"
            " COALESCE((SELECT (m.payload->>'best_floor')::int FROM meta_save m"
            "  WHERE m.account_id = b.account_id), 0),"
            " COALESCE((SELECT w.balance FROM wallet w WHERE w.account_id = b.account_id), 0),"
            # 아이템은 계정이 아니라 **플레이어 개체**가 든다. 계정과 개체를 하나로
            # 보면 나중에 한 계정이 개체를 둘 갖게 될 때 조용히 틀린 수를 적는다.
            " (SELECT count(*) FROM item_instance i JOIN entity_record p"
            "  ON p.id = i.owner_entity_id"
            "  WHERE p.kind = 'PLAYER' AND p.owner_account_id = b.account_id)"
            " FROM bot_profile b JOIN account a ON a.id = b.account_id"
            " ORDER BY b.account_id"
        ).fetchall()
    return tuple(
        BotRow(
            account_id=int(row[0]),
            handle=str(row[1]),
            label=str(row[2]),
            ruleset_id=str(row[3]),
            cadence_sec=int(row[4]),
            skill_pct=int(row[5]),
            is_active=bool(row[6]),
            due_in_sec=int(row[7] or 0),
            runs=int(row[8] or 0),
            wins=int(row[9] or 0),
            best_floor=int(row[10] or 0),
            balance=int(row[11] or 0),
            items=int(row[12] or 0),
        )
        for row in rows
    )


def list_doppel_rows(pool: ConnectionPool) -> tuple[DoppelRow, ...]:
    """도플갱어 현황을 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        층·레코드 순의 현황들. 없으면 비어 있다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT e.id, COALESCE(e.zone_floor, 0), e.level, e.alive,"
            " COALESCE(e.entity_slot, ''), COALESCE(a.handle, ''), e.lives"
            " FROM entity_record e LEFT JOIN account a ON a.id = e.origin_account_id"
            " WHERE e.kind = 'MONSTER' AND e.is_doppel"
            " ORDER BY COALESCE(e.zone_floor, 0), e.id"
        ).fetchall()
    return tuple(
        DoppelRow(
            record_id=int(row[0]),
            zone_floor=int(row[1]),
            level=int(row[2]),
            alive=bool(row[3]),
            entity_slot=str(row[4]),
            origin_handle=str(row[5]),
            lives=int(row[6]),
        )
        for row in rows
    )
