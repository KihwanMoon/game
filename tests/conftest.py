"""테스트 공통 준비.

**검사가 운영 DB 를 쓰지 않게 한다.** 컴포즈가 DB 하나만 띄우므로, 연결 문자열을 그대로
쓰면 검사가 만든 계정·티켓·제출이 실제 데이터와 같은 테이블에 쌓인다. 지금은 사용자가
없어 무해하지만, 생긴 뒤에 알아차리면 어느 행이 검사 것인지 가릴 수 없다.

여기서 데이터베이스 이름만 바꿔 붙는다. 없으면 만든다 — 컴포즈의 `POSTGRES_DB` 는 볼륨을
처음 만들 때만 적용되므로 나중에 추가할 방법이 이것뿐이다.
"""

import os

import psycopg
import pytest

from game.app.core.rng import DeterministicRng
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.app.store.connection import DATABASE_URL_ENV
from game.config import ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

# 검사 전용 데이터베이스 이름. 운영과 한 글자도 겹치지 않아야 한다.
TEST_DATABASE_NAME = "game_test"

# 데이터베이스를 만들 때 붙는 관리용 데이터베이스. postgres 이미지가 항상 갖고 있다.
ADMIN_DATABASE_NAME = "postgres"


def build_sibling_url(url: str, database: str) -> str:
    """같은 서버의 다른 데이터베이스를 가리키는 연결 문자열을 만든다.

    Args:
        url: 원래 연결 문자열.
        database: 붙을 데이터베이스 이름.

    Returns:
        경로만 바뀐 연결 문자열.
    """
    head, _, tail = url.rpartition("/")
    query = tail.partition("?")[2]
    return f"{head}/{database}" + (f"?{query}" if query else "")


def ensure_test_database(url: str) -> str:
    """검사 전용 데이터베이스를 확보한다.

    Args:
        url: 컴포즈가 준 연결 문자열.

    Returns:
        검사 전용 데이터베이스를 가리키는 연결 문자열.
    """
    admin_url = build_sibling_url(url, ADMIN_DATABASE_NAME)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        found = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DATABASE_NAME,)
        ).fetchone()
        if found is None:
            # 식별자는 매개변수로 넘길 수 없다. 이름이 상수라 주입 경로가 없다.
            connection.execute(f'CREATE DATABASE "{TEST_DATABASE_NAME}"')
    return build_sibling_url(url, TEST_DATABASE_NAME)


def check_is_test_database(url: str) -> bool:
    """이 연결 문자열이 검사 전용 데이터베이스를 가리키는가.

    **포함이 아니라 이름 일치로 본다.** 포함으로 두면 `game_test_backup` 같은 옆 DB 가
    검사 전용으로 읽혀 통째로 비워진다. 물음표 뒤(`?sslmode=require`)는 이름이 아니므로
    먼저 떼어 낸다 — 안 떼면 검사 전용 DB 를 못 알아보고 비우지 못한 채 지나간다.

    Args:
        url: 볼 연결 문자열.

    Returns:
        검사 전용이면 True.
    """
    return url.partition("?")[0].rpartition("/")[2] == TEST_DATABASE_NAME


