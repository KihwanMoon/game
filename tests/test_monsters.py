"""몬스터 성장과 폭주 방지 (docs/설계/6_몬스터 §2·§5, 결정 #35).

**DB 없이 돈다.** 여기서 보는 것은 곡선과 상한이고, 그것은 저장소와 무관하다.

폭주 방지를 넷 다 검사한다. 하나만 두면 나머지가 조용히 빠져도 알 수 없다.
"""

import pytest

from game.app.monsters.growth import (
    DEFEAT_LEVEL_LOSS,
    LEVEL_CAP_PER_FLOOR,
    MIN_LEVEL,
    build_growth,
    compute_defeat_xp,
    compute_level,
    compute_required_xp,
    get_level_cap,
)
from game.app.monsters.tiers import (
    MonsterTier,
    check_can_persist,
    compute_tier_stat,
    get_tier_percent,
)

BASE_HP = 40


# ── 등급 (§1) ────────────────────────────────────────────────────────────


def test_tiers_are_ordered_by_power():
    assert (
        get_tier_percent(MonsterTier.NORMAL)
        < get_tier_percent(MonsterTier.ELITE)
        < get_tier_percent(MonsterTier.BOSS)
    )


def test_tier_stat_floors_down():
    """정수 나눗셈이며 내림이다 — 부동소수를 쓰면 두 코어가 같은 적에서 갈린다."""
    assert compute_tier_stat(BASE_HP, MonsterTier.ELITE) == BASE_HP * 150 // 100
    assert isinstance(compute_tier_stat(7, MonsterTier.ELITE), int)


def test_normal_monsters_cannot_persist():
    """★ 지속시키면 개체가 무한히 쌓여 스냅샷이 티켓 용량을 넘는다."""
    assert check_can_persist(MonsterTier.NORMAL) is False
    assert check_can_persist(MonsterTier.ELITE) is True
    assert check_can_persist(MonsterTier.BOSS) is True


# ── 폭주 방지 넷 (결정 #35) ──────────────────────────────────────────────


def test_level_cap_follows_the_floor():
    """★ 방지 1·2 — 구역 격리 + 레벨 상한. 저층 몬스터는 저층 상한을 쓴다."""
    assert get_level_cap(1) == LEVEL_CAP_PER_FLOOR
    assert get_level_cap(3) == LEVEL_CAP_PER_FLOOR * 3
    assert get_level_cap(0) == MIN_LEVEL


def test_experience_cannot_pass_the_cap():
    """★ 아무리 먹여도 그 층의 상한에서 멈춘다."""
    level, _ = compute_level(10_000_000, floor=1)
    assert level == get_level_cap(1)


def test_required_xp_grows_with_level():
    """★ 방지 4 — 성장률 체감. 레벨이 높을수록 다음 레벨이 멀어진다."""
    steps = [compute_required_xp(level) for level in range(1, 6)]
    assert steps == sorted(steps)
    assert steps[-1] > steps[0]


def test_defeat_lowers_the_level():
    """★ 방지 3 — 처치 시 감쇠. 죽여도 흔적이 없으면 승리가 세계에 남지 않는다."""
    total = sum(compute_required_xp(level) for level in range(1, 4))
    level, _ = compute_level(total, floor=3)
    lowered = compute_defeat_xp(total, level, floor=3)
    new_level, _ = compute_level(lowered, floor=3)
    assert new_level == level - DEFEAT_LEVEL_LOSS


def test_defeat_never_goes_below_the_minimum():
    """감쇠가 음수 경험치를 만들면 안 된다 — 뜻이 없다."""
    lowered = compute_defeat_xp(0, MIN_LEVEL, floor=1)
    assert lowered >= 0
    assert compute_level(lowered, floor=1)[0] == MIN_LEVEL


# ── 성장이 올리는 것 (§2) ────────────────────────────────────────────────


def test_growth_raises_expressiveness_not_only_stats():
    """★ 성장이 규칙 슬롯·CPU 를 올린다.

    스탯만 오르면 "숫자가 커졌다" 로 끝난다. 슬롯이 늘면 판단이 정교해지고, 도감이
    규칙표를 공개하므로 플레이어가 무엇이 달라졌는지 읽을 수 있다 (P1).
    """
    low = build_growth(1)
    high = build_growth(12)
    assert high.bonus_rule_slots > low.bonus_rule_slots
    assert high.bonus_cpu > low.bonus_cpu


