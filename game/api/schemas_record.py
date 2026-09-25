"""방별 기록판의 입출력 (2026-09-25)."""

from pydantic import BaseModel, Field


class RecordTicketRequest(BaseModel):
    """기록 도전 티켓 요청. **방만 고른다** — 시드·몸·층은 서버가 정한다."""

    room_id: str = Field(min_length=1, max_length=64)


class RoomRecordRow(BaseModel):
    """기록판 한 줄."""

    rank: int
    handle: str
    cpu: int
    ticks: int
    rule_count: int
    # 이 기록을 세운 규칙표의 공유 주소. `/r/{share_id}` 로 열린다.
    share_id: str
    account_id: int


class RoomRecordBoard(BaseModel):
    """한 방의 기록판."""

    room_id: str
    core_version: str
    players: int
    entries: list[RoomRecordRow]
    # 내 기록. **윗자리 밖이어도 싣는다.** 없으면 None.
    mine: RoomRecordRow | None = None
