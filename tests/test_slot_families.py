"""칸 계열과 태그 — 무엇을 들고 갈까 (2026-09-11 결정).

`test_consumable_slots.py` 에서 갈라 나왔다. 저쪽은 **칸이 몇이고 어떻게 채우는가**이고
여기는 **한 칸이 이번 판의 무엇이 되는가**다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐,
가르는 선은 책임이다 (§4).

**「주문서 종류를 늘려 달라」에 칸을 늘려 답하지 않았다.** 칸을 늘리면 들고 갈 수 있는
것이 느는 것이지 고를 것이 느는 것이 아니다. 칸은 그대로 하나이고 **거기 무엇을
끼웠느냐가 `USE_ITEM[태그]` 를 정한다** — 그래서 「무엇을 들고 갈까」가 선택이 된다.
"""

from game.app.store.consumables import ConsumableSlot, count_slot_charges
from game.schemas.consumable import check_slot_fit, find_slot_family


def build_slot(use_tag, slot_index, catalog_id, charges):
    """칸 하나를 만든다.

    Args:
        use_tag: 칸의 계열.
        slot_index: 칸 번호.
        catalog_id: 끼운 아이템. 없으면 None.
        charges: 남은 충전.

    Returns:
        칸 하나.
    """
    return ConsumableSlot(
        use_tag=use_tag,
        slot_index=slot_index,
        catalog_id=catalog_id,
        charges=charges,
        is_base=False,
    )


def test_every_scroll_kind_fits_the_one_scroll_slot():
    """★ **칸은 계열이고 태그는 끼운 물건이다** (2026-09-11).

    주문서를 넷으로 늘리면서 칸을 안 늘렸다. 칸을 늘리면 **들고 갈 수 있는 것**이 느는
    것이지 고를 것이 느는 것이 아니다 — 지금은 한 칸에 무엇을 끼우느냐가 곧 이번 판의
    `USE_ITEM[태그]` 라, 「무엇을 들고 갈까」가 선택이 된다.
    """
    for tag in ("SCROLL", "BLINK", "FLAME", "FOCUS"):
        assert check_slot_fit(tag, "SCROLL") is True, tag
        assert check_slot_fit(tag, "POTION") is False, tag
        assert find_slot_family(tag) == "SCROLL"


def test_a_slotted_scroll_is_counted_by_its_own_tag():
    """★ **실려 가는 것은 칸 이름이 아니라 끼운 주문서다** (2026-09-11).

    칸 계열로 세면 순간이동을 끼우고도 판에서 `USE_ITEM[SCROLL]` 이 돌아, 규칙표가
    가리킨 것과 실제로 빠지는 것이 갈린다.
    """

    class Entry:
        use_tag = "BLINK"

    slot = build_slot("SCROLL", 1, "scroll_blink", 2)
    counts = count_slot_charges((slot,), {"scroll_blink": Entry()})
    assert counts == {"BLINK": 2}
