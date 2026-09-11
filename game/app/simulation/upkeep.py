"""한 개체에게 이 틱에 **저절로** 일어나는 것 (페이즈 1, GDD §7).

`engine.py` 에서 갈라 나왔다. 저쪽은 **페이즈를 순서대로 돌리는 것**이고 여기는
**아무도 고르지 않은 변화**다 — 쿨타임이 줄고, 상태이상이 한 틱 빠지고, 용암이 태우고,
회복이 찬다. 규칙표가 관여하지 않는 유일한 구간이며, 파일이 400줄 상한을 넘은 것이
계기였을 뿐 가르는 선은 책임이다 (§4).
"""

from game.app.simulation.actions import ActionExecutor
from game.app.simulation.phases import PHASE_UPKEEP
from game.app.simulation.plan import EngineConfig
from game.app.simulation.springs import apply_spring_drain
from game.app.simulation.state import Entity, WorldState
from game.schemas.room import TILE_LAVA, TILE_SPRING

# 용암 한 틱의 피해. 지형이 주는 것이라 방어를 안 본다.
LAVA_DAMAGE = 3

# 샘이 한 틱에 내주는 회복량. 잔여량이 있는 동안만 나온다.
SPRING_REGEN_PER_TICK = 2

# 백분율 기준. 부동소수를 안 쓰므로 정수 곱·내림 나눗셈으로 간다 (R5).
PERCENT_BASE = 100


def apply_entity_upkeep(
    state: WorldState,
    config: EngineConfig,
    executor: ActionExecutor,
    entity: Entity,
    *,
    in_combat: bool,
) -> None:
    """개체 하나의 유지 단계를 처리한다.

    **쿨타임·상태이상을 먼저 줄인다.** 이번 틱의 규칙표가 읽는 값이므로, 피해·회복보다
    뒤에 두면 방금 건 상태가 그 틱에 한 번 더 남아 있는 것으로 읽힌다.

    Args:
        state: 세계 상태.
        config: 엔진 설정. 전투 중 회복 감쇠를 여기서 읽는다.
        executor: 피해를 넣을 실행기. 용암도 `apply_damage` 하나를 거친다 — 직접 HP 를
            깎으면 시전 취소와 피격 로그가 조용히 빠진다.
        entity: 대상.
        in_combat: 전투 중인가.
    """
    for skill, remaining in entity.cooldowns.items():
        entity.cooldowns[skill] = max(0, remaining - 1)
    for status, remaining in entity.statuses.items():
        entity.statuses[status] = max(0, remaining - 1)
    if state.get_tile(*entity.position) == TILE_LAVA:
        executor.apply_damage(
            entity, LAVA_DAMAGE, PHASE_UPKEEP, "용암 위", actor_id=entity.entity_id
        )
    apply_regen(state, config, entity, in_combat=in_combat)


def apply_regen(
    state: WorldState, config: EngineConfig, entity: Entity, *, in_combat: bool
) -> None:
    """회복을 적용한다. 전투 중에는 감쇠하고 샘은 잔여량을 깎는다 (GDD §7).

    Args:
        state: 세계 상태.
        config: 엔진 설정.
        entity: 대상.
        in_combat: 전투 중인가.
    """
    tile_regen = 0
    position = entity.position
    if state.get_tile(*position) == TILE_SPRING:
        # 잔여량 항목이 없는 좌표에 0 을 써 넣지 않는다 — 써 넣으면 그 샘이
        # 초기화되기도 전에 RESOLVE 의 소멸 대상이 된다.
        tile_regen = apply_spring_drain(state, position, SPRING_REGEN_PER_TICK)
    # 전투 중 감쇠는 GDD §7 의 어뷰징 차단이다. 정수 연산이라 regen_base 1 은
    # 전투 중 0 이 된다 — 문서의 0.5 를 내림한 값이며 의도된 결과다.
    regen_pct = config.combat_regen_pct if in_combat else PERCENT_BASE
    base = entity.regen_base * regen_pct // PERCENT_BASE
    healed = min(entity.hp_max - entity.hp, base + tile_regen)
    if healed > 0:
        entity.hp += healed
