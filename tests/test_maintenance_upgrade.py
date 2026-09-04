"""정비 규칙의 「더 좋게 만든다」 셋 (설계/4_아이템 §5).

DB 를 안 띄운다 — 여기서 보는 것은 **판단**이지 저장이 아니다.

지키는 것은 셋이다.

1. **저울이 한 벌이다.** 장비 교체가 봇과 같은 점수 함수를 쓴다 — 두 벌이면 같은 장비가
   봇 화면과 정비 미리보기에서 다른 값을 갖는다.
2. **우선순위가 실제로 갈린다.** 공격을 고르면 공격 장비를, 방어를 고르면 방어 장비를
   고른다. 안 갈리면 인자가 있으나 마나다.
3. **어휘가 닫혀 있다.** 모르는 행동·모르는 인자는 저장 전에 막힌다 — 오타가 조용히
   「안 함」이 되면 켰다고 믿은 정비가 안 돈다.
"""

from game.app.bots.upgrade import (
    GEAR_PRIORITY_WEIGHTS,
    UPGRADE_MARGIN,
    GearItem,
    compute_weighted_score,
    find_upgrades_by_weights,
)
from game.app.store.maintenance import (
    ACTION_ARGUMENTS,
    ACTION_UNSEAL,
    ACTION_UPGRADE_CONSUMABLE,
    ACTION_UPGRADE_GEAR,
    GEAR_PRIORITY_CHOICES,
    MAINTENANCE_ACTIONS,
    MaintenanceRow,
    check_rows,
)

BASE_STATS = {"attack": 10, "defense": 10, "hp_max": 100, "initiative": 10}


def build_gear(item_id, slot="HEAD", affixes=(), attack_range=0, hands=""):
    """검사용 장비 하나를 만든다.

    Args:
        item_id: 아이템 id.
        slot: 자리.
        affixes: (스탯, 고정, 퍼센트) 들.
        attack_range: 무기가 정하는 사거리.
        hands: 손 수.

    Returns:
        점수를 매길 수 있는 절.
    """
    return GearItem(
        item_id=item_id,
        slot=slot,
        can_equip=True,
        is_broken=False,
        hands=hands,
        affixes=tuple(affixes),
        attack_range=attack_range,
    )


def test_the_two_priorities_actually_disagree():
    """★ 우선순위가 안 갈리면 인자가 있으나 마나다.

    공격 저울은 공격 장비를, 방어 저울은 방어 장비를 높게 봐야 한다.
    """
    striker = build_gear(1, affixes=(("attack", 6, 0),))
    turtle = build_gear(2, affixes=(("defense", 6, 0),))

    attack_weights = GEAR_PRIORITY_WEIGHTS["ATTACK"]
    defense_weights = GEAR_PRIORITY_WEIGHTS["DEFENSE"]

    assert compute_weighted_score(striker, attack_weights, BASE_STATS) > compute_weighted_score(
        turtle, attack_weights, BASE_STATS
    )
    assert compute_weighted_score(turtle, defense_weights, BASE_STATS) > compute_weighted_score(
        striker, defense_weights, BASE_STATS
    )


def test_range_outweighs_raw_attack():
    """★ 사거리 한 칸이 무겁다.

    기본 사거리가 1 이라 +1 은 **닿는 거리를 두 배로** 만든다 — 그것이 곧 「맞지 않고
    때린다」의 성립 여부이고, 공격 몇 점과 맞바꿀 값이다 (`bots/upgrade`).
    """
    weights = GEAR_PRIORITY_WEIGHTS["ATTACK"]
    bow = build_gear(1, slot="WEAPON_MAIN", attack_range=1)
    blade = build_gear(2, slot="WEAPON_MAIN", affixes=(("attack", 1, 0),))
    assert compute_weighted_score(bow, weights, BASE_STATS) > compute_weighted_score(
        blade, weights, BASE_STATS
    )


