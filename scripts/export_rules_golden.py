"""RuleVM·검증기·셀렉터의 기준값을 JSON 으로 내보낸다 (게이트 G3).

Phase 3 의 TypeScript 코어는 파이썬 코어와 같은 답을 내야 한다. 눈으로 대조하면 회귀를
놓치므로 파이썬 쪽 출력을 파일로 고정해 두고 TS 테스트가 그 파일을 읽어 대조한다.
기준의 정본은 언제나 파이썬 코어다.

여기 담기는 것은 세 가지다.

* **셀렉터의 동점 처리** — 같은 거리·같은 HP 일 때 누구를 고르는가. PRNG 를 쓰지 않고
  entity_id 사전순으로 가르므로 답이 하나로 정해지며, 그 답이 갈리면 같은 시드가 다른
  전투를 만든다 (R5).
* **검증기의 위반 메시지** — 문자열과 **그 순서**까지 기준이다. 규칙 에디터가 이것을
  그대로 띄우므로 (P1), 메시지가 달라지면 플레이어가 보는 화면이 달라진다.
* **조건식의 렌더링** — `적거리(2) <= 사거리(3)` 처럼 양변에 실측값이 붙는가
  (GDD §8.2). 참/거짓만 맞고 문자열이 갈리면 로그가 쓸모없어진다.

세계는 서비스 계층을 거치지 않고 여기서 직접 세운다. TS 쪽에는 아직 서비스가 없어
`build_engine` 에 대응하는 것이 없기 때문이며, 엔티티 배치를 문서에 그대로 실어 두면
양쪽이 같은 입력에서 출발하는 것이 파일 하나로 확인된다.

    uv run python -m scripts.export_rules_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.core.rng import DeterministicRng
from game.app.rules.fallback_policy import FallbackPolicy
from game.app.rules.rule_vm import build_rule_vm, count_cpu_usage, evaluate_condition
from game.app.rules.validator import CPU_COST_BY_TERM_COUNT, validate_ruleset
from game.app.simulation.perception import PerceptionSnapshot, build_snapshot
from game.app.simulation.plan import PlannedAction
from game.app.simulation.selectors import ALL_SELECTORS, resolve_target
from game.app.simulation.state import Entity, WorldState
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import BlockCatalog, load_block_catalog
from game.schemas.room import RoomTemplate, load_room_templates
from game.schemas.ruleset import Condition, RuleSet, parse_ruleset

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/golden/rules_golden.json"

# 엔티티 명세 한 항목이 가질 수 있는 값. `Any` 를 쓰지 않는 이유는 오타 난 덮어쓰기를
# 검사가 잡아 주도록 하기 위한 것이다.
SpecValue = int | str | list[int]

# 조건 항의 우변. 리터럴이거나 `{"stat": ...}` 스탯 참조다 (F-2).
RhsValue = int | bool | dict[str, str]

# 세계 상태가 난수원을 요구하지만 이 스크립트는 난수를 뽑지 않는다. 고정 시드를 넣는
# 이유는 그것뿐이며, 값이 결과에 닿지 않는다.
RNG_SEED = 0

# 규칙표 파일의 별칭. TS 쪽 `resources.ts` 가 내보내는 상수 이름과 짝을 맞춘다.
RULESET_FILES = {
    "g0": G0_RULESETS_PATH,
    "enemies": ENEMY_RULESETS_PATH,
    "benchmark": BENCHMARK_RULESETS_PATH,
}

# 엔티티 종류에서 적 유형으로. balance.json 에는 BOSS 가 아직 없어 보스 셀렉터를 재려면
# 합성 종류가 하나 필요하다 — `throne_wraith` 가 그것이다.
KIND_TYPES = {
    "hero": "PLAYER",
    "goblin_rusher": "MELEE",
    "goblin_archer": "RANGED",
    "goblin_summoner": "SUMMONER",
    "bomb_slime": "BOMBER",
    "throne_wraith": "BOSS",
}

PLAYER_SPEC = {
    "entity_id": "player",
    "kind_id": "hero",
    "faction": "player",
    "position": [1, 4],
    "hp": 100,
    "hp_max": 100,
    "attack": 12,
    "defense": 5,
    "attack_range": 1,
    "initiative": 50,
    "regen_base": 1,
    "cpu_budget": 8,
    "potions": 2,
}


def build_entity_spec(**overrides: SpecValue) -> dict[str, Any]:
    """플레이어 명세를 바탕으로 엔티티 명세를 만든다.

    Args:
        **overrides: 바꿀 항목들.

    Returns:
        JSON 에 그대로 실을 수 있는 명세.
    """
    spec = dict(PLAYER_SPEC)
    spec.update(overrides)
    return spec


def build_enemy_spec(entity_id: str, kind_id: str, **overrides: SpecValue) -> dict[str, Any]:
    """적 엔티티 명세를 만든다.

    Args:
        entity_id: 엔티티 id. 셀렉터의 동점을 가르는 열쇠이기도 하다.
        kind_id: 종류 id. KIND_TYPES 가 유형으로 옮긴다.
        **overrides: 바꿀 항목들.

    Returns:
        JSON 에 그대로 실을 수 있는 명세.
    """
    spec = build_entity_spec(
        entity_id=entity_id,
        kind_id=kind_id,
        faction="enemy",
        hp=20,
        hp_max=24,
        attack=7,
        defense=2,
        attack_range=1,
        initiative=40,
        regen_base=0,
        cpu_budget=4,
        potions=0,
    )
    spec.update(overrides)
    return spec


# 세계 명세. 셀렉터 7종이 서로 다른 답을 내도록 거리·HP·공격력의 동점을 일부러 만든다.
#
#  field_mixed  거리 동점(e_alpha·e_bravo)과 HP 동점(e_alpha·e_charlie·e_echo)과
#               공격력 동점(e_charlie·e_echo)이 한 방에 있다. min 은 사전순으로 작은
#               쪽을, max 는 큰 쪽을 고른다 — 두 방향을 한 번에 확인한다.
#  throne       보스가 있는 방. BOSS 와 NEAREST 가 서로 다른 대상을 가리킨다.
#  spring       플레이어가 생명의 샘 위에 서 있고 HP 가 낮다. 폴백이 포션을 쓴다.
#  solitude     적이 없다. 셀렉터는 전부 빈손이고 RuleVM 은 HOLD 로 떨어진다.
#  wounded      HP 80·포션 2. AND/OR 조건의 참거짓이 갈리는 자리다.
WORLD_SPECS: tuple[dict[str, Any], ...] = (
    {
        "world_id": "field_mixed",
        "room_id": "open_field",
        "tick": 3,
        "casting_ids": ["e_delta"],
        "entities": [
            build_entity_spec(),
            build_enemy_spec("e_alpha", "goblin_rusher", position=[3, 4]),
            build_enemy_spec("e_bravo", "goblin_rusher", position=[1, 6], hp=24),
            build_enemy_spec(
                "e_charlie", "goblin_archer", position=[8, 4], hp=20, hp_max=20, attack=9
            ),
            build_enemy_spec(
                "e_delta", "goblin_summoner", position=[9, 6], hp=30, hp_max=30, attack=5
            ),
            build_enemy_spec(
                "e_echo", "goblin_summoner", position=[10, 2], hp=20, hp_max=30, attack=9
            ),
        ],
    },
    {
        "world_id": "throne",
        "room_id": "open_field",
        "tick": 12,
        "casting_ids": [],
        "entities": [
            build_entity_spec(hp=64),
            build_enemy_spec("e_minion", "goblin_rusher", position=[2, 4]),
            build_enemy_spec(
                "e_boss", "throne_wraith", position=[6, 4], hp=80, hp_max=80, attack=20
            ),
        ],
    },
    {
        "world_id": "spring",
        "room_id": "spring_bait",
        "tick": 5,
        "casting_ids": [],
        "entities": [
            build_entity_spec(position=[6, 4], hp=20),
            build_enemy_spec("e_archer", "goblin_archer", position=[10, 3], attack_range=4),
        ],
    },
    {
        "world_id": "solitude",
        "room_id": "open_field",
        "tick": 0,
        "casting_ids": [],
        "entities": [build_entity_spec()],
    },
    {
        "world_id": "wounded",
        "room_id": "open_field",
        "tick": 7,
        "casting_ids": [],
        "entities": [
            build_entity_spec(hp=80),
            build_enemy_spec("e_alpha", "goblin_rusher", position=[4, 4]),
        ],
    },
)


def build_term_document(
    lhs: str, comparison: str, rhs: RhsValue, lhs_param: str | None = None
) -> dict[str, Any]:
    """조건 항의 원시 절을 만든다.

    Args:
        lhs: 인지 변수 id.
        comparison: 비교 연산자.
        rhs: 리터럴 또는 `{"stat": ...}` 스탯 참조.
        lhs_param: 인자를 받는 인지 변수의 인자.

    Returns:
        parse_term 이 읽을 수 있는 절.
    """
    term: dict[str, Any] = {"lhs": lhs, "cmp": comparison, "rhs": rhs}
    if lhs_param is not None:
        term["lhs_param"] = lhs_param
    return term


def build_rule_document(
    priority: int,
    terms: list[dict[str, Any]],
    action: str,
    op: str = "SINGLE",
    target: str | None = None,
    set_flag: str | None = None,
    cpu_cost: int | None = None,
) -> dict[str, Any]:
    """규칙 한 줄의 원시 절을 만든다.

    Args:
        priority: 우선순위. 낮을수록 먼저 평가된다.
        terms: 조건 항들.
        action: 행동 id.
        op: 조건 연산자.
        target: 셀렉터 id.
        set_flag: `A=true` 형태의 플래그 기록.
        cpu_cost: CPU 비용. None 이면 항 수 기준값을 쓴다.

    Returns:
        parse_ruleset 이 읽을 수 있는 절.
    """
    return {
        "priority": priority,
        "conditions": {"op": op, "terms": terms},
        "action": action,
        "target": target,
        "set_flag": set_flag,
        "cpu_cost": CPU_COST_BY_TERM_COUNT.get(len(terms), 1) if cpu_cost is None else cpu_cost,
    }


def build_ruleset_document(rules: list[dict[str, Any]], ruleset_id: str = "x") -> dict[str, Any]:
    """규칙표의 원시 절을 만든다.

    Args:
        rules: 규칙 절들.
        ruleset_id: 규칙표 id.

    Returns:
        parse_ruleset 이 읽을 수 있는 절.
    """
    return {"ruleset_id": ruleset_id, "version": 1, "rules": rules}


def build_single_rule_document(
    priority: int,
    lhs: str,
    comparison: str,
    rhs: RhsValue,
    action: str,
    target: str | None = None,
    lhs_param: str | None = None,
    set_flag: str | None = None,
    cpu_cost: int | None = None,
) -> dict[str, Any]:
    """한 항짜리 규칙 절을 만든다. 파이썬 테스트의 `make_rule` 에 대응한다.

    Args:
        priority: 우선순위.
        lhs: 인지 변수 id.
        comparison: 비교 연산자.
        rhs: 리터럴 또는 스탯 참조.
        action: 행동 id.
        target: 셀렉터 id.
        lhs_param: 인지 변수의 인자.
        set_flag: 플래그 기록.
        cpu_cost: CPU 비용. None 이면 1.

    Returns:
        parse_ruleset 이 읽을 수 있는 절.
    """
    return build_rule_document(
        priority=priority,
        terms=[build_term_document(lhs, comparison, rhs, lhs_param)],
        action=action,
        target=target,
        set_flag=set_flag,
        cpu_cost=cpu_cost,
    )


def create_world(spec: dict[str, Any], rooms: dict[str, RoomTemplate]) -> WorldState:
    """세계 명세에서 세계 상태를 세운다.

    Args:
        spec: WORLD_SPECS 의 한 항목.
        rooms: 룸 템플릿 대응표.

    Returns:
        엔티티가 배치된 세계 상태.
    """
    state = WorldState(room=rooms[spec["room_id"]], rng=DeterministicRng(RNG_SEED))
    for entity_spec in spec["entities"]:
        fields = dict(entity_spec)
        fields["position"] = tuple(fields["position"])
        entity = Entity(**fields)
        state.entities[entity.entity_id] = entity
    state.tick = spec["tick"]
    state.casting_ids = tuple(spec["casting_ids"])
    return state


def build_selector_cases(worlds: dict[str, WorldState]) -> list[dict[str, Any]]:
    """셀렉터 7종이 각 세계에서 누구를 고르는지 적는다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.

    Returns:
        기준 항목 목록.
    """
    cases: list[dict[str, Any]] = []
    for spec in WORLD_SPECS:
        state = worlds[spec["world_id"]]
        actor = state.entities["player"]
        for selector_id in ALL_SELECTORS:
            picked = resolve_target(selector_id, actor, state, KIND_TYPES)
            cases.append(
                {
                    "world_id": spec["world_id"],
                    "actor_id": actor.entity_id,
                    "selector": selector_id,
                    "picked_id": None if picked is None else picked.entity_id,
                }
            )
    return cases


def build_validator_specs() -> list[dict[str, Any]]:
    """검증기 기준 항목의 입력만 적는다.

    파이썬 테스트 `tests/test_rule_vm.py` 의 검증기 절을 그대로 옮기고, 거기서 다루지
    않은 경계(목록에 없는 행동·셀렉터, 항 수 초과)를 더했다.

    Returns:
        위반 메시지를 아직 채우지 않은 입력 목록.
    """
    hold = "HOLD"
    overflow = [
        build_single_rule_document(i, "self_hp_percent", "<", 50, hold) for i in range(1, 7)
    ]
    stat_ref = {"stat": "no_such_stat"}
    return [
        {"name": "슬롯 초과", "ruleset": build_ruleset_document(overflow), "rule_slots": 5},
        {"name": "CPU 초과", "ruleset": build_ruleset_document(overflow[:4]), "cpu_budget": 2},
        {
            "name": "목록에 없는 인지 변수",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "does_not_exist", "<", 1, hold)]
            ),
        },
        {
            "name": "허용되지 않는 인자",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "flag_state", "==", True, hold, lhs_param="Z")]
            ),
        },
        {
            "name": "인자를 빠뜨린 인지 변수",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "flag_state", "==", True, hold)]
            ),
        },
        {
            "name": "인자를 받지 않는 인지 변수에 인자를 줬다",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold, lhs_param="A")]
            ),
        },
        {
            "name": "TARGET 이 필요한 행동",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, "ATTACK")]
            ),
        },
        {
            "name": "TARGET 을 받지 않는 행동",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold, target="NEAREST")]
            ),
        },
        {
            "name": "우선순위 중복",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, "self_hp_percent", "<", 50, hold),
                    build_single_rule_document(1, "self_potion_count", ">", 0, hold),
                ]
            ),
        },
        {
            "name": "CPU 비용 불일치",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold, cpu_cost=4)]
            ),
        },
        {
            "name": "해금되지 않은 블록",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold)]
            ),
            "unlocked": [hold],
        },
        {
            "name": "목록에 없는 스탯",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "target_distance", "<=", stat_ref, hold, lhs_param="NEAREST"
                    )
                ]
            ),
        },
        {
            "name": "불리언 블록과 스탯 비교",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_on_heal_tile", "==", {"stat": "attack_range"}, hold
                    )
                ]
            ),
        },
        {
            "name": "목록에 없는 행동",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, "NO_SUCH_ACTION")]
            ),
        },
        {
            "name": "목록에 없는 셀렉터",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_hp_percent", "<", 50, "ATTACK", target="NO_SUCH_SELECTOR"
                    )
                ]
            ),
        },
        {
            "name": "항 수 초과",
            "ruleset": build_ruleset_document(
                [
                    build_rule_document(
                        1,
                        [
                            build_term_document("self_hp_percent", "<", 50),
                            build_term_document("self_potion_count", ">", 0),
                            build_term_document("visible_enemy_count", ">", 0),
                            build_term_document("room_elapsed_ticks", ">", 0),
                        ],
                        hold,
                        op="AND",
                        cpu_cost=4,
                    )
                ]
            ),
        },
        {
            "name": "세 항 AND 는 통과한다",
            "ruleset": build_ruleset_document(
                [
                    build_rule_document(
                        1,
                        [
                            build_term_document("self_hp_percent", "<", 50),
                            build_term_document("self_potion_count", ">", 0),
                            build_term_document("visible_enemy_count", ">", 0),
                        ],
                        hold,
                        op="AND",
                    )
                ]
            ),
        },
        {"name": "g0 압박형은 통과한다", "ruleset_ref": ["g0", "g0_pressure"]},
        {"name": "g0 카이팅은 통과한다", "ruleset_ref": ["g0", "g0_kite"]},
        {"name": "g0 엄폐형은 통과한다", "ruleset_ref": ["g0", "g0_cover"]},
        {"name": "적 소환사 규칙표는 통과한다", "ruleset_ref": ["enemies", "ai_summoner"]},
        {"name": "벤치마크 규칙표는 통과한다", "ruleset_ref": ["benchmark", "focus_summoner"]},
    ]


def resolve_case_ruleset(case: dict[str, Any]) -> RuleSet:
    """검증기 항목이 가리키는 규칙표를 얻는다.

    Args:
        case: 인라인 `ruleset` 또는 `ruleset_ref` 를 가진 항목.

    Returns:
        읽어들인 규칙표.
    """
    if "ruleset" in case:
        return parse_ruleset(case["ruleset"])
    alias, ruleset_id = case["ruleset_ref"]
    raw = json.loads(RULESET_FILES[alias].read_text(encoding="utf-8"))
    found = next(item for item in raw["rulesets"] if item["ruleset_id"] == ruleset_id)
    return parse_ruleset(found)


def build_validator_cases(catalog: BlockCatalog) -> list[dict[str, Any]]:
    """검증기가 내는 위반 메시지를 순서까지 그대로 적는다.

    Args:
        catalog: 동결된 블록 카탈로그.

    Returns:
        기준 항목 목록.
    """
    default_budget = 99
    default_slots = 5
    cases: list[dict[str, Any]] = []
    for spec in build_validator_specs():
        case = dict(spec)
        case.setdefault("cpu_budget", default_budget)
        case.setdefault("rule_slots", default_slots)
        case.setdefault("unlocked", None)
        unlocked = case["unlocked"]
        case["problems"] = validate_ruleset(
            resolve_case_ruleset(case),
            catalog,
            case["cpu_budget"],
            case["rule_slots"],
            None if unlocked is None else frozenset(unlocked),
        )
        cases.append(case)
    return cases


def build_snapshot_cases(worlds: dict[str, WorldState]) -> list[dict[str, Any]]:
    """세계마다 플레이어의 인지 스냅샷을 적는다.

    지형 격자와 예고판은 넘기지 않는다. RuleVM 대조에 필요한 것은 "값이 없는 항은
    거짓" 이라는 계약이고, 그것을 재려면 값이 비어 있는 항이 있어야 하기 때문이다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.

    Returns:
        기준 항목 목록. values 는 파이썬 dict 의 삽입 순서 그대로다.
    """
    cases: list[dict[str, Any]] = []
    for spec in WORLD_SPECS:
        state = worlds[spec["world_id"]]
        actor = state.entities["player"]
        snapshot = build_snapshot(state, actor, KIND_TYPES)
        cases.append(
            {
                "world_id": spec["world_id"],
                "entity_id": actor.entity_id,
                "values": [[key, value] for key, value in snapshot.values.items()],
            }
        )
    return cases


def render_plan_document(plan: PlannedAction) -> dict[str, Any]:
    """계획을 JSON 으로 편다.

    Args:
        plan: 대조할 계획.

    Returns:
        JSON 에 실을 딕셔너리.
    """
    return {
        "entity_id": plan.entity_id,
        "action_id": plan.action_id,
        "target_id": plan.target_id,
        "rule_index": plan.rule_index,
        "expr": plan.expr,
        "set_flag": plan.set_flag,
    }


def build_condition_specs() -> list[dict[str, Any]]:
    """조건식 렌더링 기준의 입력만 적는다.

    Returns:
        결과를 아직 채우지 않은 입력 목록.
    """
    return [
        {
            "name": "AND 는 모든 항을 요구한다",
            "world_id": "wounded",
            "condition": {
                "op": "AND",
                "terms": [
                    build_term_document("self_hp_percent", "<", 50),
                    build_term_document("self_potion_count", ">", 0),
                ],
            },
        },
        {
            "name": "OR 는 한 항이면 된다",
            "world_id": "wounded",
            "condition": {
                "op": "OR",
                "terms": [
                    build_term_document("self_hp_percent", "<", 50),
                    build_term_document("self_potion_count", ">", 0),
                ],
            },
        },
        {
            "name": "스탯 우변은 양변에 실측값이 붙는다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [
                    build_term_document(
                        "target_distance", "<=", {"stat": "attack_range"}, "NEAREST"
                    )
                ],
            },
        },
        {
            "name": "모르는 스탯은 거짓이다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [
                    build_term_document(
                        "target_distance", "<=", {"stat": "no_such_stat"}, "NEAREST"
                    )
                ],
            },
        },
        {
            "name": "값이 없는 항은 거짓이다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("self_exposed_to_los", "==", True)],
            },
        },
        {
            "name": "대상이 없으면 대상 계열도 거짓이다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("target_hp_percent", "<", 50)],
            },
        },
        {
            "name": "대상 HP% 는 셀렉터가 고른 적을 가리킨다",
            "world_id": "field_mixed",
            "target_id": "e_echo",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("target_hp_percent", "<", 90)],
            },
        },
        {
            "name": "대상 시전 여부는 예고판을 읽는다",
            "world_id": "field_mixed",
            "target_id": "e_delta",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("target_is_casting", "==", True)],
            },
        },
        {
            "name": "CPU 여유는 VM 이 답한다",
            "world_id": "field_mixed",
            "cpu_headroom": 7,
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("self_cpu_headroom", ">=", 7)],
            },
        },
        {
            "name": "불리언 리터럴은 참거짓으로 적힌다",
            "world_id": "spring",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("self_on_heal_tile", "==", True)],
            },
        },
    ]


def build_condition_cases(
    worlds: dict[str, WorldState], snapshots: dict[str, PerceptionSnapshot], catalog: BlockCatalog
) -> list[dict[str, Any]]:
    """조건식의 참거짓과 렌더링 문자열을 적는다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.
        snapshots: 세계 id 에서 플레이어 스냅샷으로의 대응표.
        catalog: 라벨을 얻을 블록 카탈로그.

    Returns:
        기준 항목 목록.
    """
    cases: list[dict[str, Any]] = []
    for spec in build_condition_specs():
        case = dict(spec)
        case.setdefault("target_id", None)
        case.setdefault("cpu_headroom", None)
        state = worlds[case["world_id"]]
        target_id = case["target_id"]
        fired, expr = evaluate_condition(
            Condition(
                op=case["condition"]["op"],
                terms=parse_ruleset(
                    build_ruleset_document(
                        [build_rule_document(1, case["condition"]["terms"], "HOLD")]
                    )
                )
                .rules[0]
                .conditions.terms,
            ),
            snapshots[case["world_id"]],
            None if target_id is None else state.entities[target_id],
            catalog,
            case["cpu_headroom"],
            actor=state.entities["player"],
            casting_ids=state.casting_ids,
        )
        case["fired"] = fired
        case["expr"] = expr
        cases.append(case)
    return cases


def build_rule_vm_specs() -> list[dict[str, Any]]:
    """RuleVM 실행 규약 기준의 입력만 적는다.

    Returns:
        계획을 아직 채우지 않은 입력 목록.
    """
    hold = "HOLD"
    hp_true = ("self_hp_percent", "<=", 100)
    return [
        {
            "name": "최초로 참인 규칙 하나만 실행한다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, "self_potion_count", ">", 0, "USE_POTION"),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "전부 거짓이면 DEFAULT 가 나간다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 0, hold)]
            ),
        },
        {
            "name": "셀렉터가 빈손이면 그 규칙은 건너뛴다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, *hp_true, "ATTACK", target="BOSS"),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "조건 문자열에 실측값이 붙는다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document([build_single_rule_document(1, *hp_true, hold)]),
        },
        {
            "name": "플래그 기록은 계획에 담긴다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, *hp_true, hold, set_flag="A=true")]
            ),
        },
        {
            "name": "스탯 우변은 주인의 값을 따른다",
            "world_id": "throne",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1,
                        "target_distance",
                        "<=",
                        {"stat": "attack_range"},
                        "ATTACK",
                        target="NEAREST",
                        lhs_param="NEAREST",
                    ),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "모르는 스탯은 거짓이라 다음 규칙으로 넘어간다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1,
                        "target_distance",
                        "<=",
                        {"stat": "no_such_stat"},
                        "ATTACK",
                        target="NEAREST",
                        lhs_param="NEAREST",
                    ),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "적이 없으면 DEFAULT 도 대기가 된다",
            "world_id": "solitude",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 0, hold)]
            ),
        },
        {
            "name": "CPU 여유는 규칙표 크기를 반영한다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, "self_cpu_headroom", ">=", 7, hold),
                    build_single_rule_document(2, *hp_true, "APPROACH", target="NEAREST"),
                ]
            ),
        },
        {
            "name": "시전 중인 적을 고르는 규칙",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, *hp_true, "ATTACK", target="CASTING"),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "g0 압박형 규칙표",
            "world_id": "field_mixed",
            "ruleset_ref": ["g0", "g0_pressure"],
        },
        {"name": "g0 카이팅 규칙표", "world_id": "spring", "ruleset_ref": ["g0", "g0_kite"]},
        {"name": "g0 엄폐형 규칙표", "world_id": "throne", "ruleset_ref": ["g0", "g0_cover"]},
    ]


def build_rule_vm_cases(
    worlds: dict[str, WorldState], snapshots: dict[str, PerceptionSnapshot], catalog: BlockCatalog
) -> list[dict[str, Any]]:
    """RuleVM 이 고른 행동을 적는다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.
        snapshots: 세계 id 에서 플레이어 스냅샷으로의 대응표.
        catalog: 동결된 블록 카탈로그.

    Returns:
        기준 항목 목록.
    """
    cases: list[dict[str, Any]] = []
    for spec in build_rule_vm_specs():
        case = dict(spec)
        state = worlds[case["world_id"]]
        ruleset = resolve_case_ruleset(case)
        vm = build_rule_vm(ruleset, catalog, KIND_TYPES)
        plan = vm.plan_action(state.entities["player"], snapshots[case["world_id"]], state)
        case["cpu_usage"] = count_cpu_usage(ruleset)
        case["plan"] = render_plan_document(plan)
        cases.append(case)
    return cases


def build_fallback_cases(
    worlds: dict[str, WorldState], snapshots: dict[str, PerceptionSnapshot]
) -> list[dict[str, Any]]:
    """규칙표가 없을 때의 폴백 계획을 적는다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.
        snapshots: 세계 id 에서 플레이어 스냅샷으로의 대응표.

    Returns:
        기준 항목 목록.
    """
    policy = FallbackPolicy()
    cases: list[dict[str, Any]] = []
    for spec in WORLD_SPECS:
        world_id = spec["world_id"]
        state = worlds[world_id]
        plan = policy.plan_action(state.entities["player"], snapshots[world_id], state)
        cases.append({"world_id": world_id, "plan": render_plan_document(plan)})
    return cases


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    catalog = load_block_catalog(BLOCKS_PATH)
    rooms = {
        template.template_id: template for template in load_room_templates(ROOM_TEMPLATES_PATH)
    }
    worlds = {spec["world_id"]: create_world(spec, rooms) for spec in WORLD_SPECS}
    snapshots = {
        world_id: build_snapshot(state, state.entities["player"], KIND_TYPES)
        for world_id, state in worlds.items()
    }
    return {
        "_comment": [
            "파이썬 코어(rules·selectors)에서 생성한 기준값이다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_rules_golden",
            "위반 메시지와 조건 문자열은 순서와 글자까지 기준이다 — 규칙 에디터와 로그가",
            "이것을 그대로 띄우기 때문이다 (GDD §8.2, P1).",
        ],
        "kind_types": [[kind_id, kind] for kind_id, kind in KIND_TYPES.items()],
        "balance_path": BALANCE_PATH.name,
        "worlds": list(WORLD_SPECS),
        "snapshots": build_snapshot_cases(worlds),
        "selectors": build_selector_cases(worlds),
        "validator": build_validator_cases(catalog),
        "conditions": build_condition_cases(worlds, snapshots, catalog),
        "rule_vm": build_rule_vm_cases(worlds, snapshots, catalog),
        "fallback": build_fallback_cases(worlds, snapshots),
    }


def export_rules_golden(target_path: Path) -> Path:
    """기준값을 파일로 쓴다.

    Args:
        target_path: 쓸 경로. 상위 디렉터리가 없으면 만든다.

    Returns:
        쓴 경로.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    document = build_golden_document()
    target_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return target_path


def main() -> None:
    """기준값을 기본 경로에 내보낸다."""
    written = export_rules_golden(GOLDEN_PATH)
    print(f"기준값을 썼다: {written}")


if __name__ == "__main__":
    main()
