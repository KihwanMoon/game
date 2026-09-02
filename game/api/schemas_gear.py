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
    # 끼우고 있는 동안 붙는 부가 옵션. **충전이 0 이면 비어 있다** — 다 쓴 물약은 파손된
    # 장비와 같아서, 효과가 남으면 보충비가 뜻을 잃는다.
    affixes: list[str] = []


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
