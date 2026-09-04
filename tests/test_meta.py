"""Run Loop 메타 프로그레션 테스트 (로드맵 W5, GDD §2.3, TDD §9).

네 가지를 본다 — 해금이 런을 넘어 누적되는가, 규칙 슬롯 상한이 층 도달 기록을
따르는가, 프리셋 공유 코드가 왕복해도 같은 규칙표인가, 도감이 적의 규칙표를 그대로
돌려주는가. 마지막 하나에는 "규칙표 밖에서 처리되는 능력도 함께 나오는가" 가 붙는다.
도감이 절반만 보여주면 플레이어가 세운 카운터가 통하지 않고, 그 이유를 어디에서도
찾을 수 없다 — P1 이 뒤집히는 지점이다.
"""

import json

import pytest

from game.app.services.manage_meta import (
    RunSummary,
    apply_run_result,
    get_rule_slot_cap,
    get_slot_bonus,
    list_ruleset_blocks,
)
from game.app.services.record_bestiary import (
    build_bestiary_page,
    format_bestiary_page,
    get_enemy_ruleset,
    list_bestiary_pages,
    load_strategy_notes,
)
from game.app.simulation.actions import DEFERRED_ACTIONS
from game.config import BALANCE_PATH, BLOCKS_PATH, ENEMY_RULESETS_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.meta_save import (
    MAX_SLOT_BONUS,
    BestiaryRecord,
    MetaSave,
)
from game.schemas.ruleset import load_rulesets

SUMMONER_KIND = "goblin_summoner"
BOMBER_KIND = "bomb_slime"
RUSHER_KIND = "goblin_rusher"
ARCHER_KIND = "goblin_archer"
BASE_SLOTS = 5


