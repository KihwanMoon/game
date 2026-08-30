"""살아 있는지 보는 라우트."""

from fastapi import APIRouter

from game.api.deps import get_core_version

router = APIRouter()


@router.get("/api/health")
def read_health() -> dict:
    """살아 있는지 본다.

    Returns:
        상태와 코어 버전.
    """
    return {"status": "ok", "core_version": get_core_version()}
