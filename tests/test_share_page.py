"""공유된 규칙표가 한 장으로 성립하는가 (2026-09-20).

**이 장이 검색으로 들어오는 문이다.** 게임 본체는 SPA 라 크롤러가 받아 가는 글자가
부트 화면 68자뿐이고, 도감은 자산에서 나와 빌드가 굽지만 이쪽은 사람이 올리는 것이라
가짓수가 무한해서 구울 수 없다 — 서버가 낸다.

**문장을 파이썬에 복제하지 않았다.** 브라우저 쪽에 규칙을 한국어 문장으로 읽는 것이
있는데(``editor/ruleSentence``) 그 문법을 옮겨 적으면 둘이 갈린다. 그래서 표를 낸다 —
칸으로 나누면 문법이 필요 없고 이름은 전부 ``blocks.json`` 에서 온다.
"""

import json

import pytest

from game.app.share.page import (
    apply_param_slot,
    build_rule_rows,
    format_action,
    format_condition,
)
from game.app.share.shell import build_description, render_missing_page, render_share_page
from game.app.store.shared_rulesets import build_share_id
from game.config import BENCHMARK_RULESETS_PATH, BLOCKS_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.ruleset import load_rulesets


@pytest.fixture(name="catalog")
def fixture_catalog():
    """블록 카탈로그.

    Returns:
        동결된 카탈로그.
    """
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(name="ruleset")
def fixture_ruleset():
    """표본 규칙표.

    Returns:
        벤치마크 한 벌.
    """
    return load_rulesets(BENCHMARK_RULESETS_PATH)["focus_lowest_guard"]


def test_rules_become_a_table(ruleset, catalog) -> None:
    """★ 규칙 줄 수만큼 표의 줄이 선다."""
    html = build_rule_rows(ruleset, catalog)
    # 머리줄도 <tr> 이라 통째로 세면 하나가 더 잡힌다. 몸통만 본다.
    body = html[html.index("<tbody>") : html.index("</tbody>")]
    assert body.count("<tr>") == len(ruleset.rules)
    assert "이런 상황이면" in html


def test_labels_come_from_the_catalog(ruleset, catalog) -> None:
    """★ 영문 id 가 그대로 나가지 않는다 — 그 줄만 다른 언어가 된다."""
    html = build_rule_rows(ruleset, catalog)
    for rule in ruleset.rules:
        assert rule.action not in html or catalog.actions[rule.action].label_ko in html


def test_condition_keeps_the_game_grammar(ruleset, catalog) -> None:
    """비교 기호를 그대로 둔다. 편집기가 그렇게 보여 주므로 풀어 적으면 둘이 갈린다."""
    shown = format_condition(ruleset.rules[0], catalog)
    assert any(mark in shown for mark in ("<", ">", "=", "!"))


def test_action_param_is_named(catalog) -> None:
    """인자를 대괄호로 붙이고 그것도 한글로 적는다."""
    from game.schemas.ruleset import parse_ruleset

    one = parse_ruleset(
        {
            "ruleset_id": "probe",
            "version": 1,
            "rules": [
                {
                    "priority": 1,
                    "cpu_cost": 1,
                    "action": "USE_SKILL",
                    "action_param": "METEOR",
                    "target": "NEAREST",
                    "set_flag": None,
                    "conditions": {
                        "op": "SINGLE",
                        "terms": [{"lhs": "self_hp_percent", "cmp": "<", "rhs": 50}],
                    },
                }
            ],
        }
    )
    assert "[" in format_action(one.rules[0], catalog)


def test_page_carries_the_name_and_canonical(ruleset, catalog) -> None:
    """★ 장마다 제목과 정식 주소가 다르다 — 같으면 한 장으로 합쳐진다."""
    html = render_share_page("내 표", "/r/abc123", build_rule_rows(ruleset, catalog), "설명")
    assert "<title>내 표 · 규칙표" in html
    assert 'rel="canonical" href="https://sealedstacks.com/r/abc123"' in html
    assert 'name="robots" content="index, follow"' in html


def test_missing_page_is_not_blank() -> None:
    """★ 빈 404 를 안 낸다 — 링크는 오래 남고, 빈 장은 사이트가 죽은 것으로 읽힌다."""
    html = render_missing_page()
    assert "없는 규칙표" in html
    assert 'href="/"' in html


def test_description_is_cut_where_we_decide() -> None:
    """검색 결과에서 잘리는 자리를 우리가 정한다."""
    assert len(build_description("가" * 200, 5, 8)) <= 150


def test_same_ruleset_gets_the_same_address(ruleset) -> None:
    """★ 주소가 내용의 해시다 — 같은 표를 두 번 올려도 링크가 안 갈린다."""
    payload = json.loads(json.dumps({"a": 1, "b": [2, 3]}))
    flipped = json.loads(json.dumps({"b": [2, 3], "a": 1}))
    assert build_share_id(payload) == build_share_id(flipped)
    assert build_share_id(payload) != build_share_id({"a": 2})


def test_label_slot_is_filled_not_appended() -> None:
    """★ 이름이 자리를 품고 있으면 갈아 끼운다.

    ``self_cooldown_ready`` 의 이름은 「내 쿨타임[재주] 완료」다. 뒤에 그냥 붙이면
    「내 쿨타임[재주] 완료[사격]」이 되어 자리가 둘로 보인다 — 실제로 그렇게 나갔다.
    """
    assert apply_param_slot("내 쿨타임[재주] 완료", "사격") == "내 쿨타임[사격] 완료"
    assert apply_param_slot("대상 거리", "가장 가까운 적") == "대상 거리[가장 가까운 적]"
