"""서버가 프로세스 수명 동안 들고 있는 것과 요청마다 푸는 것.

밸런스·카탈로그·방을 요청마다 다시 읽으면 재시뮬 94ms 가 파일 I/O 시간이 된다. 한 번
읽어 여기 둔다.
"""

import json
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from psycopg_pool import ConnectionPool

from game.app.content_versions import read_content_versions
from game.app.services.run_battle import load_balance
from game.app.services.verify_run import VerifyContext
from game.app.store.accounts import Account, find_account
from game.app.store.admin import (
    ROLE_AUTHOR,
    ROLE_OBSERVER,
    ROLE_OPERATOR,
    ROLE_OWNER,
    check_role_allows,
    read_admin_role,
)
from game.app.store.catalog_seed import apply_catalog_seed
from game.app.store.content_pack import read_asset, read_pack_generation
from game.app.store.drops import apply_drop_seed
from game.app.store.item_catalog import list_catalog, read_generation
from game.app.store.items import apply_affix_pool_seed
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets
from game.schemas.run_ticket import build_core_version

# 인증 헤더. Bearer 를 쓰지 않는 이유는 이것이 OAuth 토큰이 아니기 때문이다 — 기기에
# 저장된 익명 계정 열쇠이며, 승격 경로가 생기면 그때 표준 형식으로 옮긴다.
TOKEN_HEADER = "X-Game-Token"

_state: dict[str, object] = {}


def build_verify_context(pool: ConnectionPool) -> VerifyContext:
    """검증에 쓸 자원을 읽는다. **발행된 것이 있으면 그것을 읽는다** (§18).

    브라우저만 팩을 쓰고 서버가 파일을 읽으면 재시뮬이 다른 데이터로 돌고, 그것이 G3 가
    잡으려는 바로 그 상태다.

    팩을 임시 파일로 떨어뜨린 뒤 **코어가 쓰는 그 로더**로 읽는다. 로더가 경로를 받기
    때문이고, 절을 받는 두 번째 파서를 만들면 규칙이 둘이 된다 — 발행된 콘텐츠만 다른
    규칙으로 읽히는 날이 온다. 이 비용은 기동과 발행 때만 든다.

    Args:
        pool: 연결 풀.

    Returns:
        밸런스·카탈로그·방·적 규칙표가 실린 문맥.
    """
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        paths = {}
        for asset in ("balance", "blocks", "rooms", "enemies"):
            probe = base / f"{asset}.json"
            probe.write_text(
                json.dumps(read_asset(pool, asset), ensure_ascii=False), encoding="utf-8"
            )
            paths[asset] = probe
        return VerifyContext(
            balance=load_balance(paths["balance"]),
            catalog=load_block_catalog(paths["blocks"]),
            rooms={item.template_id: item for item in load_room_templates(paths["rooms"])},
            enemy_rulesets=load_rulesets(paths["enemies"]),
        )


def init_state(pool: ConnectionPool) -> None:
    """프로세스 상태를 채운다. 서버가 뜰 때 한 번만 부른다.

    Args:
        pool: 열린 연결 풀.
    """
    _state["pool"] = pool
    context = build_verify_context(pool)
    # **카탈로그 정본은 DB 다** (설계/4_아이템 §15.7). 파일은 빈 표를 채우는 씨앗이고,
    # 그 뒤로는 파생물이다 — 서버가 뜰 때마다 파일로 덮으면 관리자가 고친 것이 배포
    # 한 번에 사라진다.
    apply_catalog_seed(pool)
    catalog = list_catalog(pool)
    _state["items"] = catalog
    # 드롭 표도 빈 것만 채운다. 관리자가 조정한 가중치가 배포 한 번에 사라지면 안 된다.
    apply_drop_seed(pool, catalog)
    apply_affix_pool_seed(pool)
    _state["context"] = context
    # 아이템 축은 파일이 아니라 DB 세대에서 온다. 관리자가 아이템을 고치는 것은 시즌을
    # 가르는 일이고, 그 사실이 코어 버전 문자열에 남아야 한다 (§15.8).
    apply_state_versions(pool, context)


def apply_state_versions(pool: ConnectionPool, context: VerifyContext) -> None:
    """문맥과 코어 버전을 세운다. 발행 뒤에도 이것을 다시 부른다.

    **발행이 서버 컨텍스트도 갈아 끼운다.** 안 그러면 브라우저는 새 팩으로 돌고 서버는
    옛 데이터로 재시뮬한다.

    Args:
        pool: 연결 풀.
        context: 새로 읽은 문맥.
    """
    _state["context"] = context
    # 아이템 축은 카탈로그 세대(DB), 팩 축은 발행 세대다. 스킬·블록·밸런스·룸·적은
    # 팩이 정본이 됐으므로 파일 세대가 아니라 팩 세대가 시즌을 가른다 (§18).
    _state["core_version"] = build_core_version(
        replace(read_content_versions(), items=read_generation(pool)),
        pack=read_pack_generation(pool),
    )


