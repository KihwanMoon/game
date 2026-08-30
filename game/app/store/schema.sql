-- 검증 서버 스키마 (B단계). docs/설계/1_통합시스템설계 §5 의 부분집합이다.
--
-- 아이템·몬스터·거래는 여기 없다. D·E·F 단계에서 붙으며, 그때까지 자리를 비워 두는 것이
-- 설계다 — 쓰지 않는 테이블은 스키마가 아니라 약속이고, 약속은 문서가 한다.
--
-- 표준 SQL 만 쓴다. 지금은 PostgreSQL 이지만, 방언에 기대면 나중에 옮기는 일이
-- 마이그레이션이 아니라 재작성이 된다.

CREATE TABLE IF NOT EXISTS account (
    id          BIGSERIAL PRIMARY KEY,
    handle      TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 기기 토큰. **평문을 저장하지 않는다** — 저장소가 새면 계정이 통째로 넘어간다.
-- 익명 계정이라 복구 수단이 없으므로, 토큰을 잃으면 계정을 잃는다. 아이템·거래가
-- 붙기 전에 승격 경로(이메일·OAuth)가 필요하다 (docs/결정/1_결정대기목록).
CREATE TABLE IF NOT EXISTS account_token (
    token_hash    TEXT        PRIMARY KEY,
    account_id    BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 메타 세이브. 계정당 하나이며 통째로 갈아 끼운다 (manage_meta.py 와 같은 규약).
CREATE TABLE IF NOT EXISTS meta_save (
    account_id    BIGINT      PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    payload       JSONB       NOT NULL,
    core_version  TEXT        NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 런 티켓. **시드의 유일한 출처다.**
-- consumed_at 이 있어야 한 티켓으로 여러 번 제출하는 것을 막는다 (T6).
CREATE TABLE IF NOT EXISTS run_ticket (
    id            TEXT        PRIMARY KEY,
    account_id    BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    seed          BIGINT      NOT NULL,
    room_id       TEXT        NOT NULL,
    floor         INTEGER     NOT NULL,
    mode          TEXT        NOT NULL,
    core_version  TEXT        NOT NULL,
    issued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    consumed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS run_ticket_account_idx ON run_ticket (account_id, issued_at DESC);

-- 제출. **결과 컬럼이 없는 것이 설계다** (docs/설계/7_변조방지 §4).
-- 자리를 두면 언젠가 "재시뮬이 느리니 이번만" 이라는 지름길이 생긴다. 컬럼이 없으면
-- 그 지름길을 낼 수 없다.
CREATE TABLE IF NOT EXISTS run_submission (
    id            BIGSERIAL   PRIMARY KEY,
    ticket_id     TEXT        NOT NULL UNIQUE REFERENCES run_ticket(id) ON DELETE CASCADE,
    ruleset       JSONB       NOT NULL,
    core_version  TEXT        NOT NULL,
    submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 결과. 서버가 재시뮬해서 확정한 것만 들어온다.
-- verdict: verified | mismatch | rejected
CREATE TABLE IF NOT EXISTS run_result (
    submission_id  BIGINT      PRIMARY KEY REFERENCES run_submission(id) ON DELETE CASCADE,
    outcome        TEXT        NOT NULL,
    ticks          INTEGER     NOT NULL,
    player_hp      INTEGER     NOT NULL,
    verdict        TEXT        NOT NULL,
    detail         TEXT        NOT NULL DEFAULT '',
    verified_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
