"""화면에 뜨는 이름을 한 곳에서 정한다 (2026-09-16).

**화면마다 다른 이름이 뜨고 있었다.** 순위표는 아이디를, 둔갑 전적과 관리자 화면은 자동
생성 별명(`user_3f9a…`)을 보여 줬다. 같은 사람이 화면을 옮길 때마다 다른 이름이 되니
「누가 누구인지」가 끊겼다 — 내 둔갑이 남의 장에 서는 게임에서 그것은 기제의 절반을
못 쓰게 만든다.

**순서는 하나다.** 닉네임 → 아이디 → 자동 별명. 앞엣것이 비면 뒤로 내려간다.

**식을 문자열로 둔다.** 이름이 나가는 조회가 열 곳 가까이 되는데, 각 조회가 제 식을
쓰면 한 곳을 고쳤을 때 나머지가 조용히 옛 이름을 낸다. 별칭만 받아 같은 식을 낸다.
"""

import re

from psycopg_pool import ConnectionPool

# 닉네임 길이. 둘보다 짧으면 누구인지 안 담기고, 열여섯을 넘으면 순위표의 칸을 밀어낸다.
NICKNAME_MIN = 2
NICKNAME_MAX = 16

# 쓸 수 있는 글자. **공백을 안 받는다** — 앞뒤에 공백을 붙여 남과 같아 보이는 이름을
# 만들 수 있고, 화면에서는 그 둘이 구별되지 않는다.
NICKNAME_PATTERN = re.compile(r"^[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_-]+$")

# 계정이 태어날 때 받는 자동 별명의 접두어들. **사람이 이것으로 시작하는 이름을 못 쓴다** —
# `bot_` 으로 시작하는 이름을 지으면 화면에서 봇으로 읽히고, `user_` 는 남의 자동 별명과
# 겹쳐 보인다.
RESERVED_PREFIXES = ("user_", "bot_")


def build_display_name_sql(alias: str) -> str:
    """그 별칭의 계정에서 표시 이름을 뽑는 SQL 조각.

    **빈 문자열도 「없음」으로 친다.** `NULL` 만 보면 빈 닉네임이 저장된 계정이 이름 없이
    뜬다 — 빈 칸은 지운 것과 같은 뜻이어야 한다.

    Args:
        alias: 조회 안에서 `account` 에 붙인 별칭.

    Returns:
        SQL 조각. 값이 아니라 **고정 문자열**이라 주입 경로가 아니다.

    Raises:
        ValueError: 별칭이 식별자 모양이 아닌 경우. 부르는 쪽이 값을 넘기는 실수를 막는다.
    """
    if not alias.isidentifier():
        raise ValueError(f"별칭이 아니다: {alias}")
    return f"COALESCE(NULLIF({alias}.nickname, ''), NULLIF({alias}.login_id, ''), {alias}.handle)"


def check_nickname(nickname: str) -> str:
    """닉네임이 규칙에 맞는가.

    Args:
        nickname: 사람이 입력한 이름.

    Returns:
        어긋난 사유. 맞으면 빈 문자열이다.
    """
    folded = nickname.strip()
    if len(folded) < NICKNAME_MIN or len(folded) > NICKNAME_MAX:
        return f"이름은 {NICKNAME_MIN}~{NICKNAME_MAX}자다"
    if NICKNAME_PATTERN.match(folded) is None:
        return "한글·영문·숫자와 _ - 만 쓸 수 있다"
    if folded.lower().startswith(RESERVED_PREFIXES):
        return "그 머리말은 쓸 수 없다 — 자동으로 붙는 이름과 겹친다"
    return ""


def read_display_name(pool: ConnectionPool, account_id: int) -> str:
    """그 계정이 화면에 뜨는 이름.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        표시 이름. 없는 계정이면 빈 문자열.
    """
    with pool.connection() as connection:
        row = connection.execute(
            f"SELECT {build_display_name_sql('a')} FROM account a WHERE a.id = %s",
            (account_id,),
        ).fetchone()
    return str(row[0]) if row else ""


def find_nickname_owner(pool: ConnectionPool, nickname: str) -> int:
    """그 이름을 이미 쓰는 계정.

    Args:
        pool: 연결 풀.
        nickname: 볼 이름.

    Returns:
        계정 id. 아무도 안 쓰면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id FROM account WHERE lower(nickname) = lower(%s)", (nickname.strip(),)
        ).fetchone()
    return int(row[0]) if row else 0


def apply_nickname(pool: ConnectionPool, account_id: int, nickname: str) -> bool:
    """닉네임을 정한다. 이미 쓰이는 이름이면 실패한다.

    **바꿀 수 있다.** 아이디와 달리 이것은 보여 주기 위한 이름이라 고정할 이유가 없다 —
    다만 유일해야 하므로, 바꾸면 앞의 이름이 곧바로 비고 남이 가져갈 수 있다.

    Args:
        pool: 연결 풀.
        account_id: 정할 계정.
        nickname: 새 이름. 앞뒤 공백은 떼고 저장한다.

    Returns:
        정했으면 참. 이름이 이미 쓰이고 있으면 거짓.
    """
    folded = nickname.strip()
    owner = find_nickname_owner(pool, folded)
    if owner not in (0, account_id):
        return False
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE account SET nickname = %s WHERE id = %s RETURNING id", (folded, account_id)
        ).fetchone()
    return row is not None


def read_nickname(pool: ConnectionPool, account_id: int) -> str | None:
    """그 계정이 고른 이름. 안 정했으면 None 이다.

    **표시 이름과 다르다.** 표시 이름은 없으면 아이디나 자동 별명으로 내려가는데, 여기서는
    「안 정했다」가 그대로 보여야 한다 — 화면이 「이름 짓기」와 「이름 바꾸기」를 그것으로
    가른다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        닉네임. 안 정했으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT NULLIF(nickname, '') FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return str(row[0]) if row and row[0] else None