def apply_catalog_reload() -> None:
    """카탈로그를 고친 뒤 서버가 들고 있는 사본을 갈아 끼운다.

    **여기서 안 갈면 새로 등록한 아이템이 안 나온다.** 굴림이 `get_item_catalog()` 로
    보는 것은 기동 시점에 읽은 사본이라, 등록해도 서버는 그 id 를 모른다 — 콘텐츠 팩이
    발행 뒤 컨텍스트를 갈아 끼우는 것과 같은 자리다 (§18).
    """
    pool = get_pool()
    catalog = list_catalog(pool)
    _state["items"] = catalog
    apply_drop_seed(pool, catalog)
    _state["core_version"] = build_core_version(
        replace(read_content_versions(), items=read_generation(pool)),
        pack=read_pack_generation(pool),
    )


def apply_content_reload() -> None:
    """발행 뒤 서버가 읽는 콘텐츠를 갈아 끼운다.

    **여기서 안 갈면 재시뮬이 옛 데이터로 돈다.** 브라우저는 팩을 받아 새 데이터로
    도는데 서버가 옛 것으로 채점하면, 그것이 G3 가 잡으려는 바로 그 상태다.
    """
    pool = get_pool()
    apply_state_versions(pool, build_verify_context(pool))


def get_pool() -> ConnectionPool:
    """열린 연결 풀을 준다.

    Returns:
        연결 풀.
    """
    pool: ConnectionPool = _state["pool"]  # type: ignore[assignment]
    return pool


def get_context() -> VerifyContext:
    """검증 문맥을 준다.

    Returns:
        검증 문맥.
    """
    context: VerifyContext = _state["context"]  # type: ignore[assignment]
    return context


def get_core_version() -> str:
    """이 서버가 도는 코어 버전.

    Returns:
        `b4.v3.e1` 형태의 문자열. 아직 준비되지 않았으면 빈 문자열.
    """
    return str(_state.get("core_version", ""))


def resolve_account(token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None) -> Account:
    """토큰에서 계정을 찾는다.

    Args:
        token: 요청 헤더의 기기 토큰.

    Returns:
        찾은 계정.

    Raises:
        HTTPException: 토큰이 없거나 모르는 토큰인 경우.
    """
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 없다")
    account = find_account(get_pool(), token)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "모르는 토큰이다")
    return account


CurrentAccount = Annotated[Account, Depends(resolve_account)]


def check_role(account: Account, wanted: str) -> Account:
    """이 계정이 그 등급의 일을 할 수 있는지 본다.

    **두 답을 가른다.** 관리자가 아니면 404 다 — 403 은 "여기 뭔가 있는데 너는 못 본다"
    를 알려 주고, 그것은 관리자 경로의 존재 자체를 노출한다. 반대로 **관리자인데 등급이
    모자라면 403** 이다: 그 사람은 경로가 있다는 것을 이미 알고 있고, 여기서 404 를 주면
    「막혔다」와 「없어졌다」가 구별되지 않아 고장으로 신고된다.

    Args:
        account: 토큰으로 푼 계정.
        wanted: 그 일에 필요한 등급.

    Returns:
        통과한 계정.

    Raises:
        HTTPException: 관리자가 아니면 404, 등급이 모자라면 403.
    """
    role = read_admin_role(get_pool(), account.account_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 경로다")
    if not check_role_allows(role, wanted):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"이 일에는 {wanted} 등급이 필요하다")
    return account


def resolve_admin(account: CurrentAccount) -> Account:
    """등급이 무엇이든 관리자면 통과시킨다 — 읽기 경로가 쓴다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        관리자 계정.
    """
    return check_role(account, ROLE_OBSERVER)


def resolve_author(account: CurrentAccount) -> Account:
    """콘텐츠 **초안**을 쓸 수 있는 계정만 통과시킨다. 발행은 여기 없다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        통과한 계정.
    """
    return check_role(account, ROLE_AUTHOR)


def resolve_operator(account: CurrentAccount) -> Account:
    """계정·세계에 개입할 수 있는 계정만 통과시킨다. 콘텐츠는 여기 없다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        통과한 계정.
    """
    return check_role(account, ROLE_OPERATOR)


def resolve_owner(account: CurrentAccount) -> Account:
    """전부 할 수 있는 계정만 통과시킨다.

    **사람만 받는다.** 발행과 카탈로그 즉시 반영이 여기 있고, 그 둘은 시즌을 가른다 —
    에이전트가 누르면 아무도 모르게 세계가 바뀐다 (설계/9_에이전트_운영 §8).

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        통과한 계정.
    """
    return check_role(account, ROLE_OWNER)


CurrentAdmin = Annotated[Account, Depends(resolve_admin)]
CurrentAuthor = Annotated[Account, Depends(resolve_author)]
CurrentOperator = Annotated[Account, Depends(resolve_operator)]
CurrentOwner = Annotated[Account, Depends(resolve_owner)]


def get_item_catalog() -> dict:
    """아이템 카탈로그를 준다.

    Returns:
        catalog_id 에서 항목으로의 대응표.
    """
    catalog: dict = _state["items"]  # type: ignore[assignment]
    return catalog
