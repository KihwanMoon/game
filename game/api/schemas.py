"""HTTP 요청·응답 절 (docs/설계/7_변조방지 §4).

**요청에 결과를 받는 자리를 만들지 않는다.** 여기 필드가 하나 생기면 그것을 믿는 코드가
따라 들어오고, 재시뮬이 형식적인 절차가 된다. `test_api_submission_takes_no_result` 가
되돌아가는 것을 막는다.
"""

from pydantic import BaseModel, Field

from game.schemas.run_ticket import MAX_SEED

# 규칙표 절의 크기 상한. 슬롯 상한이 있으므로 정상 규칙표는 훨씬 작다 — 상한이 없으면
# 거대한 절 하나로 검증기를 묶어 둘 수 있다.
MAX_RULES = 64


class AccountResponse(BaseModel):
    """계정 응답. 토큰은 **만들 때와 로그인할 때만** 나온다.

    `login_id` 가 None 이면 익명 계정이다 — 화면이 "가입하면 지킬 수 있다" 를 그것으로
    판단한다.
    """

    account_id: int
    handle: str
    token: str | None = None
    login_id: str | None = None


class CredentialRequest(BaseModel):
    """가입·로그인 요청.

    길이 상한을 여기서도 건다. 서버가 scrypt 로 늘리므로, 상한이 없으면 긴 문자열
    하나로 CPU 를 묶어 둘 수 있다.
    """

    login_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TicketRequest(BaseModel):
    """티켓 발급 요청.

    `seed` 는 **연습 모드에서만** 반영된다. 순위·데일리는 서버가 정한 시드만 쓰며,
    그것이 T2(유리한 시드 골라 담기)를 막는 지점이다. 연습에서까지 막으면 "이 시드
    다시 해 보기" 와 리플레이 공유가 불가능해지는데, 순위에 반영되지 않는 판에서
    그것을 막을 이유가 없다.
    """

    room_id: str = Field(min_length=1, max_length=64)
    floor: int = Field(default=1, ge=1, le=99)
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)


class TicketResponse(BaseModel):
    """발급된 티켓. 런의 입력 전부가 여기 있다."""

    ticket_id: str
    seed: int
    room_id: str
    floor: int
    mode: str
    core_version: str
    # 이 런이 만날 지속 몬스터의 얼어붙은 상태 (docs/설계/6_몬스터 §5).
    # **제출 때 되보내지 않는다** — 서버가 ticket_id 로 자기 것을 조회한다 (T8).
    monster_snapshot: list[dict] = Field(default_factory=list)


class SubmissionRequest(BaseModel):
    """제출.

    필드가 셋뿐인 것이 설계다. 결과·시드·방·아이템을 받을 자리가 없다.
    """

    ticket_id: str = Field(min_length=1, max_length=128)
    ruleset: dict = Field(description="규칙표 절. 서버가 다시 파싱하고 다시 검증한다.")
    core_version: str = Field(min_length=1, max_length=32)


class SubmissionResponse(BaseModel):
    """서버가 확정한 결과. 클라이언트의 주장은 여기 반영되지 않는다."""

    submission_id: int
    outcome: str
    ticks: int
    player_hp: int
    verdict: str
    detail: str = ""
    # 이 런이 준 것. 아이템은 **서버가 발급한다** (결정 #02).
    reward: str = ""


class MetaResponse(BaseModel):
    """메타 세이브 응답."""

    payload: dict | None
    core_version: str


class MetaRequest(BaseModel):
    """메타 세이브 저장 요청."""

    payload: dict


class RequirementView(BaseModel):
    """요구조건 한 줄. **실측값을 함께 낸다** (docs/설계/4_아이템 §6.1).

    "장착할 수 없습니다" 만 띄우면 무엇이 얼마나 모자란지 알 수 없어 P1 위반이다.
    규칙 에디터의 조건문 표기와 같은 규약을 쓴다.
    """

    stat: str
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
    affixes: list[dict] = Field(default_factory=list)
    requirements: list[RequirementView] = Field(default_factory=list)
    can_equip: bool = False


class InventorySlotView(BaseModel):
    """인벤토리 한 칸 또는 장비 한 자리."""

    slot_index: int
    item: ItemView | None = None
    stack_catalog_id: str | None = None
    stack_count: int = 0
    slot: str | None = None
    # 양손무기가 막은 자리. **저장된 상태가 아니라 계산값이다** (§2.1).
    is_sealed: bool = False


class InventoryResponse(BaseModel):
    """인벤토리·장비·지갑."""

    size: int
    slots: list[InventorySlotView] = Field(default_factory=list)
    equipment: list[InventorySlotView] = Field(default_factory=list)
    balance: int = 0
    repair_cost: int = 0


class EquipRequest(BaseModel):
    """착용·해제 요청."""

    item_id: int = 0
    slot: str = Field(min_length=1, max_length=32)


class ItemActionRequest(BaseModel):
    """아이템 하나를 대상으로 하는 요청."""

    item_id: int


class WalletResponse(BaseModel):
    """지갑."""

    balance: int
    repair_cost: int


class BestiaryEntry(BaseModel):
    """도감 한 줄. **규칙표를 그대로 낸다** — 요약하면 카운터를 설계할 수 없다."""

    record_id: int
    catalog_id: str
    label_ko: str
    tier: str
    level: int
    level_cap: int
    zone_floor: int
    entity_slot: str
    ruleset: dict | None = None
    # 이 개체에 붙은 접사. 등급 배수만으로는 "같은 적인데 숫자가 큰 것" 이다.
    affixes: list[dict] = Field(default_factory=list)
    trophies: list[str] = Field(default_factory=list)
    # 이 개체가 내 아이템을 들고 있는가. 되찾으러 가는 동기가 여기서 나온다.
    holds_mine: bool = False


class BestiaryResponse(BaseModel):
    """도감 전체."""

    entries: list[BestiaryEntry] = Field(default_factory=list)
