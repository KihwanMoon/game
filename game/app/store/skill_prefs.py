"""스킬 세팅 — 장비가 연 스킬을 끌 수 있다 (결정 #13 확장).

**스킬을 더하는 설정이 아니다.** 스킬은 여전히 장비가 열고(#13) 여기서는 **빼기만**
한다 — 더하기가 되면 장비 없이 스킬을 켜는 길이 생기고 로드아웃 동결(T 계열)이 뚫린다.

기본 공격(`ATTACK`)은 끌 수 없다. 끄면 규칙표가 전부 불가일 때 폴백조차 못 때려
맨몸으로 서서 죽는다.
"""

import json

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

# 끌 수 없는 스킬. 폴백이 이것에 기댄다.
LOCKED_SKILLS: tuple[str, ...] = ("ATTACK",)


def read_disabled_skills(pool: ConnectionPool, account_id: int) -> tuple[str, ...]:
    """이 계정이 꺼 둔 스킬들을 읽는다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        꺼 둔 스킬 id 들. 정렬돼 있다 (R5 — 로드아웃에 실린다).
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT disabled FROM skill_pref WHERE account_id = %s", (account_id,)
        ).fetchone()
    raw = row[0] if row else None
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return ()
    return tuple(sorted(str(item) for item in raw if str(item) not in LOCKED_SKILLS))


def save_disabled_skills(pool: ConnectionPool, account_id: int, disabled: tuple[str, ...]) -> None:
    """꺼 둔 스킬들을 저장한다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        disabled: 끌 스킬 id 들. 잠긴 스킬은 조용히 남는다 — 요청이 실수로 ATTACK 을
            담아도 폴백이 살아야 한다.
    """
    cleaned = sorted(set(disabled) - set(LOCKED_SKILLS))
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO skill_pref (account_id, disabled) VALUES (%s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET disabled = EXCLUDED.disabled",
            (account_id, Jsonb(cleaned)),
        )
