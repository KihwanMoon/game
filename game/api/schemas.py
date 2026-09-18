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
    # 사람이 고른 이름. None 이면 아직 안 정했다.
    nickname: str | None = None
    # **화면에 실제로 뜨는 이름** (2026-09-16). 닉네임 → 아이디 → 자동 별명 순으로 고른다.
    #
    # 서버가 정해서 보내는 이유는 **정본을 하나로 두기 위해서다**. 화면마다 제 순서를 들면
    # 순위표는 아이디를, 둔갑 전적은 자동 별명을 보여 주게 되고 — 실제로 그랬다 — 같은
    # 사람이 화면을 옮길 때마다 다른 이름이 된다.
    display_name: str = ""
    # 내 빌드가 남의 던전에 그림자로 서도 되는가 (2026-09-06). **기본은 꺼져 있다** —
    # 그림자는 원본의 규칙표로 싸우므로 관전하며 행동을 보면 해답이 어느 정도 역산된다.
    doppel_opt_in: bool = False
    # 이 계정이 구글에 묶여 있는가 (2026-09-16).
    #
    # **성공이 안 보이면 다시 누른다.** 구글로 들어온 계정은 `login_id` 가 없어서, 화면이
    # 익명과 구별하지 못하고 구글 버튼을 계속 세워 두었다 — 실제로 성공한 로그인(200)
    # 11초 뒤에 같은 사람이 다시 눌렀고, 그 두 번째가 죽은 논스로 떨어졌다. 들어와 있다는
    # 사실을 화면이 말할 수 있어야 한다.
    has_google: bool = False


class WorldPulseResponse(BaseModel):
    """세계에 사람이 얼마나 오는가 (2026-09-17).

    **로그인 없이도 본다.** 「여기 사람이 사는가」는 들어오기 전에 가장 궁금한 것이고,
    그 답을 계정을 만든 뒤에만 주면 늦다.
    """

    visitors: int = 0
    joined: int = 0
    fresh_today: int = 0
    fresh_week: int = 0
    runs: int = 0
    # 창 안의 깔때기. **`visitors` 와 다른 것을 센다** — 저쪽은 출격을 누른 사람이고
    # `window_visits` 는 열어 본 사람이다(Cloudflare 가 엣지에서 센 값).
    window_days: int = 0
    window_visits: int = 0
    window_played: int = 0
    # 정수다. 부동소수를 피하는 규율이기도 하고, 화면에 적을 것이 한 자리 정수다.
    conversion_pct: int = 0
    # 화면이 출처를 밝힐 수 있어야 한다 — 계측을 갈아 끼우는 날 수가 점프하는데,
    # 출처가 안 적혀 있으면 보는 사람이 그것을 「갑자기 대박」으로 읽는다.
    traffic_source: str = ""


class StorySeenRequest(BaseModel):
    """장 카드 하나를 봤다고 남기는 요청.

    **카드 id 의 정본은 화면이다** — 서버는 이야기의 목록을 안 들고 있다. 담기는 것은
    판정에 아무 영향이 없는 문자열 하나다.
    """

    card_id: str


class StorySeenResponse(BaseModel):
    """이미 본 카드들."""

    seen: list[str] = Field(default_factory=list)


class NicknameRequest(BaseModel):
    """닉네임을 정하는 요청."""

    nickname: str


class CredentialRequest(BaseModel):
    """가입·로그인 요청.

    길이 상한을 여기서도 건다. 서버가 scrypt 로 늘리므로, 상한이 없으면 긴 문자열
    하나로 CPU 를 묶어 둘 수 있다.
    """

    login_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class GoogleAuthRequest(BaseModel):
    """구글로 들어오는 요청.

    **결과를 받을 자리가 없다.** 이메일도 이름도 계정 id 도 안 받는다 — 받는 것은 구글이
    서명한 토큰과 서버가 발급했던 논스뿐이고, 누구인지는 서버가 그 서명에서 읽는다
    (설계/7_변조방지 §4).
    """

    credential: str
    nonce: str


class NonceResponse(BaseModel):
    """일회용 논스."""

    nonce: str


