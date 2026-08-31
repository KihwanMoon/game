"""몬스터끼리의 전투를 실제로 돌린다 (결정 #38, docs/설계/6_몬스터 §6).

**예전에는 레벨 차이에 확률을 얹은 판정이었다.** 그 자리에 "방과 배치가 정의되지
않았다" 는 주석이 붙어 있었는데, 지금은 방이 열 개 있고 지속 몬스터가 자기 스탯과
규칙표를 갖는다 — 확률로 대신할 이유가 사라졌다.

**이것이 바꾸는 것.** 세계 틱이 만들어 내는 레벨 변화가 이제 규칙표의 결과다. 잘 짜인
규칙표를 가진 개체가 살아남으므로, 플레이어가 나중에 만나는 몬스터는 "운 좋게 레벨이
오른 것" 이 아니라 "그 규칙표로 이겨 온 것" 이다. 도감이 규칙표를 그대로 보여주는 것도
그때 뜻을 갖는다.

두 개체를 **서로 다른 진영에 세운다.** 엔진의 적대 판정이 진영 기반이므로 그것만으로
붙는다. 한쪽을 플레이어 진영에 두는 것은 자리 이름일 뿐이며, 플레이어 스탯은 쓰지
않는다 — 스냅샷이 두 개체의 스탯을 모두 정한다.
"""

from dataclasses import dataclass, replace

from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import build_engine
from game.app.simulation.phases import OUTCOME_ONGOING
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.simulation.pressure import PressureTracker, build_pressure_rules
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity
from game.schemas.blocks import BlockCatalog
from game.schemas.monster_snapshot import MonsterSnapshot
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet

# 결투장의 두 자리. 방 템플릿의 이름과 겹치지 않아야 한다 — 겹치면 한쪽이 조용히
# 덮이고 그 개체는 싸우지 않은 채 진 것이 된다.
LEFT_ID = "duel_left"
RIGHT_ID = "duel_right"

# 결투는 짧게 끊는다. 서로 도망만 다니는 규칙표 둘이 만나면 상한까지 가는데, 세계 틱은
# 층마다 여러 쌍을 돌리므로 그 비용이 곱해진다.
DUEL_MAX_TICKS = 200

# 추격자가 절대 등장하지 않게 미는 값. **결투에는 추격자를 넣지 않는다** — 추격자는
# 플레이어의 지연을 벌하는 장치이고 언제나 적 진영에 붙는다 (GDD §7). 결투장에서는
# 그것이 오른쪽 편만 드는 것이 되어, 왼쪽 자리에 선 개체가 긴 싸움에서 반드시 진다.
# 실제로 이 자리를 처음 만들었을 때 강한 개체가 늘 지는 현상으로 드러났다.
NO_HUNTERS_TICK = DUEL_MAX_TICKS * 10


@dataclass(frozen=True)
class DuelResult:
    """결투 하나의 결과."""

    winner_record_id: int
    loser_record_id: int
    ticks: int
    # 시간 초과로 승부가 안 났는가.
    is_timeout: bool
    # 끝난 시점에 결투장에 있던 개체 이름들. **결투에 끼면 안 되는 것이 끼었는지**를
    # 밖에서 확인할 수 있어야 한다 — 추격자가 그렇게 한 번 끼어들었다.
    entity_ids: tuple[str, ...] = ()


def build_duel_entity(
    entity_id: str, snapshot: MonsterSnapshot, faction: str, position: tuple[int, int], base: dict
) -> Entity:
    """스냅샷 하나를 결투장에 세울 개체로 만든다.

    Args:
        entity_id: 결투장에서 쓸 자리 이름.
        snapshot: 그 개체의 얼어붙은 상태.
        faction: 세울 진영.
        position: 세울 자리.
        base: balance.json 의 그 적 절. 사거리·선공권처럼 스냅샷에 없는 값을 여기서 읽는다.

    Returns:
        만들어진 개체.
    """
    return Entity(
        entity_id=entity_id,
        kind_id=snapshot.kind_id,
        faction=faction,
        position=position,
        hp=snapshot.hp_max,
        hp_max=snapshot.hp_max,
        attack=snapshot.attack,
        defense=snapshot.defense,
        attack_range=int(base["attack_range"]),
        initiative=int(base["initiative"]),
        regen_base=int(base["regen_base"]),
        cpu_budget=snapshot.cpu_budget,
        consumables={"POTION": int(base.get("potions", 0))},
    )


def build_duel_pressure(balance: dict) -> PressureTracker:
    """결투용 압력 추적기를 만든다 — 추격자만 끈다.

    층 체류에 따른 공격력 증가와 전투 중 회복 감쇠는 그대로 둔다 — 그것은 양쪽에 똑같이
    걸리므로 공정하고, 끄면 서로 도망만 다니는 규칙표 둘이 상한까지 간다.

    Args:
        balance: 밸런스 딕셔너리.

    Returns:
        추격자가 등장하지 않는 추적기.
    """
    rules = replace(build_pressure_rules(balance["anti_abuse"]), hunter_spawn_tick=NO_HUNTERS_TICK)
    return PressureTracker(
        rules=rules, enemy_stats={kind["id"]: kind for kind in balance["enemies"]}
    )


