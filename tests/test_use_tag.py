"""소모품 태그 (설계/4_아이템 §4, #54).

**한 목록이 두 가지 일을 겸하고 있었다.** `POTION`·`SCROLL` 은 코드가 읽어 가방을 세는
데 썼고, `MELEE`·`SHIELD`·`CURSED` 는 아무 데서도 안 읽혔다. 그래서 물약에 분류용 이름표를
하나 더 붙이면 **그 이름표까지 소모품 종류가 됐다.**

그리고 규칙이 모르는 종류를 가리키면 **포션이 빠졌다.** 문지기는 그 태그의 개수를 보고
(`rule_vm`), 실제로 빼는 것은 포션이었다(`abilities`) — 지금은 블록 파라미터가 둘뿐이라
안 걸리지만, 소모품을 하나 늘리는 순간 걸린다.

여기서 지키는 것은 셋이다.

1. **코드가 읽는 태그는 `use_tag` 하나다.**
2. **표시용 이름표를 늘려도 가방이 안 흔들린다.**
3. **모르는 종류는 아무것도 안 쓴다.**
"""

from game.schemas.item import ItemCatalogEntry, ItemKind, build_item_payload, parse_item


def build_potion(use_tag="POTION", tags=("POTION",)):
    """검사용 소모품 하나를 만든다.

    Args:
        use_tag: 쓰임새.
        tags: 표시용 이름표들.

    Returns:
        카탈로그 항목.
    """
    return ItemCatalogEntry(
        catalog_id="probe_potion",
        kind=ItemKind.CONSUMABLE,
        label_ko="표본 물약",
        use_tag=use_tag,
        tags=tuple(tags),
        stack_max=9,
    )


class _Stack:
    """가방 한 칸. 저장 층을 안 거치고 세는 부분만 본다."""

    def __init__(self, catalog_id, count):
        self.stack_catalog_id = catalog_id
        self.stack_count = count


def count_with(monkeypatch, entry, count=3):
    """그 항목을 가방에 넣고 세어 본다.

    Args:
        monkeypatch: pytest 픽스처.
        entry: 카탈로그 항목.
        count: 가진 개수.

    Returns:
        쓰임새에서 개수로.
    """
    from game.api import loadout_service

    monkeypatch.setattr(
        loadout_service, "list_inventory", lambda _pool, _entity: [_Stack(entry.catalog_id, count)]
    )
    return loadout_service.count_consumables(None, 1, {entry.catalog_id: entry})


def test_only_the_use_tag_is_counted(monkeypatch):
    """★ 표시용 이름표를 하나 더 붙였다고 소모품 종류가 늘면 안 된다."""
    counted = count_with(monkeypatch, build_potion(tags=("POTION", "HEAL", "STARTER")))
    assert counted == {"POTION": 3}


def test_an_item_without_a_use_tag_is_not_counted(monkeypatch):
    """★ 쓰임새가 없는 것은 어느 `USE_ITEM` 도 못 쓴다 — 세면 규칙이 「가능」으로 보인다."""
    assert count_with(monkeypatch, build_potion(use_tag=None, tags=("TRINKET",))) == {}


def test_the_use_tag_survives_the_json_round_trip():
    """★ 스냅샷을 거쳐도 쓰임새가 남는다 — 빠지면 내보내기 한 번에 물약을 못 쓰게 된다."""
    assert parse_item(build_item_payload(build_potion())).use_tag == "POTION"


def test_display_tags_stay_out_of_the_code_path():
    """★ 표시용은 표시용으로만 남는다 — 둘을 한 칸에 두면 다시 겸직이 된다."""
    entry = build_potion(use_tag="POTION", tags=("HEAL",))
    assert entry.use_tag == "POTION"
    assert entry.tags == ("HEAL",)


def test_an_unknown_kind_spends_nothing(probe_world):
    """★ 모르는 종류를 가리키면 **포션이 빠지던** 자리다.

    문지기는 그 태그를 보고 소모는 포션을 뺐다 — 엉뚱한 소모품이 사라진다.
    """
    from game.app.simulation.plan import PlannedAction

    world, player = probe_world(skills=())
    player.consumables["POTION"] = 2
    player.consumables["BOMB"] = 1
    plan = PlannedAction(entity_id=player.entity_id, action_id="USE_ITEM", item_kind="BOMB")
    build_support(world).apply_item(player, plan)
    assert player.consumables["POTION"] == 2, "모르는 종류가 포션을 태웠다"
    assert player.consumables["BOMB"] == 1


def test_a_known_kind_still_spends(probe_world):
    """★ 문지기가 정상 사용까지 막으면 포션을 못 쓴다."""
    from game.app.simulation.plan import PlannedAction

    world, player = probe_world(skills=())
    player.hp = 10
    player.consumables["POTION"] = 2
    plan = PlannedAction(entity_id=player.entity_id, action_id="USE_ITEM", item_kind="POTION")
    build_support(world).apply_item(player, plan)
    assert player.consumables["POTION"] == 1


def build_support(world):
    """검사용 행동 실행기를 만든다.

    Args:
        world: 검사용 세계.

    Returns:
        행동 실행기. 엔진이 만드는 것과 같은 것이다 — 검사 전용을 따로 만들면 검사만
        통과하는 길이 생긴다.
    """
    from game.app.core.event_log import EventLog
    from game.app.simulation.actions import ActionExecutor
    from game.app.simulation.plan import EngineConfig

    config = EngineConfig(damage_rules=(), kind_types={}, skill_coef_pct={}, skill_range={})
    return ActionExecutor(state=world, log=EventLog(), config=config, telegraphs={})
