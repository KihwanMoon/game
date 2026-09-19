"""출고되는 규칙표가 전부 성립하는가 — 적과 예시 양쪽.

**게이트에 이 구멍이 있었다** (2026-09-19). 규칙표 파일 넷을 아무도 통째로 검증하지
않아서, `later_blocks.json` 의 ``v12_who_strikes_first`` 가 **없는 행동**
(``MOVE_TO_ENEMY``)을 4번 줄에 달고 살아 있었다. 실행기에 갈래가 없어 그 줄은
400판에서 3693번 「발동」하고 **아무 일도 안 했다** — 오류도 기록도 안 남는다.

예시 규칙표는 화면이 그대로 펴서 보여 주는 것이라(``test_ruleset_names`` 의 ``SHOWN``)
고장 난 예시는 「이걸로 뭘 하지」에 틀린 답을 준다.

**예산까지 본다.** 적의 ``cpu_budget``·``rule_slots`` 는 시뮬레이터가 강제하지 않는다 —
``validate_ruleset`` 만 보고 그것은 플레이어 제출에만 걸린다. 지켜 주는 것이 없으면
조용히 어겨지므로 여기서 지킨다.
"""

import json

import pytest

from game.app.rules.validator import validate_ruleset
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    LATER_BLOCKS_RULESETS_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.ruleset import load_rulesets

PLAYER_SETS = (G0_RULESETS_PATH, BENCHMARK_RULESETS_PATH, LATER_BLOCKS_RULESETS_PATH)


@pytest.fixture(name="catalog")
def fixture_catalog():
    """블록 카탈로그.

    Returns:
        동결된 카탈로그.
    """
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(name="balance")
def fixture_balance() -> dict:
    """밸런스 원문.

    Returns:
        balance.json 내용.
    """
    return json.loads(BALANCE_PATH.read_text(encoding="utf-8"))


def test_enemy_rulesets_fit_their_kind(catalog, balance: dict) -> None:
    """적 규칙표가 그 종의 예산 안에 든다."""
    sets = load_rulesets(ENEMY_RULESETS_PATH)
    broken: dict[str, list[str]] = {}
    for row in balance["enemies"]:
        ruleset = sets.get(row["ruleset_id"])
        assert ruleset is not None, f"{row['id']} 가 없는 규칙표 {row['ruleset_id']} 를 가리킨다"
        problems = validate_ruleset(ruleset, catalog, row["cpu_budget"], row["rule_slots"])
        if problems:
            broken[row["id"]] = problems
    assert broken == {}


def test_every_enemy_ruleset_is_used(balance: dict) -> None:
    """아무 종도 안 쓰는 적 규칙표는 없다.

    남아 있으면 고칠 때 **아무 데도 안 닿는 것을 고치게 된다.**
    """
    sets = load_rulesets(ENEMY_RULESETS_PATH)
    used = {row["ruleset_id"] for row in balance["enemies"]}
    assert sorted(set(sets) - used) == []


def test_shipped_player_rulesets_are_valid(catalog, balance: dict) -> None:
    """화면이 보여 주는 예시 규칙표가 전부 성립한다."""
    player = balance["player"]
    broken: dict[str, list[str]] = {}
    for path in PLAYER_SETS:
        for name, ruleset in load_rulesets(path).items():
            problems = validate_ruleset(
                ruleset, catalog, player["cpu_budget"], player["rule_slots"]
            )
            if problems:
                broken[name] = problems
    assert broken == {}
