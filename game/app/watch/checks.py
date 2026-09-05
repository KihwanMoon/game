"""세계 지킴이의 판정 (설계/9_에이전트_운영 §4.1).

**순수 함수다.** 읽은 값을 받아 소견을 낸다 — DB 를 모르므로 임계값이 옳은지를 DB 없이
검사할 수 있고, 임계값을 고치는 자리가 한 곳에 모인다.

**아무것도 안 고친다.** 이상을 적어 사람에게 올릴 뿐이다. 자동으로 고치면 「왜 그랬는지」가
사라지는데, 이 모듈이 잡으려는 결함들은 전부 **원인이 이유였지 증상이 아니었다** — 봇
가방이 찬 것은 되찾음 보호 때문이었고, 그림자가 굳은 것은 비우는 길이 없어서였다.

**임계값에는 사유를 적는다.** 숫자만 있으면 나중에 「이게 왜 3 이지」를 아무도 못 답하고,
그러면 알림이 시끄러울 때 사유 대신 숫자를 올려 버린다.
"""

from dataclasses import dataclass

from game.app.store.watch import WorldReading

# 소견의 세 등급. 색을 못 쓰는 터미널이라 글리프와 글자를 함께 적는다.
LEVEL_OK = "OK"
LEVEL_WARN = "살핌"
LEVEL_ALARM = "틀림"

GLYPHS: dict[str, str] = {LEVEL_OK: "·", LEVEL_WARN: "◷", LEVEL_ALARM: "◈"}

# 그림자가 이만큼 안 바뀌면 굳은 것이다. 봇 열이 720초마다 돌고 깊은 죽음이 하루에
# 수십 건이므로, 반나절이면 여러 번 바뀌었어야 한다. 실측으로 굳었을 때는 **이틀**이었다.
DOPPEL_STALE_HOURS = 12

# 가방을 이만큼 쓰면 찬 것으로 본다. 20칸 중 18칸이면 갈아 끼우기가 막히기 직전이고,
# 그 포화가 `/api/run` 500 의 조건이었다.
BAG_FULL_SLOTS = 18

# 봇 몇 마리가 그 상태면 알린다. 하나는 그 봇이 운이 없는 것이고, 절반이면 규칙이 틀렸다.
BAG_FULL_PCT = 40

# 불일치가 이 비율을 넘으면 살핀다. 배포 직후에는 정상적으로 오르므로(버전 시차),
# 이것만으로 단정하지 않는다 — 원인 셋을 가르는 것은 사람의 몫이다 (결정 #47).
MISMATCH_WARN_PCT = 5
MISMATCH_ALARM_PCT = 20

# 우선권 창이 지난 매물이 이만큼 쌓이면 안 사는 이유가 시간이 아니다. 봇이 무기를
# 영영 안 사던 때, 창이 지난 매물이 계속 쌓이기만 했다.
STALE_LISTING_ALARM = 5

# 초안이 이만큼 오래 안 나가면 알린다. 지금은 사람이 만들어 드물지만, 콘텐츠 에이전트가
# 붙으면 여기가 먼저 쌓인다 — 발행은 사람이 누르기 때문이다.
DRAFT_WARN = 3


@dataclass(frozen=True)
class Finding:
    """지표 하나에 대한 소견."""

    key: str
    level: str
    text: str
    detail: str


def build_finding(key: str, level: str, text: str, detail: str) -> Finding:
    """소견 하나를 만든다.

    Args:
        key: 지표 이름.
        level: 세 등급 중 하나.
        text: 사람이 읽을 한 줄.
        detail: 근거 수치.

    Returns:
        만들어진 소견.
    """
    return Finding(key=key, level=level, text=text, detail=detail)


