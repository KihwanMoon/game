"""지킴이·배포봇 화면 라우트 (설계/9_에이전트_운영 §4.1·§4.5).

**로그에서 죽고 있었다.** 지킴이는 5분마다 정확히 판단해 컨테이너 로그에 뱉었고,
컨테이너 로그를 읽는 사람은 없다 (알려진이슈 Z1).

관리 화면의 `overview` 는 **수치는 있는데 소견이 없다.** 「매물 3건」은 있지만 「그
3건이 우선권 창을 지나도록 안 팔린다」는 없다. 그 판단을 지킴이가 이미 하고 있다.

**게이트는 여기서 안 돌린다.** 라우트가 `pytest`·`npm` 을 띄우면 그 API 가 임의 실행
통로가 된다 — 배포봇의 **세계 쪽 절반**만 보이고, 게이트는 복사할 명령으로 둔다.

읽기 전용이라 등급은 `observer` 로 족하다 (§3.1).
"""

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from game.api.deps import CurrentAdmin, get_pool
from game.app.deploy.briefing import (
    GATES,
    list_authors,
    list_breakage,
    list_changes,
    list_undo,
)
from game.app.store.content_draft import DRAFT_ASSETS
from game.app.store.deploy import read_deploy_state
from game.app.store.watch_log import list_watch_events, list_watch_state

router = APIRouter()

# 화면에 뿌릴 최근 변화 수. 등급이 바뀔 때만 쌓이므로 이 정도면 며칠치가 된다.
MAX_EVENTS = 30


class WatchRowView(BaseModel):
    """지표 하나의 지금 상태."""

    key: str
    level: str
    text: str
    detail: str
    # 이 등급이 된 때. **「어제 낮부터 틀렸다」가 여기서 읽힌다.**
    changed_at: str
    # 마지막으로 본 때. 오래됐으면 지킴이 자신이 안 도는 것이다.
    seen_at: str


class WatchEventView(BaseModel):
    """등급이 바뀐 순간 하나."""

    key: str
    level: str
    text: str
    detail: str
    happened_at: str


class DeployView(BaseModel):
    """배포 전에 알아야 하는 것 — 게이트를 뺀 절반.

    컨펌에 올리는 넷 중 셋(무엇이 바뀌는가·누가 만들었는가·무엇이 깨지는가)과 넷째
    (되돌리는 법)가 여기 있다. **넷째가 없으면 컨펌이 아니라 도박이다** (§4.5).
    """

    changes: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    breakage: list[str] = Field(default_factory=list)
    undo: list[str] = Field(default_factory=list)
    # 게이트는 화면이 안 돌린다. 사람이 그대로 옮겨 칠 명령만 준다.
    gate_commands: list[str] = Field(default_factory=list)
    open_runs: int = 0


class WatchResponse(BaseModel):
    """지킴이 화면 한 벌."""

    rows: list[WatchRowView] = Field(default_factory=list)
    events: list[WatchEventView] = Field(default_factory=list)
    deploy: DeployView


def read_asset_files() -> dict[str, dict]:
    """저장소의 실행 자산 파일들을 읽는다.

    DB 의 발행본과 견주는 데 쓴다 — 발행만 하고 파일화를 안 하면 브라우저의 오프라인
    폴백이 다른 게임을 돈다 (§4.5).

    Returns:
        자산 이름에서 절로의 대응표. 없는 파일은 뺀다.
    """
    found = {}
    for asset, (path, _version_key) in DRAFT_ASSETS.items():
        source = Path(path)
        if source.exists():
            found[asset] = json.loads(source.read_text(encoding="utf-8"))
    return found


@router.get("/api/admin/watch", response_model=WatchResponse)
def read_watch(account: CurrentAdmin) -> WatchResponse:
    """지킴이가 남긴 것과 배포 전 브리핑을 함께 준다.

    **다시 계산하지 않는다.** 지킴이가 5분마다 남긴 것을 읽는다 — 화면이 열릴 때마다
    새로 재면 그 주기가 무의미해지고, 「이게 언제부터 이랬나」를 여전히 못 답한다.

    Args:
        account: 관리자. 아니면 의존성이 404 로 끊는다.

    Returns:
        지표들·바뀐 순간들·배포 브리핑.
    """
    pool = get_pool()
    reading = read_deploy_state(pool, read_asset_files())
    return WatchResponse(
        rows=[
            WatchRowView(
                key=row.key,
                level=row.level,
                text=row.text,
                detail=row.detail,
                changed_at=row.changed_at,
                seen_at=row.seen_at,
            )
            for row in list_watch_state(pool)
        ],
        events=[
            WatchEventView(
                key=event.key,
                level=event.level,
                text=event.text,
                detail=event.detail,
                happened_at=event.happened_at,
            )
            for event in list_watch_events(pool, MAX_EVENTS)
        ],
        deploy=DeployView(
            changes=list(list_changes(reading)),
            authors=list(list_authors(reading)),
            breakage=list(list_breakage(reading)),
            undo=list(list_undo(reading)),
            gate_commands=[" ".join(gate.command) for gate in GATES],
            open_runs=reading.open_runs,
        ),
    )
