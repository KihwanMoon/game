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


class CatalogItemRequest(BaseModel):
    """관리자가 등록·수정하는 아이템 한 줄.

    **파일의 절과 같은 모양이다.** 형식을 따로 만들면 파서가 둘이 되고, 관리자가 만든
    아이템만 다른 규칙으로 검사되는 날이 온다.
    """

    id: str = Field(min_length=1, max_length=64)
    kind: str
    label_ko: str = ""
    slot: str | None = None
    hands: str | None = None
    grade: str = "COMMON"
    min_floor: int = 1
    affixes: list[dict] = Field(default_factory=list)
    requirements: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # 소모품이 무엇으로 쓰이는가 (§4). `USE_ITEM[kind]` 의 파라미터와 같은 값이며,
    # **코드가 읽는 유일한 태그다** — `tags` 는 표시 전용이다.
    use_tag: str | None = None
    grants_skill: str | None = None
    # 무기가 정하는 사거리 (§2.2). None 은 「안 정한다」다 — 0 은 아무것도 못 때리는 무기다.
    attack_range: int | None = Field(default=None, ge=0, le=20)
    stack_max: int = 1
    # 되돌릴 수 없는 조작이다. 사유 없는 개입은 나중에 아무도 설명할 수 없다.
    reason: str = ""


class CatalogRetireRequest(BaseModel):
    """폐기·복구. **삭제가 아니다** — 인스턴스·원장·경매가 이 id 를 가리킨다."""

    catalog_id: str = Field(min_length=1, max_length=64)
    is_retired: bool = True
    reason: str = ""


class CatalogAdminRow(BaseModel):
    """관리자가 보는 카탈로그 한 줄. 굴림에 걸리는 값까지 함께 낸다."""

    catalog_id: str
    kind: str
    label_ko: str
    slot: str = ""
    hands: str = ""
    grade: str
    min_floor: int = 1
    is_retired: bool = False
    affixes: list[str] = Field(default_factory=list)
    # **고치기용 원본 절.** `affixes` 는 「튼튼함 +8」 처럼 적어 둔 것이라 능력치 축이
    # 안 담긴다. 그것만 보고 편집 칸을 채우면 축을 알 길이 없어 첫 항목으로 떨어지고,
    # 이름만 고치려던 편집이 `hp_max` 접사를 `attack` 으로 바꿔 저장한다.
    affix_rows: list[dict] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    grants_skill: str = ""
    # 소모품의 쓰임새 (§4). 빈 문자열이면 어느 `USE_ITEM` 도 이것을 못 쓴다.
    use_tag: str = ""
    # 무기가 정하는 사거리. 0 은 「안 정한다」다 — 화면이 「-」 로 그린다.
    attack_range: int = 0
    # 이 아이템이 드롭 표에서 갖는 가중치. 0 이면 표에 없다 — 굴려도 안 나온다.
    drop_weight: int = 0


class CatalogAdminResponse(BaseModel):
    """카탈로그 관리 화면 하나."""

    items: list[CatalogAdminRow] = Field(default_factory=list)
    generation: int = 0
    grades: list[str] = Field(default_factory=list)
    # 접사가 붙을 수 있는 스탯. **화면이 목록을 따로 들고 있으면 정본이 둘이 된다** —
    # 서버가 아는 이름이 늘어도 화면은 옛 목록을 내보이고, 사람은 그것이 전부라고 읽는다.
    stats: list[str] = Field(default_factory=list)


class ContentDraftRequest(BaseModel):
    """콘텐츠 초안 하나.

    **이것은 아직 게임이 아니다.** 반영은 발행이 하고, 발행은 사람이 파일을 커밋해야
    끝난다 (설계/4_아이템 §15.7 의 반대편).
    """

    asset: str = Field(min_length=1, max_length=32)
    payload: dict
    note: str = ""


class ContentDraftRow(BaseModel):
    """초안 목록 한 줄. 본문은 담지 않는다 — 목록은 목록이다."""

    asset: str
    note: str = ""
    updated_at: str = ""
    # 지금 파일의 세대. 초안의 세대가 이것보다 커야 발행할 수 있다.
    current_version: int = 0


