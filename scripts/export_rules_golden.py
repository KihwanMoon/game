"""RuleVM·검증기·셀렉터의 기준값을 JSON 으로 내보낸다 (게이트 G3).

Phase 3 의 TypeScript 코어는 파이썬 코어와 같은 답을 내야 한다. 눈으로 대조하면 회귀를
놓치므로 파이썬 쪽 출력을 파일로 고정해 두고 TS 테스트가 그 파일을 읽어 대조한다.
기준의 정본은 언제나 파이썬 코어다.

여기 담기는 것은 세 가지다.

* **셀렉터의 동점 처리** — 같은 거리·같은 HP 일 때 누구를 고르는가. PRNG 를 쓰지 않고
  entity_id 사전순으로 가르므로 답이 하나로 정해지며, 그 답이 갈리면 같은 시드가 다른
  전투를 만든다 (R5).
* **검증기의 위반 메시지** — 문자열과 **그 순서**까지 기준이다. 규칙 에디터가 이것을
  그대로 띄우므로 (P1), 메시지가 달라지면 플레이어가 보는 화면이 달라진다.
* **조건식의 렌더링** — `적거리(2) <= 사거리(3)` 처럼 양변에 실측값이 붙는가
  (GDD §8.2). 참/거짓만 맞고 문자열이 갈리면 로그가 쓸모없어진다.

세계는 서비스 계층을 거치지 않고 여기서 직접 세운다. TS 쪽에는 아직 서비스가 없어
`build_engine` 에 대응하는 것이 없기 때문이며, 엔티티 배치를 문서에 그대로 실어 두면
양쪽이 같은 입력에서 출발하는 것이 파일 하나로 확인된다.

    uv run python -m scripts.export_rules_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.simulation.perception import build_snapshot
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from scripts.rules_golden_condition_cases import build_condition_cases, build_rule_vm_cases
from scripts.rules_golden_specs import KIND_TYPES, WORLD_SPECS, create_world
from scripts.rules_golden_validator_cases import build_validator_cases
from scripts.rules_golden_world_cases import (
    build_fallback_cases,
    build_selector_cases,
    build_snapshot_cases,
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/golden/rules_golden.json"


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    catalog = load_block_catalog(BLOCKS_PATH)
    rooms = {
        template.template_id: template for template in load_room_templates(ROOM_TEMPLATES_PATH)
    }
    worlds = {spec["world_id"]: create_world(spec, rooms) for spec in WORLD_SPECS}
    snapshots = {
        world_id: build_snapshot(state, state.entities["player"], KIND_TYPES)
        for world_id, state in worlds.items()
    }
    return {
        "_comment": [
            "파이썬 코어(rules·selectors)에서 생성한 기준값이다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_rules_golden",
            "위반 메시지와 조건 문자열은 순서와 글자까지 기준이다 — 규칙 에디터와 로그가",
            "이것을 그대로 띄우기 때문이다 (GDD §8.2, P1).",
        ],
        "kind_types": [[kind_id, kind] for kind_id, kind in KIND_TYPES.items()],
        "balance_path": BALANCE_PATH.name,
        "worlds": list(WORLD_SPECS),
        "snapshots": build_snapshot_cases(worlds),
        "selectors": build_selector_cases(worlds),
        "validator": build_validator_cases(catalog),
        "conditions": build_condition_cases(worlds, snapshots, catalog),
        "rule_vm": build_rule_vm_cases(worlds, snapshots, catalog),
        "fallback": build_fallback_cases(worlds, snapshots),
    }


def export_rules_golden(target_path: Path) -> Path:
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
    written = export_rules_golden(GOLDEN_PATH)
    print(f"기준값을 썼다: {written}")


if __name__ == "__main__":
    main()
