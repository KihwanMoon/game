"""봇이 판 사이에 하는 잡일 — 가방·성장·소모품 (T11).

`shopping.py` 에서 갈라 나왔다. 저쪽은 **경매에서 무엇을 살까**를 정하고, 여기는 **이미
가진 것으로 무엇을 할까**를 정한다 — 낄 것을 고르고, 고칠 것을 고르고, 능력치를 찍고,
소모품을 끼운다. 파일이 400줄 상한을 넘은 것이 계기였지만 책임도 둘이다 (§4).

전부 순수 값이다. 러너(`scripts/bot_chores.py`)가 API 로 읽어 온 절을 여기 넣고, 여기가
「무엇을 할까」를 돌려주면 러너가 그것을 보낸다 — 판단과 통신을 갈라 두면 판단만 검사할
수 있다.
"""

from dataclasses import dataclass

from game.app.bots.personas import resolve_persona
from game.app.progression.levels import STAT_KEYS, build_growth, count_spent_points

# 성격이 능력치 포인트를 어디에 싣는가. 열이 같은 몸을 가지면 규칙표를 갈라 둔 뜻이
# 절반 사라진다.
ATTRIBUTE_WEIGHTS: dict[str, dict[str, int]] = {
    "ranged": {"dex": 2, "int": 1, "str": 0},
    "caster": {"int": 2, "dex": 1, "str": 0},
    "melee": {"str": 2, "dex": 1, "int": 0},
}


@dataclass(frozen=True)
class BagItem:
    """낄지 말지 판단할 가방 속 물건 하나."""

    item_id: int
    slot: str
    can_equip: bool
    is_broken: bool


def list_equippable(bag: tuple[BagItem, ...], filled_slots: frozenset[str]) -> tuple[BagItem, ...]:
    """빈 자리에 낄 수 있는 것들을 고른다.

    **끼는 것이 지키는 것이다.** 사망 페널티는 장착·가방을 통틀어 하나를 뽑는데, 뽑힌
    것이 **장착 중이었으면 파손**(복구 가능)이고 **가방에 있었으면 삭제**다 (결정 #34).
    그것이 「좋은 건 끼고 다녀라」는 유인인데, 봇이 아무것도 안 끼면 그 유인의 반대편만
    받는다 — 실제로 봇 열이 스무 개를 그렇게 잃었다. 받은 것도 산 것도 가방에서 녹았다.

    **빈 자리만 채운다.** 값을 매길 필요가 없는 경우이기 때문이다. 갈아 끼우기는 기준이
    필요하고 그 기준이 틀리면 봇이 좋은 것을 벗고 나쁜 것을 끼므로, 그쪽은 `upgrade.py`
    가 따로 맡는다 — 그리고 **이 함수가 먼저 돈다.** 빈 자리 채우기가 끝나야 「찬 자리」가
    확정되고, 그래야 두 규칙이 같은 자리를 두고 다투지 않는다.

    Args:
        bag: 가방 속 물건들.
        filled_slots: 이미 차 있는 장비 자리들.

    Returns:
        낄 것들. 한 자리에 하나씩만 고른다.
    """
    picked: dict[str, BagItem] = {}
    for item in bag:
        if not item.can_equip or item.is_broken or not item.slot:
            continue
        if item.slot in filled_slots or item.slot in picked:
            continue
        picked[item.slot] = item
    # 자리 이름 순으로 낸다. 순서가 흔들리면 같은 가방에서 다른 일이 벌어진다.
    return tuple(picked[slot] for slot in sorted(picked))


