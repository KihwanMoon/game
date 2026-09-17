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


def build_line_tiles(
    origin: tuple[int, int], toward: tuple[int, int], length: int
) -> tuple[tuple[int, int], ...]:
    """시전자에서 대상 쪽으로 뻗는 직선 칸들.

    **`LINE` 이 P2 를 증명하는 자리다** (설계/5_스킬 §2). 「거리 스칼라로 대체 가능한
    형태만 있으면 그리드가 필요 없다」— `LINE` 은 적을 일렬로 세우게 만들고, 그것은
    1차원에서 성립하지 않는다.

    **방향은 여덟 갈래로 잘라 낸다.** 이 게임에 바라보는 방향이 없으므로 대상 쪽으로
    잡는데, 대각선을 그대로 쓰면 칸이 어긋난다 — 축마다 부호만 남기면 격자 위의 직선이
    된다. 시전자 칸은 안 넣는다: 자기 발밑을 지지는 것은 이 형태의 뜻이 아니다.

    Args:
        origin: 시전자 좌표.
        toward: 대상 좌표. 같은 칸이면 방향이 없다.
        length: 몇 칸까지 뻗는가.

    Returns:
        정렬된 좌표들. 방향이 없거나 길이가 0 이면 빈 값이다 (R5).
    """
    step_x = _resolve_sign(toward[0] - origin[0])
    step_y = _resolve_sign(toward[1] - origin[1])
    if (step_x, step_y) == (0, 0) or length <= 0:
        return ()
    return tuple(
        sorted((origin[0] + step_x * one, origin[1] + step_y * one) for one in range(1, length + 1))
    )


def _resolve_sign(delta: int) -> int:
    """부호만 남긴다.

    Args:
        delta: 차이.

    Returns:
        -1 · 0 · 1.
    """
    if delta > 0:
        return 1
    return -1 if delta < 0 else 0


def build_chain_tiles(
    origin: tuple[int, int],
    toward: tuple[int, int],
    hop: int,
    hops: int,
    enemies: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    """겨눈 대상에서 시작해 가까운 적을 타고 튀는 칸들 (2026-09-17 요청).

    **`LINE` 이 묻던 것과 다른 것을 묻는다.** 직선은 「누가 뒤에 서 있는가」를 물었고
    그것은 적이 일렬로 설 때만 값을 했다 — 1층 배치에서 그 줄이 잘 안 서서 전도 막대를
    끼고도 35% 였다 (설계/5_스킬 §10.6 실측). 이것은 「누가 서로 가까이 있는가」를
    묻는다. 뭉친 적을 벌하고 흩어진 적에게는 한 명만 맞는다.

    **고르는 규칙이 결정적이어야 한다** (R5). 같은 거리에 둘이 있으면 좌표 순으로
    앞선 쪽이다 — 딕셔너리 순회나 「처음 찾은 것」으로 고르면 두 코어가 갈린다.

    **한 번 지난 자리로 안 돌아간다.** 안 막으면 둘이 서로를 가리키며 번갈아 튀어,
    `hops` 만큼 튀고도 두 칸밖에 안 덮는다.

    Args:
        origin: 시전자 좌표. `toward` 와 같으면 겨눈 것이 없다는 뜻이다.
        toward: 첫 대상 좌표.
        hop: 한 번에 튀는 맨해튼 거리.
        hops: 첫 대상 뒤로 몇 번 더 튀는가.
        enemies: 시전자에게 적대적인 살아 있는 개체들의 좌표. 정렬돼 들어온다.

    Returns:
        정렬된 좌표들. 겨눈 것이 없으면 빈 값이다 — 직선과 같은 규율이며, 그때 예고는
        「빈 칸」으로 서고 그 사실이 로그에 남는다.
    """
    if toward == origin:
        return ()
    chain = [toward]
    seen = {toward}
    for _unused in range(max(0, hops)):
        here = chain[-1]
        nearby = sorted(
            (get_manhattan_distance(here, one), one)
            for one in enemies
            if one not in seen and get_manhattan_distance(here, one) <= hop
        )
        if not nearby:
            break
        step = nearby[0][1]
        chain.append(step)
        seen.add(step)
    return tuple(sorted(chain))
