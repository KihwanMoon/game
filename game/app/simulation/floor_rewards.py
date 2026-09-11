"""고른 층 보상을 개체에 얹는다 (GDD §2.2).

**두 코어가 같은 자리에서 같은 만큼 얹어야 한다.** 전투는 브라우저가 돌리고 재시뮬은
서버가 하므로, 한쪽만 얹으면 같은 티켓이 두 결과를 낸다 (G3). 그래서 표(`schemas/reward`)
와 이 적용부가 짝으로 이식된다.

**그 층에 들어가기 전까지 고른 것만 산다.** 보상은 층을 깬 **뒤에** 고르는 것이라,
같은 층에 소급되면 이미 끝난 전투가 다르게 재현된다.
"""

from game.app.simulation.state import Entity
from game.schemas.reward import STAT_HP_MAX, count_charge_bonus, count_floor_bonus

# 보상이 만질 수 있는 개체 축. **표에 없는 축은 조용히 무시한다** — 카탈로그가 앞서
# 나갔을 때 엉뚱한 필드를 만드는 것보다, 안 얹고 넘어가는 편이 낫다.
ENTITY_STATS: frozenset[str] = frozenset({"attack", "defense", STAT_HP_MAX, "cpu_budget"})


def apply_floor_rewards(entity: Entity, taken: dict[int, str], floor: int) -> None:
    """이 층에 들어가는 개체에 지금까지 고른 보상을 얹는다.

    **최대 HP 는 현재 HP 도 함께 올린다.** 그러지 않으면 고른 그 순간에는 아무 일도 안
    일어나 보상으로 안 읽힌다 — 헤드리스 러너가 예전부터 쓰던 규칙과 같다.

    Args:
        entity: 이 층을 도는 개체.
        taken: 층에서 보상 id 로.
        floor: 지금 들어가는 층.
    """
    bonus = count_floor_bonus(taken, floor)
    for stat in sorted(ENTITY_STATS & set(bonus)):
        setattr(entity, stat, getattr(entity, stat) + bonus[stat])
    if bonus.get(STAT_HP_MAX):
        entity.hp += bonus[STAT_HP_MAX]
    for use_tag, count in sorted(count_charge_bonus(taken, floor).items()):
        entity.consumables[use_tag] = entity.consumables.get(use_tag, 0) + count


def count_hp_gain(taken: dict[int, str], floor: int, previous_floor: int) -> int:
    """층을 넘으며 새로 얻은 최대 HP.

    **인계 HP 에 얹을 값이다.** 방을 넘어갈 때 `player.hp` 를 인계값으로 덮으므로, 그
    사이에 고른 활력의 몫을 더해 주지 않으면 최대치만 늘고 몸은 그대로다.

    Args:
        taken: 층에서 보상 id 로.
        floor: 지금 들어가는 층.
        previous_floor: 직전 방의 층.

    Returns:
        더할 HP. 없으면 0.
    """
    now = count_floor_bonus(taken, floor).get(STAT_HP_MAX, 0)
    before = count_floor_bonus(taken, previous_floor).get(STAT_HP_MAX, 0)
    return max(0, now - before)
