"""예고를 화면이 읽는 모양으로 (design/README.md 의 ThreatNotice 계약).

`telegraph.py` 에서 갈라 나왔다. 400줄 상한이 계기였지만 가르는 선은 책임이다 (§4) —
저쪽은 **판이 도는 것**(등록·카운트다운·취소·조회)이고, 이쪽은 **화면이 읽는 것**이다.

색은 정보의 유일한 채널이 될 수 없다. 글리프를 함께 내고 이모지를 안 쓴다.
"""

from dataclasses import dataclass

from game.app.simulation.telegraph import TelegraphBoard

# 이 이하로 남으면 경고를 danger 로 올린다 (design/README.md ThreatNotice).
IMMINENT_TICKS = 1
TONE_DANGER = "danger"
TONE_NEUTRAL = "neutral"
# 색은 정보의 유일한 채널이 될 수 없다 — 글리프를 함께 낸다 (design/README.md).
# 이모지를 쓰지 않는 것도 같은 문서의 규칙이다.
GLYPH_IMMINENT = "▲"
GLYPH_PENDING = "△"


@dataclass(frozen=True)
class ThreatNotice:
    """UI 의 ThreatNotice 가 그대로 받는 값 (design/README.md 컴포넌트 계약).

    LogEntry 가 LogRow 에 대응하듯 이것은 경고 배너에 대응한다. 코어가 남은 틱을
    내지 않으면 UI 는 `3틱 후 피격` 을 그릴 수 없다.
    """

    text: str
    ticks: int
    glyph: str
    tone: str


def build_threat_notice(
    board: TelegraphBoard, position: tuple[int, int], *, foresight_ticks: int = 0
) -> ThreatNotice | None:
    """그 칸에 대한 경고 배너를 만든다 (design/README.md ThreatNotice).

    Args:
        board: 예고 보드.
        position: 기준 좌표. 보통 플레이어가 선 자리다.
        foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

    Returns:
        표시할 경고. 인지 가능한 위험이 없으면 None.
    """
    ticks = board.get_remaining(position, foresight_ticks=foresight_ticks)
    if ticks is None:
        return None
    is_imminent = ticks <= IMMINENT_TICKS
    return ThreatNotice(
        text=f"위험 예고 — {ticks}틱 후 피격",
        ticks=ticks,
        glyph=GLYPH_IMMINENT if is_imminent else GLYPH_PENDING,
        tone=TONE_DANGER if is_imminent else TONE_NEUTRAL,
    )