def list_repairable(bag: tuple[BagItem, ...], balance: int, cost: int) -> tuple[BagItem, ...]:
    """고칠 수 있는 것들을 고른다.

    **안 고치면 장비가 한 방향으로만 준다.** 사망 페널티가 장착 중인 것을 부수는데
    (결정 #34), 부순 것을 아무도 안 고치면 봇의 장비는 죽을 때마다 줄기만 하고 절대
    늘지 않는다 — 그러면 「끼는 것이 지키는 것이다」의 뒷부분(복구 가능)이 봇에게는
    거짓이 되고, 몬스터가 뺏어 갈 것도 사라진다.

    **낄 수 있는 것만 고친다.** 못 끼는 것을 고치면 화폐가 나가고 아무것도 안 바뀐다.

    **낼 수 있는 만큼만 고른다.** 잔액을 넘겨 보내면 서버가 거절하고, 그것은 실패를
    로그로 옮길 뿐이다. 자리 이름 순으로 세어 나가므로 같은 가방에서 같은 결과가 나온다.

    Args:
        bag: 가방과 장비를 통틀어 본 물건들.
        balance: 봇의 화폐.
        cost: 한 번 고치는 값.

    Returns:
        고칠 것들. 낼 수 있는 만큼에서 끊는다.
    """
    if cost <= 0:
        return ()
    broken = sorted(
        (item for item in bag if item.is_broken and item.can_equip and item.slot),
        key=lambda item: (item.slot, item.item_id),
    )
    return tuple(broken[: max(0, balance // cost)])


def build_allocation(level: int, ruleset_id: str, spent: dict[str, int]) -> dict[str, int]:
    """레벨이 준 포인트를 성격에 맞게 나눈다.

    **안 쓰면 없는 것과 같다.** 포인트는 레벨과 함께 쌓이기만 하고 사람이 배분해야
    붙는다 — 봇이 배분을 안 하면 레벨 4 짜리가 레벨 1 의 몸으로 싸운다. 실제로 그렇게
    돌았다: 열 봇 전부 `stat_json` 이 비어 있었고 9점씩 놀고 있었다.

    성격을 따른다. 근접으로 미는 규칙표는 힘에, 거리를 두는 쪽은 민첩에, 규칙을 많이
    까는 쪽은 지능에 싣는다 — 열이 같은 몸을 가지면 규칙표를 갈라 둔 뜻이 절반 사라진다.

    **이미 쓴 것은 그대로 둔다.** 배분표를 통째로 다시 쓰면 사람이 손댄 봇의 배분이
    조용히 덮인다.

    Args:
        level: 지금 레벨.
        ruleset_id: 이 봇이 쓰는 규칙표. 성격을 여기서 읽는다.
        spent: 지금 배분표.

    Returns:
        새 배분표. 더 쓸 것이 없으면 지금 것 그대로다.
    """
    available = build_growth(level).stat_points - count_spent_points(spent)
    if available <= 0:
        return dict(spent)
    # 성격 판단은 `personas.resolve_persona` 한 곳에만 있다. 두 벌이면 하나만 고쳐도
    # 봇이 스탯은 사수처럼, 장비는 전사처럼 고르게 된다.
    weights = ATTRIBUTE_WEIGHTS[resolve_persona(ruleset_id)]
    total = sum(weights.values())
    next_stats = dict(spent)
    # 정렬된 열쇠로 돈다. 딕셔너리 순회 순서에 기대면 같은 상황에서 다른 몸이 나온다.
    for key in sorted(STAT_KEYS):
        next_stats[key] = int(next_stats.get(key, 0)) + available * weights.get(key, 0) // total
    # **나머지 처리를 두지 않는다.** 레벨당 포인트(3)가 가중치 합(3)의 배수라 나눗셈이
    # 아무것도 안 버린다 — 닿지 않는 갈래를 방어라고 두면 검사할 수 없는 코드가 된다.
    # 둘 중 하나가 바뀌면 「남는 포인트가 없다」 검사가 그 자리에서 걸린다.
    return next_stats


@dataclass(frozen=True)
class ConsumableSlot:
    """소모품 칸 하나."""

    use_tag: str
    slot_index: int
    catalog_id: str


@dataclass(frozen=True)
class ConsumableOption:
    """가방에 있는, 칸에 끼울 수 있는 소모품."""

    catalog_id: str
    use_tag: str
    count: int


def list_loadable(
    slots: tuple[ConsumableSlot, ...], options: tuple[ConsumableOption, ...]
) -> tuple[tuple[ConsumableSlot, str], ...]:
    """빈 칸에 끼울 것을 짝지어 낸다.

    **끼워야 보충이 돈다.** 정비의 REFILL 은 이미 끼운 것을 채우기만 한다 — 칸이 비어
    있으면 채울 대상이 없어서 아무 일도 일어나지 않는다. 그래서 봇이 소모품을 주워도
    가방에 쌓이기만 하고, 죽을 때 사망 페널티가 그것을 지운다.

    쓰임새가 맞아야 들어간다. POTION 칸에 SCROLL 을 밀어 넣으면 서버가 거절하므로,
    보내기 전에 여기서 거른다 — 거절당할 요청을 보내는 것은 실패를 로그로 옮길 뿐이다.

    Args:
        slots: 지금 칸 상태.
        options: 가방에 있는 소모품들.

    Returns:
        (빈 칸, 끼울 소모품 id) 짝들. 한 후보를 여러 칸에 나눠 쓰지 않는다.
    """
    left = {item.catalog_id: item.count for item in options}
    by_tag: dict[str, list[str]] = {}
    for item in options:
        by_tag.setdefault(item.use_tag, []).append(item.catalog_id)
    picked: list[tuple[ConsumableSlot, str]] = []
    # 칸 순서대로 채운다. 순서가 흔들리면 같은 가방에서 다른 몸이 나간다.
    for slot in sorted(slots, key=lambda item: (item.use_tag, item.slot_index)):
        if slot.catalog_id:
            continue
        found = next(
            (item for item in sorted(by_tag.get(slot.use_tag, [])) if left.get(item, 0) > 0),
            "",
        )
        if not found:
            continue
        left[found] -= 1
        picked.append((slot, found))
    return tuple(picked)


def parse_consumables(
    payload: dict,
) -> tuple[tuple[ConsumableSlot, ...], tuple[ConsumableOption, ...]]:
    """`/api/consumables` 응답을 읽는다.

    **이름을 여기 한 곳에만 적는다.** 러너 안에 인라인으로 두었더니 재고 열쇠를 `count`
    로 적었는데 서버는 `stock` 이라, 후보가 늘 0개로 읽혀 아무것도 장전되지 않았다 —
    조용히 아무 일도 안 일어나는 종류의 결함이다. 파싱이 함수로 나와 있어야 응답 모양을
    그대로 넣어 보는 검사를 쓸 수 있다.

    Args:
        payload: 서버 응답.

    Returns:
        (칸들, 가방 후보들).
    """
    slots = tuple(
        ConsumableSlot(
            use_tag=str(row.get("use_tag", "")),
            slot_index=int(row.get("slot_index", 0)),
            catalog_id=str(row.get("catalog_id") or ""),
        )
        for row in payload.get("slots", [])
    )
    options = tuple(
        ConsumableOption(
            catalog_id=str(row.get("catalog_id", "")),
            use_tag=str(row.get("use_tag") or ""),
            count=int(row.get("stock", 0)),
        )
        for row in payload.get("options", [])
    )
    return slots, options
