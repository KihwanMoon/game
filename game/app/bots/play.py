"""봇 한 판 — 브라우저가 하는 것과 같은 순서로 논다.

**결과를 보내지 않는다.** 제출에는 결과를 받을 자리가 없고 서버가 티켓으로 다시 돌려
확정한다 (T9). 그러면 봇이 왜 직접 돌려 보는가 — **어디까지 깼는지 알아야 청구할 층을
고를 수 있기 때문이다.** 브라우저도 같은 이유로 코어를 돌린다. 봇이 5층을 주장하고
서버가 「2층에서 죽었다」고 답해도 결과는 같지만, 그러면 봇은 사람이 하는 일을 하지
않는 것이고 이 봇의 값어치가 「진짜 경로가 도는지」에 있으므로 그 차이가 중요하다.

**못하는 봇이 있어야 한다.** 실력(`skill_pct`)은 규칙표의 아랫줄을 덜어 내는 것으로
표현한다 — 우선순위가 낮은 줄부터 사라지므로, 실력이 낮은 봇은 「표를 아직 다 못 짠
사람」처럼 논다. 확률을 굴리지 않는다: 같은 봇이 판마다 다른 표로 나가면 그 봇의 성적이
무엇 때문인지 아무도 모른다.
"""

import math

from game.app.bots.personas import BOT_PERSONAS

# 실력의 분모. `skill_pct` 가 퍼센트라서다.
PERCENT_BASE = 100


def build_bot_handle(index: int) -> str:
    """봇의 계정 이름을 짓는다.

    Args:
        index: 0 부터의 순번.

    Returns:
        `bot1` 꼴. 사람이 화면에서 봇임을 바로 알아보는 것이 목적이다 (T11).
    """
    return f"bot{index + 1}"


def build_played_ruleset(raw: dict, skill_pct: int) -> dict:
    """실력만큼만 규칙을 남긴 규칙표를 만든다.

    **윗줄부터 남긴다.** 우선순위가 높은 줄이 그 규칙표의 뼈대이고, 아랫줄은 다듬기다 —
    덜 다듬어진 표가 못하는 사람의 표다. 반대로 윗줄을 덜면 표가 뜻을 잃어 「못하는 것」이
    아니라 「망가진 것」이 된다.

    한 줄은 반드시 남긴다. 전부 덜면 폴백만 남아 열 봇이 모두 같은 판을 돈다.

    Args:
        raw: 규칙표 원본(JSON 그대로).
        skill_pct: 실력. 100 이면 그대로 쓴다.

    Returns:
        규칙이 줄어든 사본. 원본은 건드리지 않는다.
    """
    rules = sorted(raw.get("rules", []), key=lambda rule: int(rule.get("priority", 0)))
    if skill_pct >= PERCENT_BASE or not rules:
        return {**raw, "rules": rules}
    kept = max(1, math.ceil(len(rules) * skill_pct / PERCENT_BASE))
    return {**raw, "rules": rules[:kept]}


def resolve_claim_floors(
    start_floor: int, cleared_rooms: int, rooms_per_floor: int, total_rooms: int
) -> tuple[int, ...]:
    """이 판이 **들어간** 층들을 층 번호로 낸다.

    브라우저는 층을 깰 때마다 청구하고, **죽어도 한 번 더 청구한다**. 죽은 판을 안 보내면
    그 판은 세계에 없던 일이 된다 — 도감도 안 차고, 그 층 몬스터도 안 크고, 순위에도 안
    오른다. 실제로 그렇게 돌렸다: 봇이 티켓 18개를 태우고 제출은 0건이었다.

    깬 층만 세면 안 되는 이유가 그것이다. 「끝까지 못 갔으면 한 층 더」가 죽은 층이다.

    Args:
        start_floor: 하강이 시작한 층.
        cleared_rooms: 끝까지 깬 방 수.
        rooms_per_floor: 층 하나에 드는 방 수.
        total_rooms: 이 하강의 전체 방 수. 끝까지 갔는지 여기서 안다.

    Returns:
        청구할 층들. 층 개념이 없는 옛 티켓이면 비어 있다.
    """
    if rooms_per_floor <= 0:
        return ()
    cleared = cleared_rooms // rooms_per_floor
    entered = cleared + (1 if cleared_rooms < total_rooms else 0)
    return tuple(start_floor + step for step in range(entered))


def list_persona_specs() -> tuple[tuple[str, str, int, int], ...]:
    """봇 열의 (이름, 규칙표, 리듬, 실력) 을 낸다.

    이름을 성격에서 떼어 낸 이유는 **화면에서 봇임을 알아보는 것이 먼저**이기 때문이다
    (T11). 성격 이름(「겁쟁이」)은 사람 이름처럼 보여서 그 목적과 어긋난다.

    Returns:
        순번 순의 명세들.
    """
    return tuple(
        (build_bot_handle(index), persona.ruleset_id, persona.cadence_sec, persona.skill_pct)
        for index, persona in enumerate(BOT_PERSONAS)
    )
