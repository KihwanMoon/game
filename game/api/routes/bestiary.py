"""도감 — **위키가 아니라 표적 목록** (docs/설계/6_몬스터 §8).

지속 몬스터가 도감의 성격을 바꾼다. 규칙표만 보여 주던 것에서 "지금 어디에 있고, 얼마나
컸고, **내 아이템을 들고 있는가**" 를 함께 말한다 — 그것이 되찾으러 가는 동기이고,
World Loop 이 성립하는 이유다.

**적의 규칙표를 그대로 낸다.** 요약하지 않는다 — 몬스터가 플레이어와 같은 DSL 로
기술돼 있으므로 원문이 곧 카운터 설계의 입력이다 (GDD §2.3, P1).
"""

from fastapi import APIRouter

from game.api.deps import CurrentAccount, get_context, get_pool
from game.api.schemas import BestiaryEntry, BestiaryResponse
from game.app.monsters.affixes import build_affix_label, list_monster_affixes
from game.app.monsters.growth import get_level_cap
from game.app.monsters.tiers import MonsterTier
from game.app.store.monsters import list_monsters, list_trophies
from game.schemas.meta_save import build_ruleset_payload

router = APIRouter()

# 도감이 훑는 층 범위. 지금은 층 사슬이 없어 1층뿐이지만, 범위로 두면 층이 늘 때
# 이 라우트를 고치지 않아도 된다.
MIN_FLOOR = 1
MAX_FLOOR = 5


@router.get("/api/bestiary", response_model=BestiaryResponse)
def read_bestiary(account: CurrentAccount) -> BestiaryResponse:
    """세계에 사는 지속 몬스터를 훑는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        층·자리 순으로 정렬된 몬스터들. 내 아이템을 든 개체는 `holds_mine` 이 참이다.
    """
    pool = get_pool()
    context = get_context()
    by_id = {kind["id"]: kind for kind in context.balance["enemies"]}
    entries: list[BestiaryEntry] = []
    for floor in range(MIN_FLOOR, MAX_FLOOR + 1):
        for record in list_monsters(pool, floor):
            base = by_id.get(record.catalog_id)
            if base is None:
                continue
            trophies = list_trophies(pool, record.record_id)
            # 이 개체 전용 규칙표가 있으면 그것을, 없으면 카탈로그 기본표를 낸다.
            # 레벨별 규칙표(#36)가 정해지면 앞엣것이 채워진다.
            ruleset = context.enemy_rulesets.get(base.get("ruleset_id", ""))
            affixes = list_monster_affixes(record.spawn_seed, MonsterTier(record.tier))
            entries.append(
                BestiaryEntry(
                    record_id=record.record_id,
                    catalog_id=record.catalog_id,
                    # 접사를 앞에 붙인다 — 개체를 지목할 수 있어야 표적 목록이 된다.
                    label_ko=build_affix_label(affixes, base.get("label_ko", record.catalog_id)),
                    affixes=[
                        {"stat": a.stat, "label_ko": a.label_ko, "percent": a.percent}
                        for a in affixes
                    ],
                    tier=record.tier,
                    level=record.level,
                    level_cap=get_level_cap(floor),
                    zone_floor=floor,
                    entity_slot=record.entity_slot,
                    # 적의 규칙표를 **그대로** 낸다. 요약하면 카운터를 설계할 수 없다.
                    ruleset=(
                        record.ruleset_json
                        if record.ruleset_json is not None
                        else (None if ruleset is None else build_ruleset_payload(ruleset))
                    ),
                    trophies=[item["catalog_id"] for item in trophies],
                    holds_mine=any(item["taken_from"] == account.account_id for item in trophies),
                )
            )
    return BestiaryResponse(entries=entries)
