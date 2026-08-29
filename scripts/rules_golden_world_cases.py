"""세계 상태에서 바로 재는 기준값 — 셀렉터·스냅샷·기본 행동 (게이트 G3).

`export_rules_golden.py` 에서 갈라 나왔다. 셋 다 규칙 절을 거치지 않고 세계 상태를
그대로 읽어 답을 낸다는 점이 같다.
"""

from typing import Any

from game.app.rules.fallback_policy import FallbackPolicy
from game.app.simulation.perception import PerceptionSnapshot, build_snapshot
from game.app.simulation.selectors import ALL_SELECTORS, resolve_target
from game.app.simulation.state import WorldState
from scripts.rules_golden_specs import KIND_TYPES, WORLD_SPECS, render_plan_document


def build_selector_cases(worlds: dict[str, WorldState]) -> list[dict[str, Any]]:
    """셀렉터 9종이 각 세계에서 누구를 고르는지 적는다.

    주체를 세계마다 여러 개 둘 수 있다 (`selector_actors`). 아군 셀렉터는 주체가 누구냐에
    따라 진영이 통째로 뒤집히므로, 플레이어 쪽에서만 재면 적이 쓰는 경로가 비어 있다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.

    Returns:
        기준 항목 목록.
    """
    cases: list[dict[str, Any]] = []
    for spec in WORLD_SPECS:
        state = worlds[spec["world_id"]]
        for actor_id in spec.get("selector_actors", ["player"]):
            actor = state.entities[actor_id]
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
