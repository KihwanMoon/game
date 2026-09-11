"""층 보상 선택 — 기획의 고리에서 빠져 있던 한 칸 (GDD §2.2, 2026-09-11).

「5층 이후에 보상이 안 들어온거같아」가 신고였다. 재 보니 **층과 무관하게** 서버는 같은
확률로 주고 있었고(층별 획득률 4.3~5.2%), 진짜로 없는 것은 다른 것이었다 — GDD 가
`클리어 → 보상 선택 → 규칙 편집` 으로 적어 둔 고리에서 **보상 선택이 제품에 안 붙어
있었다.** 굴림과 카탈로그는 있었지만 헤드리스 배치 러너만 그것을 썼다.

여기서 지키는 것은 넷이다.

1. **같은 티켓·같은 층이면 같은 후보다.** 서버가 되굴려 확인할 수 있어야 한다.
2. **없는 보상은 못 고른다.** 고른 것을 적어 보낼 자리는 있지만 만들어 보낼 자리는 없다.
3. **한 층에 한 번이다.** 바꿔 고를 수 있으면 그것은 선택이 아니라 설정이다.
4. **고른 층 다음부터 산다.** 같은 층에 소급되면 재시뮬이 브라우저와 다른 판을 돈다 (G3).
"""

import pytest

from game.app.simulation.floor_rewards import apply_floor_rewards, count_hp_gain
from game.app.simulation.state import Entity
from game.schemas.reward import (
    REWARD_CATALOG,
    REWARD_OPTION_COUNT,
    build_floor_offers,
    check_offer_holds,
    count_charge_bonus,
    count_floor_bonus,
    read_taken,
)

SEED = 12345


def build_entity(**axes):
    """검사용 개체 하나.

    Args:
        **axes: 덮어쓸 축들.

    Returns:
        개체.
    """
    fields = {
        "entity_id": "player",
        "kind_id": "player",
        "faction": "player",
        "position": (0, 0),
        "hp": 40,
        "hp_max": 40,
        "attack": 10,
        "defense": 3,
        "attack_range": 1,
        "initiative": 50,
        "regen_base": 0,
        **axes,
    }
    return Entity(**fields)


# ── 후보 ───────────────────────────────────────────────────────────────


def test_the_same_ticket_and_floor_always_offer_the_same_three():
    """★ **서버가 되굴려 확인한다.** 후보를 저장하지 않고도 「그 층의 후보였는가」에 답한다."""
    first = build_floor_offers(SEED, 3)
    assert first == build_floor_offers(SEED, 3)
    assert len(first) == REWARD_OPTION_COUNT


def test_each_floor_offers_its_own_set():
    """★ 층마다 축을 갈라야 앞 층의 굴림이 뒷 층 후보를 흔들지 않는다 (R5)."""
    seen = {
        tuple(one.reward_id for one in build_floor_offers(SEED, floor)) for floor in range(1, 9)
    }
    assert len(seen) > 1, "층이 달라도 같은 셋만 나온다"


def test_no_option_appears_twice_in_one_offer():
    """★ 같은 보상이 두 칸을 차지하면 고를 것이 둘로 준다."""
    for floor in range(1, 9):
        ids = [one.reward_id for one in build_floor_offers(SEED, floor)]
        assert len(ids) == len(set(ids)), floor


def test_a_reward_outside_the_offer_is_refused():
    """★ **없는 보상을 적어 보낼 자리가 없다** (설계/7 §4)."""
    offered = {one.reward_id for one in build_floor_offers(SEED, 2)}
    outside = next(one.reward_id for one in REWARD_CATALOG if one.reward_id not in offered)
    assert check_offer_holds(SEED, 2, outside) is False
    assert check_offer_holds(SEED, 2, next(iter(offered))) is True


# ── 합산 ───────────────────────────────────────────────────────────────


def test_a_reward_lives_from_the_next_floor():
    """★ **고른 층에는 소급되지 않는다.**

    보상은 층을 깬 뒤에 고르는 것이라, 같은 층의 전투에 얹히면 이미 끝난 판이 다르게
    재현된다 — 브라우저와 서버가 다른 결과를 낸다 (G3).
    """
    taken = {3: "affix_attack"}
    assert count_floor_bonus(taken, 3) == {}
    assert count_floor_bonus(taken, 4) == {"attack": 2}


def test_rewards_stack_across_floors():
    """★ 여러 층에서 같은 축을 고르면 쌓인다."""
    taken = {1: "affix_attack", 2: "affix_attack", 3: "module_core"}
    assert count_floor_bonus(taken, 9) == {"attack": 4, "cpu_budget": 3}


def test_charges_are_counted_apart_from_stats():
    """★ 얹는 자리가 다르다 — 스탯은 개체에, 충전은 주머니에."""
    taken = {1: "potion_pair"}
    assert count_floor_bonus(taken, 5) == {}
    assert count_charge_bonus(taken, 5) == {"POTION": 2}


def test_unknown_rewards_are_ignored():
    """★ 카탈로그에서 지운 보상을 가리키는 옛 티켓이 터지면 안 된다."""
    assert count_floor_bonus({1: "gone_forever"}, 5) == {}


def test_the_stored_shape_is_read_back():
    """★ 티켓의 절은 문자열 열쇠다 — 숫자로 읽어야 층 비교가 성립한다."""
    assert read_taken({"3": "module_slot"}) == {3: "module_slot"}
    assert read_taken(None) == {}
    assert read_taken({"3": 7}) == {}


# ── 개체에 얹기 ────────────────────────────────────────────────────────


def test_the_bonus_lands_on_the_entity():
    """★ 두 코어가 같은 자리에서 같은 만큼 얹는다 (G3)."""
    entity = build_entity()
    apply_floor_rewards(entity, {1: "affix_attack", 2: "module_core"}, 3)
    assert entity.attack == 12
    assert entity.cpu_budget == 3


def test_vitality_raises_the_body_too():
    """★ **최대치만 늘리면 고른 순간에 아무 일도 안 일어난다.**"""
    entity = build_entity(hp=40, hp_max=40)
    apply_floor_rewards(entity, {1: "affix_vitality"}, 2)
    assert entity.hp_max == 50
    assert entity.hp == 50


def test_a_potion_reward_lands_in_the_pouch():
    """★ 충전은 주머니에 얹는다 — 스탯 자리에 넣으면 못 마시는 숫자가 된다."""
    entity = build_entity()
    entity.consumables["POTION"] = 1
    apply_floor_rewards(entity, {1: "potion_pair"}, 2)
    assert entity.consumables["POTION"] == 3


def test_the_carried_hp_gains_only_what_was_just_chosen():
    """★ 인계 HP 에 더할 값은 **이번 층 경계에서 새로 얻은 것**뿐이다."""
    taken = {1: "affix_vitality", 2: "affix_vitality"}
    assert count_hp_gain(taken, 3, 2) == 10
    assert count_hp_gain(taken, 2, 2) == 0


@pytest.mark.parametrize("floor", [1, 4, 8])
def test_every_offer_is_a_catalog_entry(floor):
    """★ 화면이 그릴 이름·수치가 카탈로그에서 온다 — 굴림이 값을 지어내지 않는다."""
    for option in build_floor_offers(SEED, floor):
        assert option in REWARD_CATALOG