def test_a_narrow_win_does_not_swap():
    """★ 근소한 차이로는 안 바꾼다.

    벗은 것은 가방으로 가고, 가방에 있는 것은 죽을 때 삭제된다 (결정 #34). 1점 이득을
    보려고 바꾸면 그 1점보다 큰 것을 잃을 수 있다.
    """
    weights = GEAR_PRIORITY_WEIGHTS["DEFENSE"]
    worn = (build_gear(1, affixes=(("defense", 5, 0),)),)
    barely = (build_gear(2, affixes=(("defense", 6, 0),)),)
    assert find_upgrades_by_weights(barely, worn, weights, BASE_STATS) == ()

    clearly = (build_gear(3, affixes=(("defense", 5 + UPGRADE_MARGIN, 0),)),)
    swaps = find_upgrades_by_weights(clearly, worn, weights, BASE_STATS)
    assert len(swaps) == 1
    assert swaps[0][1].item_id == 3


def test_two_handed_slots_stay_untouched():
    """★ 양손 자리는 두 칸을 함께 보는 판단이라 한 칸씩 보는 규칙으로는 틀린다."""
    weights = GEAR_PRIORITY_WEIGHTS["ATTACK"]
    worn = (build_gear(1, slot="WEAPON_MAIN", affixes=(("attack", 1, 0),)),)
    bag = (build_gear(2, slot="WEAPON_MAIN", affixes=(("attack", 40, 0),)),)
    assert find_upgrades_by_weights(bag, worn, weights, BASE_STATS) == ()


def test_the_consumable_score_puts_charges_first():
    """★ 충전 용량이 먼저다 — 「몇 번 쓸 수 있나」가 소모품의 값 그 자체다 (§5)."""
    from game.api.maintenance_upgrade import compute_consumable_score

    class Entry:
        def __init__(self, charges, affixes=()):
            self.charges = charges
            self.affixes = affixes

    class Affix:
        def __init__(self, flat):
            self.flat = flat
            self.percent = 0

    # 충전이 적으면 접사가 아무리 커도 진다.
    assert compute_consumable_score(Entry(7)) > compute_consumable_score(Entry(2, (Affix(99),)))
    # 충전이 같으면 접사가 끊는다.
    assert compute_consumable_score(Entry(4, (Affix(3),))) > compute_consumable_score(Entry(4))


def test_the_new_actions_are_in_the_closed_vocabulary():
    """★ 닫힌 어휘다 — 모르는 행동이 조용히 무시되면 켰다고 믿은 정비가 안 돈다."""
    for action in (ACTION_UNSEAL, ACTION_UPGRADE_GEAR, ACTION_UPGRADE_CONSUMABLE):
        assert action in MAINTENANCE_ACTIONS


def test_the_gear_swap_argument_is_checked():
    """★ 교체 규칙의 인자도 등급과 같은 규율로 검사한다."""
    assert ACTION_ARGUMENTS[ACTION_UPGRADE_GEAR] == GEAR_PRIORITY_CHOICES
    assert check_rows((MaintenanceRow(ACTION_UPGRADE_GEAR, "ATTACK"),)) == ""
    assert "받을 수 없는 인자" in check_rows((MaintenanceRow(ACTION_UPGRADE_GEAR, "SPEED"),))
    # 빈 인자도 막는다 — 서버가 무엇으로 고를지 정할 수 없다.
    assert check_rows((MaintenanceRow(ACTION_UPGRADE_GEAR, ""),)) != ""


def test_the_argument_free_actions_reject_arguments():
    """★ 인자를 안 받는 행동에 인자가 붙으면 막는다 — 뜻 없이 저장되면 안 된다."""
    assert check_rows((MaintenanceRow(ACTION_UNSEAL, ""),)) == ""
    assert "인자를 받지 않는다" in check_rows((MaintenanceRow(ACTION_UNSEAL, "COMMON"),))
    assert check_rows((MaintenanceRow(ACTION_UPGRADE_CONSUMABLE, ""),)) == ""


