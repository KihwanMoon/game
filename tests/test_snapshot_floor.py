"""스냅샷은 제 층에만 얹힌다.

**자리 이름이 층을 구분하지 않는다.** `goblin_rusher_0` 이 1층부터 9층까지 따로 살고,
하강 티켓은 그 전부를 싣는다. 이름만으로 겹치면 나중 것이 이기는데 그것이 가장 깊은
층의 개체다 — 1층 방에 9층 레벨 10 짜리가 섰고, 신규 계정이 첫 방에서 그것을 만났다.
규칙표 17개 어느 것으로도 1층을 못 깼다(실측 136판, 돌파 0).

두 코어가 같은 값을 썼기 때문에 검증은 어긋나지 않았다. 어긋난 것은 검증이 아니라
게임이며, 그래서 조용했다.
"""

from game.app.services.run_battle import build_floor_overrides
from game.schemas.monster_snapshot import MonsterSnapshot, sort_snapshots


def build_snapshot(zone_floor, level, record_id=0):
    """같은 자리 이름을 가진 스냅샷 하나.

    Args:
        zone_floor: 사는 층.
        level: 레벨.
        record_id: 개체 기록 id.

    Returns:
        스냅샷.
    """
    return MonsterSnapshot(
        entity_id="goblin_rusher_0",
        record_id=record_id or zone_floor,
        kind_id="goblin_rusher",
        tier="NORMAL",
        level=level,
        hp_max=10 * level,
        attack=level,
        defense=0,
        rule_slots=0,
        cpu_budget=0,
        zone_floor=zone_floor,
    )


def test_a_deep_monster_does_not_stand_in_a_shallow_room():
    """★ **버그 그 자체다.** 1층 방에 9층 개체가 서면 안 된다."""
    snapshots = (build_snapshot(1, 1), build_snapshot(9, 9))
    picked = build_floor_overrides(snapshots, 1)
    assert picked["goblin_rusher_0"].level == 1


def test_each_floor_gets_its_own():
    """★ 층마다 제 것이 선다 — 한 티켓이 1층부터 10층까지 돈다."""
    snapshots = tuple(build_snapshot(floor, floor) for floor in range(1, 11))
    for floor in range(1, 11):
        assert build_floor_overrides(snapshots, floor)["goblin_rusher_0"].level == floor


def test_a_floor_with_nothing_frozen_gets_nothing():
    """얼려 둔 것이 없는 층은 템플릿 그대로 돈다."""
    assert build_floor_overrides((build_snapshot(3, 3),), 1) == {}


def test_an_old_snapshot_still_applies_anywhere():
    """★ 층을 모르는 스냅샷(0)은 그대로 얹는다.

    층을 싣기 전에 발급된 티켓이 그 값이다. 발급 당시와 다르게 재시뮬하면 **정상 제출이
    반려된다** — 고치려던 것보다 나쁜 일이다 (R5).
    """
    old = build_snapshot(0, 4)
    assert build_floor_overrides((old,), 1)["goblin_rusher_0"].level == 4
    assert build_floor_overrides((old,), 7)["goblin_rusher_0"].level == 4


def test_sorting_is_total():
    """★ 정렬이 전순서다 — 이름이 겹치면 들어온 순서가 남고, 그것은 DB 조회 순서다."""
    first = sort_snapshots((build_snapshot(9, 9), build_snapshot(1, 1), build_snapshot(3, 3)))
    second = sort_snapshots((build_snapshot(3, 3), build_snapshot(9, 9), build_snapshot(1, 1)))
    assert [item.zone_floor for item in first] == [1, 3, 9]
    assert first == second


def test_a_tie_on_floor_breaks_on_record_id():
    """같은 층에 같은 이름이 둘이면 레코드 id 가 순서를 정한다."""
    rows = sort_snapshots((build_snapshot(2, 2, 77), build_snapshot(2, 2, 12)))
    assert [item.record_id for item in rows] == [12, 77]


def test_the_payload_carries_the_floor():
    """★ 층이 실려 나가지 않으면 브라우저는 여전히 옛 방식으로 얹는다."""
    from game.schemas.monster_snapshot import build_snapshot_payload, parse_snapshot

    payload = build_snapshot_payload(build_snapshot(6, 6))
    assert payload["zone_floor"] == 6
    assert parse_snapshot(payload).zone_floor == 6


def test_an_old_payload_reads_as_unknown():
    """구버전 절에는 층이 없다. 0 으로 읽어야 옛 티켓이 예전처럼 돈다."""
    from game.schemas.monster_snapshot import build_snapshot_payload, parse_snapshot

    payload = build_snapshot_payload(build_snapshot(6, 6))
    del payload["zone_floor"]
    assert parse_snapshot(payload).zone_floor == 0


def build_probe_ticket(floor=1):
    """검사용 티켓 하나.

    Args:
        floor: 하강이 시작하는 층.

    Returns:
        티켓.
    """
    from game.app.store.tickets import IssuedTicket

    return IssuedTicket(
        ticket_id="probe",
        seed=1,
        room_id="corridor",
        floor=floor,
        mode="PRACTICE",
        core_version="probe",
    )


def test_a_first_floor_death_does_not_grow_the_ninth_floor():
    """★ 만난 적 없는 개체가 그 죽음으로 자라면 안 된다.

    실제로 그렇게 돌았다 — 봇이 1층에서 죽을 때마다 `arch_summoner 6→7` 이 함께 찍혔다.
    """
    from game.api.monster_service import list_fought_snapshots

    world = tuple(build_snapshot(floor, floor) for floor in range(1, 11))
    fought = list_fought_snapshots(world, build_probe_ticket(1), 1)
    assert [item.zone_floor for item in fought] == [1]


def test_a_descent_covers_the_floors_it_passed():
    """★ 3층까지 갔으면 1~3층이 반영된다 — 지나온 층은 실제로 싸운 층이다."""
    from game.api.monster_service import list_fought_snapshots

    world = tuple(build_snapshot(floor, floor) for floor in range(1, 11))
    fought = list_fought_snapshots(world, build_probe_ticket(1), 3)
    assert [item.zone_floor for item in fought] == [1, 2, 3]


def test_an_old_style_submission_still_covers_everything():
    """층을 안 적는 옛 제출(0)은 하강 전체다 — 그 티켓의 반영이 사라지면 안 된다."""
    from game.api.monster_service import list_fought_snapshots

    world = tuple(build_snapshot(floor, floor) for floor in range(1, 4))
    assert len(list_fought_snapshots(world, build_probe_ticket(1), 0)) == 3


def test_a_floorless_snapshot_is_always_included():
    """층을 모르는 개체(0)는 빼지 않는다 — 빼면 옛 티켓의 세계 반영이 통째로 사라진다."""
    from game.api.monster_service import list_fought_snapshots

    world = (build_snapshot(0, 4), build_snapshot(9, 9))
    fought = list_fought_snapshots(world, build_probe_ticket(1), 1)
    assert [item.zone_floor for item in fought] == [0]
