"""층 보상 절 (GDD §2.2, 2026-09-11).

`schemas.py` 에서 갈라 나왔다. 저쪽은 **런 제출**이고 여기는 **층을 깨고 무엇을
고르는가**다 — 파일이 400줄 상한을 넘은 것이 계기였을 뿐, 가르는 선은 책임이다 (§4).

**고른 것만 받는다.** 후보는 티켓 시드와 층에서 나오므로 서버가 되굴려 확인한다 —
없는 보상을 적어 보낼 자리가 없다 (설계/7 §4).
"""

from pydantic import BaseModel


class RewardOfferView(BaseModel):
    """보상 후보 하나. 화면이 그대로 그린다."""

    reward_id: str
    label_ko: str
    target_stat: str
    amount: int


class RewardChoiceResponse(BaseModel):
    """선택이 반영된 뒤의 이 런 보너스."""

    floor: int
    reward_id: str
    # 축에서 더해진 값으로. 화면이 한도(규칙 줄·cpu)를 그때그때 다시 그린다.
    bonus: dict[str, int] = {}


class RewardChoiceRequest(BaseModel):
    """층 보상 선택.

    **고른 것만 보낸다.** 후보는 티켓 시드와 층에서 나오므로 서버가 되굴려 확인한다.
    없는 보상을 적어 보낼 자리가 없다 (설계/7 §4).
    """

    ticket_id: str
    floor: int
    reward_id: str
