"""규칙 기준값이 공유하는 세계 명세와 원시 절 빌더 (게이트 G3).

`export_rules_golden.py` 에서 갈라 나왔다. 여기 있는 것은 **입력**이다 — 어떤 세계에
누가 서 있고, 규칙 절이 어떤 모양인가. 실제로 파이썬 코어를 돌려 답을 받아 적는 것은
`rules_golden_*_cases.py` 쪽이다.

세계 명세를 문서에 그대로 실어 두면 파이썬과 TS 가 같은 입력에서 출발하는 것이 파일
하나로 확인된다.
"""

from typing import Any

from game.app.core.rng import DeterministicRng
from game.app.rules.validator import CPU_COST_BY_TERM_COUNT
from game.app.simulation.plan import PlannedAction
from game.app.simulation.state import Entity, WorldState
from game.config import (
    BENCHMARK_RULESETS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
)
from game.schemas.room import RoomTemplate

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
    "mender_acolyte": "HEALER",
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


# 세계 명세. 셀렉터 9종이 서로 다른 답을 내도록 거리·HP·공격력의 동점을 일부러 만든다.
#
#  field_mixed  거리 동점(e_alpha·e_bravo)과 HP 동점(e_alpha·e_charlie·e_echo)과
#               공격력 동점(e_charlie·e_echo)이 한 방에 있다. min 은 사전순으로 작은
#               쪽을, max 는 큰 쪽을 고른다 — 두 방향을 한 번에 확인한다.
#  throne       보스가 있는 방. BOSS 와 NEAREST 가 서로 다른 대상을 가리킨다.
#  spring       플레이어가 생명의 샘 위에 서 있고 HP 가 낮다. 폴백이 포션을 쓴다.
#  solitude     적이 없다. 셀렉터는 전부 빈손이고 RuleVM 은 HOLD 로 떨어진다.
#  wounded      HP 80·포션 2. AND/OR 조건의 참거짓이 갈리는 자리다.
#  ward         아군 셋과 적 둘. 아군 셀렉터는 주체가 어느 진영이냐에 따라 답이 통째로
#               뒤집히므로 selector_actors 에 적(e_mender)도 넣어 양쪽을 잰다.
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
    {
        "world_id": "ward",
        "room_id": "open_field",
        "tick": 9,
        "casting_ids": [],
        "selector_actors": ["player", "e_mender"],
        "entities": [
            build_entity_spec(hp=70),
            build_entity_spec(
                entity_id="a_scout", position=[2, 4], hp=30, hp_max=40, initiative=45
            ),
            build_entity_spec(
                entity_id="a_guard", position=[1, 6], hp=40, hp_max=40, initiative=44
            ),
            build_enemy_spec("e_grunt", "goblin_rusher", position=[3, 4]),
            build_enemy_spec(
                "e_mender", "mender_acolyte", position=[8, 4], hp=30, hp_max=30, attack_range=2
            ),
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
