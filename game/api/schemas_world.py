"""세계 탭이 쓰는 절 — 맥박·순위·오늘의 도전.

`schemas.py` 에서 갈라 나왔다. 400줄 상한이 계기였지만 **가르는 선은 책임이다**
(§4) — 저쪽은 한 사람의 일(계정·티켓·제출·성장)이고 여기는 **나 밖의 일**이다.
`schemas_replay.py` 를 뗀 것과 같은 결이며, 세계 탭이 화면에서 갈라져 있는 것과도
같은 선이다.
"""

from pydantic import BaseModel, Field


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


class DailyRow(BaseModel):
    """오늘의 도전 순위 한 줄."""

    rank: int
    handle: str
    floor: int
    account_id: int


class DailyBoardResponse(BaseModel):
    """오늘의 도전 상태 — 내 것과 남의 것.

    **같은 판을 다 같이 돈다는 사실이 화면에 있어야 한다.** 그러지 않으면 데일리는
    그냥 「어제와 다른 한 판」이고, 내일 다시 올 이유가 되지 못한다.
    """

    day: str
    # 이 판을 잡은 사람 수. 윗자리만 보여 주면 혼자인지 백 명인지 모른다.
    players: int = 0
    rows: list[DailyRow] = []
    # 내가 오늘 티켓을 받았는가. 안 받았으면 아래 둘은 뜻이 없다.
    has_entry: bool = False
    my_floor: int = 0
    my_rank: int = 0


class LeaderboardResponse(BaseModel):
    """순위표. `core_version` 이 시즌 이름이다 (결정 #06)."""

    mode: str
    core_version: str
    entries: list[dict] = Field(default_factory=list)
