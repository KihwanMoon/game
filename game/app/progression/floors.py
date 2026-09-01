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


def resolve_floor(wanted: int, reached: int) -> int:
    """요청한 층을 갈 수 있는 범위로 접는다.

    Args:
        wanted: 요청한 층. 0 이하이거나 도달 층을 넘으면 접힌다.
        reached: 이 계정이 여기까지 내려가 봤다는 층.

    Returns:
        실제로 갈 층. 늘 1 이상이고 도달 층 이하다.
    """
    return max(FIRST_FLOOR, min(int(wanted), max(FIRST_FLOOR, int(reached))))


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
