"""세계 지킴이의 판정 (설계/9_에이전트_운영 §4.1).

**DB 없이 돈다.** 임계값이 옳은지가 여기서 볼 것이고, 그것은 저장소와 무관하다 —
판정을 순수 함수로 갈라 둔 값이 이것이다.

명세는 상상이 아니라 실측이다. 2026-09-04~05 에 손으로 찾은 결함들이 **이 지킴이가
있었다면 그날 잡혔을 것**이고, 각 검사가 그 상황을 그대로 세운다.
"""

from game.app.store.watch import WorldReading
from game.app.watch.checks import (
    LEVEL_ALARM,
    LEVEL_OK,
    LEVEL_WARN,
    check_auction,
    check_bot_bags,
    check_bot_runner,
    check_doppel_roster,
    check_floor_record,
    check_maintenance_left,
    check_mismatch,
    list_findings,
    resolve_worst,
)

# 아무 이상 없는 세계. 검사마다 이것을 한 축씩 흔든다 — 흔들지 않은 축이 같이 울면
# 그 검사가 남의 값을 보고 있는 것이다.
CALM = WorldReading(
    floor_behind=0,
    floor_total=10,
    doppels=8,
    doppel_age_hours=2,
    doppel_floor_min=3,
    doppel_floor_max=7,
    bots_full_bag=0,
    bots_total=10,
    bots_overdue=0,
    people_dry_slots=0,
    people_with_rules=4,
    mismatch_pct=0,
    verdict_total=500,
    stale_listings=0,
    open_listings=6,
    drafts=0,
)


def build_reading(**over):
    """한 축만 흔든 세계를 만든다.

    Args:
        **over: 바꿀 값들.

    Returns:
        읽은 값들.
    """
    return WorldReading(**{**vars(CALM), **over})


def test_a_calm_world_says_nothing():
    """★ 조용할 때 조용해야 알릴 때 읽힌다.

    울리는 검사가 상시로 하나라도 있으면 사람이 보고서 전체를 안 읽게 된다.
    """
    findings = list_findings(CALM)
    assert resolve_worst(findings) == LEVEL_OK
    assert [one.level for one in findings] == [LEVEL_OK] * len(findings)


def test_the_floor_gap_of_one_is_normal():
    """★ 「갈 수 있는 층」과 「깬 층」은 한 칸 어긋난 두 값이다.

    이 지킴이가 **첫 실행에서 자기 임계값의 오류로 잡아낸** 자리다. `reached_floor` 는
    깬 층 + 1 이라(`apply_floor_progress`), 차이 1 을 결함으로 세면 정상 세계가 상시로
    울린다.
    """
    assert check_floor_record(build_reading(floor_behind=0)).level == LEVEL_OK


def test_the_floor_record_falling_behind_is_an_alarm():
    """★ 최고 층이 안 따라오면 층 보너스 슬롯이 아무에게도 안 붙는다 (GDD §2.3).

    실측으로 7층까지 내려간 계정의 최고 층이 1 로 남아 있었다.
    """
    found = check_floor_record(build_reading(floor_behind=9))
    assert found.level == LEVEL_ALARM
    assert "층 보너스" in found.text


def test_a_frozen_doppel_roster_is_an_alarm():
    """★ 보토가 굳으면 그 뒤의 죽음이 전부 버려진다.

    실측으로 자리 다섯이 하루 만에 차고 그 뒤 1,170판이 버려졌다.
    """
    found = check_doppel_roster(build_reading(doppel_age_hours=30))
    assert found.level == LEVEL_ALARM
    assert "굳었다" in found.text


def test_doppels_all_on_one_floor_are_worth_a_look():
    """★ 전부 같은 층이면 깊이 순위가 안 갈린다 — 굳기 직전의 모습이다."""
    found = check_doppel_roster(build_reading(doppel_floor_min=2, doppel_floor_max=2))
    assert found.level == LEVEL_WARN


def test_one_doppel_on_one_floor_is_not_a_finding():
    """★ 한 마리뿐이면 최저와 최고가 같은 것이 당연하다.

    당연한 것을 알리면 보고서가 시끄러워지고, 시끄러우면 안 읽힌다.
    """
    assert (
        check_doppel_roster(build_reading(doppels=1, doppel_floor_min=4, doppel_floor_max=4)).level
        == LEVEL_OK
    )


def test_full_bot_bags_are_an_alarm():
    """★ 가방이 안 비워지면 갈아 끼우기가 막히고, 그것이 500 의 조건이었다."""
    found = check_bot_bags(build_reading(bots_full_bag=6))
    assert found.level == LEVEL_ALARM


def test_one_full_bag_is_only_a_look():
    """★ 하나는 그 봇이 운이 없는 것이고, 절반이면 규칙이 틀린 것이다."""
    assert check_bot_bags(build_reading(bots_full_bag=1)).level == LEVEL_WARN


def test_a_dead_runner_is_an_alarm():
    """★ 러너가 죽으면 세계가 **조용히** 멈춘다 — 오류도 안 나고 아무 일도 안 일어난다."""
    found = check_bot_runner(build_reading(bots_overdue=10))
    assert found.level == LEVEL_ALARM
    assert "러너" in found.text


def test_maintenance_leaving_work_behind_is_an_alarm():
    """★ 「돌았는가」가 아니라 「남았는가」를 잰다.

    정비 실행은 기록에 안 남지만 결과는 남는다 — 규칙이 있는데 소모품 칸이 전부 비어
    있으면 안 돈 것이다. 실측으로 그런 계정의 잔액은 13만이었다.
    """
    found = check_maintenance_left(build_reading(people_dry_slots=1))
    assert found.level == LEVEL_ALARM


def test_mismatch_has_two_steps():
    """★ 단정하지 않는다 — 원인은 변조·버전 시차·우리 버그 셋이다 (결정 #47).

    배포 직후에는 정상적으로 오르므로, 낮은 비율은 알리되 단정하지 않는다.
    """
    assert check_mismatch(build_reading(mismatch_pct=8)).level == LEVEL_WARN
    assert check_mismatch(build_reading(mismatch_pct=40)).level == LEVEL_ALARM


def test_mismatch_without_a_sample_is_quiet():
    """★ 표본이 없으면 비율도 없다. 0% 를 「좋다」로 읽으면 안 된다."""
    assert check_mismatch(build_reading(verdict_total=0, mismatch_pct=0)).level == LEVEL_OK


def test_stale_listings_pile_up_into_an_alarm():
    """★ 창이 지났는데 쌓이면 **안 사는 이유가 시간이 아니다.**

    봇이 무기·방패를 영영 안 사던 때가 정확히 이 모습이었다.
    """
    assert check_auction(build_reading(stale_listings=1)).level == LEVEL_WARN
    assert check_auction(build_reading(stale_listings=9)).level == LEVEL_ALARM


def test_the_worst_level_wins():
    """★ 한 줄 요약은 가장 나쁜 것을 말한다 — 종료 코드가 그것을 본다."""
    assert resolve_worst(list_findings(build_reading(bots_overdue=10))) == LEVEL_ALARM
    assert resolve_worst(list_findings(build_reading(stale_listings=1))) == LEVEL_WARN
