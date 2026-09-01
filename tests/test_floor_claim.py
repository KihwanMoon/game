"""층 청구 — 한 티켓으로 층마다 한 번씩 (로드맵 W14, 설계/7_변조방지 §9).

**T6 을 다시 세운 자리다.** 「한 티켓 한 제출」은 같은 판으로 보상을 두 번 받는 것을
막으려던 규율이었다. 층 단위 보상은 여러 번 제출해야 하므로, 같은 목적을
**「더 깊은 층으로만 나아갈 수 있다」**로 다시 세운다.

인계 HP 는 여전히 클라이언트가 안 보낸다 — 서버가 **매번 처음부터** 그 층까지 다시 돌려
확정한다 (T9). 그래서 청구는 「어디까지 확인해 달라」는 말일 뿐이고, 깊게 적어 봐야 더
많이 시뮬될 뿐이다.

여기서 지키는 것은 넷이다.

1. **같은 층을 두 번 청구할 수 없다.** 보상이 두 번 나간다.
2. **하강 밖의 층은 청구할 수 없다.** 방 목록 밖을 돌게 된다.
3. **죽으면 티켓이 닫힌다.** 안 닫으면 죽은 뒤에도 더 깊은 층을 청구할 수 있다.
4. **마지막 층을 깨면 닫힌다.** 끝났는데 계속 청구할 수 있으면 끝이 아니다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


def build_ticket(floor=1, per_floor=3, floors=10):
    """검사용 티켓 하나를 만든다.

    Args:
        floor: 시작 층.
        per_floor: 층 하나에 드는 방 수.
        floors: 하강이 도는 층 수.

    Returns:
        발급된 티켓 모양의 값.
    """
    from game.app.store.tickets import IssuedTicket

    return IssuedTicket(
        ticket_id="probe",
        seed=1,
        room_id="open_field",
        floor=floor,
        mode="PRACTICE",
        core_version="x",
        room_ids=tuple(f"r{index}" for index in range(per_floor * floors)),
        rooms_per_floor=per_floor,
    )


def build_verdict(outcome="PLAYER_WIN", verdict="verified"):
    """검사용 판정 하나를 만든다.

    Args:
        outcome: 승패.
        verdict: 검증 결과.

    Returns:
        확정된 판정.
    """
    from game.app.services.verify_run import VerifiedRun

    return VerifiedRun(outcome=outcome, ticks=1, player_hp=1, verdict=verdict)


def test_a_claim_is_clamped_to_the_descent():
    """★ 하강 밖의 층을 청구하면 방 목록 밖을 돈다."""
    from game.api.floor_service import resolve_claim

    ticket = build_ticket(floor=1, per_floor=3, floors=10)
    assert resolve_claim(ticket, 99) == 10
    assert resolve_claim(ticket, 0) == 0
    assert resolve_claim(ticket, 4) == 4


def test_a_claim_never_falls_below_the_start():
    """★ 시작 층보다 얕게 청구하면 안 돈 방을 깼다고 치게 된다."""
    from game.api.floor_service import resolve_claim

    assert resolve_claim(build_ticket(floor=5, floors=6), 2) == 5


def test_the_room_count_follows_the_claim():
    """★ 청구한 층까지만 돈다 — 전부 돌면 아직 안 간 층의 결과가 섞인다."""
    from game.api.floor_service import count_claim_rooms

    ticket = build_ticket(floor=1, per_floor=3)
    assert count_claim_rooms(ticket, 1) == 3
    assert count_claim_rooms(ticket, 4) == 12
    # 0 은 「전체」다 — 층 개념이 없던 옛 클라이언트가 그 길로 온다.
    assert count_claim_rooms(ticket, 0) == 0


def test_a_loss_ends_the_descent():
    """★ 죽었는데 티켓이 열려 있으면 죽은 뒤에도 더 깊은 층을 청구할 수 있다.

    서버가 다시 돌면 또 패배로 나오지만, **그때마다 그 층의 보상이 나간다.**
    """
    from game.api.floor_service import check_descent_over

    ticket = build_ticket()
    assert check_descent_over(ticket, 3, build_verdict(outcome="ENEMY_WIN"))


def test_clearing_the_last_floor_ends_the_descent():
    """★ 끝났는데 계속 청구할 수 있으면 끝이 아니다."""
    from game.api.floor_service import check_descent_over

    ticket = build_ticket(floor=1, floors=10)
    assert check_descent_over(ticket, 10, build_verdict())


def test_a_middle_floor_keeps_the_descent_open():
    """★ 중간 층에서 닫으면 그 뒤로 한 층도 못 간다."""
    from game.api.floor_service import check_descent_over

    assert not check_descent_over(build_ticket(), 3, build_verdict())


def test_a_rejected_submission_ends_nothing():
    """★ 반려는 판정이 아니다 — 코어 버전이 어긋난 것만으로 런이 끝나면 배포 시차가 벌이 된다.

    **패배와 함께 준다.** 승리로 주면 「중간 층이라 안 끝난다」와 답이 같아져, 반려 검사를
    지워도 통과한다 — 실제로 그렇게 통과했다.
    """
    from game.api.floor_service import check_descent_over

    rejected = build_verdict(outcome="ENEMY_WIN", verdict="rejected")
    assert not check_descent_over(build_ticket(), 3, rejected)


@pytest.fixture
def issued():
    """실제로 발급한 티켓 하나."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.deps import get_pool
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as client:
        token = client.post("/api/account").json()["token"]
        body = client.post(
            "/api/ticket", json={"room_id": "open_field"}, headers={"X-Game-Token": token}
        ).json()
        yield get_pool(), body


def test_the_same_floor_cannot_be_claimed_twice(issued):
    """★ 같은 층을 두 번 청구하면 보상이 두 번 나간다 — 그것이 T6 이 막던 것이다."""
    from game.app.store.tickets import apply_floor_claim

    pool, body = issued
    assert apply_floor_claim(pool, body["ticket_id"], 1)
    assert not apply_floor_claim(pool, body["ticket_id"], 1)


def test_a_shallower_claim_is_refused(issued):
    """★ 되돌아가 청구하면 지나온 층의 보상을 다시 받는다."""
    from game.app.store.tickets import apply_floor_claim

    pool, body = issued
    assert apply_floor_claim(pool, body["ticket_id"], 3)
    assert not apply_floor_claim(pool, body["ticket_id"], 2)


def test_a_consumed_ticket_refuses_every_claim(issued):
    """★ 닫힌 티켓으로 더 청구할 수 있으면 죽은 뒤에도 보상이 나간다."""
    from game.app.store.tickets import apply_floor_claim, mark_ticket_consumed

    pool, body = issued
    assert mark_ticket_consumed(pool, body["ticket_id"])
    assert not apply_floor_claim(pool, body["ticket_id"], 1)
