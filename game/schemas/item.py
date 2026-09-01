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


# **접사가 붙을 수 있는 스탯의 정본이다.** 여기 없는 이름은 접사로 붙여도 합산에
# 들어가지 않는다 — 오타 하나가 아무 효과 없는 접사를 만들고, 그것이 어디서도 안 걸렸다.
# 로드아웃 합산·관리자 편집·봉인 옵션 풀이 전부 이 목록 하나를 본다.
#
# **순서가 뜻을 갖는다.** 로드아웃이 이 순서로 최종 스탯표를 만든다 (R5).
COMBAT_STATS: tuple[str, ...] = (
    "hp_max",
    "attack",
    "defense",
    "attack_range",
    "initiative",
    "cpu_budget",
)


def list_unknown_stats(affixes: tuple[Affix, ...]) -> tuple[str, ...]:
    """정본에 없는 스탯 이름을 모은다.

    Args:
        affixes: 검사할 접사들.

    Returns:
        모르는 이름들. 이름 순으로 정렬돼 있고 중복이 없다. 전부 아는 이름이면 빈 튜플.
    """
    return tuple(sorted({item.stat for item in affixes if item.stat not in COMBAT_STATS}))


# 등급 코드 (결정 #42). 셋을 넘기면 괘선 굵기 표기가 부족해진다.
GRADE_COMMON = "COMMON"
GRADE_FINE = "FINE"
GRADE_RELIC = "RELIC"

# 등급이 주는 봉인 칸 수 (§17). **등급이 성능에 하는 일은 이것 하나뿐이다** — 최저
# 등급은 고정 옵션만 갖고, 등급이 오를수록 칸이 하나씩 는다.
GRADE_SEALED_SLOTS: dict[str, int] = {
    GRADE_COMMON: 0,
    GRADE_FINE: 1,
    GRADE_RELIC: 2,
}

# 등급 순서. **낮은 것이 앞이다.** 카탈로그의 `grade` 는 「이 등급부터 나온다」이고,
# 드롭표를 깔 때 이 순서로 위쪽 등급까지 줄을 만든다 (§15.4).
GRADE_ORDER: tuple[str, ...] = (GRADE_COMMON, GRADE_FINE, GRADE_RELIC)


def list_grades_above(grade: str) -> tuple[str, ...]:
    """그 등급과 그 위 등급들을 낮은 것부터 돌려준다.

    Args:
        grade: 기준 등급. 모르는 값이면 전체를 돌려준다 — 데이터가 앞서 나갔을 때
            아이템이 아예 안 나오는 것보다 낫다.

    Returns:
        등급 코드들. 낮은 것이 앞이다.
    """
    if grade not in GRADE_ORDER:
        return GRADE_ORDER
    return GRADE_ORDER[GRADE_ORDER.index(grade) :]


def list_grades_downward(grade: str) -> tuple[str, ...]:
    """그 등급부터 아래로, **높은 것부터** 돌려준다.

    뽑힌 등급에 후보가 없을 때 강등해 가며 찾는 데 쓴다. 위로 올리지 않는 이유는 그것이
    공짜 승급이 되기 때문이다.

    Args:
        grade: 뽑힌 등급. 모르는 값이면 그 하나뿐이다 — 모르는 등급에서 아무 데로나
            내려가면 데이터 오타가 유물 지급이 된다.

    Returns:
        등급 코드들. 높은 것이 앞이다.
    """
    if grade not in GRADE_ORDER:
        return (grade,)
    return tuple(reversed(GRADE_ORDER[: GRADE_ORDER.index(grade) + 1]))


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
    # **무기가 가진 사거리** (§2.2). `hands` 와 같은 급이다 — 예전에는 접사로 흉내냈는데,
    # 접사는 굴림에서 잘릴 수 있어 **활이 근접무기가 되는** 경로가 있었다. 주무기의 이
    # 값이 기본 사거리를 대체하고, 접사는 그 위에 더한다.
    #
    # None 은 "이 아이템은 사거리를 안 정한다" 다. 0 과 구분해야 한다 — 0 은 아무것도
    # 못 때리는 무기다.
    attack_range: int | None = None
    # **코드가 읽는 태그는 이것 하나다** (§4). 소모품이 무엇으로 쓰이는가이며,
    # `USE_ITEM[kind]` 의 파라미터와 같은 값이다.
    #
    # `tags` 와 가른 이유는 둘이 하는 일이 다르기 때문이다 — 예전에는 한 목록이 둘을
    # 겸해서, 「소모품 종류」와 「분류 이름표」가 같은 자리에 섞여 있었다. 물약에
    # `HEAL` 을 하나 더 붙이면 가방이 그것을 소모품 종류로 세고, 무기의 `MELEE` 는
    # 적 유형의 `MELEE` 와 글자가 같아 셀렉터와 헷갈렸다.
    use_tag: str | None = None
    # **표시 전용이다.** 코드는 안 읽는다 — 화면이 묶어 보여 주고 사람이 검색하는 데
    # 쓴다. 여기에 무엇을 적어도 게임 규칙은 안 바뀐다.
    tags: tuple[str, ...] = field(default_factory=tuple)
    # **이 등급부터 나온다** (결정 #42). `min_floor` 가 층에 대해 하는 일을 등급에
    # 대해 한다 — 인스턴스의 등급은 굴려서 정해지고 이것보다 낮아지지 않는다.
    #
    # 등급이 성능에 하는 일은 **봉인 칸 수 하나뿐이다** (§17). 접사 개수를 등급이
    # 정하게 두면 「고정 옵션」이 무작위가 되어 봉인과 뜻이 겹친다.
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
        use_tag=raw.get("use_tag"),
        attack_range=(int(raw["attack_range"]) if raw.get("attack_range") is not None else None),
        tags=tuple(raw.get("tags", [])),
        # 등급이 없는 절은 보통으로 읽는다. 스냅샷 파일이 등급 이전 세대일 수 있고,
        # 그때 터지면 배포 순서 하나로 서버가 안 뜬다.
        grade=raw.get("grade", GRADE_COMMON),
        min_floor=int(raw.get("min_floor", 1)),
        is_retired=bool(raw.get("is_retired", False)),
    )


# 있을 때만 적는 필드. **빈 값을 적어 내보내면 다음 세대가 그것을 뜻으로 읽는다** —
# 사거리 0 은 「아무것도 못 때리는 무기」이지 「안 정함」이 아니다.
_OPTIONAL_KEYS: tuple[tuple[str, str], ...] = (
    ("grants_skill", "grants_skill"),
    ("attack_range", "attack_range"),
    ("use_tag", "use_tag"),
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
    if entry.tags:
        payload["tags"] = list(entry.tags)
    if entry.is_retired:
        payload["is_retired"] = True
    for key, name in _OPTIONAL_KEYS:
        value = getattr(entry, name)
        if value is not None:
            payload[key] = value
    return payload
