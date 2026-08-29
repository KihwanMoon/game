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
    add_preset,
    apply_run_result,
    filter_preset_rules,
    find_preset,
    get_rule_slot_cap,
    get_slot_bonus,
    list_ruleset_blocks,
    load_meta_save,
    remove_preset,
    save_meta_save,
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
    MAX_PRESET_SLOTS,
    MAX_SLOT_BONUS,
    META_FORMAT_TAG,
    BestiaryRecord,
    MetaSave,
    RulePreset,
    build_meta_payload,
    parse_meta_save,
)
from game.schemas.preset_code import (
    PRESET_CODE_PREFIX,
    PRESET_CODE_VERSION,
    export_preset_code,
    get_code_version,
    parse_preset_code,
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


@pytest.fixture
def sample_preset(enemy_rulesets):
    return RulePreset(name="카이팅 v3", ruleset=enemy_rulesets["ai_longbow"])


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


# --- 프리셋 8슬롯 ----------------------------------------------------------


def test_preset_slots_stop_at_eight(sample_preset):
    meta = MetaSave()
    for index in range(MAX_PRESET_SLOTS):
        meta = add_preset(meta, RulePreset(f"슬롯{index}", sample_preset.ruleset))
    assert len(meta.presets) == MAX_PRESET_SLOTS
    with pytest.raises(ValueError, match="가득"):
        add_preset(meta, RulePreset("하나 더", sample_preset.ruleset))


def test_same_name_replaces_the_slot(sample_preset, enemy_rulesets):
    meta = add_preset(MetaSave(), sample_preset)
    replaced = RulePreset(sample_preset.name, enemy_rulesets["ai_rusher"])
    meta = add_preset(meta, replaced)
    assert len(meta.presets) == 1
    assert find_preset(meta, sample_preset.name).ruleset.ruleset_id == "ai_rusher"


def test_removed_preset_is_gone(sample_preset):
    meta = remove_preset(add_preset(MetaSave(), sample_preset), sample_preset.name)
    assert meta.presets == ()
    assert find_preset(meta, sample_preset.name) is None


def test_locked_rules_are_dropped_on_load(sample_preset):
    meta = MetaSave(
        unlocked_perceptions=("target_distance",), unlocked_actions=("ATTACK", "RETREAT")
    )
    loaded = filter_preset_rules(sample_preset, meta)
    actions = tuple(rule.action for rule in loaded.ruleset.rules)
    # SKILL_1 은 미해금이라 그 줄만 빠지고 나머지는 순서대로 남는다.
    assert actions == ("RETREAT", "ATTACK")
    assert loaded.name == sample_preset.name


# --- 공유 코드 -------------------------------------------------------------


def test_preset_code_round_trip(enemy_rulesets):
    for ruleset_id, ruleset in sorted(enemy_rulesets.items()):
        preset = RulePreset(name=f"복제 {ruleset_id}", ruleset=ruleset)
        restored = parse_preset_code(export_preset_code(preset))
        assert restored == preset


def test_preset_code_has_version_prefix(sample_preset):
    code = export_preset_code(sample_preset)
    assert code.startswith(PRESET_CODE_PREFIX)
    assert get_code_version(code) == PRESET_CODE_VERSION


def test_same_preset_gives_the_same_code(sample_preset, enemy_rulesets):
    twin = RulePreset(name=sample_preset.name, ruleset=enemy_rulesets["ai_longbow"])
    assert export_preset_code(sample_preset) == export_preset_code(twin)


def test_code_survives_copy_paste_damage(sample_preset):
    code = export_preset_code(sample_preset)
    mangled = f"  {code.rstrip('=')}\n"
    assert parse_preset_code(mangled) == sample_preset


@pytest.mark.parametrize("code", ["", "hello", "v2", "9:abc", "vx:abc"])
def test_codes_without_a_version_are_rejected(code):
    with pytest.raises(ValueError, match="시작해야"):
        parse_preset_code(code)


def test_other_generation_code_is_rejected(sample_preset):
    body = export_preset_code(sample_preset)[len(PRESET_CODE_PREFIX) :]
    with pytest.raises(ValueError, match="세대"):
        parse_preset_code(f"v1:{body}")


@pytest.mark.parametrize("body", ["!!!!", "AAAA"])
def test_broken_code_body_is_rejected(body):
    with pytest.raises(ValueError, match="풀 수 없다"):
        parse_preset_code(PRESET_CODE_PREFIX + body)


def test_truncated_code_is_rejected(sample_preset):
    code = export_preset_code(sample_preset)
    with pytest.raises(ValueError, match="풀 수 없다"):
        parse_preset_code(code[: len(code) // 2])


# --- 파일 저장 -------------------------------------------------------------


def test_missing_file_gives_an_empty_save(tmp_path):
    assert load_meta_save(tmp_path / "없다.json") == MetaSave()


def test_file_round_trip_keeps_everything(tmp_path, sample_preset, catalog):
    meta = apply_run_result(
        MetaSave(),
        RunSummary(
            floor_reached=3,
            seen_perceptions=("target_distance", "self_hp_percent"),
            seen_actions=("ATTACK", "RETREAT"),
            encountered_kinds=(SUMMONER_KIND, ARCHER_KIND),
            defeated_kinds=(ARCHER_KIND,),
        ),
        catalog,
    )
    meta = add_preset(meta, sample_preset)
    target = tmp_path / "meta_save.json"
    save_meta_save(meta, target)
    assert load_meta_save(target) == meta


def test_saved_file_is_byte_identical_for_the_same_save(tmp_path, sample_preset):
    target = tmp_path / "meta_save.json"
    meta = add_preset(MetaSave(best_floor=2), sample_preset)
    save_meta_save(meta, target)
    first = target.read_bytes()
    save_meta_save(meta, target)
    assert target.read_bytes() == first


def test_save_creates_the_directory(tmp_path):
    target = tmp_path / "volume" / "meta_save.json"
    save_meta_save(MetaSave(), target)
    assert json.loads(target.read_text(encoding="utf-8"))["format"] == META_FORMAT_TAG


def test_save_leaves_no_temp_file(tmp_path):
    save_meta_save(MetaSave(), tmp_path / "meta_save.json")
    assert [path.name for path in sorted(tmp_path.iterdir())] == ["meta_save.json"]


def test_newer_format_is_rejected():
    payload = build_meta_payload(MetaSave())
    payload["format"] = "v99"
    with pytest.raises(ValueError, match="새 세이브"):
        parse_meta_save(payload)


@pytest.mark.parametrize("tag", [None, "", "1", "vx"])
def test_bad_format_tag_is_rejected(tag):
    payload = build_meta_payload(MetaSave())
    if tag is None:
        del payload["format"]
    else:
        payload["format"] = tag
    with pytest.raises(ValueError):
        parse_meta_save(payload)


def test_hand_edited_save_is_normalized():
    payload = build_meta_payload(MetaSave())
    payload["unlocked_actions"] = ["RETREAT", "ATTACK"]
    payload["bestiary"] = [
        {"kind_id": SUMMONER_KIND, "encounters": 1, "defeats": 0},
        {"kind_id": ARCHER_KIND, "encounters": 2, "defeats": 1},
    ]
    meta = parse_meta_save(payload)
    assert meta.unlocked_actions == ("ATTACK", "RETREAT")
    assert tuple(record.kind_id for record in meta.bestiary) == (ARCHER_KIND, SUMMONER_KIND)
