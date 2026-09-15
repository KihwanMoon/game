"""활자 — 둘째 재화 (설계/4_아이템 §17, 신설 2026-09-15).

**푼과 하는 일이 다르다.** 푼은 봉인을 **연다**. 활자는 연 것을 **다시 찍는다**. 열기
전에는 무엇이 나올지 모르고 열고 나면 되돌릴 수 없었는데, 그 「되돌릴 수 없음」이
사람에게는 그냥 운이었다 — 활자는 그 운을 선택으로 바꾼다.

**전투력 천장을 안 올린다.** 칸 수도 등급도 그대로고, 이미 연 칸의 값만 다시 굴린다.
천장을 올리는 재화를 하나 더 두면 결국 그것을 모으는 일이 게임이 된다.

**둔갑이 물러날 때만 들어온다.** 내 규칙표가 남의 장에 서서 이긴 만큼, 그 그림자가
목숨을 다 쓰고(또는 정원에 밀려) 사라지는 자리에서 한꺼번에 정산된다. 판마다 주면 또
하나의 노가다 지표가 되고, 그러면 둘로 가른 뜻이 없다.

**그래서 활자는 둔갑에 동의한 사람만 얻는다** (결정 2026-09-15). 동의는 「내 규칙표를
남이 본다」를 받아들이는 일이라 대가가 있어야 한다는 판단이다 — 대신 활자가 여는 것은
천장이 아니라 **다시 찍을 기회**뿐이라, 안 켠 사람이 이길 수 없게 되지는 않는다.
"""

from psycopg_pool import ConnectionPool


def read_letters(pool: ConnectionPool, account_id: int) -> int:
    """가진 활자 수. 지갑이 없으면 0 이다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        활자 수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT letters FROM wallet WHERE account_id = %s", (account_id,)
        ).fetchone()
    return int(row[0]) if row else 0


def add_letters(pool: ConnectionPool, account_id: int, amount: int) -> int:
    """활자를 더한다. 음수면 뺀다.

    **지갑이 없으면 만든다.** 활자가 먼저 들어오는 계정이 있다 — 둔갑 정산은 푼을 한 번도
    안 벌어 본 계정에도 떨어질 수 있다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.
        amount: 더할 양.

    Returns:
        바뀐 뒤의 활자 수.

    Raises:
        ValueError: 모자란 경우. 음수를 만드는 것보다 거절이 낫다.
    """
    if amount < 0:
        # **빼는 길과 더하는 길을 가른다.** 하나로 묶으면 지갑이 없는 계정에서 빼려 할 때
        # INSERT 가 음수를 만들어 CHECK 로 터진다 — 그것은 「모자란다」와 구별되지 않는다.
        with pool.connection() as connection:
            row = connection.execute(
                "UPDATE wallet SET letters = letters + %s, updated_at = now()"
                " WHERE account_id = %s AND letters + %s >= 0 RETURNING letters",
                (amount, account_id, amount),
            ).fetchone()
        if row is None:
            raise ValueError("활자가 모자란다")
        return int(row[0])
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO wallet (account_id, letters) VALUES (%s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET letters = wallet.letters + %s,"
            " updated_at = now()"
            " RETURNING letters",
            (account_id, amount, amount),
        ).fetchone()
    return int(row[0]) if row else 0


def apply_doppel_settlement(pool: ConnectionPool, record_id: int, origin_account_id: int) -> int:
    """물러나는 둔갑의 평생 승수를 활자로 정산한다.

    **전적 표가 남아 있어서 셀 수 있다.** `doppel_bout` 은 `record_id` 에 외래키를 안 걸어
    두었으므로 개체가 지워져도 그 자국은 남는다 — 「찍은 자국은 안 지워진다」가 이 세계의
    규칙이고, 그 규칙 덕분에 지우는 순간에도 셈이 선다.

    **지는 판은 세지 않는다.** 목숨 셋을 다 쓰고 사라지는 것이 정상 수명이라, 패배까지
    세면 모든 둔갑이 같은 값을 받는다.

    Args:
        pool: 연결 풀.
        record_id: 물러나는 개체.
        origin_account_id: 그 그림자의 주인. 0 이면 아무것도 안 한다.

    Returns:
        준 활자 수. 이긴 적이 없으면 0.
    """
    if origin_account_id <= 0:
        return 0
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM doppel_bout WHERE record_id = %s AND is_doppel_win",
            (record_id,),
        ).fetchone()
    won = int(row[0]) if row else 0
    if won <= 0:
        return 0
    add_letters(pool, origin_account_id, won)
    return won
