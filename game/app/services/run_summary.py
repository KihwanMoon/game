"""검증된 런에서 결산 입력을 만든다 (GDD §2.3, docs/설계/3_저장과_멀티플레이 §4).

**메타 세이브는 이 경로로만 갱신된다.** 예전에는 브라우저가 계산한 세이브를 서버가
그대로 받아 저장했는데, 그러면 해금·도감·최고 층이 전부 클라이언트가 쓴 값이 되어
순위의 근거가 될 수 없다 — 이 저장소의 전제(`클라이언트는 적대적이라고 전제한다`)와
정면으로 어긋난다.

`frontend/src/core/services/runSummary.ts` 의 이식이며 **같은 결과를 내야 한다.**
브라우저는 화면에 즉시 반영하려고 자기 것을 계산하고, 서버는 저장할 것을 계산한다.
둘이 갈리면 화면에 뜬 해금이 다음 접속에 사라진다.
"""

from game.app.services.manage_meta import RunSummary, list_ruleset_blocks
from game.app.simulation.state import FACTION_ENEMY, WorldState
from game.schemas.ruleset import RuleSet

# 층을 밟지 못한 런. 진 판이 여기 해당한다.
NO_FLOOR = 0


def count_enemy_kinds(state: WorldState) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """세계에 나타났던 적을 종류별로 센다.

    **죽은 개체도 센다.** 상태에서 지우지 않고 남기므로 소환물까지 빠짐없이 잡히며,
    그것이 도감을 정직하게 만든다 — 소환된 졸개를 잡은 것도 잡은 것이다.

    Args:
        state: 전투가 끝난 세계 상태.

    Returns:
        (만난 종류, 잡은 종류). 둘 다 정렬돼 있고 항목 하나가 1회다 — 딕셔너리 순회
        순서가 세이브에 새어 나가면 안 된다 (R5).
    """
    encountered: list[str] = []
    defeated: list[str] = []
    for entity_id in sorted(state.entities):
        entity = state.entities[entity_id]
        if entity.faction != FACTION_ENEMY:
            continue
        encountered.append(entity.kind_id)
        if entity.hp <= 0:
            defeated.append(entity.kind_id)
    return tuple(sorted(encountered)), tuple(sorted(defeated))


def build_run_summary(
    encountered: tuple[str, ...],
    defeated: tuple[str, ...],
    player_ruleset: RuleSet,
    is_cleared: bool,
    floor_reached: int,
    enemy_rulesets: tuple[RuleSet, ...] = (),
) -> RunSummary:
    """판 하나의 결산 입력을 만든다.

    해금 목록에 **적의 규칙표가 쓰는 블록도 넣는다.** 도감이 적의 규칙표를 그대로
    보여주므로, 적을 만나는 것이 곧 그 블록을 접하는 것이다 (GDD §2.3).

    Args:
        encountered: 만난 적 종류. 항목 하나가 1회다.
        defeated: 잡은 적 종류. 조우 목록의 부분집합이다.
        player_ruleset: 이번 판에 쓴 플레이어 규칙표.
        is_cleared: 플레이어가 이겼는가.
        floor_reached: 이 판이 **끝까지 깬** 가장 깊은 층. 한 층도 못 깼으면 0.
            **부르는 쪽이 재서 넘긴다** — 예전에는 여기서 「이겼으면 1층」을 박아 넣었고,
            그래서 10층을 깨도 최고 층이 1 로 남았다 (`resolve_deepest_floor`).
        enemy_rulesets: 만난 적의 규칙표들. 없으면 플레이어 것만 센다.

    Returns:
        결산 입력.
    """
    perceptions: set[str] = set()
    actions: set[str] = set()
    for ruleset in (player_ruleset, *enemy_rulesets):
        seen_perceptions, seen_actions = list_ruleset_blocks(ruleset)
        perceptions.update(seen_perceptions)
        actions.update(seen_actions)
    return RunSummary(
        floor_reached=max(NO_FLOOR, floor_reached),
        is_cleared=is_cleared,
        seen_perceptions=tuple(sorted(perceptions)),
        seen_actions=tuple(sorted(actions)),
        encountered_kinds=encountered,
        defeated_kinds=defeated,
    )


def list_encountered_rulesets(
    kind_ids: tuple[str, ...],
    enemies: list[dict],
    enemy_rulesets: dict[str, RuleSet],
) -> tuple[RuleSet, ...]:
    """만난 적 종류의 규칙표를 모은다.

    같은 종을 여러 번 만나도 규칙표는 하나다 — 해금은 누적이라 중복이 뜻이 없다.

    Args:
        kind_ids: 만난 적 종류 id. 중복이 들어와도 된다.
        enemies: 밸런스의 적 목록.
        enemy_rulesets: ruleset_id 에서 규칙표로의 대응표.

    Returns:
        찾아낸 규칙표들. 대응표에 없는 id 는 조용히 건너뛴다.
    """
    ruleset_id_by_kind = {kind["id"]: kind["ruleset_id"] for kind in enemies}
    found: dict[str, RuleSet] = {}
    for kind_id in kind_ids:
        ruleset_id = ruleset_id_by_kind.get(kind_id)
        if ruleset_id is not None and ruleset_id in enemy_rulesets:
            found[ruleset_id] = enemy_rulesets[ruleset_id]
    # 정렬해서 꺼낸다. 해금 목록이 딕셔너리 순회 순서에 기대면 안 된다 (R5).
    return tuple(found[key] for key in sorted(found))
