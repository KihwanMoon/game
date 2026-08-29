"""데이터가 정하는 능력 — 소환·예고·회복 (GDD §4.2·§5).

규칙표는 `SUMMON` · `AREA_ATTACK` · `HEAL` 을 부를 뿐이고, 무엇을 몇 마리까지
부르는지·예고를 몇 틱 앞세우는지·얼마나 회복하는지는 balance.json 이 정한다. 그 둘을
잇는 자리다. 행동 실행기(actions.ActionExecutor)에 두지 않은 것은 모듈 400줄 규약
때문이며, 여기 있는 것은 결과와 로그 문자열만 돌려주고 기록은 실행기가 한다.

## 회복

블록 목록 v4 가 연 `HEAL` 이다. 사거리는 공격과 같은 규칙으로 잰다 — 스킬 자체 사거리가
없으면 시전자의 attack_range 다. **직선 시야는 묻지 않는다.** 대상별 시야를 묻는 인지
변수가 DSL 에 없어서, 요구하면 조건이 참인데 영영 실패하는 규칙을 플레이어가 고칠 방법이
없어진다 (P1). 사거리는 `대상 거리[ALLY_WOUNDED]` 로 물을 수 있으므로 사정이 다르다.

## 소환

**언제 부르는가는 규칙표가 정한다.** 주기는 `쿨타임[SUMMON]` 이 맡고 이 모듈은
'무엇을 · 어디에 · 몇 마리까지' 만 책임진다. 두 곳이 같은 것을 정하면 도감이
보여주는 규칙표와 실제 행동이 갈려 플레이어의 카운터가 빗나간다.

소환 위치는 인접 4칸을 고정 순서로 훑어 첫 빈 칸을 쓴다. 난수를 쓰지 않는 이유는
R5 다 — 같은 시드가 같은 자리를 내야 리플레이가 성립한다.

이 몸통은 원래 TickEngine.run_summons(UPKEEP)에 있었다. ACT 로 옮긴 것은 소환이
이번 틱의 이동 결과를 반영해야 하기 때문이다.
"""

from game.app.grid.geometry import get_manhattan_distance, iter_steps
from game.app.simulation.plan import EngineConfig, PlannedAction
from game.app.simulation.scaling import get_scaled_enemy_stats
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.telegraph import TelegraphBoard, build_blast_tiles
from game.schemas.room import WALKABLE_TILES

# 소환 쿨타임을 다는 키. 인지 변수 self_cooldown_ready[SUMMON] 가 이것을 읽는다.
SUMMON_ACTION = "SUMMON"

# 회복 쿨타임을 다는 키. 인지 변수 self_cooldown_ready[HEAL] 가 이것을 읽는다.
HEAL_ACTION = "HEAL"

# 정수 퍼센트의 분모. 부동소수를 쓰지 않으므로 비율은 전부 이 값으로 나눈다 (R5).
PERCENT_BASE = 100

# 포션이 채우는 몫. 최대 HP 의 절반이다.
POTION_HEAL_DIVISOR = 2


def count_alive_minions(state: WorldState, summoner_id: str) -> int:
    """그 소환사가 부른 개체 중 살아 있는 수 (GDD §7 무한 증식 차단).

    Args:
        state: 세계 상태.
        summoner_id: 소환사 엔티티 id.

    Returns:
        살아 있는 소환물 수.
    """
    return sum(1 for other in state.list_actors() if other.summoner_id == summoner_id)


def find_summon_position(state: WorldState, summoner: Entity) -> tuple[int, int] | None:
    """소환사 옆의 첫 빈 칸을 찾는다.

    Args:
        state: 세계 상태.
        summoner: 부른 쪽.

    Returns:
        놓을 좌표. 인접 4칸이 모두 막혔으면 None.
    """
    occupied = {other.position for other in state.list_actors()}
    for position in iter_steps(summoner.position):
        if state.get_tile(*position) in WALKABLE_TILES and position not in occupied:
            return position
    return None


def create_minion(
    state: WorldState,
    config: EngineConfig,
    summoner: Entity,
    kind_id: str,
    position: tuple[int, int],
) -> Entity:
    """소환물을 만들어 세계에 넣는다.

    층 깊이 스케일을 방 배치와 같은 함수로 건다. 걸지 않으면 층 3 의 대소환사가 층 1
    기준의 궁수를 부르게 되어, 소환을 방치하는 쪽이 층이 깊어질수록 유리해진다.

    Args:
        state: 세계 상태.
        config: 엔진 설정. 종류 스탯과 층 스케일을 여기서 읽는다.
        summoner: 부른 쪽. 진영과 소환 상한 계산의 기준이 된다.
        kind_id: 불러낼 종류 id.
        position: 놓을 좌표.

    Returns:
        등장한 개체.
    """
    stats = config.enemy_stats[kind_id]
    hp_max, attack = get_scaled_enemy_stats(stats, config.floor_scale, config.floor)
    # 일련번호는 단조 증가여야 같은 시드가 같은 id 를 만든다 (R5).
    state.spawn_counter += 1
    minion = Entity(
        entity_id=f"{kind_id}_s{state.spawn_counter}",
        kind_id=kind_id,
        faction=summoner.faction,
        position=position,
        hp=hp_max,
        hp_max=hp_max,
        attack=attack,
        defense=stats["defense"],
        attack_range=stats["attack_range"],
        initiative=stats["initiative"],
        regen_base=stats.get("regen_base", 0),
        cpu_budget=stats.get("cpu_budget", 0),
        potions=stats.get("potions", 0),
        summoner_id=summoner.entity_id,
    )
    state.entities[minion.entity_id] = minion
    return minion


