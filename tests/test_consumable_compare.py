"""소모품 견줌 — 화면이 두 소모품을 스탯별로 가를 수 있는가 (설계/4_아이템 §5).

`test_consumable_slots.py` 에서 갈라 나왔다. 저쪽은 **칸의 규칙**(몇 개를 들고 가는가,
무엇이 어느 칸에 들어가는가)을 보고, 여기는 **화면에 무엇을 실어 보내는가**를 본다 —
같은 파일에 두면 400줄 상한을 넘고, 책임도 둘이다 (§4).

지키는 것은 하나다. **견줌은 능력치 축이 있어야 한다.** 접사를 구운 문자열로만 보내면
화면은 문자열 두 벌을 나란히 놓는 것이 전부이고, 가방이 이미 하는 「스탯별 차이」를
소모품에서만 못 하게 된다.
"""


def build_slot(use_tag="POTION", slot_index=0, catalog_id=None, charges=0):
    """검사용 칸 하나를 만든다.

    Args:
        use_tag: 쓰임새.
        slot_index: 칸 번호.
        catalog_id: 끼운 소모품. None 이면 빈 칸이다.
        charges: 남은 충전.

    Returns:
        칸 하나.
    """
    from game.app.store.consumables import ConsumableSlot

    return ConsumableSlot(
        use_tag=use_tag, slot_index=slot_index, catalog_id=catalog_id, charges=charges
    )


def test_the_screen_can_compare_two_consumables():
    """★ 접사를 구운 문자열로만 보내면 화면이 두 소모품을 견줄 수 없다.

    `affixes` 는 「튼튼함 · 최대체력 +8」 처럼 적어 둔 것이라 **능력치 축이 안 담긴다.**
    그것만 보내면 화면은 문자열 두 벌을 나란히 놓는 것이 전부이고, 판단은 통째로 사람에게
    넘어간다 — 가방은 이미 구조화된 절로 스탯별 차이를 낸다. 같은 질문에 두 화면이 다른
    방식으로 답하면 어느 쪽을 믿을지가 또 하나의 문제가 된다.

    관리자 카탈로그가 `affix_rows` 를 더한 것과 같은 자리다.
    """
    from game.api.routes.consumables import build_slot_view
    from game.schemas.item import Affix, ItemCatalogEntry, ItemKind

    entry = ItemCatalogEntry(
        catalog_id="potion_heal",
        kind=ItemKind.CONSUMABLE,
        label_ko="회복 물약",
        affixes=(Affix(stat="hp_max", flat=8, label_ko="튼튼함"),),
        charges=4,
        use_tag="POTION",
    )
    view = build_slot_view(build_slot(catalog_id="potion_heal", charges=1), {"potion_heal": entry})

    # 사람이 읽는 줄은 그대로 남는다 — 견줌을 더한 것이지 바꾼 것이 아니다.
    assert view.affixes == ["튼튼함 · 최대체력 +8"]
    # 견줌이 읽을 절에는 **축과 값이 따로** 있다.
    row = view.affix_rows[0]
    assert row["stat"] == "hp_max"
    assert row["flat"] == 8
    # 한글 이름을 서버가 붙인다 — 화면이 제 목록을 들면 정본이 둘이 된다.
    assert row["stat_label"] == "최대체력"


def test_bag_stock_carries_the_same_rows():
    """★ 재고에도 견줌 절이 실린다 — 갈아 끼우기 전에 견주는 것이 이 화면의 일이다.

    칸에만 실으면 「끼운 것끼리」는 견줄 수 있는데 「가방의 것과 끼운 것」은 못 견준다.
    그런데 사람이 실제로 묻는 것은 후자다.
    """
    from game.api.routes.consumables import ConsumableOption

    # 라우트가 만드는 절의 계약만 본다 — DB 는 안 띄운다.
    option = ConsumableOption(
        catalog_id="potion_elixir",
        label_ko="영약",
        grade="RELIC",
        use_tag="POTION",
        charges=7,
        stock=2,
        sell_price=630,
        affixes=["튼튼함 · 최대체력 +25"],
        affix_rows=[{"stat": "hp_max", "flat": 25, "percent": 0, "stat_label": "최대체력"}],
    )
    assert option.affix_rows[0]["stat"] == "hp_max"
