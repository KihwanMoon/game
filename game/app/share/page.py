"""공유된 규칙표를 HTML 한 장으로 만든다 (SEO · 유입).

**여기가 서버가 HTML 을 내는 유일한 자리다.** 도감은 자산에서 나오므로 빌드가 굽지만,
공유된 표는 사람이 올리는 것이라 가짓수가 무한해서 구울 수 없다.

**문장을 만들지 않는다.** 브라우저 쪽에 이미 규칙을 한국어 문장으로 읽는 것이
있는데(`editor/ruleSentence`), 그 문법을 파이썬에 옮겨 적으면 둘이 갈린다 — 이
저장소가 이름에서 이미 겪은 병이다. 그래서 여기서는 **표**를 만든다: 조건·행동·대상을
칸으로 나누면 문법이 필요 없고, 이름은 전부 `blocks.json` 에서 온다.
"""

import re
from html import escape

from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import Rule, RuleSet, StatRef

# 도감 페이지가 쓰는 판을 그대로 쓴다. 같은 성격의 장이 둘로 보이면 안 된다.
STYLESHEET = "/codex.css"
SITE_ORIGIN = "https://sealedstacks.com"


def read_block_label(catalog: BlockCatalog, block_id: str) -> str:
    """블록 id 를 사람이 읽는 이름으로.

    Args:
        catalog: 동결된 블록 카탈로그.
        block_id: 인지 변수 또는 행동 또는 셀렉터 id.

    Returns:
        한글 이름. 카탈로그에 없으면 id 그대로 — 빈 칸보다 낫다.
    """
    for table in (catalog.perceptions, catalog.actions, catalog.selectors):
        found = table.get(block_id)
        if found is not None:
            return found.label_ko
    return block_id


def apply_param_slot(label: str, param_label: str) -> str:
    """이름의 인자 자리를 채운다.

    **이름이 자리를 품고 있을 수 있다.** `self_cooldown_ready` 의 이름은
    「내 쿨타임[재주] 완료」인데, 뒤에 그냥 붙이면 「내 쿨타임[재주] 완료[사격]」이
    되어 자리가 둘로 보인다. 자리가 있으면 갈아 끼우고 없을 때만 붙인다.

    Args:
        label: 블록 이름.
        param_label: 인자의 이름.

    Returns:
        인자가 붙은 이름.
    """
    marked = re.sub(r"\[[^\]]*\]", f"[{param_label}]", label, count=1)
    return marked if marked != label else f"{label}[{param_label}]"


def format_condition(rule: Rule, catalog: BlockCatalog) -> str:
    """규칙의 조건을 한 줄로 적는다.

    비교 기호(`<=`)는 그대로 둔다. **그것이 이 게임의 문법이고** 편집기도 그렇게
    보여 준다 — 「이하」로 풀어 적으면 화면과 여기가 다른 말을 쓰게 된다.

    Args:
        rule: 규칙 한 줄.
        catalog: 블록 카탈로그.

    Returns:
        조건 문자열.
    """
    parts = []
    for term in rule.conditions.terms:
        lhs = read_block_label(catalog, term.lhs)
        if term.lhs_param is not None:
            lhs = apply_param_slot(lhs, read_block_label(catalog, term.lhs_param))
        rhs = term.rhs
        shown = read_block_label(catalog, rhs.stat) if isinstance(rhs, StatRef) else str(rhs)
        parts.append(f"{lhs} {term.comparison} {shown}")
    joiner = " 또는 " if rule.conditions.op == "OR" else " 그리고 "
    return joiner.join(parts)


def format_action(rule: Rule, catalog: BlockCatalog) -> str:
    """규칙의 행동을 한 줄로 적는다.

    Args:
        rule: 규칙 한 줄.
        catalog: 블록 카탈로그.

    Returns:
        행동 문자열. 인자가 있으면 대괄호로 붙인다.
    """
    action = read_block_label(catalog, rule.action)
    if rule.action_param is None:
        return action
    return apply_param_slot(action, read_block_label(catalog, rule.action_param))


def build_rule_rows(ruleset: RuleSet, catalog: BlockCatalog) -> str:
    """규칙표를 표로 만든다.

    Args:
        ruleset: 규칙표.
        catalog: 블록 카탈로그.

    Returns:
        `<table>`.
    """
    rows = []
    for rule in ruleset.rules:
        target = "" if rule.target is None else read_block_label(catalog, rule.target)
        rows.append(
            "<tr>"
            f"<td>{rule.priority}</td>"
            f"<td>{escape(format_condition(rule, catalog))}</td>"
            f"<td>{escape(format_action(rule, catalog))}</td>"
            f"<td>{escape(target)}</td>"
            "</tr>"
        )
    head = "<tr><th>순서</th><th>이런 상황이면</th><th>이렇게 한다</th><th>누구에게</th></tr>"
    body = "\n          ".join(rows)
    return (
        '<table class="cx__rules">\n'
        f"        <thead>{head}</thead>\n"
        f"        <tbody>\n          {body}\n        </tbody>\n"
        "      </table>"
    )
