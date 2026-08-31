#!/usr/bin/env sh
# 검사용 데이터베이스를 만들고 pytest 를 돌린다.
#
# **프로덕션 DB 와 가른다.** 예전에는 같은 `game` 을 써서 검사가 만든 계정·아이템·매물이
# 실제 서비스에 쌓였고, 검사용 계정 하나가 관리자 권한까지 갖고 있었다.
#
# `CREATE DATABASE` 는 이미 있으면 에러를 내므로 그것만 삼킨다 — 다른 실패는 그대로
# 드러나야 한다.
set -eu

python - <<'PY'
import os
import psycopg

url = os.environ["GAME_DATABASE_URL"]
admin_url, _, name = url.rpartition("/")
with psycopg.connect(f"{admin_url}/postgres", autocommit=True) as connection:
    found = connection.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
    ).fetchone()
    if found is None:
        connection.execute(f'CREATE DATABASE "{name}"')
        print(f"검사용 DB 를 만들었다: {name}")
PY

exec uv run "$@"
