"""예고를 판에 올린다 — 형태를 고르고, 벽을 거르고, 등록한다.

`abilities.py` 에서 갈라 나왔다. 400줄 상한이 계기였지만 가르는 선은 책임이다 (§4).
예고에 대한 모듈이 이제 셋이고, 셋이 다른 것을 안다.

    telegraph_shape.py   **어디를 덮는가** — 좌표만 안다. 세계를 모른다
    telegraph_cast.py    **그것을 어떻게 올리는가** — 형태를 고르고 벽을 거른다 (여기)
    telegraph.py         **언제 터지는가** — 남은 틱과 취소

저쪽(`abilities.py`)에 남은 것은 소환·회복·주문서다. 그것들은 예고를 안 쓴다.
"""

from game.app.simulation.state import Entity, WorldState
from game.app.simulation.telegraph import TelegraphBoard
from game.app.simulation.telegraph_shape import (
    build_blast_tiles,
    build_chain_tiles,
    build_line_tiles,
)
from game.app.skills.catalog import SHAPE_CHAIN, SHAPE_LINE
from game.schemas.room import WALKABLE_TILES


def build_cast_tiles(
    caster: Entity, telegraph: dict, enemies: tuple[tuple[int, int], ...] = ()
) -> tuple[tuple[int, int], ...]:
    """이 예고가 덮는 칸들. 형태가 고른다 (설계/5_스킬 §2).

    **몬스터 절에는 형태가 없다.** 없으면 반경으로 읽는다 — 지금 콘텐츠가 전부 그쪽이고,
    형태를 필수로 만들면 옛 절이 통째로 안 읽힌다.

    Args:
        caster: 시전자.
        telegraph: 예고 절.
        enemies: 시전자에게 적대적인 살아 있는 개체들의 좌표. `CHAIN` 만 본다 — 다른
            형태는 적이 어디 섰는지와 무관하게 칸이 정해진다.

    Returns:
        벽 거르기 전의 좌표들.
    """
    toward = tuple(telegraph.get("toward") or caster.position)
    if telegraph.get("shape") == SHAPE_CHAIN:
        # **적을 타고 튄다.** 다른 형태와 달리 이것만 세계를 본다 — 칸이 기하가 아니라
        # 누가 어디 섰는지로 정해지기 때문이다. 시전 시점의 자리로 굳으므로 튀는 사이에
        # 비켜선 적은 안 맞는다 (예고의 정답은 회피다).
        return build_chain_tiles(
            caster.position,
            toward,
            int(telegraph.get("radius", 0)),
            int(telegraph.get("hops", 0)),
            enemies,
        )
    if telegraph.get("shape") == SHAPE_LINE:
        return build_line_tiles(caster.position, toward, int(telegraph.get("length", 0)))
    # **중심은 겨눈 곳이다.** 자폭형에서 물려받은 자리라 발밑에 고정돼 있었고, 그래서
    # 플레이어가 10칸 밖의 적에게 던진 메테오가 제 발밑에서 터졌다 — 1층 60런 실측
    # 승률 1% 의 진짜 이유이며, 로그에 `예고 발동 → player HP 74/100 (-26)` 로
    # 찍혀 있었다. 겨눌 곳이 없으면 발밑이고, 몬스터 절에는 `toward` 가 없어 그쪽은
    # 예전 그대로 자기 자리에서 터진다.
    return build_blast_tiles(toward, telegraph["radius"])


def register_blast(
    state: WorldState, board: TelegraphBoard, caster: Entity, telegraph: dict
) -> str:
    """즉발 광역기 대신 예고를 건다 (GDD §4.2).

    반경의 정본은 이 예고 설정이다 — actions.AREA_ATTACK_RADIUS 는 예고를 쓰지 않는
    즉발 광역기의 값이며 둘은 다른 능력이다.

    벽과 방 밖은 걸러 낸다. 거르지 않으면 닿지도 않는 칸이 붉게 칠해져, 플레이어가
    피할 필요가 없는 곳을 피하려 든다.

    Args:
        state: 세계 상태.
        board: 예고를 담을 판.
        caster: 시전자.
        telegraph: balance.json 의 그 종류 telegraph 절.

    Returns:
        로그에 남길 결과 문자열.
    """
    # **적 좌표는 여기서 읽는다.** `build_cast_tiles` 에 세계를 통째로 넘기면 형태
    # 계산이 세계를 알게 되고, 그러면 그것만 따로 검사할 수 없다.
    enemies = tuple(sorted(other.position for other in state.list_hostiles(caster)))
    tiles = tuple(
        position
        for position in build_cast_tiles(caster, telegraph, enemies)
        if state.get_tile(*position) in WALKABLE_TILES
    )
    board.register(
        caster_id=caster.entity_id,
        skill_id=telegraph["skill"],
        tiles=tiles,
        damage=telegraph["damage"],
        lead_ticks=telegraph["lead_ticks"],
        visible_ticks=telegraph["visible_ticks"],
        cancel_on_death=telegraph["cancel_on_death"],
        # 몬스터 절에는 없다 — 없으면 안 켠다. 켜는 것은 스킬 데이터다 (§10.3).
        cancel_on_act=bool(telegraph.get("cancel_on_act", False)),
        cancel_on_hit=bool(telegraph.get("cancel_on_hit", False)),
        # 몬스터 절에는 없다. 스킬이 정한 것만 실린다.
        effects=tuple(telegraph.get("effects", ())),
    )
    return f"예고 {len(tiles)}칸 — {telegraph['lead_ticks']}틱 뒤 발동"