def clear_test_database(url: str) -> None:
    """검사 전용 데이터베이스의 행을 전부 지운다.

    **검사가 남긴 것이 다음 검사의 입력이 된다.** 비우지 않던 때, 한 개체가 지난 실행들이
    쌓아 둔 전리품 920개를 들고 있었다 — 상한이 5인데. 그래서 `create_trophy` 가 늘
    「상한에 걸렸고 더 강해지지도 않았다」로 False 를 냈고, 전리품·되찾기·도감 검사
    다섯이 코드와 무관하게 빨간불이었다. 그 다섯이 빨간 동안에는 그 영역의 **진짜**
    회귀도 빨간불에 묻힌다.

    스키마는 지우지 않는다. 행만 비우면 `apply_schema` 가 다시 돌 필요가 없고,
    `migrate.sql` 의 이행문은 옮길 행이 없어 no-op 이 된다.

    Args:
        url: 검사 전용 데이터베이스를 가리키는 연결 문자열.

    Raises:
        RuntimeError: 검사 전용이 아닌 데이터베이스를 가리킬 때.
    """
    # **이름을 여기서 한 번 더 본다.** 이 함수는 넘겨받은 곳의 모든 행을 지운다 —
    # 부르는 쪽이 언젠가 바뀌어 운영 URL 이 들어오면 그것으로 끝이다.
    if not check_is_test_database(url):
        raise RuntimeError(f"검사 전용 DB 가 아니다: {url.partition('?')[0]}")
    with psycopg.connect(url, autocommit=True) as connection:
        found = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        # 갓 만든 DB 는 표가 없다. 스키마는 앱이 뜰 때 선다.
        names = sorted(row[0] for row in found)
        if not names:
            return
        # 정렬해서 한 문장으로 자른다. 외래키가 얽혀 있어 하나씩 지우면 순서를 타고,
        # CASCADE 가 그 순서 문제를 없앤다. 식별자는 매개변수로 넘길 수 없다 —
        # 이름은 이 DB 의 pg_tables 에서 온 것이라 밖에서 들어올 자리가 없다.
        targets = ", ".join(f'public."{name}"' for name in names)
        connection.execute(f"TRUNCATE {targets} RESTART IDENTITY CASCADE")


def pytest_configure() -> None:
    """검사가 도는 동안 연결 문자열을 검사 전용으로 바꾸고, 남은 행을 비운다.

    **이미 검사 전용을 가리켜도 비운다.** 컴포즈의 `test` 서비스는 처음부터
    `.../game_test` 를 넘기므로, 「검사 전용이면 할 일 없음」으로 돌아서면 정작 매일 도는
    경로에서만 안 비워진다 — 실제로 그렇게 개체 하나가 전리품 920개를 쌓았다.
    """
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        return
    try:
        test_url = url if check_is_test_database(url) else ensure_test_database(url)
        clear_test_database(test_url)
        os.environ[DATABASE_URL_ENV] = test_url
    except psycopg.Error:
        # 붙지 못하면 DB 검사는 어차피 건너뛴다. 여기서 죽으면 나머지 검사까지 막힌다.
        os.environ.pop(DATABASE_URL_ENV, None)


def build_probe_world(skills: tuple[str, ...] | None = None) -> tuple[WorldState, Entity]:
    """검사용 세계 하나를 만든다. 플레이어와 적 하나가 있다.

    방과 난수원은 규칙 평가에 쓰이지 않지만 생성자가 요구한다.

    Args:
        skills: 플레이어가 장착한 스킬. None 이면 장착 개념이 배선되지 않은 상태다 —
            빈 튜플(아무것도 장착 안 함)과 구분해야 한다.

    Returns:
        (세계, 플레이어 엔티티) 짝.
    """
    template = load_room_templates(ROOM_TEMPLATES_PATH)[0]
    world = WorldState(template, DeterministicRng(0))
    world.entities["player"] = Entity(
        entity_id="player",
        kind_id="hero",
        faction=FACTION_PLAYER,
        position=(1, 1),
        hp=100,
        hp_max=100,
        attack=12,
        defense=5,
        attack_range=1,
        initiative=50,
        skills=skills,
    )
    world.entities["e1"] = Entity(
        entity_id="e1",
        kind_id="goblin_rusher",
        faction=FACTION_ENEMY,
        position=(3, 1),
        hp=40,
        hp_max=40,
        attack=8,
        defense=2,
        attack_range=1,
        initiative=60,
    )
    return world, world.entities["player"]


@pytest.fixture
def probe_world():
    """검사용 세계를 만드는 함수를 준다."""
    return build_probe_world
