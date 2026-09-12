"""조건식 한 줄을 읽는다 — 참·거짓과 **그 문장** (TDD §5, GDD §8.2).

`rule_vm.py` 에서 갈라 나왔다. 저쪽은 **어느 규칙이 뜨는가**이고 여기는 **그 규칙이
참인가, 그리고 그것을 사람에게 어떻게 적는가**다. 파일이 400줄 상한을 넘은 것이
계기였을 뿐, 가르는 선은 책임이다 (§4).

**참·거짓만 내보내지 않는다.** 화면은 `적거리(2) <= 사거리(3)` 처럼 **항별 실측값**을
병기해야 하고(GDD §8.2, P1), 그 문장을 만드는 곳이 여기다 — 판정과 문장을 두 곳에서
만들면 화면이 「참」이라 적은 식이 실제로는 다른 값을 본 식이 된다.

순수 함수다. 부작용이 없으므로 같은 스냅샷을 두 번 물으면 같은 답이 나온다.
"""

from collections.abc import Sequence

from game.app.rules.rhs_readers import RHS_STAT_READERS
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.state import Entity
from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import OP_OR, Condition, StatRef, Term

# 대상이 정해져야 값이 나오는 인지 변수. 스냅샷이 아니라 해석된 대상에서 읽는다.
TARGET_BLOCKS = frozenset({"target_hp_percent", "target_is_casting", "target_initiative"})


DEFAULT_ACTION = "APPROACH"
DEFAULT_SELECTOR = "NEAREST"

