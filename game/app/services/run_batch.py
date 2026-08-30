"""헤드리스 배치 실행 — 규칙표의 승률을 데이터로 잰다 (TDD §10).

밸런싱을 감이 아니라 데이터로 하는 것이 결정론 코어를 최우선에 둔 실질적 이유다.
같은 시드가 같은 결과를 내므로, 실패한 런을 시드만 들고 그대로 재현해 볼 수 있다.

재는 방식이 둘이다. **고정 연쇄**(`run_batch`)는 같은 방을 같은 순서로 돌아 규칙표
사이의 차이만 남긴다. **층 배치**(`run_floor_batch`)는 시드마다 층을 새로 만들어
실제 런에 가깝게 잰다.

둘을 함께 두는 이유는 고정 연쇄의 승률이 승률이 아니기 때문이다. 방도 적 배치도
템플릿이 정하고 전투 수식에 난수가 없어, 난수가 닿는 곳은 이니셔티브 동률과 타일
효과뿐이다. `open_field → corridor → pillars` 연쇄에서는 그마저 승패를 뒤집지 못해
1,000 런의 승률이 0% 아니면 100% 로만 나온다 (실측 docs/05). 전략 공간의 분포(R2)를
보려면 층 생성이 만드는 방 조합의 다양성이 필요하다.
"""

from dataclasses import dataclass

from game.app.services.build_floor import build_floor_map
from game.app.services.run_battle import BattleResult, run_battle
from game.app.services.run_chain import run_room_chain
from game.app.services.run_room_loop import RoomLoopContext, run_room_loop
from game.app.simulation.engine import TickEngine
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.simulation.state import FACTION_ENEMY, WorldState
from game.schemas.blocks import BlockCatalog
from game.schemas.room import FIRST_FLOOR, RoomTemplate
from game.schemas.ruleset import RuleSet

PERCENT = 100


@dataclass(frozen=True)
class BatchStats:
    """배치 한 묶음의 통계."""

    ruleset_id: str
    runs: int
    wins: int
    average_ticks: int
    average_hp: int
    average_cleared: int
    worst_seed: int
    # 끝난 방에 남은 적 HP 비율 (평균). **승률로는 안 보이는 기울기다.**
    #
    # 이 게임은 시드가 틱과 HP 만 흔들고 승패는 거의 바꾸지 않아, 승률이 0% 아니면
    # 100% 로만 나온다. 그러면 "적 HP 4% 남기고 진 것" 과 "한 대도 못 때리고 진 것" 이
    # 같은 0% 로 적히고, 튜닝할 곳을 고를 수 없다.
    #
    # 100% 는 손도 못 댔다는 뜻이다 — 밸런스가 아니라 그 방에서 규칙표가 아예 작동하지
    # 않는 것이며(조건이 영영 거짓), 그 둘은 고치는 방법이 다르다.
    enemy_hp_left_pct: int = 0

    @property
    def win_rate_pct(self) -> int:
        """승률. 정수 퍼센트다."""
        return self.wins * PERCENT // self.runs if self.runs else 0


def run_batch(
    ruleset_id: str,
    templates: tuple[RoomTemplate, ...],
    balance: dict,
    catalog: BlockCatalog,
    player_ruleset: RuleSet | None,
    enemy_rulesets: dict[str, RuleSet],
    runs: int,
    base_seed: int = 1,
) -> BatchStats:
    """같은 규칙표로 여러 번 돌려 통계를 낸다.

    Args:
        ruleset_id: 통계에 붙일 이름.
        templates: 연쇄할 방들.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        player_ruleset: 플레이어 규칙표. None 이면 폴백.
        enemy_rulesets: 적 규칙표들.
        runs: 반복 횟수.
        base_seed: 시작 시드. 런마다 1씩 늘린다.

    Returns:
        승률과 평균값들. 가장 빨리 진 런의 시드를 함께 담는다 — 재현해서
        어느 규칙이 왜 틀렸는지 보기 위한 것이다 (P1).
    """
    wins = 0
    total_ticks = 0
    total_hp = 0
    total_cleared = 0
    total_left = 0
    worst_seed = base_seed
    worst_cleared = len(templates) + 1

    for index in range(runs):
        seed = base_seed + index
        # 방마다 남은 적 HP 를 적어 둔다. 런이 끝난 방의 값이 그 런의 여유분이다.
        margins: list[int] = []

        def run_and_measure(engine: TickEngine, sink: list[int] = margins) -> BattleResult:
            """방 하나를 돌리고 남은 적 HP 비율을 적어 둔다.

            Args:
                engine: 조립된 엔진.
                sink: 적어 둘 목록. 기본 인자로 묶어 늦은 바인딩을 피한다.

            Returns:
                그 방의 결과.
            """
            outcome = run_battle(engine)
            sink.append(compute_enemy_hp_left_pct(engine.state))
            return outcome

        result = run_room_chain(
            templates,
            balance,
            catalog,
            player_ruleset,
            enemy_rulesets,
            seed,
            run_room=run_and_measure,
        )
        total_left += margins[-1] if margins else PERCENT
        total_ticks += result.total_ticks
        total_hp += result.player_hp
        total_cleared += result.cleared_rooms
        if result.outcome == OUTCOME_PLAYER_WIN and result.cleared_rooms == len(templates):
            wins += 1
        elif result.cleared_rooms < worst_cleared:
            worst_cleared = result.cleared_rooms
            worst_seed = seed

    return build_batch_stats(
        ruleset_id,
        runs,
        wins,
        (total_ticks, total_hp, total_cleared),
        worst_seed,
        total_left // runs if runs else 0,
    )


