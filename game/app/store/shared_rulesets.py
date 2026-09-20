"""공유된 규칙표의 저장 — 짧은 주소가 링크를 우리에게 남긴다.

**공유 코드는 이미 있었는데 아무도 안 붙였다.** `v2:H4sIA…` 가 475자라 커뮤니티에
그대로 붙는 링크가 아니고, 단축 주소를 쓰면 그 링크는 우리 것이 아니게 된다.

**id 는 내용의 해시다.** 세는 번호를 쓰면 같은 표를 두 번 올릴 때 주소가 둘이 되고,
같은 것을 가리키는 링크가 갈려 어느 쪽도 힘을 못 받는다. 해시면 같은 표는 늘 같은
주소이고 다시 올리는 것이 저장을 늘리지 않는다.
"""

import hashlib
import json

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

# 주소에 쓰는 글자 수. 32비트(8자)면 같은 주소가 겹칠 확률이 백만 개에서도 무시할
# 수준이 아니라(생일 문제), 12자를 쓴다 — 48비트다. 사람이 옮겨 적을 길이는 넘지만
# 붙여 넣는 링크라 그것이 문제가 되지 않는다.
SHARE_ID_LENGTH = 12

# 이름의 상한. 제목 줄에 그대로 들어가므로 길면 검색 결과가 잘린다.
MAX_SHARE_NAME = 40


def build_share_id(payload: dict) -> str:
    """규칙표 절에서 주소를 만든다.

    **정규 JSON 을 해싱한다.** 키 순서가 다르면 같은 표가 다른 주소를 받는다 — 공유
    코드가 같은 이유로 정규 JSON 을 쓴다.

    Args:
        payload: 규칙표 절.

    Returns:
        16진수 12자.
    """
    canonical = _format_canonical(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:SHARE_ID_LENGTH]


def _format_canonical(value: object) -> str:
    """정규 JSON 문자열로 찍는다. 키를 정렬하고 공백을 뺀다.

    Args:
        value: 찍을 값.

    Returns:
        정규 JSON.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def save_shared(
    pool: ConnectionPool,
    payload: dict,
    name: str,
    core_version: str,
    account_id: int | None,
) -> str:
    """규칙표를 공유용으로 저장하고 주소를 낸다.

    같은 내용을 다시 올리면 **같은 주소가 나오고 아무것도 안 바뀐다** — 이름도 안
    덮는다. 먼저 붙인 사람이 지은 이름이 그 주소의 이름이다.

    Args:
        pool: 연결 풀.
        payload: 규칙표 절.
        name: 붙일 이름.
        core_version: 지금 코어 버전.
        account_id: 올린 계정. 없으면 None.

    Returns:
        주소에 쓸 id.
    """
    share_id = build_share_id(payload)
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO shared_ruleset (id, name, payload, core_version, account_id)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (share_id, name[:MAX_SHARE_NAME], Jsonb(payload), core_version, account_id),
        )
    return share_id


def read_shared(pool: ConnectionPool, share_id: str) -> tuple[str, dict] | None:
    """공유된 규칙표를 읽고 조회수를 하나 올린다.

    **읽기와 세기를 한 문장으로 한다.** 갈라 두면 크롤러가 긁는 동안 둘이 어긋나고,
    무엇보다 왕복이 두 번이 된다.

    Args:
        pool: 연결 풀.
        share_id: 주소의 id.

    Returns:
        (이름, 규칙표 절). 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE shared_ruleset SET view_count = view_count + 1"
            " WHERE id = %s RETURNING name, payload",
            (share_id,),
        ).fetchone()
    return None if row is None else (str(row[0]), dict(row[1]))
