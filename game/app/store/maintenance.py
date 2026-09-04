"""정비 규칙 — 런이 끝나면 서버가 자동으로 손본다 (설계/4_아이템 §5).

**전투 규칙표의 형제이지 그 일부가 아니다.** 전투 규칙은 결정론 코어 안에서 돌고 두
코어가 재현해야 하지만(R5·G3), 정비는 계정 상태를 만지는 서버의 일이다 — 블록으로
만들면 시즌이 갈리고 재시뮬이 복잡해질 뿐이다.

**조립식이되 어휘는 닫혀 있다.** 처음에는 스위치 셋이었는데, 전투 규칙처럼 행을 더하고
빼고 순서를 바꾸고 싶다는 요청으로 정렬된 행 목록이 됐다 — 행동과 인자는 여전히 닫힌
목록이다. 자유 조건식은 전투 DSL 의 자리다.
"""

import json
from dataclasses import dataclass

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

# 정비가 아는 행동들. 닫힌 목록이다 — 모르는 행동이 조용히 무시되면, 켰다고 믿은
# 정비가 안 돈다.
ACTION_DISCARD = "DISCARD"
ACTION_REPAIR = "REPAIR"
ACTION_REFILL = "REFILL"
ACTION_SELL_STOCK = "SELL_STOCK"
ACTION_UNSEAL = "UNSEAL"
ACTION_UPGRADE_GEAR = "UPGRADE_GEAR"
ACTION_UPGRADE_CONSUMABLE = "UPGRADE_CONSUMABLE"
MAINTENANCE_ACTIONS: tuple[str, ...] = (
    ACTION_DISCARD,
    ACTION_REPAIR,
    ACTION_REFILL,
    ACTION_SELL_STOCK,
    ACTION_UNSEAL,
    ACTION_UPGRADE_GEAR,
    ACTION_UPGRADE_CONSUMABLE,
)

# 「전부」. 등급이 아니라 **등급을 안 본다는 뜻**이라 인자 목록에 함께 산다 — 자리를
# 따로 만들면 화면·검증·문장이 각자 이 값을 알아야 한다.
DISCARD_ALL = "ALL"

# 버리기가 받는 인자.
#
# **「전부」는 정말 전부다** — 등급도 유물도 되찾음 표시도 안 본다. 원래는 등급 둘뿐이었고
# 유물을 일부러 뺐는데(최상급을 자동으로 버리는 규칙은 오조작이 사고가 된다), 그 조심이
# 실제로는 **가방을 영영 안 비우는** 결과를 냈다: 되찾음 표시가 붙은 잡템이 쌓여 새
# 전리품이 들어올 자리가 없어졌다.
#
# 그래서 조심을 없앤 것이 아니라 **고르게** 했다. 등급을 고르면 지금까지처럼 되찾은 것을
# 남기고, 「전부」를 고르면 그 보호까지 함께 내려놓는다 — 이 값을 고르는 것 자체가 그
# 선언이다. 위에서 「장비 교체」가 최선을 끼운 뒤라야 남은 것이 잉여라는 말이 성립하므로,
# 순서가 틀리면 화면이 경고한다 (`maintenanceRules.checkMaintenanceRows`).
DISCARD_CHOICES: tuple[str, ...] = ("COMMON", "FINE", DISCARD_ALL)

# 장비 교체가 받는 우선순위. 무게는 `bots/upgrade.GEAR_PRIORITY_WEIGHTS` 가 든다 —
# 여기는 **어휘**이고 거기는 **저울**이다.
GEAR_PRIORITY_CHOICES: tuple[str, ...] = ("ATTACK", "DEFENSE")

# 행동에서 그 행동이 받는 인자 목록으로. **여기 없는 행동은 인자를 안 받는다.**
# 표 하나로 두는 이유는, 행동을 더할 때 검증·화면·문장이 각자 목록을 들면 셋이 갈리기
# 때문이다 — 실제로 등급 목록이 그렇게 두 곳에 있었다.
ACTION_ARGUMENTS: dict[str, tuple[str, ...]] = {
    ACTION_DISCARD: DISCARD_CHOICES,
    ACTION_UPGRADE_GEAR: GEAR_PRIORITY_CHOICES,
}

# 행 수 상한. 행동이 일곱이라 그보다 조금 넉넉하다 — 같은 행동을 인자만 바꿔 두 번
# 두는 배치(보통 버리고 상급도 버리고)가 흔해서다.
MAX_ROWS = 10


@dataclass(frozen=True)
class MaintenanceRow:
    """정비 규칙 한 행. 위에서 아래로 순서대로 돈다 — 전투 규칙표와 같은 규약이다."""

    action: str
    # **이 행동의 인자다.** 이름이 `grade` 인 것은 처음 만든 행동(버리기)이 등급만
    # 받았기 때문이고, 저장된 절의 키라 못 바꾼다 — 뜻은 「인자」이며 무엇을 받는지는
    # `ACTION_ARGUMENTS` 가 정한다. 인자를 안 받는 행동은 빈 문자열이다.
    grade: str = ""


def check_rows(rows: tuple[MaintenanceRow, ...]) -> str:
    """행 목록이 닫힌 어휘 안에 있는지 본다.

    Args:
        rows: 검사할 행들.

    Returns:
        문제가 없으면 빈 문자열, 있으면 사유.
    """
    if len(rows) > MAX_ROWS:
        return f"행이 {MAX_ROWS}개를 넘는다"
    for row in rows:
        if row.action not in MAINTENANCE_ACTIONS:
            return f"모르는 행동이다: {row.action}"
        allowed = ACTION_ARGUMENTS.get(row.action)
        if allowed is None:
            if row.grade:
                return f"{row.action} 은 인자를 받지 않는다"
            continue
        if row.grade not in allowed:
            return f"{row.action} 이 받을 수 없는 인자다: {row.grade or '(빈 값)'}"
    return ""


def read_maintenance(pool: ConnectionPool, account_id: int) -> tuple[MaintenanceRow, ...]:
    """이 계정의 정비 행들을 순서대로 읽는다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        행들. 저장한 적이 없으면 빈 목록이다 — **자동으로 켜지 않는다.** 돈이 나가고
        아이템이 사라지는 일은 사람이 켠 것이어야 한다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT rows FROM maintenance_rule WHERE account_id = %s", (account_id,)
        ).fetchone()
    raw = row[0] if row else None
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return ()
    return tuple(
        MaintenanceRow(action=str(item.get("action", "")), grade=str(item.get("grade", "")))
        for item in raw
        if isinstance(item, dict)
    )


def save_maintenance(
    pool: ConnectionPool, account_id: int, rows: tuple[MaintenanceRow, ...]
) -> None:
    """정비 행들을 저장한다. 순서 그대로다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        rows: 저장할 행들.
    """
    payload = [{"action": row.action, "grade": row.grade} for row in rows]
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO maintenance_rule (account_id, rows) VALUES (%s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET rows = EXCLUDED.rows",
            (account_id, Jsonb(payload)),
        )
