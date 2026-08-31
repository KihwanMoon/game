"""관리자·도감이 쓰는 응답 절.

`schemas.py` 에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 **게임을 도는 계약**
(제출·티켓·인벤토리)이고, 이쪽은 **세계를 들여다보는 창**이다. 저쪽은 TS 로 이식되는
자산이고 이쪽은 아니다 (TDD §3).
"""

from pydantic import BaseModel, Field


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


class DiscoveryRow(BaseModel):
    """도감 한 줄. 밝혔든 아니든 자리는 있다."""

    kind: str
    ref_id: str
    label_ko: str
    category: str = ""
    is_found: bool = False
    # 밝힌 뒤에만 채운다. 안 밝힌 것의 성능이 다 보이면 도감이 상점이 된다.
    detail: str = ""


class DiscoveryResponse(BaseModel):
    """도감 한 화면."""

    items: list[DiscoveryRow] = Field(default_factory=list)
    skills: list[DiscoveryRow] = Field(default_factory=list)
    found: int = 0
    total: int = 0
