"""G1 판정 자료를 서버 기록에서 계산한다 (로드맵 §게이트 G1).

G1 은 사람 게이트다 — 테스터가 있어야 성립한다. 이 스크립트가 하는 일은 **그 판정을
눈대중이 아니라 숫자로 만드는 것**이다. 세 기준을 세는 근거가 이미 DB 에 있다.

    [ ] 테스터 5명 중 3명 이상이 첫 패배 후 자발적으로 규칙을 고쳐 재도전했는가
    [ ] 같은 방을 클리어하는 규칙표가 서로 다른 2가지 이상 나왔는가
    [ ] 평균 재도전 횟수 3회 이상인가

**분모는 표시된 테스터다** (2026-09-05). 이 게임은 익명으로 시작하므로 접속할 때마다
계정이 하나 생긴다 — 「제출이 있는 사람 계정」을 세면 한 판 내고 떠난 사람까지 전부
테스터가 된다. 실측으로 36명 중 17명이 한 판짜리였고, 그 절반이 평균 재도전을 1.2회로
눌러 놓고 있었다. 그래서 세는 대상은 `account.is_tester` 가 켜진 계정뿐이고, 그 표시는
관리자 화면에서 사람이 켠다 — 누구를 불렀는지는 사람만 알고 있다.

제출 수로 거르지 않은 이유는 그것이 **순환**이기 때문이다. 「많이 논 계정」만 분모에
넣고 「평균 재도전 3회 이상」을 재면 기준이 저절로 통과된다.

**봇은 세지 않는다.** G1 은 사람 게이트다 — 「첫 패배 후 규칙을 고쳐 재도전했는가」는
사람에게만 뜻이 있는 질문이고, 봇은 정의상 늘 재도전한다. 안 거르면 봇이 표본을 덮는다:
실측으로 검증된 제출 4,178건 중 **3,196건(76%)이 봇의 것**이었다. 그 상태로 낸 숫자는
「사람이 재미있어했는가」가 아니라 「러너가 몇 번 돌았는가」다.

세는 방법에 판단이 하나 들어 있다. **"규칙을 고쳐 재도전" 은 규칙표가 실제로 달라진
다음 제출**이다. 같은 규칙표로 다시 돌린 것은 재도전이 아니라 재실행이며, 그것까지
세면 P1("실패는 정보다")이 통했는지가 아니라 사람이 버튼을 몇 번 눌렀는지를 재게 된다.

    uv run python -m scripts.report_g1
"""

import json
import os
from dataclasses import dataclass

import psycopg

from game.app.store.connection import DATABASE_URL_ENV
from game.app.store.runs import VERDICT_VERIFIED
from game.app.store.testers import MIN_TESTERS

# 로드맵이 정한 통과선. 테스터 수만 `store/testers.py` 에서 읽는다 — 화면도 그것을 쓰므로
# 정본이 하나여야 한다.
MIN_RETRYING_TESTERS = 3
MIN_DISTINCT_CLEARS = 2
MIN_AVERAGE_RETRIES = 3.0

# 승리로 세는 결과 문자열. 코어가 내는 값과 같아야 한다.
OUTCOME_WIN = "PLAYER_WIN"


@dataclass(frozen=True)
class Attempt:
    """제출 하나. 계정·방·규칙표·결과를 함께 본다."""

    account_id: int
    room_id: str
    ruleset_key: str
    outcome: str
    verdict: str


def build_ruleset_key(payload: dict) -> str:
    """규칙표를 비교 가능한 문자열로 접는다.

    id 와 버전을 빼고 규칙만 본다 — 이름만 바꾼 것을 "고쳤다" 로 세면 안 된다.

    Args:
        payload: 규칙표 절.

    Returns:
        정렬된 JSON 문자열.
    """
    return json.dumps(payload.get("rules", []), sort_keys=True, ensure_ascii=False)


def load_attempts(connection: psycopg.Connection) -> list[Attempt]:
    """**표시된 테스터가** 검증받은 제출을 시간 순으로 읽는다.

    Args:
        connection: 열린 연결.

    Returns:
        오래된 것부터 늘어놓은 시도들. 아무도 표시하지 않았으면 빈 목록이다 —
        그것과 "테스터가 안 돌았다" 는 다르므로, 부르는 쪽이 갈라서 말해야 한다.
    """
    rows = connection.execute(
        "SELECT t.account_id, t.room_id, s.ruleset, r.outcome, r.verdict"
        " FROM run_submission s"
        " JOIN run_ticket t ON t.id = s.ticket_id"
        " JOIN run_result r ON r.submission_id = s.id"
        " JOIN account a ON a.id = t.account_id"
        # **표시된 테스터만 본다.** 질의에서 거르는 이유는, 읽고 나서 거르면 거르는 것을
        # 잊는 자리가 하나 더 생기기 때문이다 — 세는 함수마다 같은 조건을 다시 써야 한다.
        # `is_tester` 는 봇에 안 붙으므로 봇 조건을 따로 적지 않아도 봇이 안 섞인다.
        " WHERE a.is_tester AND NOT a.is_bot"
        " ORDER BY s.submitted_at"
    ).fetchall()
    return [
        Attempt(
            account_id=int(row[0]),
            room_id=str(row[1]),
            ruleset_key=build_ruleset_key(dict(row[2])),
            outcome=str(row[3]),
            verdict=str(row[4]),
        )
        for row in rows
    ]


