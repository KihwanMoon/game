"""메타 세이브의 기준값을 JSON 으로 내보낸다 (GDD §2.3, TDD §9).

헤드리스 러너가 쓴 `volume/meta_save.json` 을 브라우저가 그대로 읽고 이어서 써야 한다.
형식만이 아니라 **결산 규칙도 같아야** 하므로, 파이썬이 결산한 결과를 파일로 고정해 두고
TS 테스트가 같은 입력으로 같은 값을 내는지 본다. 기준의 정본은 언제나 파이썬 코어다.

케이스마다 셋을 싣는다.

* **before** — 결산 전 세이브 절.
* **summary** — 이번 런의 결산 입력.
* **after** — 결산 후 세이브 절. TS 가 만든 절과 키 단위로 대조한다.

두 코어가 같은 값을 **다른 글자로** 쓴다는 점에 주의한다. 파이썬은 `indent=2` 로 찍고
TS 는 정규 형식(좁게)으로 찍으므로 바이트 대조는 성립하지 않는다. 대조 대상은 절이다.

    uv run python -m scripts.export_meta_golden
"""

import json
from pathlib import Path

from game.app.services.manage_meta import RunSummary, apply_run_result
from game.config import BLOCKS_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.meta_save import MetaSave, build_meta_payload

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/storage/__golden__/meta_save.json"

# 케이스는 결산 규칙이 갈릴 수 있는 자리를 하나씩 짚는다.
CASES: tuple[tuple[str, MetaSave, RunSummary], ...] = (
    (
        "첫 런 — 빈 세이브에 쌓인다",
        MetaSave(),
        RunSummary(
            floor_reached=1,
            is_cleared=True,
            seen_perceptions=("target_distance", "self_hp_percent"),
            seen_actions=("ATTACK", "RETREAT"),
            encountered_kinds=("goblin_rusher", "goblin_archer", "goblin_rusher"),
            defeated_kinds=("goblin_rusher",),
        ),
    ),
    (
        "재도전 — 더 얕게 죽어도 최고 층은 줄지 않는다",
        MetaSave(best_floor=4, unlocked_actions=("ATTACK",)),
        RunSummary(floor_reached=2, is_cleared=False, seen_actions=("SKILL_1",)),
    ),
    (
        "카탈로그에 없는 블록은 해금되지 않는다",
        MetaSave(),
        RunSummary(seen_actions=("ATTACK", "HOMEBREW"), seen_perceptions=("nope",)),
    ),
    (
        "도감이 누적되고 kind_id 순으로 정렬된다",
        MetaSave(),
        RunSummary(
            encountered_kinds=("mender_acolyte", "bomb_slime", "arch_summoner", "bomb_slime"),
            defeated_kinds=("bomb_slime", "arch_summoner"),
        ),
    ),
)


def build_summary_payload(summary: RunSummary) -> dict:
    """결산 입력을 JSON 절로 되돌린다.

    Args:
        summary: 되돌릴 결산 입력.

    Returns:
        TS 가 그대로 읽을 수 있는 절.
    """
    return {
        "floor_reached": summary.floor_reached,
        "is_cleared": summary.is_cleared,
        "seen_perceptions": list(summary.seen_perceptions),
        "seen_actions": list(summary.seen_actions),
        "encountered_kinds": list(summary.encountered_kinds),
        "defeated_kinds": list(summary.defeated_kinds),
    }


def export_meta_golden() -> Path:
    """기준값 파일을 쓴다.

    Returns:
        쓴 파일 경로.
    """
    catalog = load_block_catalog(BLOCKS_PATH)
    cases = []
    for label, before, summary in CASES:
        after = apply_run_result(before, summary, catalog)
        cases.append(
            {
                "label": label,
                "before": build_meta_payload(before),
                "summary": build_summary_payload(summary),
                "after": build_meta_payload(after),
            }
        )
    payload = {
        "_comment": "파이썬 정본이 만든 메타 세이브 결산 기준값. scripts/export_meta_golden.py",
        "cases": cases,
    }
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return GOLDEN_PATH


def main() -> None:
    """스크립트 진입점."""
    path = export_meta_golden()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
