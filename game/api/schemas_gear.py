"""소모품·정비·스킬 세팅의 API 계약 (설계/4_아이템 §5).

`schemas.py` 에서 갈라 나왔다 — 파일이 400줄 상한을 넘은 것이 계기였지만, 셋 다 가방
탭이 쓰는 계약이라 함께 사는 편이 맞다.
"""

from pydantic import BaseModel


class ConsumableSlotView(BaseModel):
    """소모품 칸 하나."""

    use_tag: str
    slot_index: int
    catalog_id: str | None = None
    label_ko: str = ""
    grade: str = ""
    charges: int = 0
    charge_max: int = 0
    # 이 칸을 가득 채우는 값. 빈 칸은 0 이다 — 끼운 것이 없으면 채울 것도 없다.
    refill_cost: int = 0
    # 끼우고 있는 동안 붙는 부가 옵션. **충전이 0 이어도 붙는다.** 처음에는 파손된 장비에
    # 빗대 「다 쓰면 사라진다」로 적어 뒀는데 그 비유가 틀렸고, 코드는 이미 반대로 돈다
    # (`list_loaded_consumables`) — 사라지게 두면 안 마시는 것이 이득이 된다. 보충은
    # 능력치를 되찾으려고가 아니라 다시 마실 수 있으려고 하는 것이다.
    affixes: list[str] = []
    # **견줌용 원본 절.** `affixes` 는 「튼튼함 +8」 처럼 적어 둔 것이라 능력치 축이 안
    # 담긴다. 그것만 보내면 화면이 두 소모품을 스탯별로 견줄 수 없어 문자열 두 벌을
    # 나란히 놓고 판단을 통째로 사람에게 넘기게 된다 — 가방이 이미 구조화된 절로
    # 견주고 있으므로(`CompareRow`), 같은 질문에 두 화면이 다른 방식으로 답하면 안 된다.
    affix_rows: list[dict] = []


class ConsumableOption(BaseModel):
    """가방에 있어 칸에 끼울 수 있는 소모품 한 종류."""

    catalog_id: str
    label_ko: str
    grade: str
    use_tag: str
    charges: int
    # 가방에 몇 개 있는가. 끼우면 하나 줄어든다.
    stock: int
    # 하나를 팔면 받는 값.
    sell_price: int
    # 끼우면 붙는 부가 옵션. 끼우기 전에 무엇이 붙는지 알아야 고를 수 있다.
    affixes: list[str] = []
    # 견줌용 원본 절. `ConsumableSlotView.affix_rows` 와 같은 이유다.
    affix_rows: list[dict] = []


class ConsumableResponse(BaseModel):
    """소모품 칸 화면 전체."""

    slots: list[ConsumableSlotView]
    options: list[ConsumableOption]
    balance: int
    # 빈 칸이 출격 때 공짜로 받는 충전 수.
    free_charges: int
    # 런이 도는 중이면 참. 이때는 끼우기·보충이 막힌다 (§5).
    is_run_open: bool = False


class ConsumableSlotRequest(BaseModel):
    """칸 하나를 가리키는 요청."""

    use_tag: str
    slot_index: int
    # 끼울 소모품. 비우기·보충에는 없다.
    catalog_id: str | None = None


class ConsumableSellRequest(BaseModel):
    """가방의 소모품을 판다."""

    catalog_id: str
    count: int = 1


class MaintenanceRowView(BaseModel):
    """정비 규칙 한 행."""

    action: str
    grade: str = ""


class MaintenanceView(BaseModel):
    """정비 규칙 화면·요청 겸용. 행 순서가 실행 순서다."""

    rows: list[MaintenanceRowView] = []


class SkillRowView(BaseModel):
    """스킬 세팅 한 줄."""

    skill_id: str
    is_on: bool = True
    # 기본 공격은 끌 수 없다 — 폴백이 기댄다.
    is_locked: bool = False


class SkillPrefView(BaseModel):
    """스킬 세팅 화면·요청 겸용."""

    rows: list[SkillRowView] = []


class MaintenanceRunView(BaseModel):
    """손으로 돌린 정비의 결과.

    **한 줄뿐이다.** 무엇이 바뀌었는지는 가방·소모품을 다시 읽어서 안다 — 여기에 바뀐
    상태를 실으면 화면이 두 곳에서 같은 것을 읽게 되고, 둘이 어긋나는 날이 온다.
    """

    detail: str = ""
