"""예고가 덮는 칸과, 그것을 몇 틱 일찍 보는가.

`telegraph.py` 에서 갈라 나왔다. 저쪽은 **예고가 언제 터지는가**(시간)이고, 이쪽은
**어디를 덮고 누가 먼저 보는가**(공간과 인지)다. 400줄 상한이 계기였지만 가르는 선은
책임이다 (§4).
"""

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.state import Entity

# GDD §6.2 예측 회로가 주는 보너스. 인지 폭을 이만큼 넓힌다.
PREDICTOR_BONUS_TICKS = 1
# 예측 회로 보유 여부를 담는 플래그 이름. 규칙표가 쓰는 A~D 와 겹치지 않는다.
FORESIGHT_FLAG = "FORESIGHT"


def get_foresight_ticks(entity: Entity) -> int:
    """그 엔티티의 예고 인지 보너스 틱 (GDD §6.2 예측 회로).

    아이템 모듈 접사는 아직 없다. 지금은 플래그 하나로 켜고 끄되 조회 지점을
    여기 하나로 모아 둔다 — 흩어 놓으면 모듈 시스템이 붙을 때 전부 찾아야 한다.

    Args:
        entity: 기준 엔티티.

    Returns:
        인지 폭에 더할 틱 수. 예측 회로가 없으면 0.
    """
    return PREDICTOR_BONUS_TICKS if entity.flags.get(FORESIGHT_FLAG, False) else 0


def build_blast_tiles(center: tuple[int, int], radius: int) -> tuple[tuple[int, int], ...]:
    """중심에서 맨해튼 반경 안의 좌표를 모은다.

    거리는 이동과 같은 맨해튼이다 (F-5 결정). 체비셰프로 재면 대각으로 한 칸
    물러난 자리가 안전해 보이는데 실제로는 두 칸이라 회피 판단이 어긋난다.

    Args:
        center: 중심 좌표.
        radius: 맨해튼 반경. 0 이면 중심 한 칸이다.

    Returns:
        정렬된 좌표들. 벽·방 밖은 거르지 않는다 — 무엇을 표시할지는 호출자가 정한다.
    """
    x0, y0 = center
    return tuple(
        sorted(
            (x, y)
            for y in range(y0 - radius, y0 + radius + 1)
            for x in range(x0 - radius, x0 + radius + 1)
            if get_manhattan_distance(center, (x, y)) <= radius
        )
    )
