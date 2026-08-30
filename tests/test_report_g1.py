"""G1 판정 계산 (로드맵 §게이트 G1).

**DB 없이 돈다.** 세는 규칙이 맞는지가 여기서 볼 것이고, 그것은 저장소와 무관하다.

가장 중요한 판단 하나를 검사가 지킨다 — **"규칙을 고쳐 재도전" 은 규칙표가 실제로
달라진 다음 제출이다.** 같은 규칙표로 다시 돌린 것까지 세면, P1("실패는 정보다")이
통했는지가 아니라 사람이 버튼을 몇 번 눌렀는지를 재게 된다.
"""

from scripts.report_g1 import (
    Attempt,
    build_ruleset_key,
    count_distinct_clears,
    count_edited_retries,
    list_retry_after_loss,
    render_report,
)

WIN = "PLAYER_WIN"
LOSS = "PLAYER_LOSS"
VERIFIED = "verified"
ROOM = "corridor"


def build_attempt(account, key, outcome=LOSS, room=ROOM, verdict=VERIFIED):
    return Attempt(
        account_id=account, room_id=room, ruleset_key=key, outcome=outcome, verdict=verdict
    )


def test_ruleset_key_ignores_name_and_version():
    """이름만 바꾼 것을 '고쳤다' 로 세면 안 된다."""
    first = {"ruleset_id": "a", "version": 1, "rules": [{"priority": 1}]}
    second = {"ruleset_id": "b", "version": 9, "rules": [{"priority": 1}]}
    assert build_ruleset_key(first) == build_ruleset_key(second)


def test_ruleset_key_sees_rule_changes():
    assert build_ruleset_key({"rules": [{"priority": 1}]}) != build_ruleset_key(
        {"rules": [{"priority": 2}]}
    )


def test_same_ruleset_rerun_is_not_a_retry():
    """★ 같은 규칙표로 다시 돌린 것은 재도전이 아니라 재실행이다."""
    attempts = [build_attempt(1, "same"), build_attempt(1, "same"), build_attempt(1, "same")]
    assert count_edited_retries(attempts) == {1: 0}


def test_edited_ruleset_counts_as_a_retry():
    attempts = [build_attempt(1, "a"), build_attempt(1, "b"), build_attempt(1, "c")]
    assert count_edited_retries(attempts) == {1: 2}


def test_accounts_are_counted_separately():
    attempts = [build_attempt(1, "a"), build_attempt(2, "a"), build_attempt(1, "b")]
    assert count_edited_retries(attempts) == {1: 1, 2: 0}


def test_retry_after_loss_needs_an_actual_edit():
    """★ 지고 나서 같은 규칙표로 다시 돌린 것은 '고쳐 재도전' 이 아니다."""
    assert list_retry_after_loss([build_attempt(1, "a"), build_attempt(1, "a")]) == set()
    assert list_retry_after_loss([build_attempt(1, "a"), build_attempt(1, "b")]) == {1}


def test_retry_after_a_win_is_not_counted():
    """이기고 나서 다른 규칙표를 시험한 것은 '첫 패배 후 재도전' 이 아니다."""
    attempts = [build_attempt(1, "a", WIN), build_attempt(1, "b", WIN)]
    assert list_retry_after_loss(attempts) == set()


def test_distinct_clears_count_only_verified_wins():
    attempts = [
        build_attempt(1, "a", WIN),
        build_attempt(2, "b", WIN),
        build_attempt(3, "c", WIN, verdict="rejected"),
        build_attempt(4, "d", LOSS),
    ]
    assert count_distinct_clears(attempts) == {ROOM: 2}


def test_same_ruleset_clearing_twice_counts_once():
    """서로 다른 2가지여야 한다 — 같은 표로 두 번 이긴 것은 한 가지다."""
    attempts = [build_attempt(1, "a", WIN), build_attempt(2, "a", WIN)]
    assert count_distinct_clears(attempts) == {ROOM: 1}


def test_clears_are_counted_per_room():
    attempts = [build_attempt(1, "a", WIN, room="r1"), build_attempt(2, "b", WIN, room="r2")]
    assert count_distinct_clears(attempts) == {"r1": 1, "r2": 1}


def test_empty_report_says_why_it_is_empty():
    """숫자가 없는 것과 게이트를 통과하지 못한 것은 다르다."""
    text = render_report([])
    assert "제출 기록이 없다" in text
    assert "테스터" in text


def test_report_warns_when_the_sample_is_too_small():
    text = render_report([build_attempt(1, "a"), build_attempt(1, "b")])
    assert "표본이 모자라면" in text


def test_report_marks_each_criterion():
    text = render_report([build_attempt(1, "a"), build_attempt(1, "b")])
    # 참·거짓을 글리프와 글자 둘로 적는다 — 색을 못 쓰는 터미널에서도 구분되어야 한다.
    assert "[X] 미달" in text or "[O] 통과" in text
    assert text.count("[") >= 3