@pytest.fixture(scope="module")
def balance():
    return json.loads(BALANCE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def enemy_rulesets():
    return load_rulesets(ENEMY_RULESETS_PATH)


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


# --- 영구 해금 -------------------------------------------------------------


def test_unlocks_accumulate_across_runs(catalog):
    first = apply_run_result(
        MetaSave(),
        RunSummary(seen_perceptions=("target_distance",), seen_actions=("ATTACK",)),
        catalog,
    )
    second = apply_run_result(
        first,
        RunSummary(seen_perceptions=("self_hp_percent",), seen_actions=("RETREAT",)),
        catalog,
    )
    assert second.unlocked_perceptions == ("self_hp_percent", "target_distance")
    assert second.unlocked_actions == ("ATTACK", "RETREAT")
    # 앞 런의 결과는 그대로 남는다 — 결산은 덮어쓰기가 아니라 누적이다.
    assert first.unlocked_actions == ("ATTACK",)


def test_repeated_unlock_does_not_duplicate(catalog):
    summary = RunSummary(seen_perceptions=("target_distance", "target_distance"))
    meta = apply_run_result(MetaSave(), summary, catalog)
    meta = apply_run_result(meta, summary, catalog)
    assert meta.unlocked_perceptions == ("target_distance",)


def test_unknown_block_is_not_unlocked(catalog):
    meta = apply_run_result(MetaSave(), RunSummary(seen_actions=("ATTACK", "NOT_A_BLOCK")), catalog)
    assert meta.unlocked_actions == ("ATTACK",)


def test_unlock_without_catalog_keeps_everything():
    meta = apply_run_result(MetaSave(), RunSummary(seen_actions=("ATTACK", "HOMEBREW")))
    assert meta.unlocked_actions == ("ATTACK", "HOMEBREW")


def test_enemy_ruleset_supplies_unlockable_blocks(enemy_rulesets, catalog):
    perceptions, actions = list_ruleset_blocks(enemy_rulesets["ai_archer"])
    assert perceptions == ("target_distance",)
    assert actions == ("ATTACK", "RETREAT")
    meta = apply_run_result(
        MetaSave(), RunSummary(seen_perceptions=perceptions, seen_actions=actions), catalog
    )
    assert meta.unlocked_actions == ("ATTACK", "RETREAT")


# --- 규칙 슬롯 상한 --------------------------------------------------------


@pytest.mark.parametrize(
    ("best_floor", "bonus"),
    [(0, 0), (1, 0), (2, 1), (3, 2), (5, 4), (9, 4)],
)
def test_slot_bonus_follows_best_floor(best_floor, bonus):
    assert get_slot_bonus(best_floor) == bonus


def test_slot_bonus_stops_at_the_cap():
    assert get_slot_bonus(100) == MAX_SLOT_BONUS


def test_slot_cap_adds_bonus_to_base():
    meta = apply_run_result(MetaSave(), RunSummary(floor_reached=3))
    assert get_rule_slot_cap(meta, BASE_SLOTS) == BASE_SLOTS + 2


def test_best_floor_never_decreases():
    meta = apply_run_result(MetaSave(), RunSummary(floor_reached=4))
    meta = apply_run_result(meta, RunSummary(floor_reached=1))
    assert meta.best_floor == 4
    assert get_slot_bonus(meta.best_floor) == 3


# --- 도감 기록 -------------------------------------------------------------


def test_bestiary_counts_accumulate():
    summary = RunSummary(
        encountered_kinds=(RUSHER_KIND, RUSHER_KIND, ARCHER_KIND),
        defeated_kinds=(RUSHER_KIND,),
    )
    meta = apply_run_result(MetaSave(), summary)
    meta = apply_run_result(meta, summary)
    records = {record.kind_id: record for record in meta.bestiary}
    assert records[RUSHER_KIND] == BestiaryRecord(RUSHER_KIND, encounters=4, defeats=2)
    assert records[ARCHER_KIND] == BestiaryRecord(ARCHER_KIND, encounters=2, defeats=0)


def test_bestiary_is_sorted_by_kind_id():
    summary = RunSummary(encountered_kinds=(SUMMONER_KIND, ARCHER_KIND, BOMBER_KIND))
    meta = apply_run_result(MetaSave(), summary)
    kinds = tuple(record.kind_id for record in meta.bestiary)
    assert kinds == tuple(sorted(kinds))


# --- 도감 열람 -------------------------------------------------------------


def test_bestiary_returns_enemy_ruleset_verbatim(balance, enemy_rulesets):
    for entry in balance["enemies"]:
        expected = enemy_rulesets[entry["ruleset_id"]]
        assert get_enemy_ruleset(entry["id"], balance, enemy_rulesets) is expected
        assert build_bestiary_page(entry["id"], balance, enemy_rulesets).ruleset == expected


def test_unknown_enemy_is_rejected(balance, enemy_rulesets):
    with pytest.raises(KeyError):
        get_enemy_ruleset("no_such_goblin", balance, enemy_rulesets)


def test_page_carries_stats_and_label(balance, enemy_rulesets):
    page = build_bestiary_page(ARCHER_KIND, balance, enemy_rulesets)
    stats = {line.key: line.value for line in page.stats}
    assert page.label_ko == "고블린 궁수"
    assert stats["hp_max"] == 26
    assert stats["attack_range"] == 4


def test_summon_details_appear_outside_the_ruleset(balance, enemy_rulesets):
    page = build_bestiary_page(SUMMONER_KIND, balance, enemy_rulesets)
    note = next(note for note in page.notes if note.ability_id == "SUMMON" and note.details)
    details = {line.key: line.value for line in note.details}
    assert details == {"spawns": RUSHER_KIND, "every_ticks": 3, "max_alive": 3}
    # 규칙표에는 이 셋이 어디에도 없다. 그것이 이 항목이 존재하는 이유다.
    assert all(
        term.lhs != "spawns" for rule in page.ruleset.rules for term in rule.conditions.terms
    )


def test_telegraph_details_appear_outside_the_ruleset(balance, enemy_rulesets):
    page = build_bestiary_page(BOMBER_KIND, balance, enemy_rulesets)
    note = next(note for note in page.notes if note.ability_id == "AREA_ATTACK" and note.details)
    details = {line.key: line.value for line in note.details}
    assert details["damage"] == 18
    assert details["lead_ticks"] == 2
    assert details["radius"] == 1
    assert details["self_destruct"] == "예"
    assert details["cancel_on_death"] == "예"


def test_summon_is_no_longer_warned_as_deferred(balance, enemy_rulesets):
    # W6 통합으로 SUMMON 이 ACT 에서 실제로 실행된다. 도감이 계속 "미구현" 이라
    # 경고하면 플레이어가 소환을 무시해도 된다고 오해한다.
    assert "SUMMON" not in DEFERRED_ACTIONS
    page = build_bestiary_page(SUMMONER_KIND, balance, enemy_rulesets)
    assert [note for note in page.notes if not note.details] == []


def test_deferred_action_is_warned(monkeypatch, balance, enemy_rulesets):
    # 미구현 경고 자체는 살아 있어야 한다. 다음에 같은 상황이 오면 도감이 알린다.
    monkeypatch.setitem(DEFERRED_ACTIONS, "SUMMON", "테스트용 미구현 사유")
    page = build_bestiary_page(SUMMONER_KIND, balance, enemy_rulesets)
    warnings = [note for note in page.notes if not note.details]
    assert [note.ability_id for note in warnings] == ["SUMMON"]
    assert "테스트용 미구현 사유" in warnings[0].reason_ko


def test_plain_enemy_has_no_notes(balance, enemy_rulesets):
    page = build_bestiary_page(RUSHER_KIND, balance, enemy_rulesets)
    assert page.notes == ()


def test_pages_are_limited_to_recorded_enemies(balance, enemy_rulesets):
    meta = apply_run_result(MetaSave(), RunSummary(encountered_kinds=(SUMMONER_KIND, ARCHER_KIND)))
    pages = list_bestiary_pages(meta, balance, enemy_rulesets)
    assert tuple(page.kind_id for page in pages) == (ARCHER_KIND, SUMMONER_KIND)


def test_strategy_line_comes_from_the_ruleset(balance, enemy_rulesets):
    strategies = load_strategy_notes()
    page = build_bestiary_page(BOMBER_KIND, balance, enemy_rulesets, strategies)
    assert page.strategy_ko == strategies["ai_bomber"]
    # 전략표가 없으면 밸런스 노트로 떨어진다 — 빈 줄을 내지는 않는다.
    assert build_bestiary_page(BOMBER_KIND, balance, enemy_rulesets).strategy_ko


def test_rendered_page_shows_every_rule(balance, enemy_rulesets):
    page = build_bestiary_page(SUMMONER_KIND, balance, enemy_rulesets)
    text = format_bestiary_page(page)
    for rule in page.ruleset.rules:
        assert f"[{rule.priority}]" in text
        assert rule.action in text
    assert "<attack_range>" in text
    assert "동시 상한 3" in text
    # 규칙표 JSON 과 같은 표기여야 도감을 보고 그대로 옮겨 적을 수 있다.
    assert "== true" in text
    assert "True" not in text


@pytest.mark.parametrize(
    ("start_floor", "cleared_rooms", "rooms_per_floor", "deepest"),
    [
        # 한 층도 못 깼다 — 0 은 「0층」이 아니라 **없다**는 뜻이다.
        (1, 0, 5, 0),
        (1, 4, 5, 0),
        # 딱 한 층.
        (1, 5, 5, 1),
        (1, 9, 5, 1),
        # 여러 층에 걸친 하강. 여기가 예전에 늘 1 로 접히던 자리다.
        (1, 10, 5, 2),
        (1, 35, 5, 7),
        (1, 50, 5, 10),
        # 깊은 데서 출발하면 그만큼 더 깊다.
        (3, 10, 5, 4),
        # 층 개념이 없는 옛 티켓. 연쇄 전체가 한 층이다.
        (1, 3, 0, 3),
    ],
)
def test_deepest_floor_follows_the_rooms_actually_cleared(
    start_floor, cleared_rooms, rooms_per_floor, deepest
):
    """★ 「이겼다」 하나로는 어디까지 갔는지 알 수 없다 — 깬 방 수가 그것을 말한다.

    예전에는 메타 세이브가 「이겼으면 1층」을 박아 넣어서, 7층까지 내려간 계정의 최고 층이
    1 로 남았다. 화면이 틀리게 적는 것으로 끝나지 않는다: 층 보너스 규칙 슬롯이 그 값에서
    나오므로 최대 +4 가 **아무에게도** 안 붙고 있었다 (GDD §2.3).
    """
    from game.app.progression.floors import resolve_deepest_floor

    assert resolve_deepest_floor(start_floor, cleared_rooms, rooms_per_floor) == deepest


def test_the_slot_bonus_is_reachable_at_all():
    """★ 최고 층이 1 에서 안 움직이면 이 곡선 전체가 죽은 코드다.

    `get_slot_bonus` 자체는 늘 옳았다 — 넣어 주는 값이 늘 1 이었을 뿐이다. 곡선만
    검사하면 그 사실이 안 잡히므로, **도달할 수 있는 값인지**를 함께 잰다.
    """
    from game.app.progression.floors import resolve_deepest_floor

    # 5방짜리 층을 넷 깨고 출발층이 1 이면 4층이다 → 보너스 3.
    reached = resolve_deepest_floor(1, 20, 5)
    assert reached == 4
    assert get_slot_bonus(reached) == 3