def resolve_summon(
    state: WorldState, config: EngineConfig, summoner: Entity
) -> tuple[Entity | None, str]:
    """소환을 한 번 시도하고 결과를 말한다.

    상한에 걸린 틱에도 쿨타임을 다시 건다. 걸지 않으면 소환사가 매 틱 이 규칙에
    걸려 아래 규칙과 DEFAULT 가 영영 평가되지 않는다.

    Args:
        state: 세계 상태.
        config: 소환 규칙과 종류 스탯을 담은 설정.
        summoner: 부른 쪽.

    Returns:
        (등장한 개체 또는 None, 로그에 남길 결과 문자열).
    """
    rule = config.summon_rules.get(summoner.kind_id)
    if rule is None:
        return None, "소환 능력 없음 — 틱 낭비"
    summoner.cooldowns[SUMMON_ACTION] = rule["every_ticks"]
    alive = count_alive_minions(state, summoner.entity_id)
    if alive >= rule["max_alive"]:
        return None, f"동시 상한({alive}/{rule['max_alive']})"
    stats = config.enemy_stats.get(rule["spawns"])
    position = find_summon_position(state, summoner)
    if stats is None or position is None:
        return None, "놓을 자리 없음 — 틱 낭비"
    minion = create_minion(state, config, summoner, rule["spawns"], position)
    return minion, f"{minion.entity_id} 등장 {position}"


def register_blast(
    state: WorldState, board: TelegraphBoard, caster: Entity, telegraph: dict
) -> str:
    """즉발 광역기 대신 예고를 건다 (GDD §4.2).

    반경의 정본은 이 예고 설정이다 — actions.AREA_ATTACK_RADIUS 는 예고를 쓰지 않는
    즉발 광역기의 값이며 둘은 다른 능력이다.

    벽과 방 밖은 걸러 낸다. 거르지 않으면 닿지도 않는 칸이 붉게 칠해져, 플레이어가
    피할 필요가 없는 곳을 피하려 든다.

    Args:
        state: 세계 상태.
        board: 예고를 담을 판.
        caster: 시전자.
        telegraph: balance.json 의 그 종류 telegraph 절.

    Returns:
        로그에 남길 결과 문자열.
    """
    tiles = tuple(
        position
        for position in build_blast_tiles(caster.position, telegraph["radius"])
        if state.get_tile(*position) in WALKABLE_TILES
    )
    board.register(
        caster_id=caster.entity_id,
        skill_id=telegraph["skill"],
        tiles=tiles,
        damage=telegraph["damage"],
        lead_ticks=telegraph["lead_ticks"],
        visible_ticks=telegraph["visible_ticks"],
        cancel_on_death=telegraph["cancel_on_death"],
    )
    return f"예고 {len(tiles)}칸 — {telegraph['lead_ticks']}틱 뒤 발동"


def resolve_heal(
    state: WorldState, config: EngineConfig, actor: Entity, plan: PlannedAction
) -> tuple[int, str]:
    """셀렉터가 고른 아군을 회복한다 (GDD §5 치유형).

    회복량은 대상 최대 HP 의 정수 퍼센트다. 사거리 밖이거나 채울 여지가 없으면 회복하지
    않고 그 사유를 문자열로 돌려준다 — 쿨타임을 걸지 않아야 실행기가 그 틱을 낭비로
    적고, 플레이어가 규칙표의 어디를 고쳐야 하는지 알 수 있다 (P1).

    Args:
        state: 세계 상태.
        config: 엔진 설정. 회복 비율과 스킬 사거리를 여기서 읽는다.
        actor: 시전자.
        plan: 실행 중인 계획. 회복 행동 id 와 셀렉터가 고른 아군 id 를 담고 있다.

    Returns:
        (회복량, 로그에 남길 결과 문자열). 회복하지 못했으면 회복량이 0 이다.
    """
    target = state.entities.get(plan.target_id or "")
    if target is None or not target.is_alive:
        return 0, "대상 없음 — 틱 낭비"
    reach = config.skill_range.get(plan.action_id) or actor.attack_range
    distance = get_manhattan_distance(actor.position, target.position)
    if distance > reach:
        return 0, f"사거리 밖({distance} > {reach}) — 틱 낭비"
    percent = config.skill_heal_pct.get(plan.action_id, 0)
    amount = min(target.hp_max - target.hp, target.hp_max * percent // PERCENT_BASE)
    if amount <= 0:
        return 0, f"{target.entity_id} 회복 여지 없음 — 틱 낭비"
    target.hp += amount
    return amount, f"{target.entity_id} HP {target.hp}/{target.hp_max}"


def resolve_potion(entity: Entity) -> tuple[int | None, str]:
    """포션 하나를 써서 자기 HP 를 채운다.

    Args:
        entity: 사용자.

    Returns:
        (회복량, 로그에 남길 결과 문자열). 포션이 없으면 회복량이 None 이다 — 0 과
        구분해야 "만피라서 0" 과 "포션이 없어 아무 일도 없었다" 가 갈린다.
    """
    if entity.potions <= 0:
        return None, "포션 없음 — 틱 낭비"
    entity.potions -= 1
    healed = min(entity.hp_max - entity.hp, entity.hp_max // POTION_HEAL_DIVISOR)
    entity.hp += healed
    return healed, f"HP {entity.hp}/{entity.hp_max}"
