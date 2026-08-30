"""런 티켓의 기준값을 JSON 으로 내보낸다 (docs/설계/7_변조방지 §4).

티켓 id 형식과 코어 버전 문자열이 두 코어에서 갈리면, 서버가 붙는 날 "티켓을 못
알아본다" 로 드러난다. 그때는 이미 발급된 티켓이 있어 형식을 바꿀 수 없다.

    uv run python -m scripts.export_ticket_golden
"""

import json
from pathlib import Path

from game.schemas.run_ticket import MAX_SEED, build_core_version, create_local_ticket

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/__golden__/run_ticket.json"

# 방 id 에 콜론이 없다는 전제를 깔지 않는다 — id 를 콜론으로 잇고 있으므로,
# 방 이름이 바뀌었을 때 파싱이 깨지는지가 여기서 드러난다.
CASES: tuple[tuple[int, str, int], ...] = (
    (0, "room_a", 1),
    (12345, "room_a", 1),
    (12345, "room_b", 3),
    # 이식 상한 그 자체. 여기서 두 코어가 갈리면 시드 범위 제약이 깨진 것이다.
    (MAX_SEED, "room_a", 1),
)

BLOCK_LIST_VERSION = 4
BALANCE_VERSION = 3


def export_ticket_golden() -> Path:
    """기준값 파일을 쓴다.

    Returns:
        쓴 파일 경로.
    """
    core_version = build_core_version(BLOCK_LIST_VERSION, BALANCE_VERSION)
    cases = []
    for seed, room_id, floor in CASES:
        ticket = create_local_ticket(seed, room_id, core_version, floor=floor)
        cases.append(
            {
                "seed": seed,
                "room_id": room_id,
                "floor": floor,
                "ticket_id": ticket.ticket_id,
                "mode": str(ticket.mode),
            }
        )
    payload = {
        "_comment": "파이썬 정본이 만든 티켓 id 와 코어 버전. scripts/export_ticket_golden.py",
        "block_list_version": BLOCK_LIST_VERSION,
        "balance_version": BALANCE_VERSION,
        "core_version": core_version,
        "cases": cases,
    }
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return GOLDEN_PATH


def main() -> None:
    """스크립트 진입점."""
    print(f"wrote {export_ticket_golden()}")


if __name__ == "__main__":
    main()
