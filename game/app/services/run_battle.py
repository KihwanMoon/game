"""전투 1회 실행 — 방 하나를 끝까지 돌린다.

파일 하나가 시나리오 하나다 (표준 §12). 아래 계층의 모듈들을 엮어 하나의 흐름을 만든다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from game.app.combat.damage import build_damage_rules
from game.app.core.rng import DeterministicRng
from game.app.rules.fallback_policy import FallbackPolicy
from game.app.simulation.engine import (
    OUTCOME_ONGOING,
    EngineConfig,
    TickEngine,
)
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.schemas.room import RoomTemplate


@dataclass(frozen=True)
class BattleResult:
    """전투 한 판의 결과. 리플레이 검증이 이 값을 대조한다."""

    outcome: str
    ticks: int
    player_hp: int
    log_lines: tuple[str, ...]


def build_engine(
    template: RoomTemplate, balance: dict, seed: int, max_ticks: int = 400
) -> TickEngine:
    """방 템플릿과 밸런스 값으로 엔진을 조립한다.

    Args:
        template: 사용할 룸 템플릿.
        balance: balance.json 을 읽은 딕셔너리.
        seed: 난수 시드.
        max_ticks: 이 틱을 넘기면 시간 초과로 끝낸다.

    Returns:
        첫 틱을 돌릴 준비가 된 엔진.
    """
    rng = DeterministicRng(seed)
    state = WorldState(room=template, rng=rng)

    player_stats = balance["player"]
    state.entities["player"] = Entity(
        entity_id="player",
        kind_id="player",
        faction=FACTION_PLAYER,
        position=template.player_spawn,
        hp=player_stats["hp_max"],
        hp_max=player_stats["hp_max"],
        attack=player_stats["attack"],
        defense=player_stats["defense"],
        attack_range=player_stats["attack_range"],
        initiative=player_stats["initiative"],
        regen_base=player_stats["regen_base"],
        potions=player_stats["potions"],
    )

    kinds = balance["enemies"]
    for index, position in enumerate(template.enemy_spawns):
        kind = kinds[index % len(kinds)]
        state.entities[f"{kind['id']}_{index}"] = Entity(
            entity_id=f"{kind['id']}_{index}",
            kind_id=kind["id"],
            faction=FACTION_ENEMY,
            position=position,
            hp=kind["hp_max"],
            hp_max=kind["hp_max"],
            attack=kind["attack"],
            defense=kind["defense"],
            attack_range=kind["attack_range"],
            initiative=kind["initiative"],
            regen_base=kind["regen_base"],
        )

    config = EngineConfig(
        damage_rules=build_damage_rules(balance["damage_formula"]),
        kind_types={kind["id"]: kind["type"] for kind in kinds},
        skill_coef_pct={skill["id"]: skill["coef_pct"] for skill in balance["skills"]},
        max_ticks=max_ticks,
        combat_regen_pct=balance["anti_abuse"]["combat_regen_pct"],
    )
    return TickEngine(state=state, policy=FallbackPolicy(), config=config)


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


def load_balance(source_path: Path) -> dict:
    """밸런스 JSON 을 읽는다.

    Args:
        source_path: balance.json 경로.

    Returns:
        읽어들인 딕셔너리.
    """
    return json.loads(source_path.read_text(encoding="utf-8"))
