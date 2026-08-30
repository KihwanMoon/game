"""검증 서버의 계약 검사 (docs/설계/7_변조방지 §4).

**DB 없이 돈다.** 여기서 보는 것은 "무엇을 받고 무엇을 안 받는가" 이고, 그것은 저장소와
무관하다. DB 가 필요한 검사는 `test_api_server.py` 에 있고 연결이 없으면 건너뛴다.

이 파일의 존재 이유는 검사 하나다 — **요청에 결과를 받는 자리가 생기는 것을 막는다.**
필드가 하나 생기면 그것을 믿는 코드가 따라 들어오고, 재시뮬이 형식적인 절차가 된다.
"""

import pytest

from game.api.schemas import SubmissionRequest, TicketRequest
from game.app.services.verify_run import check_submission_version
from game.app.store.runs import VERDICT_REJECTED, VERDICT_VERIFIED
from game.app.store.tickets import create_seed
from game.schemas.run_ticket import MAX_SEED

SAMPLE_COUNT = 200


def test_submission_request_takes_no_result():
    """★ 제출 요청은 입력만 받는다. 결과·시드·방을 받을 자리가 없다.

    이 검사가 붉어지면 필드를 지우기 전에 docs/설계/7_변조방지 §4 를 먼저 읽는다.
    """
    assert set(SubmissionRequest.model_fields) == {"ticket_id", "ruleset", "core_version"}


def test_ticket_request_seed_is_optional_and_bounded():
    """티켓 요청의 시드는 선택이고 이식 범위 안이다.

    **연습 모드에서만 반영된다** (T2 는 순위에 반영되는 판의 문제다). 상한을 모델에서
    거는 이유는 서버가 발급한 시드와 같은 규칙을 받는 쪽에도 걸기 위해서다.
    """
    assert set(TicketRequest.model_fields) == {"room_id", "floor", "seed"}
    assert TicketRequest(room_id="r").seed is None
    with pytest.raises(ValueError, match="less than or equal"):
        TicketRequest(room_id="r", seed=MAX_SEED + 1)


def test_extra_fields_do_not_smuggle_a_result():
    """모르는 필드를 보내도 모델에 남지 않는다."""
    request = SubmissionRequest.model_validate(
        {"ticket_id": "t", "ruleset": {}, "core_version": "b4.v3.e1", "outcome": "player_win"}
    )
    assert not hasattr(request, "outcome")


def test_issued_seed_stays_inside_the_port_limit():
    """★ 서버가 발급하는 시드는 TypeScript 가 담을 수 있어야 한다.

    상한을 넘기면 클라이언트가 반올림된 시드로 다른 판을 돌고, 서버는 원래 시드로
    재시뮬해 언제나 mismatch 가 난다. 무작위라 가끔만 틀리므로 원인까지 도달하기 어렵다.
    """
    for _ in range(SAMPLE_COUNT):
        seed = create_seed()
        assert 0 <= seed <= MAX_SEED


def test_issued_seeds_are_not_all_the_same():
    """예측 가능한 시드는 골라 담기를 연다."""
    seeds = {create_seed() for _ in range(SAMPLE_COUNT)}
    assert len(seeds) > SAMPLE_COUNT // 2


@pytest.mark.parametrize(
    ("claimed", "server", "is_ok"),
    [("b4.v3.e1", "b4.v3.e1", True), ("b4.v3.e1", "b4.v4.e1", False)],
)
def test_version_mismatch_is_reported_not_hidden(claimed, server, is_ok):
    """버전이 다르면 재시뮬하지 않고 사유를 남긴다.

    변조가 아니라 배포 시차일 가능성이 높다. 조용히 통과시키면 재현되지 않는 기록이
    쌓이고, 조용히 거절하면 사람이 원인을 못 찾는다 (§8).
    """
    detail = check_submission_version(claimed, server)
    assert (detail == "") is is_ok
    if not is_ok:
        assert claimed in detail and server in detail


def test_verdicts_are_distinct():
    assert len({VERDICT_VERIFIED, VERDICT_REJECTED}) == 2
