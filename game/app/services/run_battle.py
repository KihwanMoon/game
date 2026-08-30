"""전투 1회 실행 — 방 하나를 끝까지 돌린다.

파일 하나가 시나리오 하나다 (표준 §12). 아래 계층의 모듈들을 엮어 하나의 흐름을 만든다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from game.app.combat.damage import build_damage_rules
from game.app.core.rng import DeterministicRng
from game.app.rules.fallback_policy import FallbackPolicy
from game.app.rules.rule_vm import build_rule_vm
from game.app.simulation.engine import TickEngine
from game.app.simulation.plan import OUTCOME_ONGOING, DecisionPolicy, EngineConfig
from game.app.simulation.pressure import PressureTracker, build_pressure_rules
from game.app.simulation.scaling import build_floor_scale, get_scaled_enemy_stats
from game.app.simulation.springs import init_spring_pools
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.config import SKILLS_PATH
from game.schemas.blocks import BlockCatalog
from game.schemas.loadout import BASE_SKILL_POWER_PCT, PlayerLoadout
from game.schemas.monster_snapshot import MonsterSnapshot, build_entity_id
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet


@dataclass(frozen=True)
class EnemyPolicyFactory:
    """kind_id 로 규칙표를 찾아 결정기를 만든다 (plan.PolicyFactory).

    전투 도중 등장하는 소환물·추격자에 규칙표를 붙이는 자리다. 조립 시점의 일괄
    배정은 그때 없던 개체에 닿지 못한다.
    """

    catalog: BlockCatalog
    kind_types: dict[str, str]
    ruleset_by_kind: dict[str, RuleSet]

    def build_policy(self, entity: Entity) -> DecisionPolicy | None:
        """그 엔티티의 결정기를 만든다.

        Args:
            entity: 대상 엔티티.

        Returns:
            규칙표가 있으면 RuleVM, 없으면 None.
        """
        ruleset = self.ruleset_by_kind.get(entity.kind_id)
        if ruleset is None:
            return None
        return build_rule_vm(ruleset, self.catalog, self.kind_types)


def build_enemy_policy_factory(
    balance: dict, catalog: BlockCatalog, enemy_rulesets: dict[str, RuleSet]
) -> EnemyPolicyFactory:
    """적 종류에서 규칙표로 가는 표를 미리 풀어 공장을 만든다.

    Args:
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        enemy_rulesets: ruleset_id 에서 규칙표로의 대응표.

    Returns:
        엔티티마다 결정기를 만들어 주는 공장.
    """
    by_kind = {
        kind["id"]: enemy_rulesets[kind["ruleset_id"]]
        for kind in balance["enemies"]
        if kind.get("ruleset_id") in enemy_rulesets
    }
    return EnemyPolicyFactory(
        catalog=catalog,
        kind_types={kind["id"]: kind["type"] for kind in balance["enemies"]},
        ruleset_by_kind=by_kind,
    )


@dataclass(frozen=True)
class BattleResult:
    """전투 한 판의 결과. 리플레이 검증이 이 값을 대조한다."""

    outcome: str
    ticks: int
    player_hp: int
    log_lines: tuple[str, ...]


def build_engine(
    template: RoomTemplate,
    balance: dict,
    seed: int,
    max_ticks: int = 400,
    floor: int = 1,
    pressure: PressureTracker | None = None,
    snapshots: tuple[MonsterSnapshot, ...] = (),
    loadout: PlayerLoadout | None = None,
) -> TickEngine:
    """방 템플릿과 밸런스 값으로 엔진을 조립한다.

    Args:
        template: 사용할 룸 템플릿.
        balance: balance.json 을 읽은 딕셔너리.
        seed: 난수 시드.
        max_ticks: 이 틱을 넘기면 시간 초과로 끝낸다.
        floor: 현재 층. 피해 공식의 방어 감쇠와 층 깊이 스케일이 이 값을 본다.
            층 1 이 balance.json 에 적힌 그대로이고, 한 층 내려갈 때마다 적의 최대
            HP 와 공격력에 floor_scale 의 퍼센트가 얹힌다.
        pressure: 층 단위 압력 추적기. 방마다 새로 만들면 층 체류 스케일이
            매 방 0 으로 돌아가므로 연쇄 실행은 하나를 만들어 계속 넘긴다.
        snapshots: 티켓이 얼려 둔 지속 몬스터 상태. 해당 자리의 층 스케일을 대체한다.
        loadout: 티켓이 얼려 둔 플레이어 전투 입력 (장비·레벨). 없으면 balance.json 의
            기본값으로 선다 — 오프라인 연습이 그 경우다.

    Returns:
        첫 틱을 돌릴 준비가 된 엔진.
    """
    rng = DeterministicRng(seed)
    state = WorldState(room=template, rng=rng)
    rules = build_pressure_rules(balance["anti_abuse"])
    # 채우지 않으면 생명의 샘이 회복을 한 점도 내지 못한다 (잔여량 0 = 마른 샘).
    init_spring_pools(state, rules.spring_pool_default)

    player_stats = balance["player"]
    # 로드아웃이 있으면 장비·레벨이 확정한 값이 기본값을 **대체한다** (결정 #13).
    # 얹으면 같은 장비가 밸런스 패치마다 다른 값을 낸다.
    hp_max = loadout.hp_max if loadout else player_stats["hp_max"]
    state.entities["player"] = Entity(
        entity_id="player",
        kind_id="player",
        faction=FACTION_PLAYER,
        position=template.player_spawn,
        hp=hp_max,
        hp_max=hp_max,
        attack=loadout.attack if loadout else player_stats["attack"],
        defense=loadout.defense if loadout else player_stats["defense"],
        attack_range=loadout.attack_range if loadout else player_stats["attack_range"],
        initiative=loadout.initiative if loadout else player_stats["initiative"],
        regen_base=player_stats["regen_base"],
        cpu_budget=loadout.cpu_budget if loadout else player_stats["cpu_budget"],
        # 지능이 올린 스킬위력. 로드아웃이 없으면 기준값이라 기존 판이 그대로다.
        skill_power_pct=loadout.skill_power_pct if loadout else BASE_SKILL_POWER_PCT,
        potions=player_stats["potions"],
        # None 은 "장착 개념이 배선되지 않음" 이라 전부 허용한다 — 오프라인 연습이
        # 그 경우다. 로드아웃이 있으면 그 목록만 쓴다.
        skills=loadout.skills if loadout else None,
    )

    kinds = balance["enemies"]
    by_id = {kind["id"]: kind for kind in kinds}
    scale = build_floor_scale(balance.get("floor_scale", {}))
    # 스냅샷은 entity_id 로 겹친다. 방 배치가 `{kind}_{index}` 로 붙이므로 그 이름을
    # 겨냥하며, 이름이 갈리면 스냅샷이 아무에게도 적용되지 않고 그 사실이 조용히 넘어간다.
    overrides = {item.entity_id: item for item in snapshots}
    for index, spawn in enumerate(template.enemy_spawns):
        kind = by_id[spawn.kind]
        entity_id = build_entity_id(kind["id"], index)
        hp_max, attack = get_scaled_enemy_stats(kind, scale, floor)
        defense = kind["defense"]
        cpu_budget = kind.get("cpu_budget", 0)
        # 지속 몬스터가 이 자리에 있으면 얼려 둔 상태가 층 스케일을 **대체한다**.
        # 얹으면 같은 개체가 층마다 다른 값을 갖게 되어 스냅샷의 뜻이 사라진다.
        found = overrides.get(entity_id)
        if found is not None:
            hp_max, attack, defense, cpu_budget = (
                found.hp_max,
                found.attack,
                found.defense,
                found.cpu_budget,
            )
        state.entities[entity_id] = Entity(
            entity_id=entity_id,
            kind_id=kind["id"],
            faction=FACTION_ENEMY,
            position=spawn.position,
            hp=hp_max,
            hp_max=hp_max,
            attack=attack,
            defense=defense,
            attack_range=kind["attack_range"],
            initiative=kind["initiative"],
            regen_base=kind["regen_base"],
            cpu_budget=cpu_budget,
            potions=kind.get("potions", 0),
        )

    config = EngineConfig(
        damage_rules=build_damage_rules(balance["damage_formula"]),
        kind_types={kind["id"]: kind["type"] for kind in kinds},
        skill_coef_pct={skill["id"]: skill["coef_pct"] for skill in balance["skills"]},
        skill_range={skill["id"]: skill.get("range") for skill in balance["skills"]},
        skill_cooldowns={skill["id"]: skill["cooldown"] for skill in balance["skills"]},
        skill_guard_pct={
            skill["id"]: skill["guard_pct"] for skill in balance["skills"] if "guard_pct" in skill
        },
        skill_guard_ticks={
            skill["id"]: skill["guard_ticks"]
            for skill in balance["skills"]
            if "guard_ticks" in skill
        },
        skill_heal_pct={
            skill["id"]: skill["heal_pct"] for skill in balance["skills"] if "heal_pct" in skill
        },
        summon_rules={k["id"]: k["summon"] for k in kinds if "summon" in k},
        enemy_stats={k["id"]: k for k in kinds},
        floor_scale=scale,
        floor=floor,
        max_ticks=max_ticks,
        combat_regen_pct=rules.combat_regen_pct,
    )
    tracker = pressure or PressureTracker(rules=rules, enemy_stats={k["id"]: k for k in kinds})
    # 층은 엔진이 정본이다. 넘겨받은 추적기에도 덮어써야 층 3 에서 뒤늦게 나온 추격자만
    # 층 1 스탯으로 서는 일이 없다 — 추적기는 층 단위 객체라 방마다 재사용된다.
    tracker.floor = floor
    tracker.floor_scale = scale
    return TickEngine(state=state, policy=FallbackPolicy(), config=config, pressure=tracker)


def assign_enemy_policies(
    engine: TickEngine, balance: dict, catalog: BlockCatalog, enemy_rulesets: dict[str, RuleSet]
) -> None:
    """적 엔티티에 각자의 규칙표를 붙인다 (GDD §5).

    붙이지 않으면 적이 폴백 정책으로 싸운다. 그러면 도감이 보여줄 규칙표와 실제 행동이
    달라져, 플레이어가 도감을 읽고 세운 카운터가 통하지 않는다.

    Args:
        engine: 대상 엔진.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        enemy_rulesets: ruleset_id 에서 규칙표로의 대응표.
    """
    # 공장을 함께 걸어 둔다. 소환물·추격자는 여기 없는 개체이므로 이것이 없으면
    # 그들만 폴백 정책으로 싸운다.
    engine.policy_factory = build_enemy_policy_factory(balance, catalog, enemy_rulesets)
    engine.register_newcomers()


def run_battle(engine: TickEngine) -> BattleResult:
    """승패가 갈릴 때까지 틱을 돌린다.

    Args:
        engine: 조립된 엔진.

    Returns:
        결과와 로그.
    """
    outcome = OUTCOME_ONGOING
    while outcome == OUTCOME_ONGOING:
        outcome = engine.run_tick()
    player = engine.state.entities["player"]
    return BattleResult(
        outcome=outcome,
        ticks=engine.state.tick,
        player_hp=player.hp,
        log_lines=engine.log.format_lines(),
    )


def load_balance(source_path: Path, skills_path: Path | None = None) -> dict:
    """밸런스 JSON 을 읽는다. 스킬은 별도 파일에서 합친다.

    스킬을 갈라 둔 이유는 수명이 다르기 때문이다 — 밸런스 수치는 조정되는 것이고 스킬은
    종류가 늘어나는 것이다. 합치는 자리를 여기 하나로 두어, 읽는 쪽은 예전처럼
    `balance["skills"]` 를 그대로 본다. 소비자마다 두 파일을 알게 하면 새 소비자가
    생길 때마다 합치는 코드가 늘고, 언젠가 한 곳이 빠진다.

    Args:
        source_path: balance.json 경로.
        skills_path: skills.json 경로. 생략하면 기본 위치를 쓴다.

    Returns:
        읽어들인 딕셔너리. `skills` 절이 합쳐져 있다.
    """
    balance = json.loads(source_path.read_text(encoding="utf-8"))
    skills = json.loads((skills_path or SKILLS_PATH).read_text(encoding="utf-8"))
    balance["skills"] = skills["skills"]
    return balance