def run_monster_duel(
    left: MonsterSnapshot,
    right: MonsterSnapshot,
    rulesets: tuple[RuleSet, RuleSet],
    template: RoomTemplate,
    balance: dict,
    catalog: BlockCatalog,
    seed: int,
) -> DuelResult:
    """두 지속 몬스터를 실제로 붙인다.

    **방의 원래 스폰은 전부 지운다.** 남겨 두면 결투에 제삼자가 끼어들어, 같은 두
    개체를 붙여도 방마다 다른 결과가 나온다.

    Args:
        left: 한쪽의 얼어붙은 상태.
        right: 다른 쪽.
        rulesets: 두 개체의 규칙표. 순서가 `left`·`right` 와 같아야 한다.
        template: 결투장으로 쓸 방.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        seed: 난수 시드. 같은 시드면 같은 결과다 (R5).

    Returns:
        결투 결과.
    """
    engine = build_engine(
        template,
        balance,
        seed=seed,
        max_ticks=DUEL_MAX_TICKS,
        pressure=build_duel_pressure(balance),
    )
    by_id = {kind["id"]: kind for kind in balance["enemies"]}
    # 방이 세워 둔 것을 전부 치운다 — 플레이어 자리도 포함이다.
    engine.state.entities.clear()

    spawns = [spawn.position for spawn in template.enemy_spawns]
    left_pos = template.player_spawn
    right_pos = spawns[0] if spawns else template.player_spawn
    engine.state.entities[LEFT_ID] = build_duel_entity(
        LEFT_ID, left, FACTION_PLAYER, left_pos, by_id[left.kind_id]
    )
    engine.state.entities[RIGHT_ID] = build_duel_entity(
        RIGHT_ID, right, FACTION_ENEMY, right_pos, by_id[right.kind_id]
    )
    engine.policies[LEFT_ID] = build_rule_vm(rulesets[0], catalog, engine.config.kind_types)
    engine.policies[RIGHT_ID] = build_rule_vm(rulesets[1], catalog, engine.config.kind_types)

    # `run_battle` 을 쓰지 않는다 — 그쪽은 `"player"` 라는 이름의 개체를 요구하고,
    # 결투장에는 그런 자리가 없다. 이름을 맞추려고 한쪽을 "player" 로 부르면 로그가
    # 거짓말을 한다.
    outcome = OUTCOME_ONGOING
    while outcome == OUTCOME_ONGOING:
        outcome = engine.run_tick()
    return build_duel_result(outcome, engine.state.tick, engine.state.entities, left, right)


def build_duel_result(
    outcome: str,
    ticks: int,
    entities: dict[str, Entity],
    left: MonsterSnapshot,
    right: MonsterSnapshot,
) -> DuelResult:
    """전투 결과를 결투 결과로 옮긴다.

    **시간 초과도 승부를 낸다.** 무승부로 두면 서로 도망만 다니는 규칙표 둘이 영원히
    같은 레벨에 머물고, 세계 틱이 그 쌍에 대해서는 아무 일도 하지 않게 된다.

    판정 기준은 **가한 피해 비율**이다(상대 최대 체력에 대한). 비율로 재는 이유는 최대
    체력이 서로 다르기 때문이며, 교차 곱셈으로 나눗셈을 피한다 (R5).

    남은 체력 비율로 재는 것과 **결과가 같다** — 남은 비율은 받은 피해 비율의 뒤집힘이라
    두 식이 대수적으로 동치다. 그래도 피해 쪽으로 적는 이유는 읽는 사람이 "누가 더 잘
    싸웠는가" 로 이해하게 하려는 것이지, 동작이 달라서가 아니다.

    Args:
        outcome: 엔진이 낸 판정.
        ticks: 걸린 틱.
        entities: 전투가 끝난 시점의 개체들.
        left: 왼쪽 개체의 스냅샷.
        right: 오른쪽 개체의 스냅샷.

    Returns:
        결투 결과.
    """
    left_entity = entities[LEFT_ID]
    right_entity = entities[RIGHT_ID]
    is_timeout = left_entity.hp > 0 and right_entity.hp > 0
    if is_timeout:
        left_dealt = right_entity.hp_max - right_entity.hp
        right_dealt = left_entity.hp_max - left_entity.hp
        left_wins = left_dealt * left_entity.hp_max >= right_dealt * right_entity.hp_max
    else:
        left_wins = outcome == OUTCOME_PLAYER_WIN
    winner, loser = (left, right) if left_wins else (right, left)
    return DuelResult(
        winner_record_id=winner.record_id,
        loser_record_id=loser.record_id,
        ticks=ticks,
        is_timeout=is_timeout,
        entity_ids=tuple(sorted(entities)),
    )
