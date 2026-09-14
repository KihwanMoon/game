"""아이템 종류를 폐기 표시한다 — 지우지 않는다 (§15.7).

**왜 스크립트인가.** 카탈로그 정본은 DB 이고(§15.7), 저장소의 `items.json` 은 씨앗이다.
그래서 **저장소에 없고 DB 에만 있는 행**이 생길 수 있고 — 게이트는 `items.json` 만 보므로
그 드리프트를 못 본다 — 그것을 고치는 자리가 마이그레이션이 아니라 여기다.

**마이그레이션에 넣지 않는 이유가 있다.** `migrate.sql` 은 배포마다 돌므로, 폐기를 거기
적으면 관리자가 화면에서 되살린 것을 다음 배포가 **말없이 도로 폐기한다.** 정본이 DB 라는
말이 그 순간 거짓이 된다. 한 번 도는 도구는 그 사고를 안 만든다.

**폐기는 드롭만 막는다.** 이미 나간 인스턴스는 그대로 남아 계속 끼울 수 있다
(`store/drops` 가 `NOT is_retired` 로 거르는 곳은 표를 짤 때뿐이다). 들고 있던 사람의
장비가 사라지면 그것은 폐기가 아니라 몰수다.

    GAME_DATABASE_URL=... uv run python -m scripts.retire_catalog_item sword_great_fine
    GAME_DATABASE_URL=... uv run python -m scripts.retire_catalog_item sword_great_fine --apply
    GAME_DATABASE_URL=... uv run python -m scripts.retire_catalog_item sword_great_fine --restore
"""

import argparse
import os
import sys

from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.item_catalog import apply_retire


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="아이템 종류를 폐기 표시한다")
    parser.add_argument("catalog_id", help="대상 종류 id")
    parser.add_argument("--apply", action="store_true", help="실제로 쓴다. 없으면 보기만 한다")
    parser.add_argument("--restore", action="store_true", help="폐기를 푼다")
    return parser.parse_args(argv)


def read_entry(pool: ConnectionPool, catalog_id: str) -> tuple[str, str, bool] | None:
    """그 종류의 이름·등급·폐기 여부를 읽는다.

    Args:
        pool: 연결 풀.
        catalog_id: 대상 종류.

    Returns:
        (이름, 등급, 폐기됨). 그런 종류가 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT label_ko, grade, is_retired FROM item_catalog WHERE catalog_id = %s",
            (catalog_id,),
        ).fetchone()
    if row is None:
        return None
    return (str(row[0]), str(row[1]), bool(row[2]))


def count_instances(pool: ConnectionPool, catalog_id: str) -> tuple[int, int]:
    """이 종류를 가리키는 인스턴스와 그중 착용 중인 수를 센다.

    **폐기 전에 이것부터 보여 준다.** 「몇 개가 이미 나가 있는가」를 모르고 누르면,
    폐기가 드롭만 막는 일인지 남의 장비를 건드리는 일인지 구분이 안 간다.

    Args:
        pool: 연결 풀.
        catalog_id: 대상 종류.

    Returns:
        (인스턴스 수, 착용 중인 수).
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*), count(s.item_id) FROM item_instance i"
            " LEFT JOIN equipment_slot s ON s.item_id = i.id"
            " WHERE i.catalog_id = %s",
            (catalog_id,),
        ).fetchone()
    if row is None:
        return (0, 0)
    return (int(row[0]), int(row[1]))


def main(argv: list[str]) -> int:
    """스크립트 진입점.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        종료 코드. 0 이면 성공.
    """
    arguments = parse_arguments(argv)
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    pool = create_pool(url)
    entry = read_entry(pool, arguments.catalog_id)
    if entry is None:
        print(f"그런 종류가 없다: {arguments.catalog_id}", file=sys.stderr)
        return 1
    label, grade, is_retired = entry
    held, equipped = count_instances(pool, arguments.catalog_id)
    wants_retire = not arguments.restore
    print(f"  {arguments.catalog_id} — 「{label}」 {grade}, 폐기됨={is_retired}")
    print(f"  이미 나간 인스턴스 {held}개 (착용 중 {equipped}개) — 폐기해도 그대로 남는다")
    if is_retired == wants_retire:
        print("  이미 그 상태다. 할 일이 없다")
        return 0
    if not arguments.apply:
        print(f"  --apply 를 붙이면 폐기됨={wants_retire} 로 바꾼다")
        return 0
    apply_retire(pool, arguments.catalog_id, wants_retire)
    print(f"  폐기됨={wants_retire} 로 바꿨다. **드롭표에서만 빠진다**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
