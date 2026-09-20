"""규칙표를 짧은 주소로 공유한다 — 검색으로 들어오는 문 (2026-09-20).

**공유 코드는 이미 있었는데 아무도 안 붙였다.** `v2:H4sIA…` 가 475자라 커뮤니티에
그대로 붙는 링크가 아니고, 단축 주소를 쓰면 그 링크는 우리 것이 아니게 된다.

**게임 본체는 크롤러에게 68자였다.** 여기서 나가는 장은 사람이 지은 규칙표라 서로
다르고, 그것이 곧 「남의 표를 보고 내 것을 고친다」는 이 게임의 재미와 이어진다 —
유입과 체류를 같은 자리에서 친다.

`/r/...` 는 `/api/` 밖이라 nginx 가 따로 넘겨야 한다 (`deploy/nginx/frontend.conf`).
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from game.api.deps import CurrentAccount, get_context, get_core_version, get_pool
from game.app.rules.validator import validate_ruleset
from game.app.share.page import build_rule_rows
from game.app.share.shell import build_description, render_missing_page, render_share_page
from game.app.store.shared_rulesets import MAX_SHARE_NAME, read_shared, save_shared
from game.schemas.ruleset import parse_ruleset

router = APIRouter()

# 공유되는 표도 플레이어의 표다. 같은 예산 안에 들어야 한다 — 안 보면 예산을 넘긴
# 표가 링크로 돌아다니고, 그것을 불러온 사람은 열자마자 반려를 본다.
SHARE_CPU_BUDGET = 8
SHARE_RULE_SLOTS = 5

# 주소에 허용하는 글자. 해시라 16진수뿐이고, 이 밖의 것이 오면 조회조차 안 한다.
ID_ALPHABET = frozenset("0123456789abcdef")
MAX_ID_LENGTH = 32


class ShareRequest(BaseModel):
    """공유 요청."""

    name: str = Field(min_length=1, max_length=MAX_SHARE_NAME)
    ruleset: dict


class ShareResponse(BaseModel):
    """공유 결과."""

    share_id: str
    path: str


@router.post("/api/share", response_model=ShareResponse)
def create_share(body: ShareRequest, account: CurrentAccount) -> ShareResponse:
    """규칙표를 공유용으로 저장하고 짧은 주소를 낸다.

    **검증을 여기서 한다.** 못 읽거나 예산을 넘긴 표가 링크로 돌아다니면, 그것을
    받아 든 사람은 열자마자 반려만 본다 — 공유가 곧 고장 신고가 된다.

    같은 표를 다시 올리면 같은 주소가 나온다. 주소가 내용의 해시이기 때문이다.

    Args:
        body: 이름과 규칙표 절.
        account: 토큰으로 푼 계정.

    Returns:
        주소와 경로.

    Raises:
        HTTPException: 규칙표를 못 읽거나 예산을 넘긴 경우.
    """
    try:
        ruleset = parse_ruleset(body.ruleset)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"규칙표를 읽을 수 없다: {error}"
        ) from error
    problems = validate_ruleset(ruleset, get_context().catalog, SHARE_CPU_BUDGET, SHARE_RULE_SLOTS)
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"규칙표 위반: {problems[0]}")
    share_id = save_shared(
        get_pool(), body.ruleset, body.name, get_core_version(), account.account_id
    )
    return ShareResponse(share_id=share_id, path=f"/r/{share_id}")


@router.get("/r/{share_id}", response_class=HTMLResponse)
def read_share_page(share_id: str) -> HTMLResponse:
    """공유된 규칙표를 한 장으로 보여 준다.

    **로그인을 안 받는다.** 링크를 받아 든 사람은 아직 우리 계정이 없고, 계정을
    만들라고 먼저 말하면 그 자리에서 닫는다.

    없는 주소에도 **404 와 함께 장을 낸다.** 링크는 오래 남고, 눌러 들어온 사람에게
    아무것도 안 보여 주면 사이트가 죽은 것으로 읽힌다.

    Args:
        share_id: 주소의 id.

    Returns:
        HTML 한 장.
    """
    if len(share_id) > MAX_ID_LENGTH or not set(share_id) <= ID_ALPHABET:
        return HTMLResponse(render_missing_page(), status_code=status.HTTP_404_NOT_FOUND)
    found = read_shared(get_pool(), share_id)
    if found is None:
        return HTMLResponse(render_missing_page(), status_code=status.HTTP_404_NOT_FOUND)
    name, payload = found
    try:
        ruleset = parse_ruleset(payload)
    except (KeyError, TypeError, ValueError):
        # 저장될 때는 읽혔다는 뜻이므로, 못 읽는다면 그 사이 문법이 판올림된 것이다.
        return HTMLResponse(render_missing_page(), status_code=status.HTTP_404_NOT_FOUND)
    catalog = get_context().catalog
    cpu = sum(rule.cpu_cost for rule in ruleset.rules)
    body = "\n      ".join(
        [
            '<article class="cx">',
            f"<h1>{name}</h1>",
            f'<p class="cx__kind">규칙 {len(ruleset.rules)}줄 · CPU {cpu} / {SHARE_CPU_BUDGET}</p>',
            "<p>비각은 규칙표를 적어 두면 그것이 대신 싸우는 게임이다. 아래가 이 표의 전부이고, "
            "위에서부터 읽어 처음 맞는 줄이 그 틱의 행동이 된다.</p>",
            build_rule_rows(ruleset, catalog),
            '<p><a href="/">이 표를 열어 고쳐 본다</a></p>',
            "</article>",
        ]
    )
    return HTMLResponse(
        render_share_page(
            name, f"/r/{share_id}", body, build_description(name, len(ruleset.rules), cpu)
        )
    )