def check_floor_record(reading: WorldReading) -> Finding:
    """최고 층이 도달 기록을 따라오는가.

    **한 칸 어긋난 두 값이다.** `reached_floor` 는 「갈 수 있는 층」이라 깬 층 + 1 이고
    `best_floor` 는 「깬 층」이다 — 차이 1 은 정상이고, 그보다 벌어지면 안 따라오는 것이다.

    갈리면 층 보너스 규칙 슬롯이 안 붙는다 — 실측으로 7층까지 내려간 계정의 최고 층이
    1 로 남아 있었고, GDD §2.3 의 최대 +4 가 사람에게도 봇에게도 한 번도 안 붙고 있었다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"{reading.floor_behind} / {reading.floor_total} 계정 (최근 활동)"
    if reading.floor_behind == 0:
        return build_finding("최고층", LEVEL_OK, "최고 층이 도달 기록을 따라온다", detail)
    return build_finding(
        "최고층",
        LEVEL_ALARM,
        "최고 층이 도달 기록보다 낮다 — 층 보너스 슬롯이 안 붙는다",
        detail,
    )


def check_doppel_roster(reading: WorldReading) -> Finding:
    """그림자 보토가 도는가.

    안 돌면 **자리가 굳은 것**이다. 실측으로 자리 다섯이 하루 만에 전부 최저 층으로
    차고 그 뒤 1,170판이 버려졌다 — 「거기까지 실제로 내려간 빌드」라는 전제와 정반대다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = (
        f"{reading.doppels}마리 · 최신 {reading.doppel_age_hours}시간 전 ·"
        f" {reading.doppel_floor_min}~{reading.doppel_floor_max}층"
    )
    if reading.doppels == 0:
        return build_finding("도플갱어", LEVEL_WARN, "세계에 그림자가 없다", detail)
    if reading.doppel_age_hours >= DOPPEL_STALE_HOURS:
        return build_finding("도플갱어", LEVEL_ALARM, "보토가 굳었다 — 새 그림자가 안 선다", detail)
    if reading.doppels > 1 and reading.doppel_floor_min == reading.doppel_floor_max:
        return build_finding(
            "도플갱어", LEVEL_WARN, "전부 같은 층이다 — 깊이 순위가 안 갈린다", detail
        )
    return build_finding("도플갱어", LEVEL_OK, "보토가 돈다", detail)


def check_bot_bags(reading: WorldReading) -> Finding:
    """봇 가방이 비워지는가.

    안 비워지면 새 전리품이 들어올 자리가 없고, 꽉 찬 가방은 갈아 끼우기를 막는다 —
    실측으로 그 포화가 `/api/run` 500 의 조건이었다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"{reading.bots_full_bag} / {reading.bots_total}마리"
    if reading.bots_total == 0:
        return build_finding("봇 가방", LEVEL_WARN, "봇이 없다", detail)
    share = reading.bots_full_bag * 100 // reading.bots_total
    if share >= BAG_FULL_PCT:
        return build_finding(
            "봇 가방", LEVEL_ALARM, "가방이 안 비워진다 — 버리기가 안 걸린다", detail
        )
    if reading.bots_full_bag > 0:
        return build_finding("봇 가방", LEVEL_WARN, "가방이 찬 봇이 있다", detail)
    return build_finding("봇 가방", LEVEL_OK, "가방이 비워진다", detail)


def check_bot_runner(reading: WorldReading) -> Finding:
    """봇 러너가 살아 있는가.

    차례가 한참 지났는데 안 돌면 러너가 죽은 것이다. **세계가 조용히 멈춘다** — 아무
    오류도 안 나고 그냥 아무 일도 안 일어난다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"{reading.bots_overdue} / {reading.bots_total}마리 차례 지남"
    if reading.bots_overdue == 0:
        return build_finding("봇 러너", LEVEL_OK, "봇이 차례대로 돈다", detail)
    if reading.bots_overdue >= reading.bots_total:
        return build_finding("봇 러너", LEVEL_ALARM, "봇이 아무도 안 돈다 — 러너를 본다", detail)
    return build_finding("봇 러너", LEVEL_WARN, "차례를 놓친 봇이 있다", detail)


