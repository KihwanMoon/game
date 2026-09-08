"""자동 정비의 저울 (설계/4_아이템, 결정 #34).

**정비는 사람이 안 고른 상실을 만들면 안 된다.** 저울이 못 보는 것이 셋 있었고, 셋 다
같은 방식으로 샜다 — 안 보이는 것은 0 점이고, 0 점은 「없는 것」과 구별되지 않는다.

1. `grants_skill` 을 저울이 안 봤다. 실측으로 오늘 카탈로그에 스킬을 잃는 자동 교체가
   **16건** 있었다 — 대검(AREA_ATTACK) → 단층 검이 ATTACK 저울에서 12점 앞선다.
2. `can_equip` 이 `True` 로 박혀 있었다. 손으로 끼우면 4xx 로 거절되는 일곱 종을 자동
   정비가 그냥 끼웠고, 브라우저 미리보기는 그것을 건너뛰어 **서로 다른 개수**를 냈다.
3. `cpu_budget`·`potion_slots`·`scroll_slots` 에 무게가 없었다. 장갑 세 등급이 전부
   0 점이었고, 봉인 풀이 이미 파는 옵션이 다음 판에 공짜로 버려졌다.

DB 없이 돈다.
"""

import json

import pytest

from game.app.bots.upgrade import (
    GEAR_PRIORITY_WEIGHTS,
    UPGRADE_MARGIN,
    GearItem,
    check_keeps_skill,
    compute_weighted_score,
)
from game.app.items.catalog import find_item, load_item_catalog
from game.config import BALANCE_PATH, ITEMS_PATH


@pytest.fixture(scope="module")
def base_stats():
    player = json.loads(BALANCE_PATH.read_text(encoding="utf-8"))["player"]
    return {key: int(value) for key, value in player.items() if isinstance(value, int)}


@pytest.fixture(scope="module")
def catalog():
    return load_item_catalog(ITEMS_PATH)


def build_gear(entry, can_equip=True):
    return GearItem(
        item_id=0,
        slot=entry.slot.value if entry.slot is not None else "",
        can_equip=can_equip,
        is_broken=False,
        hands=entry.hands.value if entry.hands is not None else "",
        affixes=tuple((a.stat, a.flat, a.percent) for a in entry.affixes),
        attack_range=entry.attack_range or 0,
        grants_skill=entry.grants_skill or "",
    )


# ── 스킬을 잃는 교체 ─────────────────────────────────────────────────────


def test_a_swap_that_drops_a_skill_is_refused(catalog):
    """★ **이것이 16건이었다.** 대검 → 단층 검이 ATTACK 저울에서 12점 앞선다.

    정비를 켜 둔 사람은 출격 버튼을 누른 그 판에 `USE_SKILL[AREA_ATTACK]` 이 「불가」로
    떨어진 것을 본다 — 규칙표를 안 고쳤는데 뜻이 바뀌었으므로 P1 위반이다.
    """
    great = build_gear(find_item(catalog, "sword_great"))
    edge = build_gear(find_item(catalog, "sword_edge"))
    assert great.grants_skill == "AREA_ATTACK"
    assert edge.grants_skill == ""
    assert not check_keeps_skill(great, edge)


def test_the_same_skill_still_upgrades(catalog):
    """★ 막기만 하면 그 줄이 영영 못 오른다. 같은 것을 여는 후보는 통과해야 한다."""
    great = build_gear(find_item(catalog, "sword_great"))
    collapse = build_gear(find_item(catalog, "axe_collapse"))
    assert collapse.grants_skill == "AREA_ATTACK"
    assert check_keeps_skill(great, collapse)


def test_gaining_a_skill_is_fine(catalog):
    """★ 지금 아무것도 안 열면 잃을 것도 없다."""
    plain = build_gear(find_item(catalog, "sword_short"))
    great = build_gear(find_item(catalog, "sword_great"))
    assert check_keeps_skill(plain, great)


def test_the_picker_never_chooses_a_skill_loss(catalog, base_stats):
    """★ **선택 함수를 직접 돌린다.** 판정 함수만 보면 부르는 쪽이 안 부를 때를 못 잡는다.

    스킬을 여는 장비를 하나씩 낀 채 가방에 전량을 넣고, 고른 짝이 스킬을 잃는지 본다.
    막기 전에는 여기서 16건이 나왔다.
    """
    from game.app.bots.upgrade import find_upgrades_by_weights

    entries = [e for e in catalog.values() if e.kind.name == "EQUIPMENT"]
    bag = tuple(build_gear(entry) for entry in entries)
    losses = []
    for weights in GEAR_PRIORITY_WEIGHTS.values():
        for entry in entries:
            if not entry.grants_skill:
                continue
            worn = (build_gear(entry),)
            for current, candidate in find_upgrades_by_weights(bag, worn, weights, base_stats):
                if not check_keeps_skill(current, candidate):
                    losses.append((current.grants_skill, candidate.grants_skill))
    assert losses == [], f"정비가 스킬을 잃는 교체를 골랐다: {losses}"


# ── 저울이 보는 축 ───────────────────────────────────────────────────────


def test_the_three_glove_grades_differ(catalog, base_stats):
    """★ 전에는 셋 다 0 점이었다 — CPU 가 저울에 없어서다.

    CPU 는 규칙 에디터 전체가 그 위에 선 축인데, 값이 없으면 「연산 코어 +3」과
    「기관 회로 +6」이 같은 물건이 된다.
    """
    weights = GEAR_PRIORITY_WEIGHTS["DEFENSE"]
    scores = [
        compute_weighted_score(build_gear(find_item(catalog, key)), weights, base_stats)
        for key in ("gloves_core", "gloves_lattice", "gloves_engine")
    ]
    assert len(set(scores)) == 3, f"장갑 세 등급이 안 갈린다: {scores}"


def test_a_slot_affix_alone_cannot_move_a_weapon(base_stats):
    """★ 무게를 준 이유와 **작게** 준 이유가 함께 여기 있다.

    0 이면 봉인으로 산 옵션이 다음 판에 공짜로 버려진다. 크면 「물약 칸 +1」 하나로
    무기가 바뀐다 — 옛 주석이 0 으로 둔 이유가 그것이었다. 칸 하나는 여유폭을 혼자
    못 넘어야 한다.
    """
    weights = GEAR_PRIORITY_WEIGHTS["ATTACK"]
    one_slot = GearItem(
        item_id=0,
        slot="WEAPON_MAIN",
        can_equip=True,
        is_broken=False,
        hands="ONE",
        affixes=(("potion_slots", 1, 0),),
        attack_range=0,
    )
    score = compute_weighted_score(one_slot, weights, base_stats)
    assert score > 0, "0 이면 봉인으로 산 옵션이 공짜로 버려진다"
    assert score < UPGRADE_MARGIN, "칸 하나가 여유폭을 넘으면 그것만으로 무기가 바뀐다"


def test_the_sealed_pool_axes_are_all_weighed():
    """★ 봉인 풀이 파는 축은 전부 저울에 있어야 한다.

    돈을 내고 연 옵션을 저울이 0 으로 보면, 그 아이템이 아무 +6 짜리와 맞바뀐다.
    """
    from game.app.store.items import DEFAULT_AFFIX_POOL

    sold = {row[0] for row in DEFAULT_AFFIX_POOL}
    for name, weights in GEAR_PRIORITY_WEIGHTS.items():
        missing = sorted(sold - set(weights))
        assert not missing, f"{name} 저울이 모르는데 봉인 풀이 파는 축: {missing}"