def test_the_gear_scale_lives_in_one_file():
    """★ 저울이 파일 하나다 — 파이썬과 브라우저가 그것을 각자 직접 읽는다.

    여기 상수로 박아 두면 미리보기가 「2개 교체」라 적고 서버는 3개를 바꾸는 일이
    생기고, 그때 어느 쪽이 맞는지 물으면 답할 사람이 없다. 사본을 두지 않는 것이 이
    저장소의 규율이다 (CLAUDE.md 의 `@resources`).
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "game/resources/balance/gear_priority.json"
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert raw["margin"] == UPGRADE_MARGIN
    assert set(GEAR_PRIORITY_WEIGHTS) == set(raw["priorities"])
    for name, table in raw["priorities"].items():
        numbers = {key: value for key, value in table.items() if isinstance(value, int)}
        assert GEAR_PRIORITY_WEIGHTS[name] == numbers


def test_the_scale_is_not_sealed_content():
    """★ 봉인된 자산이 아니다 — 고쳐도 지나간 판의 재현성이 안 깨진다.

    전투 시뮬레이션에 안 들어가는 값이라 `core_version` 에 들어가면 안 된다. 들어가면
    저울을 만질 때마다 랭킹 시즌이 갈리고, 그것은 이 값이 하는 일과 무관한 대가다.
    """
    from game.app.store.content_draft import DRAFT_ASSETS

    assert "gear_priority" not in DRAFT_ASSETS


def test_the_unseal_rule_looks_at_the_bag_too():
    """★ 착용만 열면 가방에서 굴러 나온 유물이 영원히 안 열린다.

    처음에는 착용한 것만 봤다 — 안 쓰는 물건에 돈을 쓰지 않게 하려는 것이었는데, 그러면
    **열어 봐야 갈아 낄 만한지 알 수 있는** 물건을 영원히 못 연다. 「봉인 해제 → 장비
    교체」 순으로 두면 그 둘이 이어진다.

    소스를 본다 — DB 없이 확인할 수 있는 것은 「가방을 보기는 하는가」까지다.
    """
    import inspect

    from game.api.maintenance_upgrade import find_cheapest_sealed

    source = inspect.getsource(find_cheapest_sealed)
    assert "list_equipment" in source
    assert "list_inventory" in source


def test_the_bot_upkeep_earns_before_it_spends():
    """★ 파는 행이 쓰는 행보다 위다 — 아래면 판 돈을 이번 정비에서 못 쓴다.

    화면의 검증이 사람에게 일러 주는 바로 그 배치다. 봇이 그 경고를 달고 도는 규칙표를
    쓰면, 사람에게는 「고쳐라」 하고 봇은 안 고친 것을 쓰는 셈이 된다.
    """
    from game.app.bots.upkeep import build_bot_upkeep
    from game.app.store.maintenance import (
        ACTION_REFILL,
        ACTION_REPAIR,
        ACTION_SELL_STOCK,
        ACTION_UNSEAL,
    )

    actions = [row.action for row in build_bot_upkeep("g0_kite")]
    sells = actions.index(ACTION_SELL_STOCK)
    for spender in (ACTION_UNSEAL, ACTION_REPAIR, ACTION_REFILL):
        assert sells < actions.index(spender), f"{spender} 가 파는 행보다 위다"


def test_the_bot_upkeep_swaps_before_it_discards():
    """★ 버리기가 맨 끝이다 — 앞에 두면 갈아 낄 후보를 먼저 버린다."""
    from game.app.bots.upkeep import build_bot_upkeep
    from game.app.store.maintenance import ACTION_DISCARD, ACTION_UPGRADE_GEAR

    actions = [row.action for row in build_bot_upkeep("g0_kite")]
    assert actions.index(ACTION_UPGRADE_GEAR) < actions.index(ACTION_DISCARD)
    assert actions[-1] == ACTION_DISCARD


def test_the_bot_upkeep_puts_swaps_first():
    """★ 장비 교체·소모품 교체가 맨 앞이다 — 뒤의 행들이 그 결과를 먹고 산다.

    교체가 가방으로 내려보낸 것을 팔고, 판 돈으로 봉인을 연다.
    """
    from game.app.bots.upkeep import build_bot_upkeep
    from game.app.store.maintenance import ACTION_UPGRADE_CONSUMABLE, ACTION_UPGRADE_GEAR

    actions = [row.action for row in build_bot_upkeep("g0_kite")]
    assert actions[0] == ACTION_UPGRADE_GEAR
    assert actions[1] == ACTION_UPGRADE_CONSUMABLE


def test_the_bot_upkeep_passes_the_server_check():
    """★ 서버가 저장을 거절하면 봇은 정비 없이 돈다 — 어휘·상한·인자를 다 지켜야 한다."""
    from game.app.bots.upkeep import build_bot_upkeep

    for ruleset_id in ("g0_kite", "sniper", "g0_pressure", "unknown_ruleset"):
        assert check_rows(build_bot_upkeep(ruleset_id)) == ""


def test_the_persona_picks_the_priority():
    """★ 성격이 우선순위를 고른다 — 열이 같은 몸을 가지면 규칙표를 갈라 둔 뜻이 준다."""
    from game.app.bots.upkeep import build_bot_upkeep

    assert build_bot_upkeep("g0_pressure")[0].grade == "DEFENSE"
    assert build_bot_upkeep("sniper")[0].grade == "ATTACK"


def test_the_bot_buys_an_upgrade_before_it_buys_junk():
    """★ 봇이 자기 장비와 견주고 산다.

    예전에는 **가장 싼 것**을 샀다 — 6시간 넘게 안 팔린 것 중 제일 싼 것이라 정의상 가장
    값 안 나가는 물건이고, 가방에 쌓였다가 버려졌다. 사실상 화폐 소각기였다.

    싼 것 사기를 없애지는 않았다: 봇이 사 주는 것 자체가 사람이 드롭을 팔 곳이다. 둘을
    **순서**로 둔다 — 쓸모를 먼저 보고, 없으면 유동성을 낸다.
    """
    from game.app.bots.shopping import Listing, find_purchase

    worn = {"HEAD": build_gear(1, affixes=(("defense", 2, 0),))}
    weights = GEAR_PRIORITY_WEIGHTS["DEFENSE"]
    # 시장 하한(3건)을 넘겨야 산다 — 그 아래면 아무것도 안 산다.
    listings = (
        Listing(1, 10, False, 100),
        Listing(2, 500, False, 100, slot="HEAD", affixes=(("defense", 20, 0),)),
        Listing(3, 20, False, 100),
        Listing(4, 30, False, 100),
        Listing(5, 40, False, 100),
    )
    assert find_purchase(listings, 10000, worn, weights, BASE_STATS) == 2

    # 나은 것이 없으면 예전처럼 가장 싼 것을 산다.
    plain = tuple(Listing(one, one * 10, False, 100) for one in range(1, 6))
    assert find_purchase(plain, 10000, worn, weights, BASE_STATS) == 1


def test_the_bot_leaves_the_market_alone_when_it_is_thin():
    """★ 넘치는 것만 산다 — 견줌을 붙여도 이 규율은 그대로다.

    사람이 열어 봤을 때 아무것도 없는 것이 이 시스템의 실패 모습이고, 규칙 하나하나가
    지켜져도 시간당 쉰 번의 기회가 시장을 그렇게 만든다 (실측: 경매 열림 0).
    """
    from game.app.bots.shopping import Listing, find_purchase

    worn = {"HEAD": build_gear(1, affixes=(("defense", 2, 0),))}
    weights = GEAR_PRIORITY_WEIGHTS["DEFENSE"]
    thin = (
        Listing(1, 10, False, 100),
        Listing(2, 500, False, 100, slot="HEAD", affixes=(("defense", 99, 0),)),
        Listing(3, 20, False, 100),
    )
    assert find_purchase(thin, 10000, worn, weights, BASE_STATS) == 0


def test_the_bot_does_not_buy_for_an_empty_slot():
    """★ 빈 자리는 러너가 채운다 — 여기서 사면 두 곳이 같은 자리를 두고 다툰다."""
    from game.app.bots.shopping import Listing, find_purchase

    weights = GEAR_PRIORITY_WEIGHTS["ATTACK"]
    listings = (
        Listing(1, 900, False, 100, slot="HEAD", affixes=(("attack", 99, 0),)),
        Listing(2, 10, False, 100),
        Listing(3, 20, False, 100),
        Listing(4, 30, False, 100),
    )
    # 머리가 비었으므로 견줌에서 빠지고, 폴백이 가장 싼 것을 고른다.
    assert find_purchase(listings, 10000, {}, weights, BASE_STATS) == 2