def run_floor_batch(
    ruleset_id: str,
    templates: tuple[RoomTemplate, ...],
    balance: dict,
    catalog: BlockCatalog,
    player_ruleset: RuleSet | None,
    enemy_rulesets: dict[str, RuleSet],
    runs: int,
    base_seed: int = 1,
    floor_index: int = FIRST_FLOOR,
) -> BatchStats:
    """시드마다 층을 새로 만들어 돌고 통계를 낸다.

    고정 연쇄와 달리 방 조합이 시드마다 달라, 승률이 0%/100% 로 굳지 않고 실제
    분포를 낸다. R2(단일 정답 수렴) 를 보는 쪽은 이 함수다.

    Args:
        ruleset_id: 통계에 붙일 이름.
        templates: 층이 고를 수 있는 룸 템플릿 전량. min_floor 로 걸러진다.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        player_ruleset: 플레이어 규칙표. None 이면 폴백.
        enemy_rulesets: 적 규칙표들.
        runs: 반복 횟수.
        base_seed: 시작 시드. 런마다 1씩 늘린다.
        floor_index: 만들 층 번호.

    Returns:
        승률과 평균값들. 클리어 수는 방이 아니라 노드 수다.
    """
    rooms = {template.template_id: template for template in templates}
    wins = 0
    total_ticks = 0
    total_hp = 0
    total_cleared = 0
    worst_seed = base_seed
    worst_cleared = len(templates) + 1

    for index in range(runs):
        seed = base_seed + index
        context = RoomLoopContext(
            floor_map=build_floor_map(seed, floor_index, templates),
            templates=rooms,
            balance=balance,
            catalog=catalog,
            enemy_rulesets=enemy_rulesets,
        )
        result = run_room_loop(context, player_ruleset)
        total_ticks += result.total_ticks
        total_hp += result.state.hp
        total_cleared += result.cleared_nodes
        if result.outcome == OUTCOME_PLAYER_WIN:
            wins += 1
        elif result.cleared_nodes < worst_cleared:
            worst_cleared = result.cleared_nodes
            worst_seed = seed

    return build_batch_stats(
        ruleset_id, runs, wins, (total_ticks, total_hp, total_cleared), worst_seed
    )


def compute_enemy_hp_left_pct(state: WorldState) -> int:
    """살아남은 적의 HP 가 전체의 몇 퍼센트인지 센다.

    **승률이 못 보여주는 기울기를 여기서 만든다.** 0 이면 전멸시킨 것이고, 100 이면
    한 대도 못 때린 것이다 — 뒤쪽은 밸런스가 아니라 그 방에서 규칙표가 아예 작동하지
    않는다는 신호다(조건이 영영 거짓).

    Args:
        state: 전투가 끝난 세계 상태.

    Returns:
        0 이상 100 이하의 정수 퍼센트. 적이 없었으면 0.
    """
    foes = [item for item in state.entities.values() if item.faction == FACTION_ENEMY]
    total = sum(item.hp_max for item in foes)
    if total <= 0:
        return 0
    return sum(max(0, item.hp) for item in foes) * PERCENT // total


def build_batch_stats(
    ruleset_id: str,
    runs: int,
    wins: int,
    totals: tuple[int, int, int],
    worst_seed: int,
    enemy_hp_left_pct: int = 0,
) -> BatchStats:
    """누적값을 통계로 접는다. 두 실행 방식이 같은 표를 내도록 여기 하나만 둔다.

    Args:
        ruleset_id: 통계에 붙일 이름.
        runs: 반복 횟수.
        wins: 이긴 런 수.
        totals: 틱·HP·클리어 수의 합계.
        worst_seed: 가장 얕게 죽은 런의 시드.
        enemy_hp_left_pct: 끝난 방에 남은 적 HP 비율의 평균.

    Returns:
        평균까지 낸 통계. 클리어 수만 100 을 곱해 소수 둘째 자리를 정수로 나른다.
    """
    total_ticks, total_hp, total_cleared = totals
    return BatchStats(
        ruleset_id=ruleset_id,
        runs=runs,
        wins=wins,
        average_ticks=total_ticks // runs if runs else 0,
        average_hp=total_hp // runs if runs else 0,
        average_cleared=total_cleared * PERCENT // runs if runs else 0,
        enemy_hp_left_pct=enemy_hp_left_pct,
        worst_seed=worst_seed,
    )