class ContentDraftResponse(BaseModel):
    """콘텐츠 편집 화면 하나."""

    drafts: list[ContentDraftRow] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    # 검증 결과. 빈 문자열이면 통과다.
    problem: str = ""
    # 발행이 사람 손을 탄다는 사실을 화면이 말해야 한다.
    publish_hint: str = ""


class ContentAssetResponse(BaseModel):
    """자산 하나의 지금 내용과 초안.

    **지금 파일을 함께 낸다.** 편집은 백지가 아니라 지금 것에서 시작해야 하고, 화면이
    그것을 모르면 관리자가 손으로 옮겨 적게 된다 — 그 순간 오타가 콘텐츠가 된다.
    """

    asset: str
    current: dict = Field(default_factory=dict)
    draft: dict | None = None
    note: str = ""
    version_key: str = ""


class MonsterDropRequest(BaseModel):
    """몬스터별 드롭 줄 하나 (D3).

    **가중치 0 은 지우는 것이 아니라 안 나오게 하는 것이다.** 줄을 지우면 "이 몬스터가
    무엇을 떨구기로 되어 있었는가" 를 나중에 못 읽는다.
    """

    kind_id: str = Field(min_length=1, max_length=64)
    grade: str
    catalog_id: str
    weight: int = Field(ge=0, le=100_000)
    reason: str = ""


class MonsterDropRow(BaseModel):
    """드롭 줄 하나."""

    grade: str
    catalog_id: str
    label_ko: str = ""
    weight: int = 0


class MonsterDropResponse(BaseModel):
    """한 몬스터의 드롭 표."""

    kind_id: str
    rows: list[MonsterDropRow] = Field(default_factory=list)
    # 소스별 표가 없으면 ANY 로 떨어진다. 그 사실이 화면에 있어야 "왜 다른 게 나오지" 를
    # 안 겪는다.
    uses_default: bool = True


class ContentPublishRequest(BaseModel):
    """발행. **세대를 한 번 받는다** (설계/4_아이템 §18).

    여러 자산을 고쳐 두고 한 번에 낸다 — 자산마다 세대를 올리면 관리자가 셋을 고치는
    동안 세 번 올리게 되고, 그건 이르고 불편하다.
    """

    generation: int = Field(ge=1, le=100_000)
    note: str = ""


class ContentPublishResponse(BaseModel):
    """발행 결과."""

    generation: int = 0
    published: list[str] = Field(default_factory=list)
    core_version: str = ""
    problem: str = ""


class ContentPackResponse(BaseModel):
    """브라우저가 받아 가는 콘텐츠 팩.

    **코어 버전을 함께 낸다.** 브라우저가 그것을 다시 조립하면 두 곳이 갈리고, 갈린
    티켓은 제출에서 거절된다.
    """

    assets: dict = Field(default_factory=dict)
    generation: int = 0
    core_version: str = ""


class CatalogEditRequest(BaseModel):
    """이미 있는 아이템에서 **고칠 수 있는 것만** 담는 절 (설계/4_아이템 §15.7·§15.11).

    `kind`·`slot`·`hands` 를 받을 자리가 없다. 그 셋은 **이미 착용된 자리**를 가리키므로,
    투구를 갑옷으로 바꾸면 누군가의 머리 칸에 갑옷이 들어 있게 된다.

    접사·등급은 받는다. 인스턴스가 자기 접사·등급을 갖게 된 뒤로(§15.11) 카탈로그 수정이
    이미 나온 아이템에 소급하지 않는다 — 앞으로 나올 것에만 걸린다.
    """

    catalog_id: str = Field(min_length=1, max_length=64)
    label_ko: str = Field(min_length=1, max_length=64)
    min_floor: int = Field(ge=1, le=100)
    grade: str = ""
    affixes: list[dict] = Field(default_factory=list)
    # 무기 사거리. **안 보내면 지금 값을 그대로 둔다** — 0 을 「안 정함」으로 읽으면
    # 이름만 고치려던 요청이 활을 근접무기로 만든다.
    attack_range: int | None = Field(default=None, ge=0, le=20)
    # 소모품의 쓰임새. **안 보내면 지금 값을 그대로 둔다** — 빈 문자열을 「없앤다」로
    # 읽으면 이름만 고치려던 요청이 물약을 못 쓰는 것으로 만든다.
    use_tag: str | None = Field(default=None, max_length=32)
    reason: str = ""
