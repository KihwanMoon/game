"""소모품 칸 — 물약과 주문서를 장착해서 들고 간다 (설계/4_아이템 §5, 결정 #54).

**예전에는 가방에 든 것을 전부 세서 들고 갔다.** 물약을 많이 주우면 많이 들고 갔고,
그래서 「몇 개를 들고 갈까」가 선택이 아니었다 — 주운 만큼이 답이었다.

칸으로 바꾸면 셋이 한꺼번에 생긴다.

1. **한도.** 칸에 담긴 충전 수만큼만 쓴다. 다 쓰면 그 런에서는 끝이다.
2. **선택.** 어떤 물약을 끼울지가 결정이 된다 — 센 것은 더 많이 담기고 유지비가 비싸다.
3. **유지비.** 쓰고 나면 돈을 내고 채운다. 벌이가 곧 다음 판의 물약이 된다.

**빈 칸은 공짜로 한 번 찬다.** 안 그러면 새 계정이 물약 없이 시작하는데, 그것은 지금
`balance.player.potions` 가 매 판 공짜로 주던 두 개를 없애는 일이다. 빈 물약 칸 둘이
곧 예전의 기본 지급 둘이다 — 바뀐 것은 **채우면 더 좋아진다**는 것뿐이다.

칸 수는 여기 고정이다. 접사로 늘리는 것은 다음 차례이며, 그때 이 표가 하한이 된다.
"""

from game.schemas.item import GRADE_COMMON, GRADE_FINE, GRADE_RELIC

# 소모품 칸의 기본 구성. **정렬된 쌍이다** — 딕셔너리 순회 순서가 로드아웃에 새어 나가면
# 같은 계정이 실행마다 다른 티켓을 받는다 (R5).
BASE_CONSUMABLE_SLOTS: tuple[tuple[str, int], ...] = (("POTION", 2), ("SCROLL", 1))

# 아무것도 안 끼운 칸이 출격 시 공짜로 받는 충전 수. 예전의 기본 지급을 대신한다.
FREE_CHARGES = 1

# 쓰임새마다 칸을 늘리는 능력치 이름. **`COMBAT_STATS` 에 있는 이름이어야 한다** —
# 없으면 접사가 파싱은 되고 합산은 안 되어 조용히 무효가 된다 (§4).
SLOT_STATS: dict[str, str] = {"POTION": "potion_slots", "SCROLL": "scroll_slots"}

# 한 쓰임새가 가질 수 있는 칸 수의 상한. **접사가 무한히 쌓이는 것을 막는다** — 상한이
# 없으면 봉인을 여러 번 연 캐릭터가 물약을 열 개 들고 다니고, 그러면 한도가 한도가
# 아니게 된다. 늘리는 접사가 귀한 만큼 이 값은 여유롭게 둔다.
MAX_SLOTS_PER_TAG = 5

# 충전 하나를 채우는 값. **등급에 비례한다** — 센 물약은 유지비가 비싸야 「무엇을
# 끼울까」가 공짜 선택이 아니게 된다. 싸게 가고 많이 쓸지, 비싸게 가고 아낄지다.
GRADE_REFILL_COST: dict[str, int] = {
    GRADE_COMMON: 20,
    GRADE_FINE: 60,
    GRADE_RELIC: 180,
}

# 안 쓰는 소모품을 팔 때 충전 하나가 받는 값. 보충 단가의 절반이다 — 같게 두면 팔고
# 다시 채우는 것이 공짜가 되고, 그러면 「끼운다」와 「판다」가 같은 선택이 된다.
SELL_DIVISOR = 2


