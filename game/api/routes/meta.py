"""메타 세이브 라우트.

지금은 클라이언트가 보낸 절을 **형식 검사만** 하고 받는다. 최종 형태는 검증된 런의
부산물로만 갱신하는 것이며(docs/설계/3_저장과_멀티플레이 §4), 그것은 런 사슬이 서버로
올라온 뒤에 성립한다. **그 전까지 이 세이브는 순위의 근거가 될 수 없다.**
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_core_version, get_pool
from game.api.schemas import MetaRequest, MetaResponse
from game.app.store.meta import load_meta_payload, save_meta_payload
from game.schemas.meta_save import parse_meta_save

router = APIRouter()


@router.get("/api/meta", response_model=MetaResponse)
def read_meta(account: CurrentAccount) -> MetaResponse:
    """계정의 메타 세이브를 본다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        저장돼 있던 절. 없으면 payload 가 None 이다.
    """
    return MetaResponse(
        payload=load_meta_payload(get_pool(), account.account_id),
        core_version=get_core_version(),
    )


@router.put("/api/meta", response_model=MetaResponse)
def save_meta(request: MetaRequest, account: CurrentAccount) -> MetaResponse:
    """계정의 메타 세이브를 통째로 쓴다.

    Args:
        request: 저장할 절.
        account: 토큰으로 푼 계정.

    Returns:
        저장된 절.

    Raises:
        HTTPException: 세이브 형식이 아닌 경우.
    """
    try:
        parse_meta_save(request.payload)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"세이브를 읽을 수 없다: {error}"
        ) from error
    save_meta_payload(get_pool(), account.account_id, request.payload, get_core_version())
    return MetaResponse(payload=request.payload, core_version=get_core_version())
