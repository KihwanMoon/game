"""봉인된 옵션 — 등급이 칸을 주고, 화폐가 그것을 연다 (설계/4_아이템 §17).

**서버가 결과를 부여한다.** 클라이언트가 굴리면 마음에 드는 값이 나올 때까지 다시 굴릴
수 있고, 그러면 봉인이 아무것도 막지 않는다. `secrets` 를 쓰는 것은 코어 밖이라 R5 와
무관하다 (`loot.py` 머리말과 같은 자리).

**무엇이 들어올지를 미리 정해 두지 않는다.** 미리 정하면 그 값이 어딘가에 저장되고,
저장된 것은 언젠가 클라이언트로 새어 나간다 — 그 순간 "열기 전에 아는" 것이 되어 열
이유가 사라진다.
"""

from game.app.items.drops import get_below, get_weighted
from game.schemas.item import Affix

# 한 칸을 여는 값. **뒤 칸이 비싸다** — 같은 값이면 유물의 두 칸이 상급의 한 칸보다
# 싸게 먹히고, 그러면 등급이 비용에서 뜻을 잃는다. 밸런스는 나중에 정한다.
UNSEAL_BASE_COST = 120
UNSEAL_STEP_PERCENT = 150
PERCENT_BASE = 100


def compute_unseal_cost(opened: int) -> int:
    """다음 칸을 여는 값을 낸다.

    **등급을 안 받는다.** 옵션 풀이 등급과 무관하게 하나뿐이라, 유물의 칸이 상급의 칸보다
    비쌀 근거가 지금은 없다 — 근거 없이 등급을 인자로 두면 다음 사람이 그것을 의미 있는
    것으로 읽는다. 풀을 등급별로 가르는 날 그때 받는다.

    Args:
        opened: 이미 연 칸 수.

    Returns:
        내야 하는 화폐.
    """
    cost = UNSEAL_BASE_COST
    for _step in range(max(0, opened)):
        cost = cost * UNSEAL_STEP_PERCENT // PERCENT_BASE
    return cost


def create_sealed_affix(pool_rows: tuple[tuple[str, str, int, int, int, int, int], ...]) -> Affix:
    """풀에서 옵션 하나를 굴린다.

    Args:
        pool_rows: (stat, label_ko, flat_min, flat_max, percent_min, percent_max, weight) 들.

    Returns:
        굴린 접사.

    Raises:
        ValueError: 풀이 비어 있거나 가중치가 전부 0 인 경우. 그대로 열어 주면 돈만
            받고 아무것도 안 준다.
    """
    if not pool_rows:
        raise ValueError("옵션 풀이 비어 있다")
    keys = tuple((f"{row[0]}|{row[1]}", row[6]) for row in pool_rows)
    picked = get_weighted(keys)
    if picked is None:
        raise ValueError("옵션 풀의 가중치가 전부 0 이다")
    row = next(item for item in pool_rows if f"{item[0]}|{item[1]}" == picked)
    return Affix(
        stat=row[0],
        flat=row[2] + get_below(row[3] - row[2] + 1),
        percent=row[4] + get_below(row[5] - row[4] + 1),
        label_ko=row[1],
    )
