"""봇이 깊은 층에서 죽으면 그 자리에 그림자가 선다 (T11).

**서버가 판단한다.** 봇의 러너가 「나 죽었으니 그림자 세워 줘」라고 말하는 구조면 그것은
클라이언트 보고가 되고, 세계 상태를 클라이언트가 정하는 길이 열린다 (T9). 재시뮬이
확정한 패배에서만 선다.

**깊은 층에서만 선다.** 1층에서 죽은 빌드가 서면 도플갱어가 「못 하는 것들의 모임」이
되고, 만나도 사건이 아니다.
"""

from psycopg_pool import ConnectionPool

from game.app.bots.doppel import MIN_DOPPEL_FLOOR
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.store.bots import check_is_bot
from game.app.store.doppels import check_doppel_opt_in, create_doppel, find_free_slot
from game.schemas.monster_snapshot import build_entity_id
from game.schemas.room import RoomTemplate


def list_floor_slots(rooms: dict[str, RoomTemplate], room_ids: tuple[str, ...]) -> tuple[str, ...]:
    """그 층 방들의 스폰 자리 이름을 순서대로 낸다.

    **템플릿의 자리여야 한다.** 방 배치에 없는 이름으로 세우면 스냅샷이 아무에게도 안
    붙어서, 개체는 있는데 아무도 못 만나는 상태가 된다.

    Args:
        rooms: 방 템플릿 대응표.
        room_ids: 그 층이 도는 방들.

    Returns:
        자리 이름들. 순서가 곧 우선순위다.
    """
    found: list[str] = []
    for room_id in room_ids:
        template = rooms.get(room_id)
        if template is None:
            continue
        found.extend(
            build_entity_id(spawn.kind, index) for index, spawn in enumerate(template.enemy_spawns)
        )
    return tuple(found)


def apply_doppel_from_death(
    pool: ConnectionPool,
    rooms: dict[str, RoomTemplate],
    account_id: int,
    verified: VerifiedRun,
    floor: int,
    room_ids: tuple[str, ...],
    loadout: dict,
    ruleset: dict,
) -> str:
    """죽은 자리에 그림자를 세운다.

    **봇은 늘 세우고, 사람은 켠 사람만** (2026-09-06). 그림자가 원본의 규칙표로 싸우므로
    관전하며 행동을 보면 남의 해답이 어느 정도 역산된다 — 그것은 켜는 사람이 알고 켜야
    하는 대가라, 기본은 꺼져 있다.

    Args:
        pool: 연결 풀.
        rooms: 방 템플릿 대응표.
        account_id: 죽은 계정.
        verified: 서버가 확정한 결과.
        floor: 죽은 층.
        room_ids: 그 층이 도는 방들.
        loadout: 그 봇이 쓰던 전투 입력.
        ruleset: 그 봇이 쓰던 규칙표.

    Returns:
        화면에 적을 한 줄. 안 섰으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED or verified.outcome == OUTCOME_PLAYER_WIN:
        return ""
    # **봇은 늘, 사람은 켠 사람만** (2026-09-06). 그림자는 원본의 규칙표로 싸우므로
    # 관전하며 행동을 보면 남의 해답이 어느 정도 역산된다 — 켜는 사람이 알고 켜야 한다.
    if floor < MIN_DOPPEL_FLOOR:
        return ""
    if not check_is_bot(pool, account_id) and not check_doppel_opt_in(pool, account_id):
        return ""
    slot = find_free_slot(pool, floor, list_floor_slots(rooms, room_ids))
    record_id = create_doppel(pool, account_id, floor, slot, loadout, ruleset)
    return "" if record_id == 0 else f"도플갱어가 {floor}층에 섰다 (#{record_id})"
