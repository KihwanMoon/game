"""막타가 전리품을 가져간다 (결정 #34, 2026-09-06 개정).

예전에는 늘 스냅샷의 **첫 개체**가 가져갔다. 그래서 한 마리에 몰렸고(실측으로 996개),
「저 놈이 내 걸 들고 있다」가 **죽인 놈과 무관**해졌다 — 1층에서 죽었는데 그 층의 첫
고블린이 다 갖고 있었다.

**DB 없이 돈다.** 고르는 규칙이 맞는지가 여기서 볼 것이다.
"""

from dataclasses import dataclass

from game.api.monster_service import find_holder
from game.app.core.event_log import LogEntry
from game.app.services.verify_run import resolve_killer

PLAYER = "player"


def build_entry(entity_id, target_id, delta, tick=1):
    return LogEntry(
        tick=tick,
        entity_id=entity_id,
        phase="ACT",
        expr="ATTACK",
        outcome="",
        delta=delta,
        target_id=target_id,
        fired=True,
    )


@dataclass(frozen=True)
class Holder:
    entity_id: str
    record_id: int


# ── 막타 찾기 ────────────────────────────────────────────────────────────


def test_the_last_damaging_blow_wins():
    """★ **이것이 이 변경의 전부다.** 마지막으로 때린 것이 죽인 것이다."""
    entries = (
        build_entry("goblin_rusher_0", PLAYER, -5),
        build_entry("goblin_archer_1", PLAYER, -7),
    )
    assert resolve_killer(entries, PLAYER) == "goblin_archer_1"


def test_blows_on_others_do_not_count():
    entries = (
        build_entry("goblin_archer_1", PLAYER, -7),
        build_entry(PLAYER, "goblin_rusher_0", -40),
    )
    assert resolve_killer(entries, PLAYER) == "goblin_archer_1"


def test_terrain_damage_takes_nothing():
    """★ 함정이 전리품을 가져갈 수는 없다.

    지형 피해는 행위자가 플레이어 자신이라 여기서 걸러진다.
    """
    entries = (build_entry(PLAYER, PLAYER, -9),)
    assert resolve_killer(entries, PLAYER) == ""


def test_healing_is_not_a_blow():
    entries = (
        build_entry("mender_acolyte_0", PLAYER, 12),
        build_entry("goblin_rusher_0", PLAYER, -3),
        build_entry("mender_acolyte_0", PLAYER, 12),
    )
    assert resolve_killer(entries, PLAYER) == "goblin_rusher_0"


def test_no_blows_means_no_killer():
    assert resolve_killer((), PLAYER) == ""


# ── 가져갈 개체 고르기 ───────────────────────────────────────────────────


def test_the_killer_takes_it():
    holders = [Holder("goblin_rusher_0", 11), Holder("goblin_archer_1", 22)]
    assert find_holder(holders, "goblin_archer_1") == 22


def test_an_unknown_killer_takes_nothing():
    """★ 막타가 지속 개체가 아니면 **아무도 안 가져간다**.

    아무나 골라 주면 그 사본이 어디서 왔는지가 다시 거짓이 된다 — 예전의 `holders[0]`
    가 정확히 그것이었다.
    """
    holders = [Holder("goblin_rusher_0", 11)]
    assert find_holder(holders, "그_방에만_있던_잡몹_0") == 0


def test_no_killer_takes_nothing():
    assert find_holder([Holder("goblin_rusher_0", 11)], "") == 0


def test_no_holders_takes_nothing():
    assert find_holder([], "goblin_rusher_0") == 0