def check_slot_fit(use_tag: str | None, slot_tag: str) -> bool:
    """이 소모품을 그 칸에 끼울 수 있는지 본다.

    **코드가 읽는 태그는 `use_tag` 하나다** (§4). 표시용 이름표(`tags`)를 보면 물약에
    분류 이름표를 하나 더 붙이는 것만으로 주문서 칸에 들어가게 된다.

    Args:
        use_tag: 소모품의 쓰임새. 없으면 어느 칸에도 못 들어간다 — 쓰임새가 없는 것은
            어떤 `USE_ITEM` 도 가리키지 못하므로, 끼워 봐야 쓸 수 없다.
        slot_tag: 칸의 쓰임새.

    Returns:
        끼울 수 있으면 True.
    """
    return bool(use_tag) and use_tag == slot_tag


def resolve_slot_count(use_tag: str, extra: int = 0) -> int:
    """이 쓰임새의 칸 수 — 기본에 접사가 더한 만큼을 얹는다.

    **모르는 쓰임새는 접사가 있어도 0 이다.** 데이터가 앞서 나갔을 때 칸이 저절로
    생기면, 어디에도 안 적힌 칸에 물약이 들어간다.

    Args:
        use_tag: 소모품 쓰임새 (POTION·SCROLL).
        extra: 장비 접사가 더한 칸 수. 음수는 무시한다 — 칸을 빼앗는 접사는 없고,
            음수 접사가 실수로 들어와 칸이 사라지면 끼워 둔 것이 통째로 잠긴다.

    Returns:
        칸 수. `MAX_SLOTS_PER_TAG` 를 넘지 않는다.
    """
    for tag, count in BASE_CONSUMABLE_SLOTS:
        if tag == use_tag:
            return min(MAX_SLOTS_PER_TAG, count + max(0, extra))
    return 0


def resolve_refill_cost(grade: str, charges: int) -> int:
    """충전 몇 개를 채우는 값.

    Args:
        grade: 끼운 소모품의 등급.
        charges: 채울 충전 수.

    Returns:
        치러야 할 값. 채울 것이 없으면 0 이다.
    """
    if charges <= 0:
        return 0
    return GRADE_REFILL_COST.get(grade, GRADE_REFILL_COST[GRADE_COMMON]) * charges


def resolve_sell_price(grade: str, charges: int) -> int:
    """소모품 하나를 팔 때 받는 값.

    **끼우는 편이 언제나 낫다.** 판 값으로 같은 것을 다시 채울 수 없어야, 드롭이
    「보충재」가 아니라 「더 좋은 것을 얻는 길」로 남는다.

    Args:
        grade: 파는 소모품의 등급.
        charges: 그 소모품 하나가 칸에 주는 충전 수.

    Returns:
        받는 값. 최소 1 이다 — 0 이면 팔았는데 아무 일도 안 일어난 것으로 보인다.
    """
    return max(1, resolve_refill_cost(grade, max(1, charges)) // SELL_DIVISOR)


def build_slot_rows(use_tag: str, extra: int = 0) -> tuple[int, ...]:
    """이 쓰임새가 갖는 칸 번호들.

    Args:
        use_tag: 소모품 쓰임새.
        extra: 장비 접사가 더한 칸 수.

    Returns:
        0 부터 세는 칸 번호. 칸이 없으면 빈 값이다.
    """
    return tuple(range(resolve_slot_count(use_tag, extra)))


def list_slot_tags() -> tuple[str, ...]:
    """칸을 갖는 쓰임새들을 정해진 순서로 돌려준다.

    Returns:
        쓰임새 코드들. `BASE_CONSUMABLE_SLOTS` 의 순서다 (R5).
    """
    return tuple(tag for tag, _count in BASE_CONSUMABLE_SLOTS)


__all__ = [
    "BASE_CONSUMABLE_SLOTS",
    "FREE_CHARGES",
    "GRADE_REFILL_COST",
    "MAX_SLOTS_PER_TAG",
    "SLOT_STATS",
    "SELL_DIVISOR",
    "build_slot_rows",
    "check_slot_fit",
    "list_slot_tags",
    "resolve_refill_cost",
    "resolve_sell_price",
    "resolve_slot_count",
]