def count_edited_retries(attempts: list[Attempt]) -> dict[int, int]:
    """계정마다 "규칙을 고쳐 다시 돌린" 횟수를 센다.

    같은 규칙표로 다시 돌린 것은 세지 않는다 — 재도전이 아니라 재실행이다.

    Args:
        attempts: 시간 순 시도들.

    Returns:
        계정 id 에서 재도전 횟수로의 대응표.
    """
    counts: dict[int, int] = {}
    last_key: dict[int, str] = {}
    for attempt in attempts:
        previous = last_key.get(attempt.account_id)
        if previous is not None and previous != attempt.ruleset_key:
            counts[attempt.account_id] = counts.get(attempt.account_id, 0) + 1
        last_key[attempt.account_id] = attempt.ruleset_key
        counts.setdefault(attempt.account_id, 0)
    return counts


def list_retry_after_loss(attempts: list[Attempt]) -> set[int]:
    """첫 패배 뒤에 규칙을 고쳐 다시 돌린 계정을 모은다.

    Args:
        attempts: 시간 순 시도들.

    Returns:
        해당하는 계정 id 집합.
    """
    found: set[int] = set()
    lost_with: dict[int, str] = {}
    for attempt in attempts:
        account = attempt.account_id
        if account in lost_with and attempt.ruleset_key != lost_with[account]:
            found.add(account)
            continue
        if attempt.outcome != OUTCOME_WIN and account not in lost_with:
            lost_with[account] = attempt.ruleset_key
    return found


def count_distinct_clears(attempts: list[Attempt]) -> dict[str, int]:
    """방마다 클리어한 **서로 다른** 규칙표의 수를 센다.

    Args:
        attempts: 시도들.

    Returns:
        방 id 에서 서로 다른 클리어 규칙표 수로의 대응표.
    """
    clears: dict[str, set[str]] = {}
    for attempt in attempts:
        if attempt.outcome == OUTCOME_WIN and attempt.verdict == VERDICT_VERIFIED:
            clears.setdefault(attempt.room_id, set()).add(attempt.ruleset_key)
    return {room: len(keys) for room, keys in sorted(clears.items())}


def format_check(label: str, is_ok: bool, detail: str) -> str:
    """판정 한 줄을 만든다.

    참·거짓을 글리프와 글자 둘로 적는다 — 색을 쓸 수 없는 터미널에서도 구분되어야 한다.

    Args:
        label: 기준 이름.
        is_ok: 통과했는가.
        detail: 실측값.

    Returns:
        한 줄 문자열.
    """
    mark = "[O] 통과" if is_ok else "[X] 미달"
    return f"  {mark}  {label}\n          {detail}"


@dataclass(frozen=True)
class Excluded:
    """분모 밖에 있는 것들.

    **뺀 것을 적기 위해서다.** 보고서가 무엇을 세는지가 화면에 안 보이면, 분모가 다시
    틀어져도 숫자가 그럴듯해서 아무도 눈치채지 못한다 — 실제로 봇이 섞인 채로 한동안
    돌았고, 그 뒤로는 한 판짜리 익명 계정이 섞인 채로 돌았다.
    """

    testers: int
    bot_attempts: int
    guest_attempts: int


def count_excluded(connection: psycopg.Connection) -> Excluded:
    """분모와, 분모 밖으로 뺀 제출 수를 센다.

    표시된 테스터 수를 **제출이 아니라 계정 표에서** 읽는다. 제출에서 세면 부르고도 한
    판도 안 돌린 사람이 분모에서 사라지고, 그러면 "5명 중 3명" 이 조용히 "3명 중 3명" 이
    된다 — G1 이 묻는 것은 부른 사람 가운데 몇이 다시 왔는가다.

    Args:
        connection: 열린 연결.

    Returns:
        표시된 테스터 수와, 제외한 봇·비테스터 제출 수.
    """
    row = connection.execute(
        "SELECT (SELECT count(*) FROM account WHERE is_tester AND NOT is_bot),"
        " count(*) FILTER (WHERE a.is_bot),"
        " count(*) FILTER (WHERE NOT a.is_bot AND NOT a.is_tester)"
        " FROM run_submission s"
        " JOIN run_ticket t ON t.id = s.ticket_id"
        " JOIN run_result r ON r.submission_id = s.id"
        " JOIN account a ON a.id = t.account_id"
    ).fetchone()
    if row is None:
        return Excluded(testers=0, bot_attempts=0, guest_attempts=0)
    return Excluded(
        testers=int(row[0] or 0),
        bot_attempts=int(row[1] or 0),
        guest_attempts=int(row[2] or 0),
    )


