"""런 티켓과 제출 계약 (docs/설계/7_변조방지 §4).

이 파일의 존재 이유는 검사 하나다 — **제출에 결과 필드가 생기는 것을 막는다.**
문서에만 적어 두면 "재시뮬이 느리니 이번만" 이라는 지름길이 언젠가 생긴다.
"""

import pytest

from game.schemas.ruleset import RuleSet
from game.schemas.run_ticket import (
    ENGINE_VERSION,
    LOCAL_TICKET_PREFIX,
    MAX_SEED,
    RunMode,
    build_core_version,
    build_submission,
    create_local_ticket,
    list_submission_fields,
)

CORE_VERSION = "b4.v3.e1"


def test_submission_carries_no_results():
    """★ 제출은 입력만 담는다. 결과·시드·스냅샷을 받을 자리가 없다.

    이 검사가 붉어지면 필드를 지우기 전에 docs/설계/7_변조방지 §4 를 먼저 읽는다.
    자리가 생기는 순간, 언젠가 그 값을 믿는 코드가 따라 들어온다.
    """
    assert list_submission_fields() == ("ticket_id", "ruleset", "core_version")


def test_ranked_ticket_cannot_be_issued_locally():
    """★ 로컬이 순위 티켓을 만들 수 있으면 시드 서버 발급이 아무것도 막지 못한다."""
    for mode in (RunMode.RANKED, RunMode.DAILY):
        with pytest.raises(ValueError, match="서버가 발급"):
            create_local_ticket(1, "room", CORE_VERSION, mode=mode)


def test_practice_ticket_is_local():
    ticket = create_local_ticket(12345, "room_a", CORE_VERSION)
    assert ticket.ticket_id.startswith(LOCAL_TICKET_PREFIX)
    assert ticket.mode is RunMode.PRACTICE
    assert not ticket.is_ranked


def test_ticket_id_is_derived_not_random():
    """같은 입력이 같은 티켓을 낸다. 시간이나 난수를 쓰면 리플레이가 깨진다 (R5)."""
    first = create_local_ticket(7, "room_a", CORE_VERSION)
    second = create_local_ticket(7, "room_a", CORE_VERSION)
    assert first == second


def test_different_seed_makes_a_different_ticket():
    first = create_local_ticket(7, "room_a", CORE_VERSION)
    second = create_local_ticket(8, "room_a", CORE_VERSION)
    assert first.ticket_id != second.ticket_id


def test_submission_takes_seed_from_the_ticket():
    """제출은 시드를 다시 싣지 않는다 — 티켓이 이미 들고 있다."""
    ticket = create_local_ticket(99, "room_a", CORE_VERSION)
    submission = build_submission(ticket, RuleSet(ruleset_id="r", version=1, rules=()))
    assert submission.ticket_id == ticket.ticket_id
    assert submission.core_version == CORE_VERSION
    assert not hasattr(submission, "seed")


def test_core_version_carries_three_generations():
    """블록·밸런스·엔진 셋이 모여 코어 버전을 이룬다 (docs/설계/1 §2)."""
    assert build_core_version(4, 3) == f"b4.v3.e{ENGINE_VERSION}"


def test_seed_above_the_port_limit_is_rejected():
    """★ 이식 제약. TypeScript 의 number 는 53비트라 그 위는 반올림된다.

    파이썬만 64비트 시드를 받으면 같은 시드가 두 코어에서 다른 판을 돌고, 골든이 작은
    시드만 쓰므로 G3 도 그것을 보지 못한다. 서버가 시드를 발급할 때도 이 상한을
    지켜야 하며, 64비트로 올리려면 TS 쪽 seed 를 bigint 로 바꾸는 것이 선행이다.
    """
    assert MAX_SEED == (1 << 53) - 1
    create_local_ticket(MAX_SEED, "room", CORE_VERSION)
    with pytest.raises(ValueError, match="이식 범위"):
        create_local_ticket(MAX_SEED + 1, "room", CORE_VERSION)
    with pytest.raises(ValueError, match="이식 범위"):
        create_local_ticket(-1, "room", CORE_VERSION)
