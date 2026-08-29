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
from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.app.simulation.engine import TickEngine
from game.app.simulation.state import FACTION_ENEMY, Entity, WorldState
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
from game.schemas.ruleset import RuleSet, load_rulesets

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/__golden__/cases.json"

# 플레이어 엔티티의 고정 id. 규칙표는 이 이름으로 걸린다.
PLAYER_ID = "player"

# 시간 초과로 끝나는 판도 대조 대상이다. 400 은 실제 실행값과 같다.
MAX_TICKS = 400

# 층. 피해 공식의 방어 감쇠와 층 스케일이 이 값을 본다.
FLOOR = 1

# 방 다섯 개 전부. 지형·적 구성이 달라 서로 다른 코드 경로를 밟는다.
ROOM_IDS = ("open_field", "corridor", "pillars", "hazard_field", "spring_bait")

# 방마다 다른 시드를 준다. 같은 시드로 다섯 판을 돌리면 난수 소비 지점이 같은 순서로만
# 검증되어, 소비 횟수가 어긋나는 버그가 한 방향으로만 드러난다.
ROOM_SEEDS = (1, 12345, 7, 99, 2024)

# 대표 규칙표 3종 (g0_examples.json). 압박·카이팅·엄폐로 행동 경로가 갈린다.
PLAYER_RULESET_IDS = ("g0_pressure", "g0_kite", "g0_cover")

# 벤치마크 규칙표로 도는 추가 조합. (규칙표 id, 방 id, 시드).
# g0 3종이 쓰지 않는 행동 — 광역·원거리 스킬·샘 점거·문 지키기 — 를 여기서 태운다.
BENCHMARK_CASES = (
    ("sniper", "corridor", 4242),
    ("area_sweep", "open_field", 555),
    ("spring_camp", "spring_bait", 808),
    ("door_hold", "pillars", 31337),
    ("focus_summoner", "hazard_field", 20240931),
)

