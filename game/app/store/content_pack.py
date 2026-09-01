"""발행된 콘텐츠 — 지금 돌고 있는 것 (설계/4_아이템 §18).

초안과 갈라 둔다. 초안은 게임에 영향이 없고, 이쪽은 두 코어가 실제로 읽는 것이다.

**서버도 이것을 읽는다.** 브라우저만 팩을 쓰고 서버가 파일을 읽으면 재시뮬이 다른
데이터로 돌고, 그것이 G3 가 잡으려는 바로 그 상태다.

파일은 씨앗이자 폴백이다 — 발행된 것이 없으면 파일이 정본이고, 브라우저가 서버에 못
닿으면 번들에 박힌 것으로 돈다. "서버가 없어도 게임은 돈다" 가 유지되는 자리다.
"""

import json
from pathlib import Path

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.store.content_draft import DRAFT_ASSETS


def read_published(pool: ConnectionPool, asset: str) -> dict | None:
    """발행된 자산 하나를 읽는다.

    Args:
        pool: 연결 풀.
        asset: 자산 이름.

    Returns:
        발행된 절. 없으면 None — 그때는 파일이 정본이다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT payload FROM content_published WHERE asset = %s", (asset,)
        ).fetchone()
    return None if row is None else dict(row[0])


def read_asset(pool: ConnectionPool, asset: str) -> dict:
    """지금 도는 자산을 읽는다. 발행된 것이 있으면 그것, 없으면 파일.

    **부르는 쪽이 어느 쪽인지 몰라도 되게 한다.** 두 갈래를 부르는 쪽마다 적으면 한
    곳을 빠뜨렸을 때 서버의 일부만 옛 데이터로 돈다.

    Args:
        pool: 연결 풀.
        asset: 자산 이름.

    Returns:
        절.
    """
    found = read_published(pool, asset)
    if found is not None:
        return found
    path, _version_key = DRAFT_ASSETS[asset]
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_pack(pool: ConnectionPool) -> dict:
    """브라우저가 받을 팩을 만든다.

    Args:
        pool: 연결 풀.

    Returns:
        자산 이름에서 절로. 세대는 부르는 쪽이 붙인다.
    """
    return {asset: read_asset(pool, asset) for asset in sorted(DRAFT_ASSETS)}


def save_published(
    pool: ConnectionPool, asset: str, payload: dict, note: str, account_id: int
) -> None:
    """자산 하나를 발행한다.

    Args:
        pool: 연결 풀.
        asset: 자산 이름.
        payload: 절.
        note: 사유.
        account_id: 발행한 관리자.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO content_published (asset, payload, note, published_by)"
            " VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (asset) DO UPDATE SET payload = EXCLUDED.payload,"
            " note = EXCLUDED.note, published_by = EXCLUDED.published_by, published_at = now()",
            (asset, Jsonb(payload), note, account_id),
        )


def read_pack_generation(pool: ConnectionPool) -> int:
    """팩 세대를 읽는다. core_version 의 `p` 축이다.

    Args:
        pool: 연결 풀.

    Returns:
        세대. 아직 발행한 적이 없으면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT generation FROM content_generation WHERE id = 1"
        ).fetchone()
    return 0 if row is None else int(row[0])


def save_pack_generation(pool: ConnectionPool, generation: int) -> None:
    """팩 세대를 세운다.

    **관리자가 입력한 값을 그대로 쓴다.** 자동으로 +1 하면 여러 자산을 한 번에 발행할 때
    세대가 몇이 될지 관리자가 모르고, 모르는 값으로 시즌이 갈린다.

    Args:
        pool: 연결 풀.
        generation: 세울 세대.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO content_generation (id, generation) VALUES (1, %s)"
            " ON CONFLICT (id) DO UPDATE SET generation = EXCLUDED.generation,"
            " updated_at = now()",
            (generation,),
        )
