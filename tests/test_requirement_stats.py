"""요구조건이 보는 소재 능력치 (설계/4_아이템 §6·§7, 결정 #51).

**두 가지가 빠져 있었고 증상이 같았다 — 「아무리 해도 못 낀다」.**

1. `initiative` 가 `BASE_STAT_KEYS` 에 없었다. 없는 축은 0 으로 읽히므로
   (`check_requirement`), 선공권을 요구하는 활 둘이 기본값 50 을 이미 갖고도 언제나
   「0 >= 50 거짓」이었다 — 원거리 업그레이드 줄이 통째로 죽어 있었다.
2. 배분한 능력치가 판정에 안 들어갔다. 시작값이 영원히 고정이라 **유물 일곱이 전부**
   장착 불가였다. #51 이 정해지기 전에 쓴 주석이 남아 있었고 그 사이 `attributes.py`
   가 구현됐다.

DB 없이 돈다 — 판정 규칙이 맞는지가 여기서 볼 것이다.
"""

import json

import pytest

from game.api.routes.items import BASE_STAT_KEYS, build_base_stats
from game.app.items.catalog import find_item, load_item_catalog
from game.app.items.requirements import check_requirements
from game.config import BALANCE_PATH, ITEMS_PATH


@pytest.fixture(scope="module")
def balance():
    return json.loads(BALANCE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog():
    return load_item_catalog(ITEMS_PATH)


def list_blocked(catalog, base):
    return sorted(
        item.catalog_id
        for item in catalog.values()
        if item.kind.name == "EQUIPMENT"
        and any(not check for check in check_requirements(item, base) if not check.is_met)
    )


def test_initiative_is_one_of_the_axes():
    """★ 빠져 있으면 그 축을 요구하는 장비가 영원히 못 낀다."""
    assert "initiative" in BASE_STAT_KEYS


def test_the_bows_are_equippable_at_the_start(balance, catalog):
    """★ 곡궁은 선공권 50 을 요구하고 시작값이 정확히 50 이다.

    「딱 맞으면 된다」가 성립해야 그 요구조건이 뜻을 갖는다. 0 으로 읽히던 때는
    3~5층 카이팅 업그레이드가 존재하지 않는 것과 같았다.
    """
    base = build_base_stats(balance)
    unmet = [
        check
        for check in check_requirements(find_item(catalog, "bow_recurve"), base)
        if not check.is_met
    ]
    assert not unmet, f"곡궁이 시작부터 막혔다: {unmet}"


def test_allocation_reaches_the_check(balance, catalog):
    """★ **배분이 안 들어가면 유물 일곱이 전부 죽는다.**

    붕락 도끼는 공격 18 을 요구하고 시작값은 12 다. 힘을 배분해도 판정이 안 움직이면
    그 장비는 카탈로그에만 있는 그림이 된다.
    """
    axe = find_item(catalog, "axe_collapse")
    bare = [c for c in check_requirements(axe, build_base_stats(balance)) if not c.is_met]
    strong = build_base_stats(balance, {"str": 6})
    grown = [c for c in check_requirements(axe, strong) if not c.is_met]
    assert bare, "시작부터 열리면 요구조건이 뜻이 없다"
    assert not grown, "힘을 배분했는데 판정이 안 움직였다"


def test_every_item_opens_with_some_allocation(balance, catalog):
    """★ 배분으로도 안 열리는 장비가 있으면 그것은 벽이지 요구조건이 아니다.

    힘8·민3·지6 은 17포인트이고 레벨 7~8 이면 닿는다.
    """
    base = build_base_stats(balance, {"str": 8, "dex": 3, "int": 6})
    assert list_blocked(catalog, base) == []


def test_equipment_bonuses_never_enter(balance):
    """★ 장비 보너스가 들어가면 착용 순서가 결과를 바꾼다 (§7).

    배분은 착용 순서를 안 타므로 넣어도 그 규율과 어긋나지 않는다 — 그 구분이
    이 함수가 배분만 받고 장비를 안 받는 이유다.
    """
    assert "equipped" not in build_base_stats.__code__.co_varnames


def test_an_empty_allocation_is_the_starting_line(balance):
    """★ 배분표가 없을 때 시작값 그대로여야 한다. 여기가 흔들리면 전부 흔들린다."""
    player = balance["player"]
    base = build_base_stats(balance, {})
    for key in BASE_STAT_KEYS:
        if key in player:
            assert base[key] == int(player[key]), key
