"""헤드리스 배치 러너 — 규칙표별 승률을 뽑는다 (TDD §10, 로드맵 §10).

매주 금요일 리뷰가 이 출력을 본다. 밸런싱을 감이 아니라 데이터로 하기 위한 것이다.

    uv run python -m scripts.run_batch --runs 200

`-m` 로 부르는 이유는 그래야 저장소 루트가 import 경로에 들어가기 때문이다.
이 프로토타입은 설치 가능한 패키지로 만들지 않는다 (TDD §1.2 — 버릴 코드).
"""

import argparse
import sys
import time

from game.app.services.run_batch import run_batch
from game.app.services.run_battle import load_balance
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import RuleSet, load_rulesets

CHAIN_ROOM_IDS = ("open_field", "corridor", "pillars")
MILLISECONDS = 1000


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
    return parser.parse_args(argv)


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


def main() -> int:
    """진입점.

    Returns:
        정상 종료면 0.
    """
    arguments = parse_arguments(sys.argv[1:])
    catalog = load_block_catalog(BLOCKS_PATH)
    balance = load_balance(BALANCE_PATH)
    rooms = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    chain = tuple(rooms[room_id] for room_id in CHAIN_ROOM_IDS)
    enemy_rulesets = load_rulesets(ENEMY_RULESETS_PATH)
    player_rulesets = load_rulesets(G0_RULESETS_PATH)

    candidates: list[tuple[str, RuleSet | None]] = [("fallback", None)]
    candidates.extend(player_rulesets.items())

    started = time.perf_counter()
    rows = [
        run_batch(
            name,
            chain,
            balance,
            catalog,
            ruleset,
            enemy_rulesets,
            runs=arguments.runs,
            base_seed=arguments.seed,
        )
        for name, ruleset in candidates
    ]
    elapsed = time.perf_counter() - started

    print(f"방 연쇄: {' → '.join(CHAIN_ROOM_IDS)}")
    print(format_report(rows))
    total_runs = arguments.runs * len(candidates)
    print(
        f"\n{total_runs}런 {elapsed:.1f}초 "
        f"(런당 {elapsed / total_runs * MILLISECONDS:.1f}ms — TDD §11 목표 300ms)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
