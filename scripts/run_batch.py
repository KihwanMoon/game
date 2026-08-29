"""헤드리스 배치 러너 — 규칙표별 승률을 뽑는다 (TDD §10, 로드맵 §10).

매주 금요일 리뷰가 이 출력을 본다. 밸런싱을 감이 아니라 데이터로 하기 위한 것이다.

    uv run python -m scripts.run_batch --runs 1000                 # 고정 3방 연쇄
    uv run python -m scripts.run_batch --runs 300 --mode floor     # 시드마다 새 층

`-m` 로 부르는 이유는 그래야 저장소 루트가 import 경로에 들어가기 때문이다.
이 프로토타입은 설치 가능한 패키지로 만들지 않는다 (TDD §1.2 — 버릴 코드).

**두 방식은 다른 것을 잰다.** 고정 연쇄는 방도 적 배치도 템플릿이 정하므로 난수가
닿는 곳이 좁고, 이 세 방에서는 12개 규칙표 전부가 시드에 대해 상수다 — 1,000 런의
승률이 0% 아니면 100% 로만 나온다 (실측 docs/05). R2(전략이 하나로 수렴했는가)를
보려면 층 생성이 만드는 방 조합의 다양성이 필요하고, 그것이 `--mode floor` 다.
"""

import argparse
import sys
import time
from dataclasses import dataclass

from game.app.services.run_batch import BatchStats, run_batch, run_floor_batch
from game.app.services.run_battle import load_balance
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import BlockCatalog, load_block_catalog
from game.schemas.room import FIRST_FLOOR, RoomTemplate, load_room_templates
from game.schemas.ruleset import RuleSet, load_rulesets

CHAIN_ROOM_IDS = ("open_field", "corridor", "pillars")
MILLISECONDS = 1000
MODE_CHAIN = "chain"
MODE_FLOOR = "floor"
FALLBACK_ID = "fallback"


@dataclass(frozen=True)
class BatchResources:
    """배치가 도는 동안 바뀌지 않는 것들."""

    catalog: BlockCatalog
    balance: dict
    templates: tuple[RoomTemplate, ...]
    enemy_rulesets: dict[str, RuleSet]
    candidates: tuple[tuple[str, RuleSet | None], ...]


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자 목록.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="헤드리스 배치 밸런싱 러너")
    parser.add_argument("--runs", type=int, default=100, help="규칙표당 반복 횟수")
    parser.add_argument("--seed", type=int, default=1, help="시작 시드")
    parser.add_argument(
        "--mode",
        choices=(MODE_CHAIN, MODE_FLOOR),
        default=MODE_CHAIN,
        help="chain 은 고정 3방 연쇄, floor 는 시드마다 새로 만든 층",
    )
    parser.add_argument("--floor", type=int, default=FIRST_FLOOR, help="floor 모드의 층 번호")
    return parser.parse_args(argv)


def load_batch_resources() -> BatchResources:
    """밸런스·블록·룸·규칙표를 한 번만 읽는다.

    Returns:
        배치에 넘길 자원 묶음. 후보 목록의 첫째는 규칙표 없는 폴백이다.
    """
    player_rulesets = load_rulesets(G0_RULESETS_PATH)
    player_rulesets.update(load_rulesets(BENCHMARK_RULESETS_PATH))
    candidates: list[tuple[str, RuleSet | None]] = [(FALLBACK_ID, None)]
    candidates.extend(player_rulesets.items())
    return BatchResources(
        catalog=load_block_catalog(BLOCKS_PATH),
        balance=load_balance(BALANCE_PATH),
        templates=load_room_templates(ROOM_TEMPLATES_PATH),
        enemy_rulesets=load_rulesets(ENEMY_RULESETS_PATH),
        candidates=tuple(candidates),
    )


def run_one_batch(
    name: str,
    ruleset: RuleSet | None,
    resources: BatchResources,
    arguments: argparse.Namespace,
) -> BatchStats:
    """규칙표 하나를 인자가 고른 방식으로 돌린다.

    Args:
        name: 통계에 붙일 이름.
        ruleset: 플레이어 규칙표. None 이면 폴백.
        resources: 자원 묶음.
        arguments: 해석된 명령행 인자.

    Returns:
        그 규칙표의 통계.
    """
    common = {
        "balance": resources.balance,
        "catalog": resources.catalog,
        "player_ruleset": ruleset,
        "enemy_rulesets": resources.enemy_rulesets,
        "runs": arguments.runs,
        "base_seed": arguments.seed,
    }
    if arguments.mode == MODE_FLOOR:
        return run_floor_batch(name, resources.templates, floor_index=arguments.floor, **common)
    rooms = {template.template_id: template for template in resources.templates}
    chain = tuple(rooms[room_id] for room_id in CHAIN_ROOM_IDS)
    return run_batch(name, chain, **common)


def format_report(rows: list) -> str:
    """통계를 표로 편다.

    Args:
        rows: BatchStats 목록.

    Returns:
        출력할 문자열.
    """
    header = (
        f"{'규칙표':<14} {'런':>5} {'승률':>6} {'평균틱':>7} {'평균HP':>7} {'클리어':>8}  최악시드"
    )
    lines = [header, "-" * 68]
    for stats in rows:
        lines.append(
            f"{stats.ruleset_id:<14} {stats.runs:>5} {stats.win_rate_pct:>5}% "
            f"{stats.average_ticks:>7} {stats.average_hp:>7} "
            f"{stats.average_cleared / 100:>9.2f}  {stats.worst_seed}"
        )
    return "\n".join(lines)


def format_scope(arguments: argparse.Namespace) -> str:
    """무엇을 돌린 표인지 한 줄로 적는다.

    Args:
        arguments: 해석된 명령행 인자.

    Returns:
        표 위에 붙일 머리글.
    """
    if arguments.mode == MODE_FLOOR:
        return f"층 {arguments.floor} — 시드마다 새로 만든 층 (클리어는 노드 수)"
    return f"방 연쇄: {' → '.join(CHAIN_ROOM_IDS)}"


def main() -> int:
    """진입점.

    Returns:
        정상 종료면 0.
    """
    arguments = parse_arguments(sys.argv[1:])
    resources = load_batch_resources()

    started = time.perf_counter()
    rows = [
        run_one_batch(name, ruleset, resources, arguments) for name, ruleset in resources.candidates
    ]
    elapsed = time.perf_counter() - started

    print(format_scope(arguments))
    print(format_report(rows))
    total_runs = arguments.runs * len(resources.candidates)
    print(
        f"\n{total_runs}런 {elapsed:.1f}초 "
        f"(런당 {elapsed / total_runs * MILLISECONDS:.1f}ms — TDD §11 목표 300ms)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
