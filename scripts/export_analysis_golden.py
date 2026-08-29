"""사후 분석 기준값을 JSON 으로 내보낸다 (GDD §8.3, 게이트 G3).

웹 UI 의 사후 분석 패널은 `game/app/services/analyze_battle.py` 와 **같은 집계**를 해야
한다. 화면이 파이썬과 다른 수를 적으면 플레이어는 터미널로 돌린 결과와 브라우저에서 본
결과 중 어느 쪽을 믿어야 할지 알 수 없고, 그 순간 사후 분석은 진단 도구가 아니게 된다.

내보내는 것은 세 가지다.

* `rule_stats` — 규칙별 발동·성공·헛돔. "어느 규칙이 틀렸는가" 에 답한다.
* `hits` — 피격 한 건마다의 틱·피격자·좌표·피해량. 좌표는 로그에 없고 틱 전후의 세계
  상태에만 있으므로, 한 틱씩 끊어 돌며 받아 적은 값이다(`replay_battle.BattleRecorder`).
* `heatmap_*` — 그 피격 기록을 격자로 접은 값. 행마다 쉼표로 이은 문자열이다. 정수 배열로
  찍으면 indent 를 준 JSON 에서 한 칸이 한 줄이 되어 파일이 열 배로 벌어진다.

전투를 돌리는 배선은 `scripts/export_golden.py` 것을 그대로 쓴다. 여기서 다시 조립하면
두 기준 문서가 서로 다른 전투를 담게 되어 대조가 무의미해진다.

    uv run python -m scripts.export_analysis_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.services.analyze_battle import (
    DamageHit,
    RuleStat,
    build_damage_heatmap,
    build_rule_stats,
)
from game.app.services.replay_battle import (
    DEATH_REPLAY_TICKS,
    BattleRecorder,
    RoomPlayback,
    filter_recent_entries,
)
from game.app.simulation.engine import TickEngine
from game.config import ENEMY_RULESETS_PATH
from game.schemas.ruleset import load_rulesets
from scripts.export_golden import (
    FLOOR,
    MAX_TICKS,
    PLAYER_ID,
    add_extra_enemies,
    build_case_engine,
    load_case_resources,
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/hud/__golden__/analysis.json"

# 덧붙일 적이 없는 조합이 쓰는 빈 목록.
NO_EXTRAS: tuple[tuple[str, int, int], ...] = ()

# 대조할 조합 — (방 id, 규칙표 id, 시드, 덧붙일 적).
#
# 집계가 갈리는 지점이 서로 다른 조합을 고른다. `hazard_field` 는 용암 피해가 UPKEEP 에
# 나므로 "틱 **시작** 좌표에서 맞았다" 는 규칙(PRE_MOVE_PHASES)을 태우고, 폭탄 슬라임을
# 덧붙인 조합은 TELEGRAPH 발동 피해를, 대소환사를 덧붙인 조합은 전투 도중 등장한 개체의
# 피격 좌표를 태운다. 덧붙이는 적과 좌표는 export_golden.py 의 ADVANCED_CASES 와 같다.
ANALYSIS_CASES: tuple[tuple[str, str, int, tuple[tuple[str, int, int], ...]], ...] = (
    ("open_field", "g0_pressure", 1, NO_EXTRAS),
    ("corridor", "g0_kite", 12345, NO_EXTRAS),
    ("hazard_field", "g0_cover", 99, NO_EXTRAS),
    ("spring_bait", "g0_pressure", 2024, NO_EXTRAS),
    ("open_field", "g0_kite", 4242, (("bomb_slime", 5, 4), ("mender_acolyte", 6, 2))),
    ("pillars", "g0_cover", 555, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
)


def build_stat_rows(stats: tuple[RuleStat, ...]) -> list[dict[str, Any]]:
    """규칙 성적표를 JSON 행으로 편다.

    Args:
        stats: build_rule_stats 결과.

    Returns:
        우선순위 순서를 유지한 행 목록. 헛돔 비율까지 함께 싣는다.
    """
    return [
        {
            "label": stat.label,
            "fired": stat.fired,
            "acted": stat.acted,
            "wasted": stat.wasted,
            "waste_pct": stat.waste_pct,
        }
        for stat in stats
    ]


def build_hit_rows(hits: tuple[DamageHit, ...]) -> list[dict[str, Any]]:
    """피격 기록을 JSON 행으로 편다.

    Args:
        hits: 방 하나에서 받아 적은 피격 기록.

    Returns:
        로그에 남은 순서 그대로의 행 목록.
    """
    return [
        {
            "tick": hit.tick,
            "target_id": hit.target_id,
            "x": hit.position[0],
            "y": hit.position[1],
            "amount": hit.amount,
        }
        for hit in hits
    ]


def format_heatmap_rows(grid: tuple[tuple[int, ...], ...]) -> list[str]:
    """히트맵 격자를 행마다 한 줄의 문자열로 편다.

    Args:
        grid: build_damage_heatmap 결과.

    Returns:
        `[y]` 순서의 문자열들. 각 줄은 그 행의 값을 쉼표로 이은 것이다.
    """
    return [",".join(str(value) for value in row) for row in grid]


def list_logged_entity_ids(playback: RoomPlayback) -> list[str]:
    """로그에 이름이 남은 엔티티를 사전순으로 모은다.

    플레이어만 대조하면 적 규칙표 쪽 집계가 검증되지 않는다. 소환물처럼 전투 도중 등장한
    개체도 로그에 남으므로 여기서 함께 잡힌다.

    Args:
        playback: 방 하나의 재생 결과.

    Returns:
        entity_id 사전순 목록.
    """
    return sorted({entry.entity_id for entry in playback.entries})


def build_case_record(
    engine: TickEngine,
    playback: RoomPlayback,
    plan: tuple[str, str, int, tuple[tuple[str, int, int], ...]],
) -> dict[str, Any]:
    """조합 하나의 사후 분석 기준을 만든다.

    Args:
        engine: 다 돌린 엔진.
        playback: 그 방의 재생 결과.
        plan: (방 id, 규칙표 id, 시드, 덧붙일 적).

    Returns:
        JSON 에 넣을 레코드.
    """
    room_id, ruleset_id, seed, extras = plan
    recent = filter_recent_entries(playback.entries, DEATH_REPLAY_TICKS)
    width, height = playback.width, playback.height
    return {
        "case_id": f"{room_id}__{ruleset_id}__{seed}",
        "room_id": room_id,
        "ruleset_id": ruleset_id,
        "seed": seed,
        "extra_enemies": [{"kind": kind, "x": x, "y": y} for kind, x, y in extras],
        "max_ticks": MAX_TICKS,
        "floor": FLOOR,
        "outcome": playback.outcome,
        "ticks": playback.ticks,
        "player_hp": engine.state.entities[PLAYER_ID].hp,
        "width": width,
        "height": height,
        "log_count": len(playback.entries),
        "rule_stats": {
            entity_id: build_stat_rows(build_rule_stats(engine.log, entity_id))
            for entity_id in list_logged_entity_ids(playback)
        },
        "hits": build_hit_rows(playback.hits),
        "heatmap_player": format_heatmap_rows(
            build_damage_heatmap(playback.hits, width, height, target_id=PLAYER_ID)
        ),
        "heatmap_all": format_heatmap_rows(build_damage_heatmap(playback.hits, width, height)),
        "recent_ticks": DEATH_REPLAY_TICKS,
        "recent_count": len(recent),
        "recent_first_tick": recent[0].tick if recent else None,
    }


def run_case(plan: tuple[str, str, int, tuple[tuple[str, int, int], ...]]) -> dict[str, Any]:
    """조합 하나를 한 틱씩 끊어 돌리고 기준 레코드를 만든다.

    한 틱씩 도는 이유는 피격 좌표 때문이다. 로그는 "누가 얼마를 맞았는가" 까지만 남기고
    "어디에서" 는 그 틱의 세계 상태에만 있다.

    Args:
        plan: (방 id, 규칙표 id, 시드, 덧붙일 적).

    Returns:
        JSON 에 넣을 레코드.
    """
    room_id, ruleset_id, seed, extras = plan
    balance, rooms, catalog, rulesets = load_case_resources()
    enemy_rulesets = load_rulesets(ENEMY_RULESETS_PATH)
    engine = build_case_engine(
        balance, rooms[room_id], catalog, enemy_rulesets, rulesets[ruleset_id], seed
    )
    if extras:
        add_extra_enemies(engine, balance, extras)
    recorder = BattleRecorder()
    recorder.run_room(engine)
    return build_case_record(engine, recorder.rooms[0], plan)


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    cases = [run_case(plan) for plan in ANALYSIS_CASES]
    return {
        "_comment": [
            "파이썬의 analyze_battle 집계 기준이다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_analysis_golden",
            "hits 는 한 틱씩 끊어 돌며 받아 적은 피격 좌표다 (replay_battle.BattleRecorder).",
            "heatmap_* 의 한 줄은 격자 한 행이며 값은 쉼표로 잇는다.",
        ],
        "max_ticks": MAX_TICKS,
        "floor": FLOOR,
        "player_id": PLAYER_ID,
        "case_count": len(cases),
        "cases": cases,
    }


def export_analysis_golden(target_path: Path) -> Path:
    """기준값을 파일로 쓴다.

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
    """기준값을 기본 경로에 내보낸다."""
    written = export_analysis_golden(GOLDEN_PATH)
    print(f"사후 분석 기준을 썼다: {written}")


if __name__ == "__main__":
    main()
