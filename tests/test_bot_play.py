"""봇이 판을 고르는 방식.

두 가지를 지킨다. **못하는 봇이 실제로 못해야 하고**(실력이 규칙표에 반영돼야 한다),
**깬 층을 빠짐없이 청구해야 한다**(마지막 층만 청구하면 중간 층 정산이 통째로 빠진다).
"""

import json

from game.app.bots.play import build_bot_handle, degrade_ruleset, resolve_claim_floors
from game.config import BENCHMARK_RULESETS_PATH


def build_raw(count):
    """규칙 `count` 줄짜리 원본을 짠다.

    Args:
        count: 줄 수.

    Returns:
        규칙표 원본.
    """
    return {
        "ruleset_id": "probe",
        "version": 1,
        "rules": [{"priority": index + 1, "action": "ATTACK"} for index in range(count)],
    }


def test_full_skill_keeps_every_rule():
    """실력 100 은 규칙표를 그대로 쓴다."""
    assert len(degrade_ruleset(build_raw(6), 100)["rules"]) == 6


def test_low_skill_drops_the_lower_rows():
    """★ 실력이 낮으면 아랫줄부터 사라진다 — 「표를 아직 다 못 짠 사람」이다.

    윗줄을 덜면 표가 뜻을 잃어 「못하는 것」이 아니라 「망가진 것」이 된다.
    """
    kept = degrade_ruleset(build_raw(10), 30)["rules"]
    assert [rule["priority"] for rule in kept] == [1, 2, 3]


def test_one_rule_always_survives():
    """★ 전부 덜지 않는다 — 폴백만 남으면 열 봇이 같은 판을 돈다."""
    assert len(degrade_ruleset(build_raw(2), 1)["rules"]) == 1


def test_degrading_does_not_touch_the_original():
    """원본을 건드리면 다음 봇이 이미 깎인 표를 물려받는다."""
    raw = build_raw(8)
    degrade_ruleset(raw, 25)
    assert len(raw["rules"]) == 8


def test_every_persona_ruleset_exists():
    """★ 성격이 가리키는 규칙표가 실제로 있다 — 없으면 그 봇은 영영 안 논다."""
    from game.app.bots.play import list_persona_specs
    from game.config import G0_RULESETS_PATH

    known = set()
    for path in (BENCHMARK_RULESETS_PATH, G0_RULESETS_PATH):
        raw = json.loads(path.read_text(encoding="utf-8"))
        known.update(item["ruleset_id"] for item in raw["rulesets"])
    for _handle, ruleset_id, _cadence, _skill in list_persona_specs():
        assert ruleset_id in known, ruleset_id


def test_degrading_a_real_ruleset_still_parses():
    """★ 깎은 표가 여전히 규칙표다 — 파싱이 깨지면 그 봇은 폴백으로만 논다."""
    from game.schemas.ruleset import parse_ruleset

    raw = json.loads(BENCHMARK_RULESETS_PATH.read_text(encoding="utf-8"))["rulesets"][0]
    parsed = parse_ruleset(degrade_ruleset(raw, 40))
    assert len(parsed.rules) >= 1


def test_claims_cover_every_cleared_floor():
    """★ 깬 층을 빠짐없이 청구한다 — 마지막 층만 청구하면 중간 정산이 사라진다."""
    assert resolve_claim_floors(1, 15, 5) == (1, 2, 3)
    assert resolve_claim_floors(3, 10, 5) == (3, 4)


def test_a_partial_floor_is_not_claimed():
    """★ 덜 깬 층은 청구하지 않는다 — 하면 서버가 반려하거나 거짓이 확정된다."""
    assert resolve_claim_floors(1, 4, 5) == ()
    assert resolve_claim_floors(1, 9, 5) == (1,)


def test_an_old_ticket_claims_nothing():
    """층 개념이 없던 티켓은 층을 청구하지 않는다 — 0 이 「하강 전체」다."""
    assert resolve_claim_floors(1, 9, 0) == ()


def test_handles_are_numbered_from_one():
    """사람이 세는 방식으로 적는다."""
    assert build_bot_handle(0) == "bot1"
    assert build_bot_handle(9) == "bot10"