class GoogleConfigResponse(BaseModel):
    """구글 로그인이 켜져 있는가, 그리고 어느 클라이언트 id 인가.

    **클라이언트 id 는 공개값이다** — 구글 버튼이 그것을 그대로 싣는다. 화면이 빌드 시점에
    박아 두지 않고 서버에서 받는 이유는 **정본을 하나로 두기 위해서다**: 서버가 `aud` 를
    그 값으로 검증하므로, 둘이 갈리면 화면은 멀쩡한데 로그인만 조용히 실패한다.
    """

    is_enabled: bool
    client_id: str


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
    # 층 하나에 드는 방 수. **화면과 서버가 같은 값을 봐야 한다** — 방 순번에서 층을
    # 파생하므로, 갈리면 화면과 서버가 다른 층으로 같은 방을 돈다 (G3).
    rooms_per_floor: int = 3
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
    # **여기까지 깼다고 주장하는 층** (로드맵 W14). 주장일 뿐이고 서버가 처음부터 그
    # 층까지 다시 돌려 확정한다 — 결과를 받을 자리는 여전히 없다.
    #
    # 0 은 「하강 전체」다. 층 개념이 없던 옛 클라이언트가 그 길로 온다.
    floor: int = Field(default=0, ge=0, le=99)


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
    # 능력치를 무르는 값 (2026-09-17). **화면이 미리 알아야 한다** — 누르고 나서 400 을
    # 받으면 「왜 안 되지」가 되고, 값을 모르면 낼지 말지를 고를 수가 없다.
    respec_cost: int = 0
    # 1장을 깨기 전인가. 그 전까지는 무르기가 공짜다 (`progression/levels`).
    respec_is_free: bool = True
    # **여기까지 내려가 봤다** (설계/6_몬스터 §3). 서버만 올린다.
    reached_floor: int = 1
    # 마지막 층. 화면이 「7 / 10」 을 그리려면 끝을 알아야 한다.
    floor_cap: int = 1
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
    # **누가 내놓았는가.** 값만 보이면 한 사람이 시세를 쥐고 있어도 화면이 그것을 안 말한다.
    seller_name: str = ""
    # **사기 전에 알아야 하는 것들.** 이름과 값만 보고 사면 같은 「장궁」이라도 무엇이
    # 붙어 있는지 모르고, 언제 사라질지도 모른다.
    affixes: list[dict] = Field(default_factory=list)
    # **무기가 정하는 사거리** (§2.2). 접사가 아니라 필드라, 안 보내면 활과 단검이
    # 같아 보인다 — 값을 매기는 쪽에서 이것이 가장 무거운 항이다 (`GEAR_PRIORITY_WEIGHTS`).
    attack_range: int = 0
    # 한 손인가 양손인가. **양손무기는 보조 칸을 봉인한다** — 사고 나서야 알면 방패가
    # 조용히 죽는다. 봇도 이 값을 보고 못 끼울 것을 안 산다 (`check_blocked_by_hands`).
    hands: str = ""
    # **이 장비가 여는 재주** (2026-09-17). 없으면 빈 문자열이다.
    #
    # 사기 전에 알아야 하는 것 중 **가장 큰 것**인데 안 보내고 있었다 — 같은 값이면
    # 재주가 붙은 쪽을 산다. 서버는 카탈로그에서 이미 알고 있었다.
    grants_skill: str = ""
    # 남은 시간(분). 절대 시각이 아니라 남은 양으로 보내는 이유는 기기 시계가 어긋나도
    # 같은 값을 보여야 하기 때문이다.
    expires_in_minutes: int = 0
    # 걸 때 떼는 수수료. 화면이 다시 계산하면 두 곳이 갈린다.
    fee: int = 0
    # **어느 자리 물건인가.** 이것이 없으면 화면이 「지금 낀 것과 견주기」를 할 수 없다 —
    # 견줄 상대를 못 찾는다. 서버는 카탈로그에서 이미 알고 있었고 안 보내고 있었다.
    slot: str = ""
    # 급. 가방 격자가 이름을 등급색으로 칠하는데, 매물만 그 색을 못 쓰고 있었다.
    grade: str = ""


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


class AdminBotView(BaseModel):
    """관리 화면이 보는 봇 한 줄.

    성격(규칙표·실력)보다 **결과**가 먼저다 — 몇 판을 돌았고 몇 번 이겼는가. 승리가
    0이면 그 봇은 세계에 아무것도 안 남긴다.
    """

    account_id: int
    handle: str
    label: str
    ruleset_id: str
    cadence_sec: int
    skill_pct: int
    is_active: bool
    due_in_sec: int
    runs: int
    wins: int
    best_floor: int
    balance: int
    items: int


class AdminDoppelView(BaseModel):
    """관리 화면이 보는 도플갱어 한 줄."""

    record_id: int
    zone_floor: int
    level: int
    alive: bool
    entity_slot: str
    origin_handle: str
    # 남은 목숨. 잡을 때마다 하나 줄고 다 쓰면 지워지므로 **여기 보이는 것은 늘 1 이상**이다.
    lives: int = 1


class AdminBotOverviewResponse(BaseModel):
    """봇·도플갱어 현황."""

    # 상한을 함께 싣는다. 화면이 제 값으로 적으면 서버가 물리는 값과 갈릴 수 있다.
    max_runs_per_hour: int
    min_cadence_sec: int
    bots: list[AdminBotView]
    doppels: list[AdminDoppelView]
