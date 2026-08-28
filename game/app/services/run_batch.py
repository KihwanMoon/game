"""헤드리스 배치 실행 — 규칙표의 승률을 데이터로 잰다 (TDD §10).

밸런싱을 감이 아니라 데이터로 하는 것이 결정론 코어를 최우선에 둔 실질적 이유다.
같은 시드가 같은 결과를 내므로, 실패한 런을 시드만 들고 그대로 재현해 볼 수 있다.
"""

from dataclasses import dataclass

from game.app.services.run_chain import run_room_chain
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.schemas.blocks import BlockCatalog
from game.schemas.room import RoomTemplate
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
    worst_seed = base_seed
    worst_cleared = len(templates) + 1

    for index in range(runs):
        seed = base_seed + index
        result = run_room_chain(templates, balance, catalog, player_ruleset, enemy_rulesets, seed)
        total_ticks += result.total_ticks
        total_hp += result.player_hp
        total_cleared += result.cleared_rooms
        if result.outcome == OUTCOME_PLAYER_WIN and result.cleared_rooms == len(templates):
            wins += 1
        elif result.cleared_rooms < worst_cleared:
            worst_cleared = result.cleared_rooms
            worst_seed = seed

    return BatchStats(
        ruleset_id=ruleset_id,
        runs=runs,
        wins=wins,
        average_ticks=total_ticks // runs if runs else 0,
        average_hp=total_hp // runs if runs else 0,
        average_cleared=total_cleared * PERCENT // runs if runs else 0,
        worst_seed=worst_seed,
    )
