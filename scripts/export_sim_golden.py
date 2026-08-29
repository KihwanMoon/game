"""파이썬 시뮬레이션 코어의 기준 전투를 JSON 으로 내보낸다 (게이트 G3).

TypeScript 코어는 파이썬 코어와 **비트 단위로 같은 결과**를 내야 한다. RNG 수열만 맞추면
난수를 뽑는 지점과 횟수가 어긋나도 대조가 통과하므로, 방 하나를 끝까지 돌린 결과와 이벤트
로그 전문을 기준으로 고정한다. 로그 한 줄이 어긋나면 그 틱의 어느 페이즈에서 갈렸는지가
바로 드러난다.

정책 두 가지로 돌린다.

* `fallback` — 실행 경로가 실제 전투와 가장 가깝다. 다만 폴백 정책은 접근·공격·포션·대기
  네 가지만 내므로 나머지 행동 아홉 개가 한 번도 실행되지 않는다.
* `cycle` — 그 빈자리를 메우는 **대조 전용** 정책이다. 틱과 엔티티 id 만 보고 행동 14개를
  차례로 돌린다. RuleVM 이 아직 이식되지 않아 규칙표로는 양쪽을 같은 조건에 둘 수 없는데,
  이 정책은 규칙이 없어도 두 코어가 똑같이 재현할 수 있다. 소환·예고·자폭·엄폐 이동·
  플래그가 여기서 처음 검증된다. RuleVM 이 이식되면 규칙표 사례로 갈음한다.

    uv run python -m scripts.export_sim_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.services.run_battle import build_engine, load_balance, run_battle
from game.app.simulation.engine import TickEngine
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.plan import PlannedAction
from game.app.simulation.scaling import build_floor_scale, get_scaled_enemy_stats
from game.app.simulation.selectors import (
    SELECTOR_ALLY_WOUNDED,
    SELECTOR_NEAREST,
    resolve_target,
)
from game.app.simulation.state import FACTION_ENEMY, Entity, WorldState
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import RoomTemplate, load_room_templates

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/golden/sim_golden.json"

POLICY_FALLBACK = "fallback"
POLICY_CYCLE = "cycle"

# 시간 초과로 끝나는 판도 대조 대상이다. 400 은 실제 실행값과 같다.
MAX_TICKS = 400

# 기본 층. 케이스마다 다를 수 있으므로 각 레코드가 자기 층을 함께 싣는다.
FLOOR = 1

# 동결된 행동 14개 전부. 순서를 바꾸면 기준 로그가 통째로 달라진다. HEAL 은 v4 에서
# 뒤에 붙였다 — 사이에 끼우면 그 뒤의 모든 기준 로그가 이유 없이 밀린다.
ACTION_CYCLE = (
    "APPROACH",
    "ATTACK",
    "SKILL_2",
    "AREA_ATTACK",
    "RETREAT",
    "MOVE_TO_COVER",
    "SUMMON",
    "USE_POTION",
    "MOVE_TO_HEAL",
    "SET_FLAG",
    "MOVE_TO_EXIT",
    "HOLD",
    "SKILL_1",
    "HEAL",
)

# 행동별 대상 셀렉터. 이 정책은 규칙표를 타지 않으므로 진영을 여기서 맞춘다 —
# 전부 NEAREST 로 두면 HEAL 이 적을 회복해 기준 로그가 뜻 없는 것을 고정한다.
CYCLE_SELECTORS = {"HEAL": SELECTOR_ALLY_WOUNDED}

# SET_FLAG 가 세울 플래그. 규칙표가 쓰는 A~D 안에서 고른다.
CYCLE_FLAG = "A=true"

# 템플릿 id · 시드 · 층. 템플릿마다 적 구성과 지형이 달라 서로 다른 코드 경로를 밟는다.
# 뒤의 다섯은 min_floor 로 층 2~3 에 묶인 방이며, 그 방이 나오는 층에서 돌린다 — 폭탄
# 슬라임·수복 사제·장궁병·정예 돌격병·대소환사가 룸 템플릿에 배치되면서 생긴 자리다.
FALLBACK_CASES = (
    ("open_field", 1, 1),
    ("corridor", 12345, 1),
    ("pillars", 7, 1),
    ("hazard_field", 99, 1),
    ("spring_bait", 2024, 1),
    ("blast_yard", 606, 1),
    ("chapel", 707, 2),
    ("longshot", 909, 2),
    ("warlord_gate", 1212, 2),
    ("summoner_vault", 1515, 3),
)

# 템플릿 id · 시드 · 덧붙일 적. 좌표는 전부 통행 가능하고 스폰과 겹치지 않는 칸이다.
# 폭탄 슬라임과 대소환사를 넣는 것은 예고·자폭·소환이 이 조합에서만 돌기 때문이다.
# 템플릿 id · 시드 · 층 · 덧붙일 적.
CYCLE_CASES = (
    ("open_field", 4242, 1, (("bomb_slime", 5, 4), ("mender_acolyte", 6, 2))),
    ("pillars", 555, 1, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
    ("hazard_field", 808, 1, (("longbow_archer", 6, 4),)),
    ("spring_bait", 31337, 1, (("bomb_slime", 6, 6),)),
    # 층 깊이 스케일이 걸린 채로 행동 14개를 다 돌린다. 방 배치·소환·덧붙인 적이 모두
    # 같은 기준으로 서는지 여기서 고정된다 (docs/04 P-1).
    ("pillars", 3131, 3, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
)


class CyclingPolicy:
    """틱과 엔티티 id 만 보고 행동 13개를 차례로 내는 대조 전용 결정기.

    난수를 쓰지 않는다. 엔진이 뽑는 난수의 횟수와 순서가 정책 때문에 흔들리면 대조가
    검증하려던 것 자체가 사라진다.
    """

    def __init__(self, kind_types: dict[str, str]) -> None:
        """대상 선택에 쓸 종류 표를 받는다.

        Args:
            kind_types: 엔티티 종류에서 적 유형으로의 대응표.
        """
        self._kind_types = kind_types

    def plan_action(
        self, entity: Entity, snapshot: PerceptionSnapshot, state: WorldState
    ) -> PlannedAction:
        """이번 틱의 행동을 정한다. 부작용을 내지 않는다.

        Args:
            entity: 결정 대상.
            snapshot: PERCEPTION 이 고정한 값들. 이 정책은 읽지 않는다.
            state: 세계 상태. 읽기만 한다.

        Returns:
            실행할 계획.
        """
        offset = sum(ord(char) for char in entity.entity_id)
        index = (snapshot.tick + offset) % len(ACTION_CYCLE)
        action_id = ACTION_CYCLE[index]
        selector_id = CYCLE_SELECTORS.get(action_id, SELECTOR_NEAREST)
        target = resolve_target(selector_id, entity, state, self._kind_types)
        return PlannedAction(
            entity_id=entity.entity_id,
            action_id=action_id,
            target_id=target.entity_id if target is not None else None,
            rule_index=index,
            expr=f"틱({snapshot.tick}) + 오프셋({offset}) % {len(ACTION_CYCLE)} = {index}",
            set_flag=CYCLE_FLAG if action_id == "SET_FLAG" else None,
        )


def find_template(templates: tuple[RoomTemplate, ...], template_id: str) -> RoomTemplate:
    """id 로 룸 템플릿을 찾는다.

    Args:
        templates: 읽어 둔 템플릿들.
        template_id: 찾을 템플릿 id.

    Returns:
        찾은 템플릿.

    Raises:
        KeyError: 그 id 의 템플릿이 없는 경우.
    """
    for template in templates:
        if template.template_id == template_id:
            return template
    raise KeyError(f"룸 템플릿이 없다: {template_id}")


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
    scale = build_floor_scale(balance.get("floor_scale", {}))
    for index, (kind_id, x, y) in enumerate(extras):
        kind = by_id[kind_id]
        hp_max, attack = get_scaled_enemy_stats(kind, scale, engine.config.floor)
        entity_id = f"{kind_id}_x{index}"
        engine.state.entities[entity_id] = Entity(
            entity_id=entity_id,
            kind_id=kind_id,
            faction=FACTION_ENEMY,
            position=(x, y),
            hp=hp_max,
            hp_max=hp_max,
            attack=attack,
            defense=kind["defense"],
            attack_range=kind["attack_range"],
            initiative=kind["initiative"],
            regen_base=kind["regen_base"],
            cpu_budget=kind.get("cpu_budget", 0),
            potions=kind.get("potions", 0),
        )
    engine.register_newcomers()


def build_case(
    balance: dict,
    templates: tuple[RoomTemplate, ...],
    case: tuple[str, int, int],
    policy_name: str,
    extras: tuple[tuple[str, int, int], ...] = (),
) -> dict[str, Any]:
    """전투 한 판을 돌리고 대조용 레코드를 만든다.

    Args:
        balance: 밸런스 딕셔너리.
        templates: 읽어 둔 템플릿들.
        case: (템플릿 id, 시드, 층).
        policy_name: POLICY_FALLBACK 또는 POLICY_CYCLE.
        extras: 덧붙일 적 목록.

    Returns:
        JSON 에 넣을 레코드.
    """
    template_id, seed, floor = case
    template = find_template(templates, template_id)
    engine = build_engine(template, balance, seed=seed, max_ticks=MAX_TICKS, floor=floor)
    if policy_name == POLICY_CYCLE:
        engine.policy = CyclingPolicy({k["id"]: k["type"] for k in balance["enemies"]})
    if extras:
        add_extra_enemies(engine, balance, extras)
    result = run_battle(engine)
    return {
        "template_id": template_id,
        "seed": seed,
        "policy": policy_name,
        "max_ticks": MAX_TICKS,
        "floor": floor,
        "extra_enemies": [{"kind": kind, "x": x, "y": y} for kind, x, y in extras],
        "outcome": result.outcome,
        "ticks": result.ticks,
        "player_hp": result.player_hp,
        "spawn_counter": engine.state.spawn_counter,
        "entities": build_entity_rows(engine.state),
        "log_line_count": len(result.log_lines),
        "log_lines": list(result.log_lines),
    }


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


def build_battle_cases() -> list[dict[str, Any]]:
    """모든 조합의 전투를 돌린다.

    Returns:
        조합과 그 결과·로그 전문 목록.
    """
    balance = load_balance(BALANCE_PATH)
    templates = load_room_templates(ROOM_TEMPLATES_PATH)
    cases = [build_case(balance, templates, case, POLICY_FALLBACK) for case in FALLBACK_CASES]
    cases.extend(
        build_case(balance, templates, (template_id, seed, floor), POLICY_CYCLE, extras)
        for template_id, seed, floor, extras in CYCLE_CASES
    )
    return cases


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    return {
        "_comment": [
            "파이썬 코어(game/app/simulation)에서 생성한 기준 전투다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_sim_golden",
            "policy=cycle 은 대조 전용 결정기다 — 행동 14개를 틱마다 차례로 돌린다.",
        ],
        "max_ticks": MAX_TICKS,
        "floor": FLOOR,
        "action_cycle": list(ACTION_CYCLE),
        "cycle_selectors": [[action, selector] for action, selector in CYCLE_SELECTORS.items()],
        "cycle_flag": CYCLE_FLAG,
        "battles": build_battle_cases(),
    }


def export_sim_golden(target_path: Path) -> Path:
    """기준 전투를 파일로 쓴다.

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
    """기준 전투를 기본 경로에 내보낸다."""
    written = export_sim_golden(GOLDEN_PATH)
    print(f"기준 전투를 썼다: {written}")


if __name__ == "__main__":
    main()