def render_no_testers(excluded: Excluded) -> str:
    """아무도 표시되지 않았을 때의 보고서.

    **0 과 "안 쟀다" 는 다르다.** 표시가 비었는데 0명·0회를 적으면 미달로 읽히고, 그러면
    분모를 안 정했다는 사실이 미달이라는 판정 뒤에 숨는다.

    Args:
        excluded: 분모 밖 제출 수.

    Returns:
        사람이 읽을 보고서.
    """
    return (
        "G1 판정 자료 (로드맵 §게이트 G1)\n"
        "\n"
        "  테스터로 표시된 계정이 없다 — 판정할 분모가 없다.\n"
        "\n"
        f"  서버에는 사람 제출 {excluded.guest_attempts}건이 있다"
        f" (봇 {excluded.bot_attempts}건 제외).\n"
        "  이 게임은 익명으로 시작하므로 접속마다 계정이 하나 생긴다 — 그것을 다 세면\n"
        "  한 판 내고 떠난 계정까지 테스터가 되고, 그 숫자는 「재미있었는가」가 아니라\n"
        "  「몇 명이 지나갔는가」다.\n"
        "\n"
        "  관리자 화면 〈테스터〉 탭에서 부른 사람의 계정을 표시한 뒤 다시 돌린다."
    )


def render_excluded(excluded: Excluded) -> list[str]:
    """분모 밖으로 뺀 것을 적는다.

    뺀 것이 화면에 안 보이면, 분모가 다시 틀어져도 숫자가 그럴듯해서 아무도 눈치채지
    못한다 — 봇이 섞인 채로 한동안 돌았던 것이 그렇게 됐다.

    Args:
        excluded: 분모 밖 제출 수.

    Returns:
        적을 줄들. 뺀 것이 없으면 빈 목록이다.
    """
    parts = []
    if excluded.bot_attempts:
        parts.append(f"봇 {excluded.bot_attempts}건")
    if excluded.guest_attempts:
        parts.append(f"표시 안 된 계정 {excluded.guest_attempts}건")
    return [f"  ({' · '.join(parts)} 제외)"] if parts else []


def render_report(attempts: list[Attempt], excluded: Excluded) -> str:
    """판정 자료를 글로 만든다.

    Args:
        attempts: 시간 순 시도들. **표시된 테스터 것만이다.**
        excluded: 분모와 분모 밖 제출 수.

    Returns:
        사람이 읽을 보고서.
    """
    if not excluded.testers:
        return render_no_testers(excluded)

    retries = count_edited_retries(attempts)
    retried_after_loss = list_retry_after_loss(attempts)
    clears = count_distinct_clears(attempts)
    # **분모는 표시된 수다.** 실제로 돌린 사람으로 나누면 부르고도 안 온 사람이 사라져,
    # "5명 중 3명" 이 조용히 "3명 중 3명" 이 된다.
    average = sum(retries.values()) / excluded.testers
    best_room = max(clears.values(), default=0)
    played = len(retries)

    lines = [
        "G1 판정 자료 (로드맵 §게이트 G1)",
        "",
        f"  테스터 {excluded.testers}명 중 {played}명이 돌림 · 검증된 제출 {len(attempts)}건",
        # **뺀 것이 있을 때만 적는다.** 「봇 0건 제외」는 읽는 사람에게 잡음이고, 잡음이
        # 섞인 줄은 곧 안 읽히게 된다 — 그러면 진짜로 뺐을 때도 안 보인다.
        *render_excluded(excluded),
        "",
        format_check(
            "첫 패배 후 자발적으로 규칙을 고쳐 재도전",
            len(retried_after_loss) >= MIN_RETRYING_TESTERS,
            f"{len(retried_after_loss)}명 / 기준 {MIN_RETRYING_TESTERS}명 이상",
        ),
        format_check(
            "같은 방을 클리어하는 규칙표가 서로 다른 2가지 이상",
            best_room >= MIN_DISTINCT_CLEARS,
            (
                f"최다 방 {best_room}가지 / 기준 {MIN_DISTINCT_CLEARS}가지 이상"
                + (f" — 방별 {clears}" if clears else " — 클리어 기록 없음")
            ),
        ),
        format_check(
            "평균 재도전 횟수",
            average >= MIN_AVERAGE_RETRIES,
            f"{average:.1f}회 / 기준 {MIN_AVERAGE_RETRIES}회 이상"
            + (f" — 표시 {excluded.testers}명으로 나눔" if played < excluded.testers else ""),
        ),
    ]
    if excluded.testers < MIN_TESTERS:
        lines += [
            "",
            f"  주의: 표시된 테스터가 {excluded.testers}명이다."
            f" 로드맵은 {MIN_TESTERS}명을 전제한다 —",
            "  표본이 모자라면 위 숫자는 참고값이지 판정이 아니다.",
        ]
    return "\n".join(lines)


def main() -> int:
    """스크립트 진입점.

    Returns:
        종료 코드. 연결이 없으면 1.
    """
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다")
        return 1
    with psycopg.connect(url) as connection:
        print(render_report(load_attempts(connection), count_excluded(connection)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