COMPARATORS = {
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


def read_term_value(
    term: Term,
    snapshot: PerceptionSnapshot,
    target: Entity | None,
    cpu_headroom: int | None = None,
    casting_ids: Sequence[str] = (),
) -> int | bool | None:
    """조건 항의 좌변 값을 읽는다.

    대상 계열과 CPU 여유는 스냅샷에 없다. 전자는 규칙마다 셀렉터가 다르고, 후자는
    규칙표를 알아야 계산되기 때문이다 — 둘 다 VM 만 답할 수 있다.

    Args:
        term: 읽을 항.
        snapshot: PERCEPTION 이 고정한 값들.
        target: 이 규칙의 셀렉터가 고른 대상. 없으면 None.
        cpu_headroom: 남은 CPU 예산.
        casting_ids: 예고를 걸어 둔 엔티티 id 들 (WorldState.casting_ids).

    Returns:
        측정된 값. 아직 구현되지 않은 블록이면 None.
    """
    if term.lhs == "target_hp_percent":
        return target.hp_percent if target is not None else None
    if term.lhs == "target_is_casting":
        return target.entity_id in casting_ids if target is not None else None
    # **선공은 v12 에서 열렸다** (2026-09-11 실측). 틱 안 행동 순서를 정하는 값인데
    # 규칙표가 못 읽어서, 신발을 바꿔도 규칙을 다시 짤 이유가 안 생겼다 — 아이템이
    # 움직일 수 있는 폭에서 승률 변화가 0 이었다. 이제 「내가 먼저 치는가」를 묻는다.
    if term.lhs == "target_initiative":
        return target.initiative if target is not None else None
    if term.lhs == "self_cpu_headroom":
        return cpu_headroom
    if term.lhs in TARGET_BLOCKS:
        return None
    return snapshot.read(term.lhs, term.lhs_param)


def read_stat_value(actor: Entity | None, stat: str) -> int | None:
    """엔티티의 스탯 값을 읽는다 (F-2).

    Args:
        actor: 규칙표의 주인. 없으면 값을 만들 수 없다.
        stat: blocks.json 의 rhs_stats 에 있는 스탯 id.

    Returns:
        측정된 값. 주인이 없거나 모르는 스탯이면 None.
    """
    reader = RHS_STAT_READERS.get(stat)
    if actor is None or reader is None:
        return None
    return reader(actor)


def read_rhs_value(term: Term, actor: Entity | None) -> int | bool | None:
    """조건 항의 우변 값을 읽는다. 리터럴이면 그대로다.

    Args:
        term: 읽을 항.
        actor: 규칙표의 주인. 스탯 우변이 이 엔티티에서 값을 얻는다.

    Returns:
        비교에 쓸 값. 읽을 수 없는 스탯이면 None.
    """
    if isinstance(term.rhs, StatRef):
        return read_stat_value(actor, term.rhs.stat)
    return term.rhs


def format_value(value: int | bool | None) -> str:
    """측정값을 로그에 넣을 문자열로 만든다.

    Args:
        value: 측정된 값. 아직 만들 수 없는 값이면 None.

    Returns:
        사람이 읽는 표기. 값이 없으면 "없음".
    """
    if value is None:
        return "없음"
    if value is True:
        return "참"
    if value is False:
        return "거짓"
    return str(value)


def render_term(
    term: Term, value: int | bool | None, catalog: BlockCatalog, rhs_value: int | bool | None = None
) -> str:
    """항을 실측값이 붙은 문자열로 편다.

    GDD §8.2 가 요구하는 것은 참/거짓이 아니라 **평가된 조건의 실제 값**이다.
    `적거리(2) <= 사거리(3)` 처럼 양변에 괄호로 병기해야 죽고 나서 고칠 곳이 특정된다.
    우변이 리터럴이면 값이 곧 표기이므로 괄호를 붙이지 않는다.

    Args:
        term: 대상 항.
        value: 측정된 좌변 값.
        catalog: 라벨을 얻을 블록 카탈로그.
        rhs_value: 측정된 우변 값. 스탯 우변일 때만 쓰인다.

    Returns:
        사람이 읽는 조건 문자열.
    """
    block = catalog.perceptions.get(term.lhs)
    label = block.label_ko if block is not None else term.lhs
    if term.lhs_param is not None:
        label = f"{label}[{term.lhs_param}]"
    if isinstance(term.rhs, StatRef):
        stat = catalog.rhs_stats.get(term.rhs.stat)
        stat_label = stat.label_ko if stat is not None else term.rhs.stat
        right = f"{stat_label}({format_value(rhs_value)})"
    else:
        right = format_value(term.rhs)
    return f"{label}({format_value(value)}) {term.comparison} {right}"


def evaluate_condition(
    condition: Condition,
    snapshot: PerceptionSnapshot,
    target: Entity | None,
    catalog: BlockCatalog,
    cpu_headroom: int | None = None,
    actor: Entity | None = None,
    casting_ids: Sequence[str] = (),
) -> tuple[bool, str]:
    """조건식을 평가하고 사람이 읽는 문자열을 함께 만든다.

    값을 아직 만들 수 없는 블록(LOS 등)이 섞이면 그 항은 거짓으로 본다. 0 으로 채워
    참이 되게 하면 구현되지 않은 기능이 동작하는 것처럼 보인다. 읽을 수 없는 스탯
    우변도 같은 이유로 거짓이다.

    Args:
        condition: 평가할 조건식.
        snapshot: PERCEPTION 이 고정한 값들.
        target: 셀렉터가 고른 대상.
        catalog: 라벨을 얻을 블록 카탈로그.
        cpu_headroom: 남은 CPU 예산. self_cpu_headroom 항이 이것을 읽는다.
        actor: 규칙표의 주인. 스탯 우변이 이 엔티티에서 값을 얻는다 (F-2).
        casting_ids: 예고를 걸어 둔 엔티티 id 들. `대상이 시전 중인가` 가 읽는다.

    Returns:
        (참/거짓, 렌더링된 조건 문자열).
    """
    results: list[bool] = []
    rendered: list[str] = []
    for term in condition.terms:
        value = read_term_value(term, snapshot, target, cpu_headroom, casting_ids)
        right = read_rhs_value(term, actor)
        rendered.append(render_term(term, value, catalog, right))
        if value is None or right is None:
            results.append(False)
            continue
        results.append(bool(COMPARATORS[term.comparison](value, right)))

    joiner = " OR " if condition.op == OP_OR else " AND "
    outcome = any(results) if condition.op == OP_OR else all(results)
    return outcome, joiner.join(rendered)