# 템플릿에 없는 적을 덧붙여 도는 조합. (규칙표 id, 방 id, 시드, 덧붙일 적).
# 방 다섯 개의 스폰이 전부 고블린 3종이라, 이것이 없으면 폭탄 슬라임·수복사·대소환사·
# 장궁병의 규칙표가 한 번도 돌지 않는다. 예고(TELEGRAPH) 페이즈도 여기서만 로그에 남는다.
# 좌표는 전부 통행 가능하고 템플릿 스폰과 겹치지 않는 칸이다.
ADVANCED_CASES = (
    ("g0_kite", "open_field", 4242, (("bomb_slime", 5, 4), ("mender_acolyte", 6, 2))),
    ("g0_cover", "pillars", 555, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
    ("focus_ranged", "hazard_field", 808, (("longbow_archer", 6, 4),)),
    ("focus_lowest", "spring_bait", 31337, (("bomb_slime", 6, 6),)),
    ("focus_threat", "corridor", 20240931, (("mender_acolyte", 6, 2),)),
)

# 덧붙일 적이 없는 조합이 쓰는 빈 목록.
NO_EXTRAS: tuple[tuple[str, int, int], ...] = ()


def load_case_resources() -> tuple[dict, dict[str, RoomTemplate], BlockCatalog, dict[str, RuleSet]]:
    """케이스를 돌리는 데 필요한 리소스를 전부 읽는다.

    Returns:
        밸런스 딕셔너리, 방 id 대응표, 블록 카탈로그, 규칙표 id 대응표.
    """
    balance = load_balance(BALANCE_PATH)
    rooms = {
        template.template_id: template for template in load_room_templates(ROOM_TEMPLATES_PATH)
    }
    catalog = load_block_catalog(BLOCKS_PATH)
    rulesets = dict(load_rulesets(G0_RULESETS_PATH))
    rulesets.update(load_rulesets(BENCHMARK_RULESETS_PATH))
    return balance, rooms, catalog, rulesets


def list_case_plans() -> list[tuple[str, str, int, tuple[tuple[str, int, int], ...]]]:
    """돌릴 조합을 (방 id, 규칙표 id, 시드, 덧붙일 적) 로 편다.

    Returns:
        조합 목록. 순서가 곧 기준 문서의 순서다.
    """
    plans = [
        (room_id, ruleset_id, seed, NO_EXTRAS)
        for ruleset_id in PLAYER_RULESET_IDS
        for room_id, seed in zip(ROOM_IDS, ROOM_SEEDS, strict=True)
    ]
    plans.extend(
        (room_id, ruleset_id, seed, NO_EXTRAS) for ruleset_id, room_id, seed in BENCHMARK_CASES
    )
    plans.extend(
        (room_id, ruleset_id, seed, extras) for ruleset_id, room_id, seed, extras in ADVANCED_CASES
    )
    return plans


def add_extra_enemies(
    engine: TickEngine, balance: dict, extras: tuple[tuple[str, int, int], ...]
) -> None:
    """템플릿에 없는 적을 방에 덧붙인다.

    id 는 `{종류}_x{순번}` 이다. 템플릿 스폰의 `_{index}` 와 겹치지 않아야 한 쪽이 조용히
    덮이지 않는다.

    Args:
        engine: 조립된 엔진.
        balance: 밸런스 딕셔너리.
        extras: (종류 id, x, y) 목록.
    """
    by_id = {kind["id"]: kind for kind in balance["enemies"]}
    for index, (kind_id, x, y) in enumerate(extras):
        kind = by_id[kind_id]
        entity_id = f"{kind_id}_x{index}"
        engine.state.entities[entity_id] = Entity(
            entity_id=entity_id,
            kind_id=kind_id,
            faction=FACTION_ENEMY,
            position=(x, y),
            hp=kind["hp_max"],
            hp_max=kind["hp_max"],
            attack=kind["attack"],
            defense=kind["defense"],
            attack_range=kind["attack_range"],
            initiative=kind["initiative"],
            regen_base=kind["regen_base"],
            cpu_budget=kind.get("cpu_budget", 0),
            potions=kind.get("potions", 0),
        )
    engine.register_newcomers()


def build_case_engine(
    balance: dict,
    template: RoomTemplate,
    catalog: BlockCatalog,
    enemy_rulesets: dict[str, RuleSet],
    player_ruleset: RuleSet,
    seed: int,
) -> TickEngine:
    """실제 플레이와 같은 배선으로 엔진을 조립한다.

    플레이어 규칙표를 먼저 걸고 적 규칙표를 나중에 붙인다. 순서를 바꾸면
    `assign_enemy_policies` 가 도는 `register_newcomers` 가 플레이어 자리를 먼저 채워
    규칙표가 조용히 덮인다.

    Args:
        balance: 밸런스 딕셔너리.
        template: 쓸 룸 템플릿.
        catalog: 동결된 블록 카탈로그.
        enemy_rulesets: 적 규칙표 대응표.
        player_ruleset: 플레이어가 쓸 규칙표.
        seed: 난수 시드.

    Returns:
        첫 틱을 돌릴 준비가 된 엔진.
    """
    engine = build_engine(template, balance, seed=seed, max_ticks=MAX_TICKS, floor=FLOOR)
    engine.policies[PLAYER_ID] = build_rule_vm(player_ruleset, catalog, engine.config.kind_types)
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    return engine


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
                "potions": entity.potions,
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
    plan: tuple[str, str, int, tuple[tuple[str, int, int], ...]],
) -> dict[str, Any]:
    """조합 하나를 끝까지 돌리고 대조용 레코드를 만든다.

    Args:
        balance: 밸런스 딕셔너리.
        rooms: 방 id 대응표.
        catalog: 동결된 블록 카탈로그.
        rulesets: 플레이어 규칙표 대응표.
        enemy_rulesets: 적 규칙표 대응표.
        plan: (방 id, 규칙표 id, 시드, 덧붙일 적).

    Returns:
        JSON 에 넣을 레코드.
    """
    room_id, ruleset_id, seed, extras = plan
    engine = build_case_engine(
        balance, rooms[room_id], catalog, enemy_rulesets, rulesets[ruleset_id], seed
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
        "floor": FLOOR,
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
