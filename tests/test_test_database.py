"""검사 전용 데이터베이스를 가른다 (알려진 이슈 Z8).

**검사가 남긴 것이 다음 검사의 입력이 되면 안 된다.** 비우지 않던 때, 개체 하나가 지난
실행들이 쌓아 둔 전리품 920개를 들고 있었다 — 상한이 5인데. `create_trophy` 가 늘
「상한에 걸렸고 더 강해지지도 않았다」로 False 를 내서 전리품·되찾기·도감 검사 다섯이
코드와 무관하게 빨간불이었고, 그 다섯이 빨간 동안에는 그 영역의 **진짜** 회귀도 묻힌다.

비우는 쪽은 DB 가 있어야 볼 수 있지만, **어디를 비우는지 고르는 규칙**은 DB 없이 본다.
그것이 틀리면 지워지는 것이 운영 데이터라 여기가 제일 중요한 자리다.
"""

import pytest
from conftest import (
    TEST_DATABASE_NAME,
    build_sibling_url,
    check_is_test_database,
    clear_test_database,
)

LIVE_URL = "postgresql://game:pw@postgres:5432/game"


def test_it_refuses_a_database_that_is_not_the_test_one():
    """★ **이 함수는 넘겨받은 곳의 모든 행을 지운다.**

    부르는 쪽이 언젠가 바뀌어 운영 URL 이 들어오면 그것으로 끝이다. 붙기 전에 이름을
    보고 돌아서야 한다 — 붙은 뒤에 보면 이미 늦는 판이 있다.
    """
    with pytest.raises(RuntimeError, match="검사 전용"):
        clear_test_database(LIVE_URL)


def test_a_name_that_merely_contains_the_test_name_is_not_enough():
    """★ `game_test_backup` 은 검사 전용이 아니다.

    포함 검사로 두면 이름이 비슷한 옆 DB 가 통째로 비워진다.
    """
    with pytest.raises(RuntimeError, match="검사 전용"):
        clear_test_database(f"postgresql://game:pw@postgres:5432/{TEST_DATABASE_NAME}_backup")


def test_a_query_string_does_not_hide_the_name():
    """★ `?sslmode=require` 가 붙어도 이름은 그대로 읽힌다.

    물음표 뒤를 이름으로 읽으면 검사 전용 DB 를 못 알아보고, 비우지 못한 채 Z8 이
    조용히 돌아온다 — 터지지 않고 조용히 안 하는 쪽이라 더 늦게 들킨다.
    """
    url = build_sibling_url(f"{LIVE_URL}?sslmode=require", TEST_DATABASE_NAME)
    assert check_is_test_database(url)


def test_the_live_database_is_not_the_test_one():
    assert not check_is_test_database(LIVE_URL)


def test_a_similar_name_is_not_the_test_one():
    """★ 이름이 비슷한 옆 DB 를 검사 전용으로 읽으면 그것을 통째로 비운다."""
    assert not check_is_test_database(f"{LIVE_URL}_test_backup")
    assert not check_is_test_database(f"postgresql://game:pw@postgres:5432/x{TEST_DATABASE_NAME}")
