"""아이템 계약 (docs/설계/4_아이템).

**시스템의 모양만 담는다.** 접사 굴림은 여기 없다 — 파생식이 결정 대기(#02)이고, 정하기
전에 굴리면 그때까지 나온 아이템이 전부 무효가 된다.

분류는 셋이다. 장비는 슬롯에 들어가고, 소모품은 스택으로 쌓이며, 퀘스트 아이템은 소모도
장비도 되지 않는다. 셋을 한 타입으로 두는 이유는 인벤토리가 셋을 같은 칸에 담기 때문이다.

**슬롯 순서가 고정이다.** 스탯 합산이 이 순서로 돌므로, 순서가 흔들리면 클램프가 끼는
순간 같은 장비 구성이 다른 값을 낸다 (R5).
"""

from dataclasses import dataclass, field
from enum import StrEnum


class ItemKind(StrEnum):
    """아이템 분류 셋."""

    EQUIPMENT = "EQUIPMENT"
    CONSUMABLE = "CONSUMABLE"
    QUEST = "QUEST"


class EquipSlot(StrEnum):
    """장비 슬롯 여섯. 선언 순서가 곧 스탯 합산 순서다."""

    WEAPON_MAIN = "WEAPON_MAIN"
    WEAPON_OFF = "WEAPON_OFF"
    HEAD = "HEAD"
    BODY = "BODY"
    FEET = "FEET"
    HANDS = "HANDS"


class WeaponHands(StrEnum):
    """무기가 손을 쓰는 방식.

    방패는 별도 슬롯이 아니라 `OFFHAND` 무기다. 별도 슬롯을 만들면 "양손무기 대
    한손+방패" 라는 트레이드오프가 사라진다 (P3).
    """

    ONE = "ONE"
    TWO = "TWO"
    OFFHAND = "OFFHAND"


# 슬롯 고정 순서. EquipSlot 의 선언 순서를 값으로 굳혀 둔다 — 열거형 순회에 기대면
# 나중에 슬롯을 추가할 때 순서가 조용히 바뀐다.
SLOT_ORDER: tuple[EquipSlot, ...] = (
    EquipSlot.WEAPON_MAIN,
    EquipSlot.WEAPON_OFF,
    EquipSlot.HEAD,
    EquipSlot.BODY,
    EquipSlot.FEET,
    EquipSlot.HANDS,
)


@dataclass(frozen=True)
class Requirement:
    """사용 제한 한 줄. 정수 비교뿐이다 (R5).

    어떤 능력치가 존재하는지는 밸런스 데이터가 정한다. 코드는 이름을 모르므로,
    능력치 축이 정해지기 전에도(#11) 구조가 바뀌지 않는다.
    """

    stat: str
    minimum: int


@dataclass(frozen=True)
class Affix:
    """접사 하나. 고정 합계에 붙거나 퍼센트에 붙는다.

    `percent` 가 음수일 수 있다 — 저주 접사다. 그래서 합산이 내림 나눗셈의 부호를
    신경 써야 한다 (docs/설계/4_아이템 §9).
    """

    stat: str
    flat: int = 0
    percent: int = 0
    label_ko: str = ""


# 등급 코드 (결정 #42). 셋을 넘기면 괘선 굵기 표기가 부족해진다.
GRADE_COMMON = "COMMON"
GRADE_FINE = "FINE"
GRADE_RELIC = "RELIC"

# 등급별 접사 굴림 수. 등급이 성능을 정하는 유일한 자리다 (§15.4).
GRADE_AFFIX_ROLLS: dict[str, tuple[int, int]] = {
    GRADE_COMMON: (1, 1),
    GRADE_FINE: (1, 2),
    GRADE_RELIC: (2, 3),
}


@dataclass(frozen=True)
class ItemCatalogEntry:
    """카탈로그 한 줄. 런과 무관하게 고정인 정의다."""

    catalog_id: str
    kind: ItemKind
    label_ko: str
    slot: EquipSlot | None = None
    hands: WeaponHands | None = None
    affixes: tuple[Affix, ...] = ()
    requirements: tuple[Requirement, ...] = ()
    stack_max: int = 1
    # 이 장비가 여는 스킬 (결정 #13). 장비는 전투 전에 캐릭터로 녹으므로, 스킬도
    # 규칙표가 직접 장비를 보는 것이 아니라 **캐릭터가 그것을 갖게** 되는 방식이다.
    grants_skill: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    # 등급 (결정 #42). 접사 굴림 수를 이것이 정한다 — 이름표로만 두면 「유물 단검」이
    # 「보통 단검」보다 나은 점이 없어 등급이 뜻을 잃는다 (설계/4_아이템 §15.4).
    grade: str = GRADE_COMMON
    # 이 층부터 나온다 (D1). 1층에서 유물이 나오면 깊이 들어갈 이유가 없다.
    min_floor: int = 1
    # 폐기. **지우지 않는다** — 인스턴스·원장·경매가 catalog_id 를 가리키므로 지우면
    # 과거 기록을 못 읽는다. 이것은 "새로 안 나온다" 만 뜻한다 (§15.7).
    is_retired: bool = False


