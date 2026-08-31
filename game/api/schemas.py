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
    # 장비·레벨이 확정한 플레이어 전투 입력 (결정 #13). **제출 때 되보내지 않는다** —
    # 서버가 ticket_id 로 자기 것을 조회한다.
    loadout: dict | None = None
    # 이 런이 도는 방들 (로드맵 W3). 브라우저가 이 목록대로 이어 돌고 서버가 같은
    # 목록으로 재시뮬한다 — 여기가 비면 브라우저는 세 방, 서버는 한 방을 돈다.
    room_ids: list[str] = Field(default_factory=list)


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
    # 거래 후 귀속 (결정 #07). **팔기 전에 보여야 한다** — 모르면 걸다가 거절당하고,
    # 그때는 이미 "왜 안 되지" 를 겪은 뒤다.
    is_bound: bool = False
    # 빼앗겼다가 되찾은 것 (`설계/6_몬스터` §5). 되찾으러 간 런이 가방에 남는다.
    is_recovered: bool = False
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
    # **얼마나 센가.** 규칙표만으로는 "어떻게 싸우는가" 만 알 수 있고, 이길 수 있는지는
    # 알 수 없다 — 도감이 표적 목록이려면 둘 다 필요하다 (`설계/6_몬스터` §8).
    hp_max: int = 0
    attack: int = 0
    defense: int = 0
    trophies: list[str] = Field(default_factory=list)
    # 이 개체가 내 아이템을 들고 있는가. 되찾으러 가는 동기가 여기서 나온다.
    holds_mine: bool = False


class BestiaryResponse(BaseModel):
    """도감 전체."""

    entries: list[BestiaryEntry] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    """플레이어 성장. **레벨이 표현력과 능력치 포인트를 함께 준다** (기획 §0.1)."""

    entity_id: int
    level: int
    total_xp: int
    remaining_xp: int
    next_xp: int
    stats: dict = Field(default_factory=dict)
    bonus_rule_slots: int = 0
    bonus_cpu: int = 0
    bonus_flags: int = 0
    stat_points: int = 0
    spent_points: int = 0
    # 배분할 수 있는 능력치. 무엇을 여는지는 `progression/attributes.py` 가 정한다 (#51).
    stat_keys: list[str] = Field(default_factory=list)
    # **지금 이 캐릭터의 확정 전투 입력.** 에디터가 CPU·슬롯 한도를 여기서 읽는다 —
    # 기본값으로 두면 레벨·장비로 늘어난 한도가 에디터에 안 보이고, 보이더라도 제출이
    # 반려된다. 규칙 검증은 클라이언트와 서버가 **같은 한도**를 봐야 한다.
    loadout: dict = Field(default_factory=dict)


class AllocationRequest(BaseModel):
    """능력치 배분 요청."""

    stats: dict[str, int] = Field(default_factory=dict)


class LeaderboardResponse(BaseModel):
    """순위표. `core_version` 이 시즌 이름이다 (결정 #06)."""

    mode: str
    core_version: str
    entries: list[dict] = Field(default_factory=list)


class ListingView(BaseModel):
    """매물 한 건."""

    listing_id: int
    item_id: int
    catalog_id: str
    label_ko: str
    price: int
    is_mine: bool = False
    # **사기 전에 알아야 하는 것들.** 이름과 값만 보고 사면 같은 「장궁」이라도 무엇이
    # 붙어 있는지 모르고, 언제 사라질지도 모른다.
    affixes: list[dict] = Field(default_factory=list)
    # 남은 시간(분). 절대 시각이 아니라 남은 양으로 보내는 이유는 기기 시계가 어긋나도
    # 같은 값을 보여야 하기 때문이다.
    expires_in_minutes: int = 0
    # 걸 때 떼는 수수료. 화면이 다시 계산하면 두 곳이 갈린다.
    fee: int = 0


class AuctionResponse(BaseModel):
    """경매장. 수수료율을 함께 낸다 — 걸기 전에 얼마가 나가는지 알아야 한다."""

    listings: list[ListingView] = Field(default_factory=list)
    balance: int = 0
    fee_percent: int = 0


class AuctionListRequest(BaseModel):
    """경매 등록 요청."""

    item_id: int
    price: int = Field(gt=0, le=1_000_000)


class ListingAction(BaseModel):
    """매물 하나를 대상으로 하는 요청."""

    listing_id: int


class AdminMonsterView(BaseModel):
    """관리자 화면의 몬스터 한 줄."""

    record_id: int
    catalog_id: str
    tier: str
    zone_floor: int
    entity_slot: str
    level: int
    # 그 층의 상한. **함께 보내야 한다** — 레벨만 보면 그것이 높은 값인지 알 수 없다.
    level_cap: int
    total_xp: int
    alive: bool
    # 이 개체가 들고 있는 아이템 수. 남의 장비를 들고 있는 것이 World Loop 의 동기다.
    held_items: int


class AdminActionView(BaseModel):
    """관리자가 세계에 손댄 기록 한 줄."""

    handle: str
    action: str
    target: str
    detail: str
    created_at: str


class AdminHeldItemView(BaseModel):
    """몬스터가 들고 있는 아이템 한 줄."""

    item_id: int
    record_id: int
    monster_id: str
    catalog_id: str
    # 누구에게서 빼앗았는가. 되찾으러 갈 동기가 World Loop 의 전부다.
    taken_from_handle: str
    is_broken: bool
    is_bound: bool


class AdminOverviewResponse(BaseModel):
    """세계 현황 한 화면.

    **콘텐츠 수치는 읽기 전용이다.** 아이템 카탈로그·적 종류는 `resources/*.json` 이고
    그것은 `core_version` 에 묶여 있다 — 런타임에 바꾸면 이미 발급된 티켓이 다른 게임을
    가리킨다 (결정 #06, R5).
    """

    accounts: int
    registered: int
    entities: int
    monsters_alive: int
    items: int
    items_bound: int
    items_held_by_monsters: int
    listings_open: int
    currency_total: int
    verified_runs: int
    catalog_items: int
    enemy_kinds: int
    core_version: str
    level_counts: list[dict] = Field(default_factory=list)
    monsters: list[AdminMonsterView] = Field(default_factory=list)
    held_items: list[AdminHeldItemView] = Field(default_factory=list)
    recent_actions: list[AdminActionView] = Field(default_factory=list)


class MonsterLevelRequest(BaseModel):
    """지속 몬스터 레벨 조정."""

    record_id: int
    level: int


class AdminReasonRequest(BaseModel):
    """되돌릴 수 없는 개입.

    **사유가 비면 거절한다.** 무엇을 했는지만 남으면 "왜 그랬지" 를 나중에 아무도 답할
    수 없고, 그때 원장은 기록이 아니라 알리바이가 된다.
    """

    target_id: int
    reason: str


class AdminCatalogResponse(BaseModel):
    """콘텐츠 카탈로그 — 읽기 전용이다.

    아이템·적·레벨 곡선은 `resources/*.json` 과 코어 상수이고 `core_version` 에 묶여
    있다 — 런타임에 바꾸면 이미 발급된 티켓이 다른 게임을 가리킨다 (결정 #06, R5).
    """

    core_version: str
    items: list[dict] = Field(default_factory=list)
    enemies: list[dict] = Field(default_factory=list)
    # 레벨 곡선. **실제 인원 분포와 겹쳐서 온다** — 곡선만 보면 튜닝할 수 없다.
    level_curve: list[dict] = Field(default_factory=list)
    caps: dict = Field(default_factory=dict)