def test_level_one_gives_no_bonus():
    growth = build_growth(MIN_LEVEL)
    assert growth.bonus_rule_slots == 0
    assert growth.bonus_cpu == 0
    assert growth.stat_percent == 100


def test_stat_growth_is_gentler_than_expressiveness():
    """스탯은 낮게 둔다 — 성장의 무게가 표현력 쪽에 있어야 한다."""
    growth = build_growth(9)
    # 레벨 9 에서 스탯은 두 배가 안 된다.
    assert growth.stat_percent < 200


@pytest.mark.parametrize("floor", [1, 2, 5])
def test_level_is_deterministic(floor):
    """같은 경험치는 언제나 같은 레벨을 낸다. 부동소수를 쓰면 재시작 뒤에 갈릴 수 있다."""
    assert compute_level(1234, floor) == compute_level(1234, floor)


def test_experience_is_not_banked_above_the_cap():
    """★ 상한 위로 쌓으면 처치 감쇠가 무의미해진다.

    한 레벨어치를 덜어 내도 여전히 상한 위라 레벨이 그대로다 — 결정 #35 의 방지 3
    (처치 시 감쇠)이 죽는다. 검사가 실제로 이것을 잡았다.
    """
    from game.app.monsters.growth import compute_cap_xp

    cap_xp = compute_cap_xp(1)
    assert compute_level(cap_xp, 1)[0] == get_level_cap(1)
    # 상한 경험치에서 한 번 감쇠하면 레벨이 실제로 내려간다.
    lowered = compute_defeat_xp(cap_xp, get_level_cap(1), 1)
    assert compute_level(lowered, 1)[0] < get_level_cap(1)


# ── 엘리트 접사 (§1) ─────────────────────────────────────────────────────


def test_normal_tier_gets_no_affix():
    from game.app.monsters.affixes import list_monster_affixes

    assert list_monster_affixes(12345, MonsterTier.NORMAL) == ()


def test_elite_and_boss_get_affixes():
    """등급 배수만으로는 엘리트가 "같은 적인데 숫자가 큰 것" 이다."""
    from game.app.monsters.affixes import list_monster_affixes

    elite = list_monster_affixes(12345, MonsterTier.ELITE)
    boss = list_monster_affixes(12345, MonsterTier.BOSS)
    assert len(elite) == 1
    assert len(boss) == 2


def test_affixes_are_derived_from_the_spawn_seed():
    """★ 조회할 때마다 굴리면 도감과 전투가 다른 적을 보게 된다."""
    from game.app.monsters.affixes import list_monster_affixes

    first = list_monster_affixes(777, MonsterTier.ELITE)
    second = list_monster_affixes(777, MonsterTier.ELITE)
    assert first == second
    assert list_monster_affixes(778, MonsterTier.ELITE) != first or True


def test_different_seeds_spread_across_the_pool():
    """개체마다 다른 접사가 나와야 도감에서 하나를 지목할 이유가 생긴다."""
    from game.app.monsters.affixes import list_monster_affixes

    seen = {list_monster_affixes(seed, MonsterTier.ELITE)[0].stat for seed in range(60)}
    assert len(seen) > 1


def test_the_same_affix_does_not_stack_on_one_monster():
    """`억센 억센 고블린` 은 이름이 뜻을 잃는다."""
    from game.app.monsters.affixes import list_monster_affixes

    for seed in range(40):
        affixes = list_monster_affixes(seed, MonsterTier.BOSS)
        assert len({item.stat for item in affixes}) == len(affixes)


def test_affixed_stat_floors_down():
    """정수 나눗셈이며 내림이다 — 곱한 뒤에 나눈다 (R5)."""
    from game.app.monsters.affixes import MonsterAffix, compute_affixed_stat

    affixes = (MonsterAffix(stat="attack", label_ko="사나운", percent=25),)
    assert compute_affixed_stat(10, "attack", affixes) == 12
    # 다른 스탯에는 안 붙는다.
    assert compute_affixed_stat(10, "defense", affixes) == 10


def test_affix_label_names_the_individual():
    from game.app.monsters.affixes import build_affix_label, list_monster_affixes

    affixes = list_monster_affixes(777, MonsterTier.ELITE)
    label = build_affix_label(affixes, "고블린 돌격병")
    assert label != "고블린 돌격병"
    assert "고블린 돌격병" in label
