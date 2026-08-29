"""프리셋 공유 코드의 기준값을 JSON 으로 내보낸다 (M3, TDD §9).

브라우저가 규칙표를 저장하고 남과 주고받으려면 `game/schemas/preset_code.py` 와 **같은
형식**을 TS 쪽에도 두어야 한다. 형식이 갈리면 증상이 "가끔 프리셋이 안 열린다" 로 나와
원인까지 도달하기 어려우므로, 파이썬이 구운 코드를 파일로 고정해 두고 TS 테스트가 그것을
풀어 본다. 기준의 정본은 언제나 파이썬 코어다.

케이스마다 셋을 함께 싣는다.

* **payload** — 프리셋 절 자체. TS 가 만든 절과 키 단위로 대조한다.
* **canonical_json** — 그 절을 정렬해 좁게 찍은 글자. 압축 이전 단계가 어긋나면 여기서
  먼저 드러나고, gzip 바이트를 비교하는 것보다 어긋난 자리를 짚기 쉽다.
* **code** — `v2:` 공유 코드 전문.

반대 방향(TS 가 구운 코드를 파이썬이 푸는 것)은 `tests/test_preset_code_interop.py` 가
`ts_preset_code.json` 을 읽어 검사한다.

    uv run python -m scripts.export_preset_code_golden
"""

import json
from pathlib import Path

from game.config import BENCHMARK_RULESETS_PATH, ENEMY_RULESETS_PATH, G0_RULESETS_PATH
from game.schemas.meta_save import RulePreset, build_preset_payload
from game.schemas.preset_code import PRESET_CODE_PREFIX, export_preset_code
from game.schemas.ruleset import RuleSet, load_rulesets

GOLDEN_PATH = (
    Path(__file__).resolve().parents[1] / "frontend/src/storage/__golden__/preset_code.json"
)

# 슬롯 이름은 한글로 둔다. 이름이 ASCII 뿐이면 UTF-8 을 base64 로 접었다 펴는 구간이
# 검사되지 않는다 — 거기서 갈리면 한글 이름을 붙인 프리셋만 깨진다.
CASE_NAMES: tuple[tuple[Path, str, str], ...] = (
    (G0_RULESETS_PATH, "g0_pressure", "근접 압박"),
    (G0_RULESETS_PATH, "g0_kite", "원거리 견제"),
    (G0_RULESETS_PATH, "g0_cover", "엄폐 우선"),
    # 스탯 참조 우변(`{"stat": ...}`)과 인자 있는 좌변이 들어 있는 규칙표. 우변이 객체인
    # 갈래는 적 규칙표에만 있어 여기서 함께 싣는다 (F-2).
    (ENEMY_RULESETS_PATH, "ai_archer", "고블린 궁수의 논리"),
    (BENCHMARK_RULESETS_PATH, "focus_summoner", "소환사 우선"),
)


def build_case(name: str, ruleset: RuleSet) -> dict:
    """프리셋 하나의 기준값을 만든다.

    Args:
        name: 슬롯 이름.
        ruleset: 프리셋에 담을 규칙표.

    Returns:
        절·정규 JSON·공유 코드를 담은 한 케이스.
    """
    preset = RulePreset(name=name, ruleset=ruleset)
    payload = build_preset_payload(preset)
    return {
        "name": name,
        "ruleset_id": ruleset.ruleset_id,
        "payload": payload,
        "canonical_json": json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ),
        "code": export_preset_code(preset),
    }


def build_golden() -> dict:
    """기준값 전체를 만든다.

    Returns:
        접두어와 케이스 목록을 담은 딕셔너리.
    """
    cases = []
    for source_path, ruleset_id, name in CASE_NAMES:
        rulesets = load_rulesets(source_path)
        cases.append(build_case(name, rulesets[ruleset_id]))
    return {"prefix": PRESET_CODE_PREFIX, "cases": cases}


def main() -> None:
    """기준값을 파일로 쓴다."""
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(build_golden(), ensure_ascii=False, indent=2)
    GOLDEN_PATH.write_text(f"{text}\n", encoding="utf-8")
    print(f"wrote {GOLDEN_PATH}")


if __name__ == "__main__":
    main()
