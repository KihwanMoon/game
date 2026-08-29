"""컴포지션 루트. 설정을 읽고 코어를 조립해 실행한다 (표준 문서 §12).

Phase 1 은 UI 가 없다. 출력은 터미널 텍스트 로그이며, 매 틱 평가된 조건의 실제 값을
그대로 보여준다 (GDD §8.2) — 죽고 나서 어느 규칙이 왜 틀렸는지 여기서 특정한다.

오토배틀은 플레이어 입력이 없는 시간이 길다. 그 시간을 관찰과 진단으로 채우는 것이
이 화면의 일이며(GDD §8), 그래서 보는 방식을 셋 둔다.

    uv run python -m game.main --seed 12345 --ruleset g0_kite --room corridor
    uv run python -m game.main --ruleset g0_kite --step 10      # 10틱씩 끊어 보기
    uv run python -m game.main --ruleset g0_kite --replay-last 15  # 사망 직전 15틱
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from game.app.core.event_log import EventLog
from game.app.rules.rule_vm import build_rule_vm
from game.app.services.analyze_battle import (
    build_damage_heatmap,
    build_rule_stats,
    format_damage_heatmap,
    format_rule_stats,
)
from game.app.services.replay_battle import (
    build_replay_payload,
    build_replay_record,
    filter_recent_entries,
    format_playback_lines,
    parse_replay,
    run_replay,
)
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.app.services.run_stepped_battle import iter_tick_batches
from game.app.simulation.engine import TickEngine
from game.app.simulation.phases import OUTCOME_ONGOING
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import BlockCatalog, load_block_catalog
from game.schemas.room import RoomTemplate, load_room_templates
from game.schemas.ruleset import RuleSet, load_rulesets

DEFAULT_ROOM = "open_field"
TAIL_LINES = 24
PLAYER_ID = "player"


@dataclass(frozen=True)
class RunContext:
    """한 번의 실행이 쓰는 자원 묶음. 어느 보기 방식이든 같은 것을 본다."""

    balance: dict
    catalog: BlockCatalog
    rooms: dict[str, RoomTemplate]
    enemy_rulesets: dict[str, RuleSet]
    player_ruleset: RuleSet | None


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
    parser.add_argument(
        "--ruleset-file",
        default=None,
        help="규칙표 JSON 경로. 생략하면 번들된 예시를 쓴다. 자기 파일로 연습할 때 쓴다",
    )
    parser.add_argument("--tail", type=int, default=TAIL_LINES, help="출력할 마지막 줄 수")
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        help="N틱씩 끊어 출력한다. 0 이면 끊지 않는다 (즉시 실행)",
    )
    parser.add_argument(
        "--replay-last",
        type=int,
        default=0,
        help="시드와 규칙표만으로 다시 돌린 뒤 마지막 N틱과 피해 히트맵을 낸다",
    )
    return parser.parse_args(argv)


def load_player_ruleset(ruleset_id: str | None, ruleset_file: str | None) -> RuleSet | None:
    """플레이어 규칙표를 읽는다.

    Args:
        ruleset_id: 규칙표 id. None 이면 폴백 정책으로 돈다.
        ruleset_file: 규칙표 JSON 경로. None 이면 번들된 예시를 쓴다.

    Returns:
        읽어들인 규칙표. id 를 주지 않았으면 None.

    Raises:
        KeyError: 그 id 가 파일에 없는 경우. 있는 id 목록을 메시지에 담는다.
    """
    if ruleset_id is None:
        return None
    source = Path(ruleset_file) if ruleset_file else G0_RULESETS_PATH
    rulesets = load_rulesets(source)
    if ruleset_id not in rulesets:
        raise KeyError(
            f"'{ruleset_id}' 를 {source} 에서 찾지 못했다. 있는 것: {', '.join(sorted(rulesets))}"
        )
    return rulesets[ruleset_id]


def build_run_context(arguments: argparse.Namespace) -> RunContext:
    """번들된 데이터를 읽어 자원 묶음을 만든다.

    Args:
        arguments: 해석된 명령행 인자.

    Returns:
        조립에 필요한 자원 묶음.

    Raises:
        KeyError: 요청한 규칙표가 없는 경우.
    """
    return RunContext(
        balance=load_balance(BALANCE_PATH),
        catalog=load_block_catalog(BLOCKS_PATH),
        rooms={t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)},
        enemy_rulesets=load_rulesets(ENEMY_RULESETS_PATH),
        player_ruleset=load_player_ruleset(arguments.ruleset, arguments.ruleset_file),
    )


def build_battle_engine(arguments: argparse.Namespace, context: RunContext) -> TickEngine:
    """방 하나짜리 전투 엔진을 조립한다.

    Args:
        arguments: 해석된 명령행 인자.
        context: 자원 묶음.

    Returns:
        첫 틱을 돌릴 준비가 된 엔진.
    """
    engine = build_engine(context.rooms[arguments.room], context.balance, seed=arguments.seed)
    if context.player_ruleset is not None:
        engine.policies[PLAYER_ID] = build_rule_vm(
            context.player_ruleset, context.catalog, engine.config.kind_types
        )
    assign_enemy_policies(engine, context.balance, context.catalog, context.enemy_rulesets)
    return engine


def render_rule_stats(log: EventLog) -> None:
    """플레이어의 규칙별 성적을 낸다 (GDD §8.3).

    Args:
        log: 전투 이벤트 로그.
    """
    print("\n규칙별 성적")
    print(format_rule_stats(build_rule_stats(log, PLAYER_ID)))


def render_full_battle(arguments: argparse.Namespace, context: RunContext) -> None:
    """전투를 끝까지 돌리고 로그 꼬리를 낸다.

    Args:
        arguments: 해석된 명령행 인자.
        context: 자원 묶음.
    """
    engine = build_battle_engine(arguments, context)
    result = run_battle(engine)
    for line in result.log_lines[-arguments.tail :]:
        print(line)
    print(f"\n{result.outcome} — {result.ticks}틱, 플레이어 HP {result.player_hp}")
    render_rule_stats(engine.log)


def render_stepped_battle(arguments: argparse.Namespace, context: RunContext) -> None:
    """전투를 N틱씩 끊어 낸다 (GDD §2.1 의 배속을 터미널로 옮긴 것).

    한 번에 다 쏟아 내면 400줄을 거슬러 올라가야 원인을 찾는다. 구간마다 머리글을
    붙여 어느 틱을 보고 있는지 잃지 않게 한다.

    Args:
        arguments: 해석된 명령행 인자.
        context: 자원 묶음.
    """
    engine = build_battle_engine(arguments, context)
    outcome = OUTCOME_ONGOING
    for batch in iter_tick_batches(engine, arguments.step):
        outcome = batch.outcome
        print(f"── T{batch.start_tick:03d}~T{batch.end_tick:03d} ({len(batch.entries)}줄)")
        for line in format_playback_lines(batch.entries):
            print(line)
    player_hp = engine.state.entities[PLAYER_ID].hp
    print(f"\n{outcome} — {engine.state.tick}틱, 플레이어 HP {player_hp}")
    render_rule_stats(engine.log)


def render_death_replay(arguments: argparse.Namespace, context: RunContext) -> None:
    """시드와 규칙표만으로 다시 돌린 뒤 마지막 N틱을 낸다 (GDD §8.3).

    직렬화를 한 번 왕복시킨 뒤 재생한다. 저장한 것을 읽어 돌리는 경로와 같은 경로를
    타야 "시드와 규칙표만으로 재현된다"는 계약(TDD §9)이 매 실행 확인된다.

    Args:
        arguments: 해석된 명령행 인자.
        context: 자원 묶음.
    """
    record = build_replay_record(arguments.seed, (arguments.room,), context.player_ruleset)
    playback = run_replay(
        parse_replay(build_replay_payload(record)),
        context.rooms,
        context.balance,
        context.catalog,
        context.enemy_rulesets,
    )
    room = playback.last_room
    print(f"직전 {arguments.replay_last}틱 재생 — {room.room_id} / {room.ticks}틱\n")
    for line in format_playback_lines(filter_recent_entries(room.entries, arguments.replay_last)):
        print(line)
    print(f"\n{playback.outcome} — {playback.total_ticks}틱, 플레이어 HP {playback.player_hp}")
    print("\n피해 히트맵 — 플레이어가 어느 칸에서 맞았는가")
    grid = build_damage_heatmap(room.hits, room.width, room.height, target_id=PLAYER_ID)
    print(format_damage_heatmap(grid))
    render_rule_stats(EventLog(entries=list(room.entries)))


def main() -> int:
    """진입점.

    Returns:
        정상 종료면 0, 규칙표를 찾지 못했으면 1.
    """
    arguments = parse_arguments(sys.argv[1:])
    try:
        context = build_run_context(arguments)
    except KeyError as error:
        print(error.args[0])
        return 1

    template = context.rooms[arguments.room]
    print(f"방 {template.template_id} — {template.purpose}")
    print(f"시드 {arguments.seed} / 규칙표 {arguments.ruleset or 'fallback'}\n")

    if arguments.replay_last > 0:
        render_death_replay(arguments, context)
    elif arguments.step > 0:
        render_stepped_battle(arguments, context)
    else:
        render_full_battle(arguments, context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
