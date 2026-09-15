"""둔갑의 전적 I/O 계약 — **돌아오는 길** (2026-09-15).

`schemas.py` 에서 갈라 나왔다. 파일이 400줄을 넘은 것이 계기였을 뿐, 가르는 선은
책임이다 (§4) — 이 셋은 「내 내력이 남의 장에서 무엇을 했는가」 하나만 말한다.

**성장은 안 담는다.** 레벨·장비는 다른 응답이 이미 낸다. 여기 담기는 것은 이 게임에서
**유일하게 성장과 무관한 사실**이다.
"""

from pydantic import BaseModel


class DoppelStanding(BaseModel):
    """지금 서 있는 내 둔갑 하나."""

    record_id: int
    floor: int
    level: int
    lives: int


class DoppelBout(BaseModel):
    """내 둔갑이 만난 한 판."""

    floor: int
    is_doppel_win: bool
    opponent: str
    at: str


class DoppelRetirement(BaseModel):
    """물러난 내 둔갑 하나와 그것이 남긴 활자.

    **활자는 `won` 과 같은 수다.** 따로 안 싣는 이유는 둘이 갈릴 자리를 안 만들기
    위해서다 — 정산이 승수를 그대로 준다(`letters.apply_doppel_settlement`).
    """

    record_id: int
    floor: int
    won: int
    lost: int
    at: str


class MyDoppelResponse(BaseModel):
    """내 둔갑의 지금과 전적.

    **성장과 무관한 사실만 담는다.** 레벨·장비가 아니라 「내가 적은 것이 남의 장에서
    무엇을 했는가」다 — 그것이 이 응답의 이유다.
    """

    standing: list[DoppelStanding]
    met: int
    won: int
    recent: list[DoppelBout]
    retired: list[DoppelRetirement]
    is_opted_in: bool
