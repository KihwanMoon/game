"""층 진행 결산 (설계/6_몬스터 §3).

`routes/run.py` 에서 갈라 나왔다 — 저쪽은 제출을 받고 재시뮬을 부르는 자리이고, 여기는
**그 결과가 층에 무엇을 하는가** 다. 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는
선은 책임이다 (§4).

**서버만 층을 올린다.** 클라이언트 보고로 올리면 "10층을 깼다" 고 적어 보내는 것이 곧
진행이 된다 (T9 와 같은 자리).
"""

from game.api.deps import get_context, get_pool
from game.app.progression.floors import read_floor_cap
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.store.accounts import find_player_entity
from game.app.store.progress import apply_floor_progress, read_reached_floor


def apply_floor_outcome(
    account_id: int, verified: VerifiedRun, floor: int, rooms_per_floor: int = 0
) -> str:
    """연쇄를 다 이겼으면 다음 층을 연다 (설계/6_몬스터 §3).

    **재시뮬이 확정한 결과만 본다.** 클라이언트 보고로 열면 "10층을 깼다" 고 적어 보내는
    것이 곧 진행이 된다 (T9 와 같은 자리). 반려된 제출은 아무것도 안 연다.

    **마지막 층에서는 안 연다.** 끝이 있어야 「깼다」가 성립한다.

    Args:
        account_id: 대상 계정.
        verified: 서버가 확정한 결과.
        floor: 하강이 시작한 층.
        rooms_per_floor: 층 하나에 드는 방 수.

    Returns:
        화면에 적을 한 줄. 열린 것이 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    # **진 판도 몇 층까지는 깼다.** 하강이 여러 층에 걸치므로 "이겼다" 하나로는 어디까지
    # 갔는지 알 수 없다 — 깬 방 수가 그것을 말한다.
    per_floor = max(1, rooms_per_floor)
    cleared_floors = verified.cleared_rooms // per_floor
    if cleared_floors <= 0:
        return ""
    cap = read_floor_cap(get_context().balance)
    deepest = min(floor + cleared_floors - 1, cap)
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    before = read_reached_floor(pool, entity_id)
    after = apply_floor_progress(pool, entity_id, deepest, cap)
    if deepest >= cap and verified.outcome == OUTCOME_PLAYER_WIN:
        return f"{cap}층을 깼다"
    # **열린 순간만 말한다.** 이미 지나온 층을 다시 이겼을 때도 말하면 그 줄이 뜻을 잃는다.
    return f"{after}층이 열렸다" if after > before else ""
