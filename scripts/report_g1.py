"""G1 판정 자료를 서버 기록에서 계산한다 (로드맵 §게이트 G1).

G1 은 사람 게이트다 — 테스터가 있어야 성립한다. 이 스크립트가 하는 일은 **그 판정을
눈대중이 아니라 숫자로 만드는 것**이다. 세 기준을 세는 근거가 이미 DB 에 있다.

    [ ] 테스터 5명 중 3명 이상이 첫 패배 후 자발적으로 규칙을 고쳐 재도전했는가
    [ ] 같은 방을 클리어하는 규칙표가 서로 다른 2가지 이상 나왔는가
    [ ] 평균 재도전 횟수 3회 이상인가

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

# 로드맵이 정한 통과선.
MIN_TESTERS = 5
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
    """검증된 제출을 시간 순으로 읽는다.

    Args:
        connection: 열린 연결.

    Returns:
        오래된 것부터 늘어놓은 시도들.
    """
    rows = connection.execute(
        "SELECT t.account_id, t.room_id, s.ruleset, r.outcome, r.verdict"
        " FROM run_submission s"
        " JOIN run_ticket t ON t.id = s.ticket_id"
        " JOIN run_result r ON r.submission_id = s.id"
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


def render_report(attempts: list[Attempt]) -> str:
    """판정 자료를 글로 만든다.

    Args:
        attempts: 시간 순 시도들.

    Returns:
        사람이 읽을 보고서.
    """
    if not attempts:
        return (
            "제출 기록이 없다.\n"
            "  G1 은 테스터가 있어야 성립한다. 사람이 실제로 돌린 판이 서버에 남아야\n"
            "  이 숫자가 나온다 — 로컬 티켓으로 돈 판은 여기 잡히지 않는다."
        )

    retries = count_edited_retries(attempts)
    retried_after_loss = list_retry_after_loss(attempts)
    clears = count_distinct_clears(attempts)
    testers = len(retries)
    average = sum(retries.values()) / testers if testers else 0.0
    best_room = max(clears.values(), default=0)

    lines = [
        "G1 판정 자료 (로드맵 §게이트 G1)",
        "",
        f"  테스터 {testers}명 · 검증된 제출 {len(attempts)}건",
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
            f"{average:.1f}회 / 기준 {MIN_AVERAGE_RETRIES}회 이상",
        ),
    ]
    if testers < MIN_TESTERS:
        lines += [
            "",
            f"  주의: 테스터가 {testers}명이다. 로드맵은 {MIN_TESTERS}명을 전제한다 —",
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
        print(render_report(load_attempts(connection)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
