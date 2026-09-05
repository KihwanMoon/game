"""지킴이가 본 것을 남긴다 (설계/9_에이전트_운영 §4.1).

**세계를 고치는 것이 아니다.** `store/watch.py` 는 여전히 질의만 하고, 지킴이는 세계
상태에 손대지 않는다 (§8: 「에이전트가 이상을 자동으로 고치기」는 안 하기로 한 것이다).
여기서 쓰는 것은 **지킴이 자신이 무엇을 봤는가**뿐이다.

**로그에서 죽고 있었다.** 5분마다 정확히 판단해 컨테이너 로그에 뱉었고, 컨테이너 로그를
읽는 사람은 없다 (알려진이슈 Z1). 남겨야 화면에 올린다.

**등급이 바뀔 때만 이력을 쌓는다.** 매 틱을 다 쌓으면 하루 2천 줄이 되고, 그 안에서
「언제부터 틀렸나」를 찾는 것이 다시 일이 된다. 바뀐 순간만 남기면 그 질문이 곧 답이다.
"""

from dataclasses import dataclass
from datetime import timedelta

from psycopg_pool import ConnectionPool

from game.app.watch.checks import Finding

# 이력을 얼마나 두는가. 등급이 바뀔 때만 쌓이므로 실제로는 아주 적지만, 상한이 없으면
# 언젠가는 상한이 없다는 사실이 문제가 된다.
EVENT_KEEP = timedelta(days=90)


@dataclass(frozen=True)
class WatchRow:
    """지표 하나의 지금 상태."""

    key: str
    level: str
    text: str
    detail: str
    # 이 등급이 된 때. **「어제 낮부터 틀렸다」가 여기서 읽힌다.**
    changed_at: str
    # 마지막으로 본 때. 오래됐으면 지킴이 자신이 안 도는 것이다.
    seen_at: str


@dataclass(frozen=True)
class WatchEvent:
    """등급이 바뀐 순간 하나."""

    key: str
    level: str
    text: str
    detail: str
    happened_at: str


def save_watch_findings(pool: ConnectionPool, findings: tuple[Finding, ...]) -> int:
    """이번에 본 것을 남긴다.

    **등급이 그대로면 이력을 안 쌓는다.** 수치가 조금 움직인 것과 판단이 바뀐 것은 다르고,
    화면이 알아야 하는 것은 뒤엣것이다.

    Args:
        pool: 연결 풀.
        findings: 이번 틱의 소견들.

    Returns:
        등급이 바뀐 지표 수. 0 이면 지난번과 판단이 같다는 뜻이다.
    """
    changed = 0
    with pool.connection() as connection:
        for finding in findings:
            row = connection.execute(
                "SELECT level FROM watch_state WHERE key = %s", (finding.key,)
            ).fetchone()
            is_new = row is None or str(row[0]) != finding.level
            connection.execute(
                "INSERT INTO watch_state (key, level, text, detail)"
                " VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (key) DO UPDATE SET level = EXCLUDED.level,"
                " text = EXCLUDED.text, detail = EXCLUDED.detail, seen_at = now(),"
                # 등급이 그대로면 `changed_at` 을 안 건드린다 — 건드리면 「언제부터」가
                # 매 틱 지금으로 밀려 그 값이 뜻을 잃는다.
                " changed_at = CASE WHEN watch_state.level = EXCLUDED.level"
                "   THEN watch_state.changed_at ELSE now() END",
                (finding.key, finding.level, finding.text, finding.detail),
            )
            if is_new:
                changed += 1
                connection.execute(
                    "INSERT INTO watch_event (key, level, text, detail) VALUES (%s, %s, %s, %s)",
                    (finding.key, finding.level, finding.text, finding.detail),
                )
        connection.execute("DELETE FROM watch_event WHERE happened_at < now() - %s", (EVENT_KEEP,))
    return changed


def list_watch_state(pool: ConnectionPool) -> tuple[WatchRow, ...]:
    """지금 상태를 읽는다.

    **나쁜 것부터 준다.** 여덟 줄이 등급 없이 늘어서면 화면에서 무엇을 먼저 볼지가
    안 정해지고, 그러면 결국 안 읽힌다.

    Args:
        pool: 연결 풀.

    Returns:
        지표들. 지킴이가 아직 한 번도 안 돌았으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT key, level, text, detail,"
            " to_char(changed_at, 'YYYY-MM-DD HH24:MI'),"
            " to_char(seen_at, 'YYYY-MM-DD HH24:MI')"
            " FROM watch_state"
            # 등급 이름이 한글이라 사전순이 뜻을 안 따른다 — 순서를 손으로 적는다.
            " ORDER BY CASE level WHEN '틀림' THEN 0 WHEN '살핌' THEN 1 ELSE 2 END,"
            " changed_at DESC"
        ).fetchall()
    return tuple(
        WatchRow(
            key=str(row[0]),
            level=str(row[1]),
            text=str(row[2]),
            detail=str(row[3]),
            changed_at=str(row[4]),
            seen_at=str(row[5]),
        )
        for row in rows
    )


def list_watch_events(pool: ConnectionPool, limit: int) -> tuple[WatchEvent, ...]:
    """등급이 바뀐 순간들을 최근 것부터 읽는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수.

    Returns:
        바뀐 순간들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT key, level, text, detail, to_char(happened_at, 'YYYY-MM-DD HH24:MI')"
            " FROM watch_event ORDER BY happened_at DESC, id DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        WatchEvent(
            key=str(row[0]),
            level=str(row[1]),
            text=str(row[2]),
            detail=str(row[3]),
            happened_at=str(row[4]),
        )
        for row in rows
    )
