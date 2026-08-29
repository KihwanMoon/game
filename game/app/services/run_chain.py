"""고정 맵 연쇄 실행 — 방 3개를 연속으로 돈다 (로드맵 Phase 1 W3).

Room Loop 정식판(노드 그래프·보상 선택·방 사이 규칙 편집)은 Phase 2 W4 산출물이다.
여기서는 "여러 방을 이어서 도는 것만으로 난이도가 성립하는가"를 보는 데 필요한
최소한만 한다 — HP 와 포션을 이어 받는 것.

규칙 편집은 방 사이에서만 가능하다는 규약(GDD §2.2)을 지키기 위해, 이 함수는 정책을
방마다 다시 받지 않는다. 한 런 동안 같은 규칙표로 간다.
"""

from collections.abc import Callable
from dataclasses import dataclass

from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import (
    BattleResult,
    assign_enemy_policies,
    build_engine,
    run_battle,
)
from game.app.simulation.engine import TickEngine
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.simulation.pressure import PressureTracker, build_pressure_rules
from game.schemas.blocks import BlockCatalog
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet

# 방 하나를 끝까지 돌리는 것. 기본값은 run_battle 이고, 리플레이는 틱을 끊어 돌며
# 좌표를 함께 받아 적는 것을 넣는다 — 연쇄 진행 규칙(시드 분기·HP 인계·층 압력)을
# 리플레이가 다시 구현하면 두 경로가 갈려 "재현"이 재현이 아니게 된다.
RoomRunner = Callable[[TickEngine], BattleResult]


@dataclass(frozen=True)
class ChainResult:
    """연쇄 한 판의 결과."""

    cleared_rooms: int
    outcome: str
    total_ticks: int
    player_hp: int
    per_room: tuple[BattleResult, ...]


def run_room_chain(
    templates: tuple[RoomTemplate, ...],
    balance: dict,
    catalog: BlockCatalog,
    player_ruleset: RuleSet | None,
    enemy_rulesets: dict[str, RuleSet],
    seed: int,
    max_ticks: int = 400,
    run_room: RoomRunner = run_battle,
) -> ChainResult:
    """방들을 순서대로 돌고 결과를 모은다.

    방마다 시드를 갈라 준다. 한 수열을 공유하면 앞 방의 전투 길이가 바뀔 때 뒷 방의
    이니셔티브 동률 처리까지 흔들려, 방 하나를 고쳤을 뿐인데 전체가 달라진다 (R5).

    Args:
        templates: 순서대로 돌 방들.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        player_ruleset: 플레이어 규칙표. None 이면 폴백 정책을 쓴다.
        enemy_rulesets: 적 규칙표들.
        seed: 런 시드.
        max_ticks: 방 하나의 틱 상한.
        run_room: 방 하나를 돌리는 것. 기본값은 끝까지 한 번에 돌린다.

    Returns:
        연쇄 결과.
    """
    carried_hp: int | None = None
    carried_potions: int | None = None
    results: list[BattleResult] = []
    cleared = 0
    outcome = OUTCOME_PLAYER_WIN
    # 층 단위 객체다. 방마다 새로 만들면 층 체류 스케일이 매 방 0 으로 돌아가
    # GDD §7 의 '층 지연' 압력이 사라진다.
    pressure = PressureTracker(
        rules=build_pressure_rules(balance["anti_abuse"]),
        enemy_stats={kind["id"]: kind for kind in balance["enemies"]},
    )

    for index, template in enumerate(templates):
        # 방을 넘어가면 방 체류 틱과 기준 공격력을 지운다. entity_id 가 방마다 다시
        # 붙으므로(어느 방에나 goblin_rusher_0 이 있다) 남기면 남의 기준값을 읽는다.
        pressure.reset_room()
        engine = build_engine(
            template,
            balance,
            seed=seed + index * 1000,
            max_ticks=max_ticks,
            pressure=pressure,
        )
        player = engine.state.entities["player"]
        if carried_hp is not None:
            player.hp = carried_hp
            player.potions = carried_potions or 0
        if player_ruleset is not None:
            engine.policies["player"] = build_rule_vm(
                player_ruleset, catalog, engine.config.kind_types
            )
        assign_enemy_policies(engine, balance, catalog, enemy_rulesets)

        result = run_room(engine)
        results.append(result)
        outcome = result.outcome
        if result.outcome != OUTCOME_PLAYER_WIN:
            break
        cleared += 1
        carried_hp = result.player_hp
        carried_potions = player.potions

    return ChainResult(
        cleared_rooms=cleared,
        outcome=outcome,
        total_ticks=sum(r.ticks for r in results),
        player_hp=results[-1].player_hp if results else 0,
        per_room=tuple(results),
    )
