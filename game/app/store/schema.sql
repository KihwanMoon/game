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

-- 로그인 자격증명. **NULL 이면 익명 계정이다.**
-- 계정 자체를 가르지 않고 컬럼을 비워 두는 이유는 승격 때문이다 — 익명으로 놀다 가입하면
-- 같은 행에 자격증명이 붙고, 계정 id 가 그대로라 세이브·티켓·제출이 전부 따라온다.
-- 계정을 새로 만들어 옮기는 구조였다면 그 이관이 매번 필요했을 것이다.
ALTER TABLE account ADD COLUMN IF NOT EXISTS login_id      TEXT;
ALTER TABLE account ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE account ADD COLUMN IF NOT EXISTS password_salt TEXT;

-- 소문자로 정규화한 값에 유일성을 건다. Alice 와 alice 가 다른 계정이면 사람은 자기
-- 계정에 못 들어가고, 그것을 노린 사칭이 열린다.
CREATE UNIQUE INDEX IF NOT EXISTS account_login_id_key ON account (lower(login_id));

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

-- 로그인 시도 기록. **비밀번호 대량 시도를 막는 유일한 수단이다.**
-- scrypt 가 시도당 수십 ms 를 쓰게 하지만 그것만으로는 못 막는다 — 병렬로 보내면
-- 서버 CPU 만 태우고 시도는 계속된다.
--
-- 아이디로 세는 이유는 그것이 지켜야 할 대상이기 때문이다. 주소로만 세면 프록시 뒤의
-- 정상 사용자가 함께 막히고, 주소를 바꾸는 쪽은 안 막힌다.
CREATE TABLE IF NOT EXISTS login_attempt (
    id            BIGSERIAL   PRIMARY KEY,
    login_id      TEXT        NOT NULL,
    attempted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_ok         BOOLEAN     NOT NULL
);

CREATE INDEX IF NOT EXISTS login_attempt_lookup_idx
    ON login_attempt (login_id, attempted_at DESC);

-- ── 아이템 (D단계) ───────────────────────────────────────────────────────
-- **서버가 발급한다** (결정 #02). 전리품 생성이 전투 시뮬레이션 밖에 있으므로 코어는
-- 아이템을 모르고, 전투 결정론이 온전하다. 대가는 오프라인에서 아이템이 안 나오는 것이다.
--
-- affixes 가 **정본이다.** 시드 파생이 아니므로 재현으로 다시 만들 수 없다 — 발급 경로가
-- 서버 하나뿐이라는 것이 그 자리를 대신하고, 그래서 발급 코드가 API 층 밖으로 새면 안 된다.
CREATE TABLE IF NOT EXISTS item_instance (
    id                    BIGSERIAL   PRIMARY KEY,
    owner_account_id      BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    catalog_id            TEXT        NOT NULL,
    affixes               JSONB       NOT NULL DEFAULT '[]'::jsonb,
    -- 어느 검증된 런에서 나왔는가. 재현 검증은 못 하지만 감사와 조사에 이 연결이 필요하다.
    origin_run_result_id  BIGINT      REFERENCES run_result(submission_id) ON DELETE SET NULL,
    -- 파손. 사망 시 뽑힌 장착 아이템이 이 상태가 되고, 복구비용을 내야 다시 쓴다 (#34).
    is_broken             BOOLEAN     NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS item_instance_owner_idx ON item_instance (owner_account_id, id);

-- 인벤토리. **slot_index 가 PK 에 든다** — 순서를 조회 시점에 정하지 않는다 (R5).
CREATE TABLE IF NOT EXISTS inventory_slot (
    account_id        BIGINT   NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    slot_index        INTEGER  NOT NULL,
    item_id           BIGINT   REFERENCES item_instance(id) ON DELETE CASCADE,
    stack_catalog_id  TEXT,
    stack_count       INTEGER,
    PRIMARY KEY (account_id, slot_index),
    -- 장비 한 개이거나 소모품 스택이거나, 둘 중 하나다.
    CHECK ((item_id IS NULL) <> (stack_catalog_id IS NULL))
);

-- 장비 슬롯 여섯. 양손무기의 보조 봉인은 **저장하지 않는다** — 파생값이며, 저장하면
-- 착용·해제 순서에 따라 갈린다 (docs/설계/4_아이템 §2.1).
CREATE TABLE IF NOT EXISTS equipment_slot (
    account_id  BIGINT  NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    slot        TEXT    NOT NULL,
    item_id     BIGINT  NOT NULL REFERENCES item_instance(id) ON DELETE CASCADE,
    PRIMARY KEY (account_id, slot),
    UNIQUE (item_id)
);

-- 퀘스트 주머니. **인벤토리 칸을 먹지 않는다** (docs/설계/4_아이템 §4).
CREATE TABLE IF NOT EXISTS quest_pouch (
    account_id   BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    catalog_id   TEXT        NOT NULL,
    obtained_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, catalog_id)
);

-- 지갑. 복구비용의 통화이며 나중에 거래 화폐로 그대로 쓴다.
CREATE TABLE IF NOT EXISTS wallet (
    account_id  BIGINT      PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    balance     BIGINT      NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (balance >= 0)
);

-- 아이템 이력. 획득·장착·해제·파손·복구·소멸을 남긴다 — 무엇이 언제 사라졌는지를
-- 되짚을 수 없으면 문의에 답할 수 없다.
CREATE TABLE IF NOT EXISTS item_event (
    id          BIGSERIAL   PRIMARY KEY,
    item_id     BIGINT      REFERENCES item_instance(id) ON DELETE SET NULL,
    account_id  BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    kind        TEXT        NOT NULL,
    detail      TEXT        NOT NULL DEFAULT '',
    at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
