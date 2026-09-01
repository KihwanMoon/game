"""메타 세이브 라우트.

**세이브는 두 조각으로 나뉘고 주인이 다르다** (docs/설계/3_저장과_멀티플레이 §4).

| 조각 | 주인 | 왜 |
|:--|:--|:--|
| 해금 · 도감 · 최고 층 | **서버** | 성취다. 클라이언트가 쓰면 순위의 근거가 될 수 없다 |
| 프리셋 (코드 라이브러리) | 클라이언트 | 유저가 지은 규칙표다. 판정할 것이 없다 |

그래서 이 라우트의 PUT 은 **프리셋만 받는다.** 성취 조각은 `/api/run` 이 재시뮬에서
직접 뽑아 갱신하며(`apply_verified_meta`), 클라이언트가 보낸 값은 무시된다 — 이 저장소의
전제가 "클라이언트는 적대적이다" 이고, 예전 형태는 그 전제와 정면으로 어긋났다.
"""

from dataclasses import replace

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_core_version, get_pool
from game.api.schemas import MetaRequest, MetaResponse
from game.app.store.meta import load_meta_payload, save_meta_payload
from game.schemas.meta_save import MetaSave, build_meta_payload, parse_meta_save

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
    """계정의 프리셋과 편집 중인 규칙표를 쓴다. 성취 조각은 받지 않는다.

    보낸 절에 해금·도감·최고 층이 들어 있어도 조용히 버린다. 400 으로 거절하지 않는
    이유는 구버전 클라이언트가 그것을 함께 보내기 때문이며, 거절하면 프리셋 저장까지
    막혀 그 사람은 규칙표를 잃는다.

    Args:
        request: 저장할 절. 프리셋과 초안만 읽는다.
        account: 토큰으로 푼 계정.

    Returns:
        저장된 절. **서버가 아는 성취와 방금 받은 프리셋·초안을 합친 것**이라, 보낸
        것과 다를 수 있다.

    Raises:
        HTTPException: 세이브 형식이 아닌 경우.
    """
    try:
        incoming = parse_meta_save(request.payload)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"세이브를 읽을 수 없다: {error}"
        ) from error
    pool = get_pool()
    stored = load_meta_payload(pool, account.account_id)
    # **서버가 아는 성취 위에 프리셋과 초안만 얹는다.** 반대로 하면 클라이언트가 보낸
    # 해금이 그대로 저장되고, 그것이 예전의 구멍이었다.
    #
    # 초안(편집 중인 규칙표)은 성취가 아니라 **쓰는 사람의 것**이라 그대로 받는다.
    # 예전에는 프리셋만 얹었고, 그래서 기기를 바꾸면 규칙이 사라졌다 — 올라오긴 했는데
    # 여기서 버려지고 있었다.
    merged = replace(
        parse_meta_save(stored) if stored else MetaSave(),
        presets=incoming.presets,
        draft=incoming.draft,
    )
    payload = build_meta_payload(merged)
    save_meta_payload(pool, account.account_id, payload, get_core_version())
    return MetaResponse(payload=payload, core_version=get_core_version())
