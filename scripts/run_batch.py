"""헤드리스 배치 러너 — 규칙표별 승률을 뽑는다 (TDD §10, 로드맵 §10).

매주 금요일 리뷰가 이 출력을 본다. 밸런싱을 감이 아니라 데이터로 하기 위한 것이다.

    uv run python -m scripts.run_batch --runs 1000                 # 고정 3방 연쇄
    uv run python -m scripts.run_batch --runs 300 --mode floor     # 시드마다 새 층
    uv run python -m scripts.run_batch --runs 50 --mode descent    # 1층→보스 하강

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

from game.app.progression.floors import BOSS_ROOM_ID, read_boss_floor
from game.app.services.run_batch import BatchStats, run_batch, run_floor_batch
from game.app.services.run_battle import load_balance
from game.app.services.run_descent import DescentStats, run_descent_batch
from game.app.store.tickets import CHAIN_LENGTH
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    LATER_BLOCKS_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import BlockCatalog, load_block_catalog
from game.schemas.room import FIRST_FLOOR, RoomTemplate, load_room_templates
from game.schemas.ruleset import RuleSet, load_rulesets

CHAIN_ROOM_IDS = ("open_field", "corridor", "pillars")
MILLISECONDS = 1000
PERCENT_BASE = 100
MODE_CHAIN = "chain"
MODE_FLOOR = "floor"
MODE_DESCENT = "descent"

# 하강의 첫 방. 실제 런에서 편집기가 고르는 자리이고, 여기서는 고정해 둔다 —
# 규칙표 사이의 차이만 남기려면 출발선이 같아야 한다.
DESCENT_FIRST_ROOM = "open_field"
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
        choices=(MODE_CHAIN, MODE_FLOOR, MODE_DESCENT),
        default=MODE_CHAIN,
        help="chain 은 고정 3방, floor 는 시드마다 새 층, descent 는 1층→보스 하강",
    )
    parser.add_argument("--floor", type=int, default=FIRST_FLOOR, help="floor 모드의 층 번호")
    parser.add_argument(
        "--rooms-per-floor", type=int, default=CHAIN_LENGTH, help="descent 모드의 층당 방 수"
    )
    return parser.parse_args(argv)


def load_batch_resources() -> BatchResources:
    """밸런스·블록·룸·규칙표를 한 번만 읽는다.

    Returns:
        배치에 넘길 자원 묶음. 후보 목록의 첫째는 규칙표 없는 폴백이다.
    """
    player_rulesets = load_rulesets(G0_RULESETS_PATH)
    player_rulesets.update(load_rulesets(BENCHMARK_RULESETS_PATH))
    player_rulesets.update(load_rulesets(LATER_BLOCKS_RULESETS_PATH))
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


def run_one_descent(
    name: str,
    ruleset: RuleSet | None,
    resources: BatchResources,
    arguments: argparse.Namespace,
) -> DescentStats:
    """규칙표 하나로 하강을 돌린다.

    Args:
        name: 통계에 붙일 이름.
        ruleset: 플레이어 규칙표. None 이면 폴백.
        resources: 자원 묶음.
        arguments: 해석된 명령행 인자.

    Returns:
        그 규칙표의 도달 층 분포.
    """
    return run_descent_batch(
        name,
        {template.template_id: template for template in resources.templates},
        resources.balance,
        resources.catalog,
        ruleset,
        resources.enemy_rulesets,
        arguments.runs,
        arguments.seed,
        DESCENT_FIRST_ROOM,
        arguments.rooms_per_floor,
        BOSS_ROOM_ID,
        read_boss_floor(resources.balance),
    )


def format_descent_report(rows: list, boss_floor: int) -> str:
    """하강 통계를 표로 편다.

    **승률을 안 적는다.** 대부분 0% 로 나오고, 그러면 1층에서 죽은 것과 9층에서 죽은
    것이 같은 줄로 보인다 — 재야 하는 것은 어디까지 갔는가다.

    Args:
        rows: DescentStats 목록.
        boss_floor: 보스가 서는 층.

    Returns:
        출력할 문자열.
    """
    width = max([len(stats.ruleset_id) for stats in rows] + [len("규칙표")])
    floors = "".join(f"{floor:>3}" for floor in range(1, boss_floor + 1))
    lines = [
        f"{'규칙표':<{width}} {'런':>4} {'평균층':>7} {'최고':>4} {'완주':>4}  {floors}  최악시드",
        "-" * (width + 30 + boss_floor * 3),
    ]
    for stats in rows:
        bars = "".join(
            f"{count * PERCENT_BASE // stats.runs if stats.runs else 0:>3}"
            for count in stats.cleared_by_floor
        )
        lines.append(
            f"{stats.ruleset_id:<{width}} {stats.runs:>4} {stats.average_floor_pct / 100:>7.2f} "
            f"{stats.deepest_floor:>4} {stats.finished:>4}  {bars}  "
            f"{stats.worst_seed}(층 {stats.worst_floor})"
        )
    lines.append("")
    lines.append("층 칸은 **그 층을 깬 런의 비율(%)** 이다. 100 이면 전부 지났다는 뜻이고,")
    lines.append("  0 이 나오는 첫 칸이 그 규칙표가 멈추는 벽이다.")
    return "\n".join(lines)


def format_report(rows: list) -> str:
    """통계를 표로 편다.

    Args:
        rows: BatchStats 목록.

    Returns:
        출력할 문자열.
    """
    # 이름 칸은 **가장 긴 id 에 맞춘다.** 고정 폭이면 긴 이름이 칸을 밀어 그 줄만
    # 어긋나고, 표를 세로로 훑을 수 없다.
    width = max([len(stats.ruleset_id) for stats in rows] + [len("규칙표")])
    header = (
        f"{'규칙표':<{width}} {'런':>5} {'승률':>6} {'적HP':>6} {'평균틱':>7} "
        f"{'평균HP':>7} {'클리어':>8}  최악시드"
    )
    lines = [header, "-" * (width + 62)]
    for stats in rows:
        lines.append(
            f"{stats.ruleset_id:<{width}} {stats.runs:>5} {stats.win_rate_pct:>5}% "
            f"{stats.enemy_hp_left_pct:>5}% "
            f"{stats.average_ticks:>7} {stats.average_hp:>7} "
            f"{stats.average_cleared / 100:>9.2f}  {stats.worst_seed}"
        )
    lines.append("")
    lines.append(
        "적HP = 런이 끝난 방에 남은 적 체력. 0% 는 전멸시킨 것이고 100% 는 **한 대도"
        " 못 때린 것**이다 —"
    )
    lines.append(
        "  후자는 밸런스가 아니라 그 방에서 규칙표가 아예 작동하지 않는다는 신호다"
        " (조건이 영영 거짓)."
    )
    return "\n".join(lines)


def format_scope(arguments: argparse.Namespace) -> str:
    """무엇을 돌린 표인지 한 줄로 적는다.

    Args:
        arguments: 해석된 명령행 인자.

    Returns:
        표 위에 붙일 머리글.
    """
    if arguments.mode == MODE_DESCENT:
        return f"하강: 1층 → 보스 (층당 {arguments.rooms_per_floor}방, 첫 방 {DESCENT_FIRST_ROOM})"
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
    if arguments.mode == MODE_DESCENT:
        descents = [
            run_one_descent(name, ruleset, resources, arguments)
            for name, ruleset in resources.candidates
        ]
        elapsed = time.perf_counter() - started
        print(format_scope(arguments))
        print(format_descent_report(descents, read_boss_floor(resources.balance)))
        rows = []
    else:
        rows = [
            run_one_batch(name, ruleset, resources, arguments)
            for name, ruleset in resources.candidates
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
