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
