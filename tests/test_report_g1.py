"""G1 판정 계산 (로드맵 §게이트 G1).

**DB 없이 돈다.** 세는 규칙이 맞는지가 여기서 볼 것이고, 그것은 저장소와 무관하다.

가장 중요한 판단 하나를 검사가 지킨다 — **"규칙을 고쳐 재도전" 은 규칙표가 실제로
달라진 다음 제출이다.** 같은 규칙표로 다시 돌린 것까지 세면, P1("실패는 정보다")이
통했는지가 아니라 사람이 버튼을 몇 번 눌렀는지를 재게 된다.
"""

from scripts.report_g1 import (
    Attempt,
    Excluded,
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


def build_excluded(testers=1, bots=0, guests=0):
    return Excluded(testers=testers, bot_attempts=bots, guest_attempts=guests)


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


def test_a_report_without_marked_testers_refuses_to_judge():
    """★ 분모가 없는 것과 미달인 것은 다르다.

    표시가 비었는데 0명·0회를 적으면 미달로 읽히고, 그러면 **분모를 안 정했다는 사실이
    미달이라는 판정 뒤에 숨는다.** 실측으로 「테스터 36명」이 그렇게 나왔다 — 익명 계정이
    접속마다 생기므로 한 판 내고 떠난 17명이 전부 분모에 들어가 있었다.
    """
    text = render_report([], build_excluded(testers=0, guests=982))
    assert "판정할 분모가 없다" in text
    # 판정 줄이 하나도 없어야 한다. 하나라도 있으면 그것이 판정으로 읽힌다.
    assert "[X] 미달" not in text
    assert "[O] 통과" not in text
    # 그렇다고 침묵하면 안 된다 — 서버에 무엇이 있는지는 말해야 다음 행동이 나온다.
    assert "982건" in text


def test_the_average_divides_by_the_testers_we_called():
    """★ 부르고도 안 온 사람이 분모에서 사라지면 안 된다.

    실제로 돌린 사람으로 나누면 「5명 중 3명」이 조용히 「3명 중 3명」이 되고, 그러면
    게이트가 묻는 것(부른 사람 가운데 몇이 다시 왔는가)이 바뀐다.
    """
    # 한 사람이 4번 고쳐 돌렸고, 나머지 넷은 오지 않았다. 4 / 5 = 0.8 이지 4.0 이 아니다.
    attempts = [build_attempt(1, key) for key in ("a", "b", "c", "d", "e")]
    text = render_report(attempts, build_excluded(testers=5))
    assert "0.8회" in text
    assert "5명 중 1명이 돌림" in text


def test_the_average_says_when_some_testers_never_played():
    """분모가 실제로 돌린 수보다 크면 그 사실을 적는다 — 안 적으면 낮은 값이 오해된다."""
    attempts = [build_attempt(1, "a"), build_attempt(1, "b")]
    assert "표시 5명으로 나눔" in render_report(attempts, build_excluded(testers=5))


def test_report_warns_when_the_sample_is_too_small():
    text = render_report([build_attempt(1, "a")], build_excluded(testers=2))
    assert "표본이 모자라면" in text


def test_report_marks_each_criterion():
    text = render_report([build_attempt(1, "a"), build_attempt(1, "b")], build_excluded())
    # 참·거짓을 글리프와 글자 둘로 적는다 — 색을 못 쓰는 터미널에서도 구분되어야 한다.
    assert "[X] 미달" in text or "[O] 통과" in text
    assert text.count("[") >= 3


def test_the_report_says_what_it_dropped():
    """★ 뺀 것을 적어야 다시 섞였을 때 눈에 띈다.

    실측으로 봇을 안 거를 때와 거를 때의 **판정이 뒤집혔다** — 「첫 패배 후 규칙을 고쳐
    재도전」이 7명(통과)에서 1명(미달)이 됐다. 여섯은 봇이었다. 표시 안 된 계정도 같다:
    안 적으면 「제출이 982건인데 왜 안 세지」를 화면에서 답할 수 없다.
    """
    text = render_report([build_attempt(1, "a")], build_excluded(bots=3201, guests=982))
    assert "봇 3201건" in text
    assert "표시 안 된 계정 982건" in text


def test_the_report_stays_quiet_when_nothing_was_dropped():
    """★ 뺀 것이 없으면 안 적는다 — 「봇 0건 제외」는 읽는 사람에게 잡음이다."""
    text = render_report([build_attempt(1, "a")], build_excluded())
    assert "제외" not in text


def test_the_query_counts_only_marked_testers():
    """★ 분모는 **표시된 테스터**다 — 자동으로 세면 지나간 사람이 테스터가 된다.

    질의에서 거르는 이유는, 읽고 나서 거르면 거르는 것을 잊는 자리가 하나 더 생기기
    때문이다. 세는 함수마다 같은 조건을 다시 써야 한다.
    """
    from pathlib import Path

    source = Path("scripts/report_g1.py").read_text(encoding="utf-8")
    # 문자열로 확인하는 이유는 이 검사가 DB 없이 돌기 때문이다 — 질의를 실제로 돌리는
    # 검사는 컨테이너 게이트의 몫이고, 여기서 지키는 것은 **조건이 사라지지 않는 것**이다.
    assert "JOIN account a ON a.id = t.account_id" in source
    assert "WHERE a.is_tester AND NOT a.is_bot" in source


def test_the_denominator_is_not_derived_from_submissions():
    """★ 「제출 N건 이상」으로 분모를 정하면 **순환**이다.

    많이 논 계정만 분모에 넣고 「평균 재도전 3회 이상」을 재면 기준이 저절로 통과된다.
    표시된 수는 계정 표에서 읽어야 하고, 제출 표에서 세면 안 된다.
    """
    from pathlib import Path

    source = Path("scripts/report_g1.py").read_text(encoding="utf-8")
    assert "SELECT count(*) FROM account WHERE is_tester AND NOT is_bot" in source
