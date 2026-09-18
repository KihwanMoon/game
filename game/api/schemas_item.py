"""아이템·가방·지갑의 I/O 계약 (TDD §3).

`schemas.py` 에서 갈라 나왔다. 저쪽은 **판을 도는 것**(계정·티켓·제출·도감·저잣거리)이고
여기는 **가진 것**이다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐, 가르는 선은 책임이다
(§4) — `schemas_gear`·`schemas_doppel` 을 가른 것과 같은 자리다.

**재화가 둘이라 여기 모인다** (2026-09-15). 푼은 봉인을 열고 활자는 연 것을 다시 찍는데,
가방 화면이 그 둘을 같은 자리에서 묻는다.
"""

from pydantic import BaseModel, Field


class RequirementView(BaseModel):
    """요구조건 한 줄. **실측값을 함께 낸다** (docs/설계/4_아이템 §6.1).

    "장착할 수 없습니다" 만 띄우면 무엇이 얼마나 모자란지 알 수 없어 P1 위반이다.
    규칙 에디터의 조건문 표기와 같은 규약을 쓴다.
    """

    stat: str
    # **이름을 서버가 싣는다.** 접사는 이미 `stat_label` 을 실어 보내는데 요구조건만 안
    # 보내서, 화면이 `STAT_LABELS` 의 사본을 따로 들고 있었다 — 정본이 바뀌면 그 사본만
    # 옛 이름으로 남는다. 실제로 「최대체력」과 「최대 체력」으로 갈렸다 (2026-09-18).
    stat_label: str = ""
    actual: int
    minimum: int
    is_met: bool


class ItemView(BaseModel):
    """아이템 하나."""

    item_id: int
    catalog_id: str
    label_ko: str
    kind: str
    slot: str | None = None
    hands: str | None = None
    equipped_slot: str | None = None
    is_broken: bool = False
    # 거래 후 귀속 (결정 #07). **팔기 전에 보여야 한다** — 모르면 걸다가 거절당하고,
    # 그때는 이미 "왜 안 되지" 를 겪은 뒤다.
    is_bound: bool = False
    # 빼앗겼다가 되찾은 것 (`설계/6_몬스터` §5). 되찾으러 간 런이 가방에 남는다.
    is_recovered: bool = False
    # 남은 봉인 칸 (§17). **무엇이 들어올지는 안 보낸다** — 보내면 열기 전에 아는 것이
    # 되어 열 이유가 사라진다.
    sealed_slots: int = 0
    # 다음 칸을 여는 값. 화면이 다시 계산하면 두 곳이 갈린다.
    unseal_cost: int = 0
    # **다시 찍을 수 있는 첫 접사의 첨자** (신설 2026-09-15). 이 자리부터 꼬리까지가
    # 봉인에서 나온 줄이고, 앞쪽은 드롭이 달고 나온 것이라 활자로 못 바꾼다.
    #
    # 화면이 계산하지 않는다 — 등급별 칸 수(`GRADE_SEALED_SLOTS`)를 TS 가 다시 들면
    # 정본이 둘이 되고, 등급을 하나 더할 때 **고친 쪽에서만** 맞는다. 접사 수가 0 이면
    # 접사 수와 같은 값이라 「바꿀 자리가 없다」로 읽힌다.
    recast_from: int = 0
    grade: str = ""
    # 무기가 정하는 사거리 (§2.2). 0 은 「안 정한다」다.
    #
    # **가방에서 보여야 한다.** 사거리를 접사에서 필드로 올리면서 한 번 안 보이게 됐다 —
    # 접사였을 때는 「먼 사거리 +3」 으로 뜨던 것이 필드가 된 순간 어느 화면에도 안 남았다.
    attack_range: int = 0
    affixes: list[dict] = Field(default_factory=list)
    requirements: list[RequirementView] = Field(default_factory=list)
    can_equip: bool = False
    # 이 장비가 여는 스킬 (§6). **가방에서 보여야 한다** — 관리자 카탈로그 뷰에만 있어서,
    # 정비 미리보기는 「이 교체가 스킬을 뺏는다」를 알고 싶어도 알 길이 없었다.
    grants_skill: str = ""


class InventorySlotView(BaseModel):
    """인벤토리 한 칸 또는 장비 한 자리."""

    slot_index: int
    item: ItemView | None = None
    stack_catalog_id: str | None = None
    stack_count: int = 0
    # 쌓인 소모품의 이름·등급·쓰임새. **없으면 화면이 `potion_heal` 을 그대로 적는다** —
    # 서버는 아는데 화면이 말하지 않는 자리이며, 이 저장소에서 아홉 번째다.
    stack_label_ko: str = ""
    stack_grade: str = ""
    stack_use_tag: str = ""
    slot: str | None = None
    # 양손무기가 막은 자리. **저장된 상태가 아니라 계산값이다** (§2.1).
    is_sealed: bool = False


class InventoryResponse(BaseModel):
    """인벤토리·장비·지갑.

    **재화 둘을 함께 싣는다.** 가방은 「이것을 열 수 있는가」와 「이것을 다시 찍을 수
    있는가」를 같은 화면에서 묻는다 — 따로 내면 요청이 둘로 갈리고 그 사이에 값이
    어긋나는 창이 생긴다.
    """

    size: int
    slots: list[InventorySlotView] = Field(default_factory=list)
    equipment: list[InventorySlotView] = Field(default_factory=list)
    balance: int = 0
    repair_cost: int = 0
    letters: int = 0
    recast_cost: int = 0


class EquipRequest(BaseModel):
    """착용·해제 요청."""

    item_id: int = 0
    slot: str = Field(min_length=1, max_length=32)


class ItemActionRequest(BaseModel):
    """아이템 하나를 대상으로 하는 요청."""

    item_id: int


class AffixRecastRequest(BaseModel):
    """봉인에서 나온 옵션 한 줄을 다시 찍는 요청."""

    item_id: int
    affix_index: int


class WalletResponse(BaseModel):
    """지갑. **둘을 함께 낸다** — 푼과 활자는 언제나 같이 읽힌다."""

    balance: int
    repair_cost: int
    letters: int = 0
    recast_cost: int = 0
