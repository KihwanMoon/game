"""층 진행 규칙 (설계/6_몬스터 §3).

**층은 서버가 정한다.** 클라이언트가 고르게 두면 1층 캐릭터로 10층 보상을 뽑고, 그것은
시드를 골라 담는 것(T2)과 같은 종류의 구멍이다.

되돌아가는 것은 막지 않는다 — 편한 층을 다시 도는 것은 손해이지 이득이 아니고, 막으면
연습할 곳이 사라진다.
"""

FIRST_FLOOR = 1

# 보스 방. **일반 후보에서 빠지고 보스 층의 마지막 자리에만 선다** — 섞이면 보스를 두 번
# 만나거나 보스 층이 아닌 데서 만나게 된다.
BOSS_ROOM_ID = "boss_hall"

# 퍼센트의 밑값. 정수 내림 나눗셈으로만 쓴다 (R5).
PERCENT_BASE = 100


def resolve_floor(wanted: int, reached: int) -> int:
    """요청한 층을 갈 수 있는 범위로 접는다.

    Args:
        wanted: 요청한 층. 0 이하이거나 도달 층을 넘으면 접힌다.
        reached: 이 계정이 여기까지 내려가 봤다는 층.

    Returns:
        실제로 갈 층. 늘 1 이상이고 도달 층 이하다.
    """
    return max(FIRST_FLOOR, min(int(wanted), max(FIRST_FLOOR, int(reached))))


def resolve_deepest_floor(start_floor: int, cleared_rooms: int, rooms_per_floor: int) -> int:
    """이 하강이 **끝까지 깬** 가장 깊은 층.

    **진 판도 몇 층까지는 깼다.** 하강이 여러 층에 걸치므로 「이겼다」 하나로는 어디까지
    갔는지 알 수 없고, 끝까지 깬 방 수가 그것을 말한다.

    도달 기록과 메타 세이브의 최고 층이 **같은 수를 봐야 한다.** 예전에는 아니었다 —
    도달 기록은 여기서 나온 값을 받았는데 메타 세이브는 「이겼으면 1층」을 박아 넣고
    있어서, 7층까지 내려간 계정의 최고 층이 1 로 남았다. 화면이 틀리게 적는 것으로 끝나지
    않는다: 층 보너스 규칙 슬롯이 그 값에서 나오므로(`manage_meta.get_slot_bonus`)
    최대 +4 가 아무에게도 안 붙고 있었다 (GDD §2.3).

    Args:
        start_floor: 하강이 시작한 층.
        cleared_rooms: 끝까지 깬 방 수.
        rooms_per_floor: 층 하나에 드는 방 수. 0 이면 연쇄 전체가 한 층이다.

    Returns:
        가장 깊은 층. 한 층도 못 깼으면 0 — 「0층」이 아니라 **없다**는 뜻이다.
    """
    cleared_floors = cleared_rooms // max(1, rooms_per_floor)
    if cleared_floors <= 0:
        return 0
    return start_floor + cleared_floors - 1


def read_floor_cap(balance: dict) -> int:
    """마지막 층을 읽는다.

    Args:
        balance: balance.json 을 읽은 딕셔너리.

    Returns:
        마지막 층. 안 적혀 있으면 1 — **모르면 안 내려보낸다.** 큰 값으로 넘겨짚으면
        방이 모자란 층으로 사람을 보내게 된다.
    """
    return max(FIRST_FLOOR, int(balance.get("floor_scale", {}).get("max_floor", FIRST_FLOOR)))


def read_boss_floor(balance: dict) -> int:
    """보스가 서는 층을 읽는다.

    Args:
        balance: balance.json 을 읽은 딕셔너리.

    Returns:
        보스 층. 안 적혀 있으면 마지막 층.
    """
    return int(balance.get("floor_scale", {}).get("boss_floor", read_floor_cap(balance)))


def read_floor_heal_pct(balance: dict) -> int:
    """층을 깰 때 돌려주는 최대체력의 퍼센트를 읽는다.

    Args:
        balance: balance.json 을 읽은 딕셔너리.

    Returns:
        퍼센트. 안 적혀 있으면 0 이다 — **모르면 안 준다.** 넘겨짚어 주면 저장된
        리플레이가 조용히 다른 판이 된다.
    """
    return max(0, int(balance.get("floor_scale", {}).get("floor_heal_pct", 0)))


def resolve_floor_heal(hp: int, hp_max: int, heal_pct: int) -> int:
    """층을 깬 직후의 HP 를 정한다.

    **정수 내림 나눗셈이다** (R5). 부동소수를 쓰면 두 코어가 마지막 자리에서 갈리고,
    그 한 점이 30방을 도는 동안 다른 판으로 벌어진다.

    이 회복이 있는 이유는 실측이다 — 없을 때 18개 규칙표 중 **아무도 2층을 못 넘었다.**
    회복 수단이 물약 두 개뿐이라 30방을 도는 동안 소진이 벽이 된다. 반대로 전부
    돌려주면 층마다 새 판이 되어 「앞 층을 얼마나 깔끔하게 깼는가」가 뜻을 잃는다.

    Args:
        hp: 층을 끝냈을 때의 HP.
        hp_max: 최대체력.
        heal_pct: 돌려줄 퍼센트.

    Returns:
        다음 층을 여는 HP. 최대체력을 안 넘는다.
    """
    return min(hp_max, hp + hp_max * heal_pct // PERCENT_BASE)
