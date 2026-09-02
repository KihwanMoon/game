"""정비 규칙 — 런이 끝나면 서버가 자동으로 손본다 (설계/4_아이템 §5).

**전투 규칙표의 형제이지 그 일부가 아니다.** 전투 규칙은 결정론 코어 안에서 돌고 두
코어가 재현해야 하지만(R5·G3), 정비는 계정 상태(가방·지갑·소모품 칸)를 만지는 서버의
일이다 — 블록으로 만들면 시즌이 갈리고 재시뮬이 복잡해질 뿐 얻는 것이 없다.

그래서 닫힌 목록의 스위치다. 켜 두면 **티켓이 닫힐 때**(죽거나 완주) 서버가 실행하고,
무엇을 했는지 한 줄로 돌려준다 — 조용한 자동화는 「왜 돈이 줄었지」가 된다 (P1).
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

# 버리기 규칙이 받는 등급. 닫힌 목록이다 — 자유 조건식은 전투 DSL 의 자리이지
# 정비의 자리가 아니다.
DISCARD_CHOICES: tuple[str, ...] = ("", "COMMON")


@dataclass(frozen=True)
class MaintenanceRule:
    """계정 하나의 정비 규칙."""

    # 런이 끝나면 끼운 소모품을 잔액 안에서 가득 채운다.
    is_refill_on: bool = False
    # 런이 끝나면 파손된 착용 장비를 잔액 안에서 복구한다.
    is_repair_on: bool = False
    # 이 등급의 가방 장비를 버린다. 빈 문자열이면 안 버린다.
    discard_grade: str = ""


def read_maintenance(pool: ConnectionPool, account_id: int) -> MaintenanceRule:
    """이 계정의 정비 규칙을 읽는다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        정비 규칙. 저장된 것이 없으면 전부 꺼진 기본값이다 — **자동으로 켜지 않는다.**
        돈이 나가고 아이템이 사라지는 일은 사람이 켠 것이어야 한다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT refill_on, repair_on, discard_grade FROM maintenance_rule"
            " WHERE account_id = %s",
            (account_id,),
        ).fetchone()
    if row is None:
        return MaintenanceRule()
    return MaintenanceRule(
        is_refill_on=bool(row[0]),
        is_repair_on=bool(row[1]),
        discard_grade=str(row[2] or ""),
    )


def save_maintenance(pool: ConnectionPool, account_id: int, rule: MaintenanceRule) -> None:
    """정비 규칙을 저장한다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        rule: 저장할 규칙.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO maintenance_rule (account_id, refill_on, repair_on, discard_grade)"
            " VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET"
            " refill_on = EXCLUDED.refill_on, repair_on = EXCLUDED.repair_on,"
            " discard_grade = EXCLUDED.discard_grade",
            (account_id, rule.is_refill_on, rule.is_repair_on, rule.discard_grade),
        )
