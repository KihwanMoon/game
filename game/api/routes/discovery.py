"""도감 — 세계에 무엇이 있고, 그중 무엇을 내가 밝혔는가.

**미해금도 자리를 보여준다.** 안 밝힌 것을 목록에서 빼면 도감이 "내가 가진 것 목록" 이
되고, 그러면 무엇을 더 찾아야 하는지가 화면에서 사라진다 — 도감이 표적 목록인 이유가
그것이다 (docs/설계/6_몬스터 §8 이 몬스터에 대해 말하는 것과 같다).

**이름은 가리지 않는다.** 실루엣만 남기고 이름까지 지우면 목표가 안 보이고, 그러면
찾아갈 이유도 안 생긴다. 가리는 것은 성능·접사 같은 **속살**이다.
"""

from fastapi import APIRouter

from game.api.catalog_view import build_item_rows
from game.api.deps import CurrentAccount, get_context, get_item_catalog, get_pool
from game.api.view_schemas import DiscoveryResponse, DiscoveryRow
from game.app.store.discovery import KIND_ITEM, KIND_SKILL, list_discovery

router = APIRouter()


def build_item_discovery(found: frozenset[str]) -> list[DiscoveryRow]:
    """아이템 도감 줄들을 만든다.

    Args:
        found: 이 계정이 밝힌 카탈로그 id 들.

    Returns:
        카탈로그 순 줄들.
    """
    rows = []
    for row in build_item_rows(get_item_catalog()):
        is_found = row["catalog_id"] in found
        rows.append(
            DiscoveryRow(
                kind=KIND_ITEM,
                ref_id=row["catalog_id"],
                label_ko=row["label_ko"],
                # 분류는 늘 보여준다 — 그림 자리의 코드가 이것으로 정해지고, 무엇을
                # 찾는지("투구 하나가 비었다")를 아는 데 필요하다.
                category=row["slot"] or row["kind"],
                is_found=is_found,
                # 속살은 밝힌 뒤에만. 안 밝힌 것의 성능이 다 보이면 도감이 상점이 된다.
                detail=" · ".join(row["affixes"]) if is_found else "",
            )
        )
    return rows


def build_skill_discovery(found: frozenset[str]) -> list[DiscoveryRow]:
    """스킬 도감 줄들을 만든다.

    스킬 정의는 파일에서 온다 — 두 코어가 함께 읽는 실행 자산이라 DB 에 두지 않는다.

    Args:
        found: 이 계정이 밝힌 스킬 id 들.

    Returns:
        id 순 줄들.
    """
    skills = get_context().balance.get("skills", [])
    rows = []
    for skill in sorted(skills, key=lambda item: str(item["id"])):
        skill_id = str(skill["id"])
        is_found = skill_id in found
        detail = f"계수 {skill['coef_pct']}% · 재사용 {skill['cooldown']}"
        rows.append(
            DiscoveryRow(
                kind=KIND_SKILL,
                ref_id=skill_id,
                label_ko=skill_id,
                category=str(skill.get("family", "")),
                is_found=is_found,
                detail=detail if is_found else "",
            )
        )
    return rows


@router.get("/api/discovery", response_model=DiscoveryResponse)
def read_discovery(account: CurrentAccount) -> DiscoveryResponse:
    """내 도감을 본다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        아이템·스킬 줄들과 해금 수.
    """
    pool = get_pool()
    items = build_item_discovery(list_discovery(pool, account.account_id, KIND_ITEM))
    skills = build_skill_discovery(list_discovery(pool, account.account_id, KIND_SKILL))
    return DiscoveryResponse(
        items=items,
        skills=skills,
        found=sum(1 for row in items + skills if row.is_found),
        total=len(items) + len(skills),
    )
