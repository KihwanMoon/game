"""봇이 판마다 돌리는 정비 규칙 (설계/4_아이템 §5).

**봇도 사람과 같은 정비를 쓴다.** 예전에는 러너가 소모품을 끼워 주고 `REFILL` 한 줄만
세워 뒀다 — 그래서 봇의 장비는 굳고, 봉인은 안 열리고, 가방은 잡템으로 찼다. 사람이 쓰는
규칙 일곱이 이미 있는데 봇만 그것을 안 썼다.

**순서가 실행 순서다.** 아래 배치는 그 순서가 서로를 먹여 살리도록 짠 것이다.

    1  장비 교체    가방의 더 나은 것을 낀다. 벗은 것은 가방으로 간다
    2  소모품 교체  더 나은 소모품으로 갈아 낀다. 밀려난 것은 가방으로 간다
    3  재고 팔기    1·2 가 가방으로 내려보낸 것을 판다 — **돈을 여기서 만든다**
    4  봉인 해제    번 돈으로 연다. 여는 것은 지금 낀 것과 가방의 것
    5  복구         파손된 착용 장비를 고친다
    6  보충         끼운 소모품을 채운다
    7  버리기(전부) 남은 것을 버린다. 1 이 이미 쓸 것을 골라 간 뒤다

**파는 행이 쓰는 행보다 위인 것이 요점이다.** 아래에 두면 판 돈을 이번 정비에서 못 쓴다 —
화면의 검증이 그것을 일러 주는 바로 그 배치다 (`maintenanceRules.checkMaintenanceRows`).

**버리기가 맨 끝인 것도 요점이다.** 앞에 두면 갈아 끼울 후보를 먼저 버린다.

**「보통」이 아니라 「전부」다.** 등급으로 버리면 되찾은 것을 남기는데, 봇은 매 판 죽고
매 판 되찾으므로 **가방 전체에 그 표시가 붙는다** — 실제로 한 봇은 17칸이 17칸 다 되찾은
것이었고, 그래서 새 전리품이 들어올 자리가 없어 판마다 「가방이 가득 찼다」로 흘렸다.
1·2 가 위에서 최선을 끼우고 3 이 소모품을 팔고 난 뒤라, 여기 남은 것은 정의상 잉여다.
"""

from game.app.bots.personas import resolve_persona
from game.app.store.maintenance import (
    ACTION_DISCARD,
    ACTION_REFILL,
    ACTION_REPAIR,
    ACTION_SELL_STOCK,
    ACTION_UNSEAL,
    ACTION_UPGRADE_CONSUMABLE,
    ACTION_UPGRADE_GEAR,
    DISCARD_ALL,
    MaintenanceRow,
)

# 성격에서 장비 교체 우선순위로.
#
# **저울이 둘이면 봇이 장비를 두고 싸운다.** 성격표(`STAT_WEIGHTS`)와 우선순위표
# (`GEAR_PRIORITY_WEIGHTS`)가 서로 다른 답을 내면, 한쪽이 낀 것을 다른 쪽이 벗기는 일이
# 매 판 반복된다. 그래서 **장비 교체의 주인을 정비 규칙 하나로 정하고**(러너의
# `apply_bot_upgrade` 를 뺐다), 성격은 그 안에서 우선순위를 고르는 데만 쓴다.
#
# 근접은 붙어서 맞으므로 버티는 쪽, 원거리·시전은 닿는 거리와 화력이 값한다.
PERSONA_PRIORITY: dict[str, str] = {
    "ranged": "ATTACK",
    "caster": "ATTACK",
    "melee": "DEFENSE",
}


def build_bot_upkeep(ruleset_id: str) -> tuple[MaintenanceRow, ...]:
    """이 봇이 쓸 정비 행들을 만든다.

    Args:
        ruleset_id: 이 봇의 규칙표. 성격을 여기서 읽는다 — 능력치 배분·장비 교체가 쓰는
            것과 같은 표다.

    Returns:
        위에서 아래로 도는 행들.
    """
    priority = PERSONA_PRIORITY.get(resolve_persona(ruleset_id), "ATTACK")
    return (
        MaintenanceRow(ACTION_UPGRADE_GEAR, priority),
        MaintenanceRow(ACTION_UPGRADE_CONSUMABLE, ""),
        MaintenanceRow(ACTION_SELL_STOCK, ""),
        MaintenanceRow(ACTION_UNSEAL, ""),
        MaintenanceRow(ACTION_REPAIR, ""),
        MaintenanceRow(ACTION_REFILL, ""),
        MaintenanceRow(ACTION_DISCARD, DISCARD_ALL),
    )


def check_upkeep_matches(rows: tuple[MaintenanceRow, ...], ruleset_id: str) -> bool:
    """지금 행들이 이 봇의 표준 배치와 같은가.

    **같으면 안 쓴다.** 러너가 매 판 같은 값을 다시 저장하면 로그가 그것으로 덮이고,
    사람이 손으로 고친 배치도 매번 되돌아간다 — 다를 때만 세운다.

    Args:
        rows: 지금 저장된 행들.
        ruleset_id: 이 봇의 규칙표.

    Returns:
        같으면 참.
    """
    return rows == build_bot_upkeep(ruleset_id)