def check_maintenance_left(reading: WorldReading) -> Finding:
    """정비가 할 일을 남겨 뒀는가.

    **「돌았는가」가 아니라 「남았는가」를 잰다.** 정비 실행은 기록에 안 남지만 결과는
    남는다 — 규칙을 세워 둔 계정의 소모품 칸이 전부 비어 있으면 정비가 안 돈 것이다.
    실측으로 그런 계정이 있었고, 잔액은 13만이었다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"{reading.people_dry_slots} / {reading.people_with_rules} 계정"
    if reading.people_with_rules == 0:
        return build_finding("정비", LEVEL_OK, "정비 규칙을 세운 사람이 없다", detail)
    if reading.people_dry_slots > 0:
        return build_finding(
            "정비", LEVEL_ALARM, "규칙이 있는데 소모품 칸이 비어 있다 — 안 돈 것이다", detail
        )
    return build_finding("정비", LEVEL_OK, "정비가 할 일을 안 남겼다", detail)


def check_mismatch(reading: WorldReading) -> Finding:
    """불일치가 늘고 있는가.

    **단정하지 않는다.** 원인은 변조·버전 시차·우리 버그 셋이고, 배포 직후에는 정상적으로
    오른다 (결정 #47). 가르는 것은 사람의 몫이다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"{reading.mismatch_pct}% · 표본 {reading.verdict_total}건"
    if reading.verdict_total == 0:
        return build_finding("불일치", LEVEL_OK, "최근 판정이 없다", detail)
    if reading.mismatch_pct >= MISMATCH_ALARM_PCT:
        return build_finding("불일치", LEVEL_ALARM, "불일치가 많다 — 원인 셋을 가른다", detail)
    if reading.mismatch_pct >= MISMATCH_WARN_PCT:
        return build_finding("불일치", LEVEL_WARN, "불일치가 늘었다", detail)
    return build_finding("불일치", LEVEL_OK, "불일치가 드물다", detail)


def check_auction(reading: WorldReading) -> Finding:
    """매물이 팔리는가.

    우선권 창이 지난 매물이 쌓이면 **안 사는 이유가 시간이 아니다.** 실측으로 봇이
    무기·방패를 영영 안 사던 때, 창이 지난 매물이 계속 쌓이기만 했다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"창 지난 {reading.stale_listings} / 열린 {reading.open_listings}건"
    if reading.stale_listings >= STALE_LISTING_ALARM:
        return build_finding("경매", LEVEL_ALARM, "창이 지났는데 안 팔린다", detail)
    if reading.stale_listings > 0:
        return build_finding("경매", LEVEL_WARN, "창이 지난 매물이 있다", detail)
    return build_finding("경매", LEVEL_OK, "매물이 돈다", detail)


def check_drafts(reading: WorldReading) -> Finding:
    """초안이 쌓여 있는가.

    발행은 사람이 누르므로 **초안은 사람을 기다리는 줄**이다. 콘텐츠 에이전트가 붙으면
    여기가 먼저 쌓인다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견.
    """
    detail = f"{reading.drafts}건"
    if reading.drafts >= DRAFT_WARN:
        return build_finding("콘텐츠 초안", LEVEL_WARN, "낼 초안이 쌓였다", detail)
    return build_finding("콘텐츠 초안", LEVEL_OK, "쌓인 초안이 적다", detail)


# 돌릴 판정들. **순서가 곧 보고서의 순서**다 — 세계가 멈추는 것(러너)부터 사람이
# 겪는 것(정비), 그다음이 경제와 운영이다.
CHECKS = (
    check_bot_runner,
    check_maintenance_left,
    check_floor_record,
    check_doppel_roster,
    check_bot_bags,
    check_auction,
    check_mismatch,
    check_drafts,
)


def list_findings(reading: WorldReading) -> tuple[Finding, ...]:
    """모든 판정을 돌린다.

    Args:
        reading: 읽은 값들.

    Returns:
        소견들. 순서는 `CHECKS` 가 정한다.
    """
    return tuple(check(reading) for check in CHECKS)


def resolve_worst(findings: tuple[Finding, ...]) -> str:
    """가장 나쁜 등급.

    보고서 한 줄 요약과 종료 코드가 이것을 본다.

    Args:
        findings: 소견들.

    Returns:
        세 등급 중 하나.
    """
    levels = {finding.level for finding in findings}
    if LEVEL_ALARM in levels:
        return LEVEL_ALARM
    if LEVEL_WARN in levels:
        return LEVEL_WARN
    return LEVEL_OK
