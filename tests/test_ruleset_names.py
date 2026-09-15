"""화면에 내는 내력(규칙표)마다 이름이 있는가.

**목록이 `g0_cover` 스물다섯 줄이었다** (2026-09-15). 방 이름에서 고친 것과 같은 자리다 —
데이터에 이름 칸이 없으면 화면이 적을 것이 id 뿐이고, **없는 것은 안 보이는 것이 아니라
id 로 보인다.**

파서는 `label_ko` 를 필수로 안 본다(발행된 팩에 없을 수 있다). 그래서 저장소 파일은
여기서 본다 — 느슨한 파서와 엄한 게이트를 함께 둔다.

**적 내력(`enemies.json`)은 안 본다.** 그것은 화면의 「고르기」 목록에 안 서고, 이문록이
개체 이름으로 보여 준다.
"""

import json

from game.config import G0_RULESETS_PATH

SHOWN = ("g0_examples", "benchmark", "later_blocks")


def read_rulesets(name: str) -> list[dict]:
    """그 파일의 내력들을 읽는다.

    Args:
        name: 파일 이름(확장자 없이).

    Returns:
        내력 딕셔너리들.
    """
    path = G0_RULESETS_PATH.parent / f"{name}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return list(raw["rulesets"])


def test_every_shown_ruleset_has_a_name():
    """★ 이름 없는 내력은 화면에 id 로 나온다."""
    missing = [
        one["ruleset_id"]
        for name in SHOWN
        for one in read_rulesets(name)
        if not str(one.get("label_ko", "")).strip()
    ]
    assert missing == [], f"이름이 없다: {missing}"


def test_ruleset_names_do_not_collide():
    """★ 두 내력이 같은 이름이면 고르는 사람이 어느 쪽인지 알 수 없다."""
    seen: dict[str, str] = {}
    for name in SHOWN:
        for one in read_rulesets(name):
            label = str(one["label_ko"])
            clash = seen.get(label)
            assert clash is None, f"「{label}」 를 {clash} 와 {one['ruleset_id']} 가 함께 쓴다"
            seen[label] = str(one["ruleset_id"])
