"""지나간 판을 다시 돌리는 절 (결정 #09).

`schemas.py` 에서 갈라 나왔다. 저쪽은 **지금 상태를 주고받는 절**이고 여기는 **지나간
판을 재현하는 절**이다 — 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는 선은 책임이다
(§4). `schemas_gear.py` 와 같은 자리다.

**결과가 아니라 입력이다.** 이벤트 로그는 저장하지 않으므로 재생은 「그때 찍은 화면을
트는 것」이 아니라 같은 입력으로 다시 돌리는 것이다 — 코어가 결정론이라 같은 입력이면
같은 판이 나온다 (R5·G3).
"""

from pydantic import BaseModel, Field


class ReplayResponse(BaseModel):
    """지나간 판 하나를 **다시 돌릴 수 있는 입력 전부**.

    **결과가 아니라 입력이다.** 이벤트 로그는 저장하지 않으므로 재생은 「그때 찍은 화면을
    트는 것」이 아니라 **같은 입력으로 다시 돌리는 것**이다 — 코어가 결정론이라 같은
    입력이면 같은 판이 나온다 (R5·G3). 그래서 서버가 돌려주는 것도 결과가 아니라 입력이고,
    그 입력은 전부 **티켓의 것**이다: 제출이 실어 온 것은 규칙표 하나뿐이다 (§4).
    """

    submission_id: int
    ruleset: dict = Field(default_factory=dict)
    room_id: str
    seed: int
    floor: int
    rooms_per_floor: int
    room_ids: list[str] = Field(default_factory=list)
    loadout: dict = Field(default_factory=dict)
    # 티켓이 얼려 둔 지속 몬스터. **이것이 없으면 재생이 다른 판을 돈다** — 화면은 기본
    # 적을 그리는데 그때는 엘리트가 서 있었다 (설계/6_몬스터 §5).
    snapshots: list[dict] = Field(default_factory=list)
    # 그때 확정된 결과. 재생이 같은 답을 내는지 눈으로 대조할 수 있어야 한다.
    outcome: str
    ticks: int
    player_hp: int


class RunHistoryRow(BaseModel):
    """내가 돈 판 한 줄.

    **이벤트 로그는 없다.** 저장하는 것은 제출(규칙표)과 판정(결과)뿐이라 여기 낼 수
    있는 것은 「어떤 판을 돌았고 어떻게 끝났는가」까지다 — 「어떻게 돌았는가」는 시드와
    규칙표로 다시 돌려야 나온다. 그것이 재생이다.
    """

    submission_id: int
    room_id: str
    floor: int
    seed: int
    outcome: str
    ticks: int
    player_hp: int
    # 판정이 없는 제출도 낸다. 검증 전인 것과 없는 것이 같아 보이면, 서버가 밀렸을 때
    # 화면이 「안 돌았다」로 읽힌다.
    verdict: str
    submitted_at: str


class RunHistoryResponse(BaseModel):
    """최근에 돈 판들. 새것부터다."""

    runs: list[RunHistoryRow] = Field(default_factory=list)
