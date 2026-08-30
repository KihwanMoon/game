"""층 사슬의 기준 결과를 JSON 으로 내보낸다 (게이트 G3).

**연쇄는 방 하나짜리 골든이 잡지 못하는 것을 잡는다.** 시드 분기(`seed + index * 1000`),
HP·포션 인계, 층 압력 유지 — 셋 다 방 사이에서만 일어나므로 단일 방 대조로는 검증되지
않는다. 파이썬과 TS 가 두 번째 방부터 갈라져도 기존 골든은 침묵한다.

    uv run python -m scripts.export_chain_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.services.run_battle import load_balance
from game.app.services.run_chain import run_room_chain
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

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/golden/chain_golden.json"

# 대조할 연쇄들. (규칙표, 방 목록, 시드) 의 조합이다.
#
# **방을 이어 붙이는 순서가 계약이다.** 사이에 끼우면 그 뒤의 모든 기준 결과가 밀린다.
#
# 폴백 정책만으로는 첫 방에서 지므로 **인계도 시드 분기도 한 번도 실행되지 않는다.**
# 그래서 실제로 방을 넘어가는 규칙표를 쓴다 — 이기지 못하는 골든은 연쇄를 검증하지
# 못한다.
CHAIN_CASES: tuple[tuple[str | None, tuple[str, ...], int], ...] = (
    # HP 인계. 같은 방을 세 번 도는데 체력이 100→82→64→46 으로 줄어야 한다 —
    # 방마다 회복되면 연쇄가 뜻을 잃는다.
    ("g0_kite", ("corridor", "corridor", "corridor"), 4242),
    # 방마다 다른 템플릿 + 시드가 결과를 바꾸는 사례. 시드를 방마다 가르지 않으면
    # 여기서 갈린다.
    ("g0_kite", ("open_field", "corridor", "pillars"), 8080),
    ("g0_kite", ("open_field", "corridor", "pillars"), 4242),
    # 도중에 지는 것 — 진 방에서 멈추고 그때까지만 담는지 본다.
    ("g0_cover", ("open_field", "corridor", "pillars"), 4242),
    # 규칙표 없이 폴백 정책으로. 첫 방에서 져도 결과 형태는 같아야 한다.
    (None, ("corridor", "corridor"), 31337),
)


def build_chain_rows() -> list[dict[str, Any]]:
    """연쇄 사례들을 돌려 기준 결과를 만든다.

    Returns:
        사례마다 한 줄씩. 방별 결과를 함께 담는다.
    """
    balance = load_balance(BALANCE_PATH)
    catalog = load_block_catalog(BLOCKS_PATH)
    templates = load_room_templates(ROOM_TEMPLATES_PATH)
    by_id = {template.template_id: template for template in templates}
    enemy_rulesets = load_rulesets(ENEMY_RULESETS_PATH)
    player_rulesets = load_rulesets(G0_RULESETS_PATH)

    rows: list[dict[str, Any]] = []
    for ruleset_id, room_ids, seed in CHAIN_CASES:
        result = run_room_chain(
            tuple(by_id[room_id] for room_id in room_ids),
            balance,
            catalog,
            None if ruleset_id is None else player_rulesets[ruleset_id],
            enemy_rulesets,
            seed,
        )
        rows.append(
            {
                "ruleset_id": ruleset_id,
                "room_ids": list(room_ids),
                "seed": seed,
                "cleared_rooms": result.cleared_rooms,
                "outcome": result.outcome,
                "total_ticks": result.total_ticks,
                "player_hp": result.player_hp,
                "per_room": [
                    {"outcome": room.outcome, "ticks": room.ticks, "player_hp": room.player_hp}
                    for room in result.per_room
                ],
            }
        )
    return rows


def export_chain_golden(target_path: Path) -> Path:
    """기준 연쇄를 파일로 쓴다.

    Args:
        target_path: 쓸 경로.

    Returns:
        쓴 경로.
    """
    document = {
        "_comment": (
            "층 사슬 기준 결과 (게이트 G3). 시드 분기·HP 인계·층 압력 유지를 고정한다 —"
            " 셋 다 방 사이에서만 일어나므로 단일 방 골든이 잡지 못한다."
            " 손으로 고치지 않는다. scripts/export_chain_golden.py 로 다시 만든다."
        ),
        "seed_stride": 1000,
        "chains": build_chain_rows(),
    }
    target_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target_path


def main() -> None:
    """기준 연쇄를 내보낸다."""
    print(f"기준 연쇄를 썼다: {export_chain_golden(GOLDEN_PATH)}")


if __name__ == "__main__":
    main()
