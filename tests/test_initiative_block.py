"""선공을 규칙표가 읽는다 (블록 v12, 2026-09-11 실측).

**오래 화면에만 있던 값이었다.** 선공은 틱 안 행동 순서를 정하는데 규칙표가 못 읽어서,
신발을 바꿔도 규칙을 다시 짤 이유가 안 생겼다 — 아이템이 움직일 수 있는 폭(44~66)에서
승률 변화가 **0** 이었다 (200런 × 5조건). 사거리가 이미 그런 축이고(무기를 바꾸면 같은
규칙표의 뜻이 달라진다), 선공만 그 밖에 있었다.

둘을 함께 연다 — 하나만 있으면 비교가 성립하지 않는다.

    내 선공      rhs_stats.initiative     (스탯 참조)
    대상 선공    target_initiative        (인지, 셀렉터가 고른 대상에서 읽는다)

**주의: 지금 적 표에서는 갈림이 얕다.** 근접으로 달려드는 적은 대부분 플레이어보다
빠르다(돌진형 60 · 정예 65 · 늑대 78 vs 50). 느린 근접은 방패 골렘(20)·돌문지기(45)인데
둘 다 9~10층에 산다 — 얕은 층에서는 「빠른 적에게만」이 사실상 「늘」이 된다. 축은
열렸고, 그 축이 값을 하게 하는 것은 **몬스터 표의 몫**이다.
"""

import pytest

from game.app.rules.condition import evaluate_condition
from game.app.services.run_battle import build_engine, load_balance
from game.config import BALANCE_PATH, BLOCKS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import Condition, StatRef, Term

PLAYER = "player"


@pytest.fixture(scope="module")
def parts():
    templates = {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}
    return {
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "rooms": templates,
    }


def build_probe(parts, target_initiative):
    """플레이어와 선공을 정한 적 하나를 세운다.

    Args:
        parts: 밸런스·카탈로그·방.
        target_initiative: 적에게 줄 선공.

    Returns:
        (엔진, 플레이어, 적).
    """
    engine = build_engine(parts["rooms"]["open_field"], parts["balance"], seed=3)
    player = engine.state.entities[PLAYER]
    player.initiative = 50
    enemy = engine.state.list_hostiles(player)[0]
    enemy.initiative = target_initiative
    return engine, player, enemy


def check_faster(parts, engine, player, enemy):
    """`대상 선공 > 내 선공` 이 참인가.

    Args:
        parts: 밸런스·카탈로그·방.
        engine: 엔진.
        player: 행위자.
        enemy: 셀렉터가 고른 대상.

    Returns:
        (참·거짓, 화면에 적힐 문장).
    """
    condition = Condition(
        op="SINGLE",
        terms=(Term("target_initiative", ">", StatRef("initiative"), None),),
    )
    return evaluate_condition(
        condition,
        engine.build_perceptions()[PLAYER],
        enemy,
        parts["catalog"],
        0,
        actor=player,
    )


def test_a_faster_enemy_reads_true(parts):
    """★ 나보다 빠른 적이면 참이다 — 「붙는 순간 먼저 맞는다」를 규칙표가 묻는다."""
    engine, player, enemy = build_probe(parts, 60)
    fired, _expr = check_faster(parts, engine, player, enemy)
    assert fired is True


def test_a_slower_enemy_reads_false(parts):
    """★ 느린 적이면 거짓이다 — 방패 골렘(20)·돌문지기(45)가 그 자리다."""
    engine, player, enemy = build_probe(parts, 20)
    fired, _expr = check_faster(parts, engine, player, enemy)
    assert fired is False


def test_a_tie_reads_false(parts):
    """★ 동률은 거짓이다. 순서가 무작위로 갈리는 자리라 「먼저 친다」고 말할 수 없다."""
    engine, player, enemy = build_probe(parts, 50)
    fired, _expr = check_faster(parts, engine, player, enemy)
    assert fired is False


def test_the_sentence_carries_both_numbers(parts):
    """★ **항별 실측값을 병기한다** (GDD §8.2, P1).

    참·거짓만 내보내면 「왜 안 떴지」에 답할 수 없다 — 화면이 `대상 선공(60) > 선공(50)`
    이라 적어야 규칙을 고칠 자리가 보인다.
    """
    engine, player, enemy = build_probe(parts, 60)
    _fired, expr = check_faster(parts, engine, player, enemy)
    assert "60" in expr and "50" in expr


def test_the_block_is_in_the_catalog(parts):
    """★ 카탈로그에 없으면 편집기가 그 블록을 못 내놓는다 — 있어도 아무도 못 찾는다."""
    assert "target_initiative" in parts["catalog"].perceptions
    assert "initiative" in parts["catalog"].rhs_stats


def test_a_ruleset_ships_that_uses_it(parts):
    """★ **쓰는 예시가 하나는 있어야 한다.**

    블록만 열고 예시가 없으면 아무도 그 축을 안 쓴다 — 사거리가 예시 하나로 살아난
    자리와 같다 (`v8_skill_identity`).
    """
    from game.config import LATER_BLOCKS_RULESETS_PATH
    from game.schemas.ruleset import load_rulesets

    rulesets = load_rulesets(LATER_BLOCKS_RULESETS_PATH)
    found = [
        one
        for one in rulesets.values()
        for rule in one.rules
        for term in rule.conditions.terms
        if term.lhs == "target_initiative"
    ]
    assert found, "선공을 읽는 예시 규칙표가 없다"
