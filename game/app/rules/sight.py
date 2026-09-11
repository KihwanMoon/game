"""원거리 공격이 벽에 막혔는가 (GDD §4.1).

`rule_vm.py` 에서 갈라 나왔다. 저쪽은 **어느 규칙이 뜨는가**(평가)이고 여기는 **그
규칙이 닿는가**(지형)다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐, 가르는 선은
책임이다 (§4).

**「불가」의 세 번째 사유다** (결정 #04). 조건은 참인데 수단이 없는 것 — 스킬 미장착·
소모품 없음과 같은 자리이며, 거짓과 구분해서 화면에 적어야 P1 이 성립한다.
"""

from game.app.grid.vision import VisionGrid, check_line_of_sight
from game.app.simulation.plan import ATTACK_ACTIONS, MELEE_REACH
from game.app.simulation.state import Entity, WorldState


def check_sight_blocked(
    action: str, entity: Entity, target: Entity | None, state: WorldState
) -> bool:
    """원거리 공격인데 직선 시야가 막혔는가.

    근접은 안 본다 — 인접한 칸에 시야를 묻는 것은 뜻이 없고, 물으면 벽 모서리에서 근접
    공격이 안 나가는 일이 생긴다.

    **막으면 다음 규칙이 기회를 얻는다.** 예전에는 그대로 발동시켜 틱만 버렸다. 사거리
    안에 있는 한 조건은 매 틱 참이라 **같은 규칙이 영원히 다시 뽑히고**, 캐릭터가
    엄폐물 뒤의 적을 향해 가만히 선 채로 판이 끝났다.

    Args:
        action: 규칙이 고른 행동.
        entity: 행위자.
        target: 셀렉터가 고른 대상. None 이면 막힌 것이 아니다.
        state: 지금 세계. 부순 벽을 반영해야 하므로 템플릿이 아니라 상태를 본다.

    Returns:
        막혔으면 True.
    """
    if action not in ATTACK_ACTIONS or target is None:
        return False
    if entity.attack_range <= MELEE_REACH:
        return False
    grid = VisionGrid(state, state.room.width, state.room.height)
    return not check_line_of_sight(grid, entity.position, target.position)
