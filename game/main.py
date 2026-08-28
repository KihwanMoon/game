"""컴포지션 루트. 설정을 읽고 코어를 조립해 실행한다 (표준 문서 §12).

Phase 1 은 UI 가 없다. 출력은 터미널 텍스트 로그이며, 매 틱 평가된 조건의 실제 값을
그대로 보여준다 (GDD §8.2) — 죽고 나서 어느 규칙이 왜 틀렸는지 여기서 특정한다.

    uv run python -m game.main --seed 12345 --ruleset g0_kite --room corridor
"""

import argparse
import sys

from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

DEFAULT_ROOM = "open_field"
TAIL_LINES = 24


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자 목록.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="전투 1회를 돌리고 텍스트 로그를 낸다")
    parser.add_argument("--seed", type=int, default=12345, help="시드")
    parser.add_argument("--room", default=DEFAULT_ROOM, help="룸 템플릿 id")
    parser.add_argument("--ruleset", default=None, help="플레이어 규칙표 id. 생략하면 폴백")
    parser.add_argument("--tail", type=int, default=TAIL_LINES, help="출력할 마지막 줄 수")
    return parser.parse_args(argv)


def main() -> int:
    """진입점.

    Returns:
        정상 종료면 0.
    """
    arguments = parse_arguments(sys.argv[1:])
    catalog = load_block_catalog(BLOCKS_PATH)
    balance = load_balance(BALANCE_PATH)
    rooms = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    template = rooms[arguments.room]

    engine = build_engine(template, balance, seed=arguments.seed)
    if arguments.ruleset is not None:
        player_rulesets = load_rulesets(G0_RULESETS_PATH)
        engine.policies["player"] = build_rule_vm(
            player_rulesets[arguments.ruleset], catalog, engine.config.kind_types
        )
    assign_enemy_policies(engine, balance, catalog, load_rulesets(ENEMY_RULESETS_PATH))

    result = run_battle(engine)
    print(f"방 {template.template_id} — {template.purpose}")
    print(f"시드 {arguments.seed} / 규칙표 {arguments.ruleset or 'fallback'}\n")
    for line in result.log_lines[-arguments.tail :]:
        print(line)
    print(f"\n{result.outcome} — {result.ticks}틱, 플레이어 HP {result.player_hp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