def parse_requirement(raw: dict) -> Requirement:
    """요구조건 한 줄을 읽는다.

    Args:
        raw: stat 과 min 을 가진 절.

    Returns:
        만들어진 요구조건.
    """
    return Requirement(stat=raw["stat"], minimum=int(raw["min"]))


def parse_affix(raw: dict) -> Affix:
    """접사 한 줄을 읽는다.

    Args:
        raw: stat 과 flat·percent 를 가진 절.

    Returns:
        만들어진 접사.
    """
    return Affix(
        stat=raw["stat"],
        flat=int(raw.get("flat", 0)),
        percent=int(raw.get("percent", 0)),
        label_ko=raw.get("label_ko", ""),
    )


def parse_item(raw: dict) -> ItemCatalogEntry:
    """카탈로그 한 줄을 읽는다.

    Args:
        raw: 아이템 절.

    Returns:
        만들어진 카탈로그 항목.

    Raises:
        ValueError: 장비인데 슬롯이 없거나, 무기 슬롯인데 손 규격이 없는 경우.
    """
    kind = ItemKind(raw["kind"])
    slot = EquipSlot(raw["slot"]) if raw.get("slot") else None
    hands = WeaponHands(raw["hands"]) if raw.get("hands") else None
    if kind is ItemKind.EQUIPMENT and slot is None:
        raise ValueError(f"장비에 슬롯이 없다: {raw['id']}")
    if slot in {EquipSlot.WEAPON_MAIN, EquipSlot.WEAPON_OFF} and hands is None:
        raise ValueError(f"무기에 손 규격(hands)이 없다: {raw['id']}")
    return ItemCatalogEntry(
        catalog_id=raw["id"],
        kind=kind,
        label_ko=raw.get("label_ko", raw["id"]),
        slot=slot,
        hands=hands,
        affixes=tuple(parse_affix(item) for item in raw.get("affixes", [])),
        requirements=tuple(parse_requirement(item) for item in raw.get("requirements", [])),
        stack_max=int(raw.get("stack_max", 1)),
        grants_skill=raw.get("grants_skill"),
        tags=tuple(raw.get("tags", [])),
        # 등급이 없는 절은 보통으로 읽는다. 스냅샷 파일이 등급 이전 세대일 수 있고,
        # 그때 터지면 배포 순서 하나로 서버가 안 뜬다.
        grade=raw.get("grade", GRADE_COMMON),
        min_floor=int(raw.get("min_floor", 1)),
        is_retired=bool(raw.get("is_retired", False)),
    )


def build_item_payload(entry: ItemCatalogEntry) -> dict:
    """카탈로그 항목을 JSON 절로 되돌린다.

    `scripts/export_items.py` 가 DB 스냅샷을 파일로 내보낼 때 쓴다. `parse_item` 이 다시
    읽을 수 있어야 하므로 **키 이름이 그쪽과 같아야 한다.**

    Args:
        entry: 카탈로그 항목.

    Returns:
        items.json 에 들어갈 절.
    """
    payload: dict = {
        "id": entry.catalog_id,
        "kind": str(entry.kind.value),
        "label_ko": entry.label_ko,
        "grade": entry.grade,
        "min_floor": entry.min_floor,
    }
    if entry.slot is not None:
        payload["slot"] = str(entry.slot.value)
    if entry.hands is not None:
        payload["hands"] = str(entry.hands.value)
    if entry.affixes:
        payload["affixes"] = [
            {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
            for a in entry.affixes
        ]
    if entry.requirements:
        payload["requirements"] = [{"stat": r.stat, "min": r.minimum} for r in entry.requirements]
    if entry.stack_max != 1:
        payload["stack_max"] = entry.stack_max
    if entry.grants_skill:
        payload["grants_skill"] = entry.grants_skill
    if entry.tags:
        payload["tags"] = list(entry.tags)
    if entry.is_retired:
        payload["is_retired"] = True
    return payload
