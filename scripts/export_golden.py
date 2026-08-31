"""골든 리플레이 기준 케이스를 JSON 으로 내보낸다 (게이트 G3).

TypeScript 코어는 파이썬 코어와 **비트 단위로 같은 결과**를 내야 한다. `export_sim_golden`
이 고정한 것은 폴백·순환 정책이라 규칙표(RuleVM)를 타지 않는다. 여기서는 실제 플레이와
같은 배선 — 플레이어에 규칙표를, 적에게 각자의 규칙표를 붙인 상태 — 로 여러 (시드 × 방 ×
규칙표) 조합을 끝까지 돌려 고정한다.

승패·틱·HP 만 비교하면 중간에 갈린 판이 우연히 같은 결말에 도달할 때 통과한다. 그래서
**이벤트 로그 전문**을 필드 단위(`tick·entity_id·phase·expr·outcome·rule·delta·fired`)로
내보낸다. 한 항목이 어긋나면 그 틱의 어느 페이즈에서 갈렸는지가 바로 드러난다.

    uv run python -m scripts.export_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.core.event_log import LogEntry
from game.app.services.run_battle import (
    run_battle,
)
from game.app.simulation.state import WorldState
from game.config import (
    ENEMY_RULESETS_PATH,
)
from game.schemas.blocks import BlockCatalog
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet, load_rulesets
from scripts.golden_battle_cases import (
    FLOOR,
    MAX_TICKS,
    PLAYER_ID,
    CasePlan,
    add_extra_enemies,
    build_case_engine,
    list_case_plans,
    load_case_resources,
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/__golden__/cases.json"


def build_log_rows(entries: list[LogEntry]) -> list[dict[str, Any]]:
    """이벤트 로그를 필드 단위로 편다.

    포맷된 한 줄이 아니라 필드로 내보내는 이유는, 서식을 고쳤을 때 대조가 통째로 깨지는
    것을 막고 어긋난 **필드**를 지목할 수 있게 하기 위해서다.

    Args:
        entries: 쌓인 로그 레코드들.

    Returns:
        레코드를 남긴 순서 그대로의 딕셔너리 목록.
    """
    return [
        {
            "tick": entry.tick,
            "entity_id": entry.entity_id,
            "phase": entry.phase,
            "expr": entry.expr,
            "outcome": entry.outcome,
            "rule": entry.rule,
            "delta": entry.delta,
            "fired": entry.fired,
            "target_id": entry.target_id,
        }
        for entry in entries
    ]


def build_entity_rows(state: WorldState) -> list[dict[str, Any]]:
    """전투가 끝난 시점의 개체 상태를 id 순으로 편다.

    로그가 같아도 최종 좌표나 쿨타임이 갈릴 수 있다. 로그에 찍히지 않는 상태까지 대조에
    넣어 두면 어긋난 지점이 좁혀진다.

    Args:
        state: 세계 상태.

    Returns:
        entity_id 사전순의 상태 목록. 죽은 개체도 남긴다.
    """
    rows = []
    for entity_id in sorted(state.entities):
        entity = state.entities[entity_id]
        rows.append(
            {
                "entity_id": entity_id,
                "kind_id": entity.kind_id,
                "hp": entity.hp,
                "x": entity.position[0],
                "y": entity.position[1],
                "attack": entity.attack,
                "potions": entity.count_item("POTION"),
                "cooldowns": {key: entity.cooldowns[key] for key in sorted(entity.cooldowns)},
                "flags": {key: entity.flags[key] for key in sorted(entity.flags)},
            }
        )
    return rows


def build_case_record(
    balance: dict,
    rooms: dict[str, RoomTemplate],
    catalog: BlockCatalog,
    rulesets: dict[str, RuleSet],
    enemy_rulesets: dict[str, RuleSet],
    plan: CasePlan,
) -> dict[str, Any]:
    """조합 하나를 끝까지 돌리고 대조용 레코드를 만든다.

    Args:
        balance: 밸런스 딕셔너리.
        rooms: 방 id 대응표.
        catalog: 동결된 블록 카탈로그.
        rulesets: 플레이어 규칙표 대응표.
        enemy_rulesets: 적 규칙표 대응표.
        plan: (방 id, 규칙표 id, 시드, 층, 덧붙일 적).

    Returns:
        JSON 에 넣을 레코드.
    """
    room_id, ruleset_id, seed, floor, extras = plan
    engine = build_case_engine(
        balance, rooms[room_id], catalog, enemy_rulesets, rulesets[ruleset_id], seed, floor
    )
    if extras:
        add_extra_enemies(engine, balance, extras)
    result = run_battle(engine)
    return {
        "case_id": f"{room_id}__{ruleset_id}__{seed}",
        "room_id": room_id,
        "ruleset_id": ruleset_id,
        "seed": seed,
        "extra_enemies": [{"kind": kind, "x": x, "y": y} for kind, x, y in extras],
        "max_ticks": MAX_TICKS,
        "floor": floor,
        "outcome": result.outcome,
        "ticks": result.ticks,
        "player_hp": result.player_hp,
        "spawn_counter": engine.state.spawn_counter,
        "entities": build_entity_rows(engine.state),
        "log_count": engine.log.count(),
        "log": build_log_rows(engine.log.entries),
    }


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    balance, rooms, catalog, rulesets = load_case_resources()
    enemy_rulesets = load_rulesets(ENEMY_RULESETS_PATH)
    cases = [
        build_case_record(balance, rooms, catalog, rulesets, enemy_rulesets, plan)
        for plan in list_case_plans()
    ]
    return {
        "_comment": [
            "파이썬 코어에서 생성한 골든 리플레이 기준이다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_golden",
            "플레이어는 ruleset_id 의 규칙표로, 적은 각자의 규칙표로 싸운다.",
            "extra_enemies 는 템플릿에 없는 적을 덧붙인 것이다 — 예고·자폭·소환이 여기서 돈다.",
            "케이스마다 floor 가 다르다. min_floor 로 층 2~3 에 묶인 방과, 층 깊이 스케일을",
            "고정하는 조합이 함께 들어 있다 — 적 능력치는 층 1 기준이고 층마다 정수 퍼센트가",
            "얹힌다 (docs/04 P-1).",
            "log 는 이벤트 로그 전문이며 항목 순서까지 계약이다.",
        ],
        "max_ticks": MAX_TICKS,
        "floor": FLOOR,
        "player_id": PLAYER_ID,
        "log_fields": [
            "tick",
            "entity_id",
            "phase",
            "expr",
            "outcome",
            "rule",
            "delta",
            "fired",
            "target_id",
        ],
        "case_count": len(cases),
        "cases": cases,
    }


def export_golden_cases(target_path: Path) -> Path:
    """기준 케이스를 파일로 쓴다.

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
    """기준 케이스를 기본 경로에 내보낸다."""
    written = export_golden_cases(GOLDEN_PATH)
    print(f"골든 케이스를 썼다: {written}")


if __name__ == "__main__":
    main()
