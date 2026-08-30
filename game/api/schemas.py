"""HTTP 요청·응답 절 (docs/설계/7_변조방지 §4).

**요청에 결과를 받는 자리를 만들지 않는다.** 여기 필드가 하나 생기면 그것을 믿는 코드가
따라 들어오고, 재시뮬이 형식적인 절차가 된다. `test_api_submission_takes_no_result` 가
되돌아가는 것을 막는다.
"""

from pydantic import BaseModel, Field

# 규칙표 절의 크기 상한. 슬롯 상한이 있으므로 정상 규칙표는 훨씬 작다 — 상한이 없으면
# 거대한 절 하나로 검증기를 묶어 둘 수 있다.
MAX_RULES = 64


class AccountResponse(BaseModel):
    """계정 응답. 토큰은 **만들 때와 로그인할 때만** 나온다.

    `login_id` 가 None 이면 익명 계정이다 — 화면이 "가입하면 지킬 수 있다" 를 그것으로
    판단한다.
    """

    account_id: int
    handle: str
    token: str | None = None
    login_id: str | None = None


class CredentialRequest(BaseModel):
    """가입·로그인 요청.

    길이 상한을 여기서도 건다. 서버가 scrypt 로 늘리므로, 상한이 없으면 긴 문자열
    하나로 CPU 를 묶어 둘 수 있다.
    """

    login_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TicketRequest(BaseModel):
    """티켓 발급 요청. **시드를 받지 않는다** — 시드는 서버가 정한다 (T2)."""

    room_id: str = Field(min_length=1, max_length=64)
    floor: int = Field(default=1, ge=1, le=99)


class TicketResponse(BaseModel):
    """발급된 티켓. 런의 입력 전부가 여기 있다."""

    ticket_id: str
    seed: int
    room_id: str
    floor: int
    mode: str
    core_version: str


class SubmissionRequest(BaseModel):
    """제출.

    필드가 셋뿐인 것이 설계다. 결과·시드·방·아이템을 받을 자리가 없다.
    """

    ticket_id: str = Field(min_length=1, max_length=128)
    ruleset: dict = Field(description="규칙표 절. 서버가 다시 파싱하고 다시 검증한다.")
    core_version: str = Field(min_length=1, max_length=32)


class SubmissionResponse(BaseModel):
    """서버가 확정한 결과. 클라이언트의 주장은 여기 반영되지 않는다."""

    submission_id: int
    outcome: str
    ticks: int
    player_hp: int
    verdict: str
    detail: str = ""


class MetaResponse(BaseModel):
    """메타 세이브 응답."""

    payload: dict | None
    core_version: str


class MetaRequest(BaseModel):
    """메타 세이브 저장 요청."""

    payload: dict
