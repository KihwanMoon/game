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
    -- 층 하나에 드는 방 수 (로드맵 W14). **티켓에 얼린다** — 상수를 바꾸면 이미 발급한
    -- 티켓의 방 목록이 조용히 다른 층 배치로 읽힌다. 0 은 전체가 한 층이라는 뜻이다.
    rooms_per_floor INTEGER   NOT NULL DEFAULT 0,
    -- **어디까지 확정했는가** (로드맵 W14). 층 단위 보상 때문에 한 티켓으로 여러 번
    -- 제출한다 — T6 의 「한 티켓 한 제출」을 「**더 깊은 층으로만 나아갈 수 있다**」로
    -- 다시 세운 것이다. 같은 층을 두 번 제출해 보상을 두 번 받는 길을 이 값이 막는다.
    cleared_floor   INTEGER   NOT NULL DEFAULT 0,
    mode          TEXT        NOT NULL,
    core_version  TEXT        NOT NULL,
    issued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    -- 이 런이 **이미 깎은** 소모품 충전. 쓰임새에서 개수로.
    --
    -- 층마다 서버가 처음부터 다시 돌려 「몇 개 썼는가」를 낸다. 그 값은 누적이라,
    -- 이미 깎은 만큼을 빼지 않으면 3층을 청구할 때 1·2층에서 쓴 것이 또 깎인다.
    -- 이것이 있어야 **런 중에 보충해도** 낸 돈이 안 사라진다.
    spent_charges JSONB       NOT NULL DEFAULT '{}'::jsonb,
    consumed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS run_ticket_account_idx ON run_ticket (account_id, issued_at DESC);

-- 제출. **결과 컬럼이 없는 것이 설계다** (docs/설계/7_변조방지 §4).
-- 자리를 두면 언젠가 "재시뮬이 느리니 이번만" 이라는 지름길이 생긴다. 컬럼이 없으면
-- 그 지름길을 낼 수 없다.
CREATE TABLE IF NOT EXISTS run_submission (
    id            BIGSERIAL   PRIMARY KEY,
    -- **UNIQUE 가 아니다** (로드맵 W14). 층 단위 보상 때문에 한 티켓으로 층마다 한 번씩
    -- 제출한다. 「한 티켓 한 제출」이 막던 것(같은 판으로 보상을 두 번 받기)은
    -- `run_ticket.cleared_floor` 가 막는다 — **더 깊은 층으로만 나아갈 수 있다.**
    ticket_id     TEXT        NOT NULL REFERENCES run_ticket(id) ON DELETE CASCADE,
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

-- ── 개체 (E단계) ────────────────────────────────────────────────────────
-- **아이템 표보다 먼저 선다.** 아이템·인벤토리·장비가 이 표를 외래키로 가리키므로
-- 순서가 뒤집히면 신규 DB 에서 생성이 실패한다.
CREATE TABLE IF NOT EXISTS entity_record (
    id            BIGSERIAL   PRIMARY KEY,
    -- PLAYER | MONSTER. **한 표에 둘을 담는다** (docs/설계/6_몬스터 §7) — 장비·인벤토리가
    -- 이 표를 참조하므로 "몬스터가 내 장비를 들고 있다" 가 특수 케이스가 아니다.
    -- 따로 두면 아이템이 계정을 참조하게 되고, 몬스터가 무언가를 들려면 그때 양쪽을
    -- 마이그레이션해야 한다.
    kind              TEXT        NOT NULL,
    -- PLAYER 만 채운다. 계정 하나에 개체 하나다.
    owner_account_id  BIGINT      UNIQUE REFERENCES account(id) ON DELETE CASCADE,
    -- MONSTER 만 채운다. 어느 종인가.
    catalog_id        TEXT,
    tier              TEXT,
    persistence       TEXT        NOT NULL DEFAULT 'PERSISTENT',
    level             INTEGER     NOT NULL DEFAULT 1,
    total_xp          BIGINT      NOT NULL DEFAULT 0,
    -- 요구조건 판정의 소재. **장비 보너스를 담지 않는다** (docs/설계/4_아이템 §7) —
    -- 담으면 착용 순서가 결과를 바꾸고 서버가 (계정, 아이템)만으로 재판정할 수 없다.
    stat_json         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    -- **이것이 이 설계의 중심이다.** 몬스터의 정체는 스탯이 아니라 규칙표이고, 도감이
    -- 공개하는 것도 성장이 바꾸는 것도 그것이다. 비어 있으면 카탈로그 기본표를 쓴다.
    ruleset_json      JSONB,
    rule_slots        INTEGER     NOT NULL DEFAULT 0,
    cpu_budget        INTEGER     NOT NULL DEFAULT 0,
    -- 굴림의 재현 근거. 엘리트 접사가 여기서 나온다.
    spawn_seed        BIGINT,
    -- 어디에 있는가 (PERSISTENT 만).
    zone_floor        INTEGER,
    -- **PLAYER 만 채운다. 여기까지 내려가 봤는가** (설계/6_몬스터 §3).
    --
    -- `zone_floor` 와 가른 이유는 뜻이 다르기 때문이다 — 저쪽은 「지금 어느 층에 있는
    -- 몬스터인가」이고 이쪽은 「최대 얼마나 깊이 갔는가」다. 한 칸에 담으면 층을 골라
    -- 들어가는 순간 도달 기록이 지워진다.
    --
    -- **서버만 올린다.** 클라이언트가 층을 고르게 두면 1층 캐릭터로 10층 보상을 뽑는다.
    reached_floor     INTEGER     NOT NULL DEFAULT 1,
    entity_slot       TEXT,
    alive             BOOLEAN     NOT NULL DEFAULT true,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 한 층의 한 자리에 개체 하나. 없으면 같은 자리에 여럿이 겹쳐 스냅샷이 어느 것을
    -- 가리키는지 알 수 없다.
    UNIQUE (zone_floor, entity_slot)
);

CREATE INDEX IF NOT EXISTS entity_record_zone_idx ON entity_record (zone_floor, entity_slot);

-- ── 아이템 (D단계) ───────────────────────────────────────────────────────
-- **서버가 발급한다** (결정 #02). 전리품 생성이 전투 시뮬레이션 밖에 있으므로 코어는
-- 아이템을 모르고, 전투 결정론이 온전하다. 대가는 오프라인에서 아이템이 안 나오는 것이다.
--
-- affixes 가 **정본이다.** 시드 파생이 아니므로 재현으로 다시 만들 수 없다 — 발급 경로가
-- 서버 하나뿐이라는 것이 그 자리를 대신하고, 그래서 발급 코드가 API 층 밖으로 새면 안 된다.
CREATE TABLE IF NOT EXISTS item_instance (
    id                    BIGSERIAL   PRIMARY KEY,
    -- 소유자는 **개체다**. 계정이 아니라 entity_record 를 가리키므로 "몬스터가 내 장비를
    -- 들고 있다" 가 특수 케이스가 아니다 (docs/설계/6_몬스터 §7).
    owner_entity_id       BIGINT      NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    -- 누구에게서 빼앗았는가. 도감이 "내 아이템을 들고 있다" 를 말하려면 필요하다 (#34).
    taken_from            BIGINT      REFERENCES account(id) ON DELETE SET NULL,
    catalog_id            TEXT        NOT NULL,
    affixes               JSONB       NOT NULL DEFAULT '[]'::jsonb,
    -- 어느 검증된 런에서 나왔는가. 재현 검증은 못 하지만 감사와 조사에 이 연결이 필요하다.
    origin_run_result_id  BIGINT      REFERENCES run_result(submission_id) ON DELETE SET NULL,
    -- 파손. 사망 시 뽑힌 장착 아이템이 이 상태가 되고, 복구비용을 내야 다시 쓴다 (#34).
    is_broken             BOOLEAN     NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- 인벤토리. **slot_index 가 PK 에 든다** — 순서를 조회 시점에 정하지 않는다 (R5).
CREATE TABLE IF NOT EXISTS inventory_slot (
    entity_id         BIGINT   NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    slot_index        INTEGER  NOT NULL,
    item_id           BIGINT   REFERENCES item_instance(id) ON DELETE CASCADE,
    stack_catalog_id  TEXT,
    stack_count       INTEGER,
    PRIMARY KEY (entity_id, slot_index),
    -- 장비 한 개이거나 소모품 스택이거나, 둘 중 하나다.
    CHECK ((item_id IS NULL) <> (stack_catalog_id IS NULL))
);

-- 스킬 세팅 (결정 #13 확장). 장비가 연 스킬을 **빼기만** 한다 — 더하기가 되면
-- 장비 없이 스킬을 켜는 길이 생긴다.
CREATE TABLE IF NOT EXISTS skill_pref (
    account_id BIGINT PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    disabled   JSONB  NOT NULL DEFAULT '[]'::jsonb
);

-- 정비 규칙 (설계/4_아이템 §5). 런이 닫힐 때 서버가 실행하는 자동화 스위치들.
--
-- **기본은 전부 꺼짐이다.** 돈이 나가고 아이템이 사라지는 일은 사람이 켠 것이어야 한다.
CREATE TABLE IF NOT EXISTS maintenance_rule (
    account_id BIGINT PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    -- 정렬된 행 목록 [{action, grade}] — 전투 규칙표처럼 위에서 아래로 돈다.
    rows       JSONB  NOT NULL DEFAULT '[]'::jsonb
);

-- 소모품 칸 (설계/4_아이템 §5). 물약 둘·주문서 하나가 기본이다.
--
-- **가방과 다른 것이다.** 가방은 「가진 것」이고 이 표는 「들고 갈 것」이다. 예전에는
-- 가방에 든 소모품을 전부 세서 들고 갔고, 그래서 「몇 개를 들고 갈까」가 선택이
-- 아니었다 — 주운 만큼이 답이었다.
--
-- `catalog_id` 가 NULL 인 줄은 **빈 칸**이며 출격할 때 한 개가 공짜로 찬다. 예전의
-- `balance.player.potions` 를 대신하는 자리다.
--
-- 칸 수는 코드가 정한다 (`schemas/consumable.py`). 여기 줄이 없어도 빈 칸으로 읽는다 —
-- 계정마다 미리 깔아 두면 칸 수를 늘릴 때 기존 계정만 안 늘어난다.
CREATE TABLE IF NOT EXISTS consumable_slot (
    entity_id   BIGINT   NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    use_tag     TEXT     NOT NULL,
    slot_index  INTEGER  NOT NULL,
    catalog_id  TEXT     REFERENCES item_catalog(catalog_id),
    charges     INTEGER  NOT NULL DEFAULT 0,
    PRIMARY KEY (entity_id, use_tag, slot_index),
    CHECK (charges >= 0)
);

-- 장비 슬롯 여섯. 양손무기의 보조 봉인은 **저장하지 않는다** — 파생값이며, 저장하면
-- 착용·해제 순서에 따라 갈린다 (docs/설계/4_아이템 §2.1).
CREATE TABLE IF NOT EXISTS equipment_slot (
    entity_id   BIGINT  NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    slot        TEXT    NOT NULL,
    item_id     BIGINT  NOT NULL REFERENCES item_instance(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_id, slot),
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
    -- 개체 기준이다. 몬스터도 아이템을 가지므로 계정으로 두면 그쪽 이력이 남지 않는다.
    entity_id   BIGINT      NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    kind        TEXT        NOT NULL,
    detail      TEXT        NOT NULL DEFAULT '',
    at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 몬스터 (E단계) ───────────────────────────────────────────────────────
-- **플레이어와 같은 형태다** (docs/설계/6_몬스터 §7). 장비·인벤토리가 이 표를 참조하므로
-- "몬스터가 내 장비를 들고 있다" 가 특수 케이스가 아니다.
--
-- ruleset_json 이 여기 있는 것이 이 설계의 중심이다 — 몬스터의 정체는 스탯이 아니라
-- 규칙표이고, 도감이 공개하는 것도 성장이 바꾸는 것도 그것이다.


-- 티켓이 얼려 둔 상태 (§5). **클라이언트가 되보내지 않는다** — 서버가 ticket_id 로
-- 자기가 발급한 것을 조회한다. 받으면 약한 스냅샷으로 바꿔 제출할 수 있다 (T8).
CREATE TABLE IF NOT EXISTS monster_snapshot (
    ticket_id  TEXT   NOT NULL REFERENCES run_ticket(id) ON DELETE CASCADE,
    record_id  BIGINT NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    state      JSONB  NOT NULL,
    PRIMARY KEY (ticket_id, record_id)
);

-- 경험치 원장. **검증된 런에서만 들어온다** — 클라이언트가 "내가 졌다" 고 보고해서
-- 몬스터가 크는 구조면, 자기 몬스터를 키우려고 일부러 지는 어뷰징이 열린다.
CREATE TABLE IF NOT EXISTS monster_kill (
    id             BIGSERIAL   PRIMARY KEY,
    record_id      BIGINT      NOT NULL REFERENCES entity_record(id) ON DELETE CASCADE,
    victim_kind    TEXT        NOT NULL,
    victim_id      BIGINT,
    run_result_id  BIGINT      REFERENCES run_result(submission_id) ON DELETE SET NULL,
    xp_gained      INTEGER     NOT NULL,
    at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 전리품 표를 따로 두지 않는다. 몬스터가 가져간 장비는 **그 개체가 소유한
-- item_instance** 이며, taken_from 이 원주인을 가리킨다 — 표를 가르면 "몬스터가 내 장비를
-- 들고 있다" 가 다시 특수 케이스가 된다 (결정 #34, docs/설계/6_몬스터 §7).

-- ── 랭킹 (F단계) ─────────────────────────────────────────────────────────
-- **코어 버전별로 가른다** (결정 #06). 밸런스나 블록 목록이 바뀌면 과거 기록이
-- 재현되지 않으므로, 한 표에 섞으면 검증할 수 없는 기록이 상위에 남는다.
--
-- 점수는 **누적 경험치**다. 한 판의 성적이 아니라 얼마나 멀리 왔는가를 잰다.
CREATE TABLE IF NOT EXISTS leaderboard (
    mode          TEXT        NOT NULL,
    core_version  TEXT        NOT NULL,
    account_id    BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    score         BIGINT      NOT NULL DEFAULT 0,
    level         INTEGER     NOT NULL DEFAULT 1,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (mode, core_version, account_id)
);

CREATE INDEX IF NOT EXISTS leaderboard_rank_idx
    ON leaderboard (mode, core_version, score DESC, updated_at);

-- 데일리 챌린지. 하루에 한 번, 모두가 같은 시드를 받는다.
-- **티켓 자체가 아니라 참가 기록이다** — 티켓은 run_ticket 이 들고 있고, 여기는
-- "이 계정이 오늘 이미 받았다" 만 본다.
CREATE TABLE IF NOT EXISTS daily_entry (
    account_id   BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    day          DATE        NOT NULL,
    ticket_id    TEXT        NOT NULL REFERENCES run_ticket(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, day)
);

-- ── 경매장 (F단계, 결정 #20) ─────────────────────────────────────────────
-- **원장이다.** 상태 전이만 남기고 지우지 않는다 — "내 아이템이 어디로 갔나" 를 되짚을
-- 수 없으면 문의에 답할 수 없고, 자전거래 탐지도 불가능해진다.
--
-- 경제 설계에서 이 표가 담당하는 것은 셋이다.
--   * **수수료** — 등록할 때 떼는 몫이 화폐를 태운다. 인플레이션의 유일한 배출구다.
--   * **만료** — 안 팔린 물건이 영원히 걸려 있으면 시세가 굳는다.
--   * **자전거래 흔적** — 판 사람과 산 사람이 원장에 남아 계정 간 이전을 셀 수 있다.
CREATE TABLE IF NOT EXISTS auction_listing (
    id              BIGSERIAL   PRIMARY KEY,
    item_id         BIGINT      NOT NULL UNIQUE REFERENCES item_instance(id) ON DELETE CASCADE,
    seller_id       BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    buyer_id        BIGINT      REFERENCES account(id) ON DELETE SET NULL,
    price           BIGINT      NOT NULL,
    fee             BIGINT      NOT NULL DEFAULT 0,
    -- OPEN | SOLD | CANCELLED | EXPIRED
    state           TEXT        NOT NULL DEFAULT 'OPEN',
    listed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    settled_at      TIMESTAMPTZ,
    CHECK (price > 0)
);

CREATE INDEX IF NOT EXISTS auction_open_idx ON auction_listing (state, price, listed_at);
CREATE INDEX IF NOT EXISTS auction_seller_idx ON auction_listing (seller_id, listed_at DESC);

-- 티켓이 얼려 둔 플레이어 전투 입력 (장비·레벨). 몬스터 스냅샷과 같은 이유로 필요하다 —
-- 장비를 서버가 알고 전투를 브라우저가 도므로, 얼려 두지 않으면 화면은 맨몸으로 싸우고
-- 서버는 장비를 낀 채로 재시뮬한다 (결정 #13).
ALTER TABLE run_ticket ADD COLUMN IF NOT EXISTS loadout JSONB;

-- 이 티켓이 도는 방들 (로드맵 W3). **목록을 저장한다** — 길이를 서버 상수로 두면
-- 상수를 고치는 순간 이미 발급한 티켓이 소급해 달라지고, 그 티켓으로 돈 판은 서버가
-- 다시 계산할 수 없다.
ALTER TABLE run_ticket ADD COLUMN IF NOT EXISTS room_ids JSONB;

-- 아이템 귀속 (결정 #07). **거래 후 귀속**이다 — 주운 것은 한 번 팔 수 있고, 산 사람에게
-- 묶인다. 자유 거래로 두면 같은 아이템을 A→B→A 로 돌려 계정 사이에 화폐를 씻을 수 있고,
-- 봇이 파밍해 파는 것이 최적 전략이 된다. 완전 귀속으로 두면 경매장이 죽고 그와 함께
-- 유일한 화폐 배출구가 사라진다.
--
-- **기존 아이템은 전부 미귀속으로 시작한다** (기본값 FALSE). 지금 유통량이 거의 없어
-- 실질 차이가 없고, "언제 얻었나" 를 따지는 예외를 만들지 않는 편이 규칙을 단순하게 한다.
ALTER TABLE item_instance ADD COLUMN IF NOT EXISTS is_bound BOOLEAN NOT NULL DEFAULT FALSE;

-- 매물의 UNIQUE(item_id) 를 **열린 매물에만** 거는 부분 인덱스로 바꾼다.
--
-- 원래 제약은 "같은 아이템이 두 번 걸리는 것" 을 막으려던 것인데, 상태를 보지 않아
-- **한 번 걸었다 내린 아이템이 영원히 다시 걸리지 않았다.** 취소는 거래가 아니므로
-- 그러면 걸어 보는 것 자체가 벌이 된다. 팔린 뒤에는 귀속(#07)이 막으므로 이 인덱스가
-- 느슨해져도 재판매가 열리지 않는다.
ALTER TABLE auction_listing DROP CONSTRAINT IF EXISTS auction_listing_item_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS auction_open_item_idx
    ON auction_listing (item_id) WHERE state = 'OPEN';

-- 관리자 권한.
--
-- **API 로는 절대 세울 수 없다.** 세우는 길은 `scripts/grant_admin.py` 뿐이고, 그것은
-- DB 접속이 있어야 돈다 — 관리자 승격이 엔드포인트로 열려 있으면 그 하나가 뚫리는 순간
-- 세계 전체가 뚫린다. 이 게임은 클라이언트를 적대적이라고 전제하는데(CLAUDE.md),
-- 관리자 경로는 그 전제가 가장 크게 걸리는 자리다.
ALTER TABLE account ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- 관리자가 세계에 손댄 기록.
--
-- **개입은 반드시 남는다.** 남지 않으면 "이 몬스터 레벨이 왜 이렇지" 를 나중에 아무도
-- 답할 수 없고, 경매 원장이 있는 이유와 같다 — 손댄 사실 자체가 조사 대상이다.
CREATE TABLE IF NOT EXISTS admin_action (
    id          BIGSERIAL   PRIMARY KEY,
    account_id  BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    action      TEXT        NOT NULL,
    target      TEXT        NOT NULL DEFAULT '',
    detail      TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS admin_action_recent_idx ON admin_action (created_at DESC);

-- 도감 해금 — 이 계정이 무엇을 처음 손에 넣어 봤는가.
--
-- **소유가 아니라 이력이다.** 팔거나 잃어도 해금은 남는다 — 소유로 계산하면 아이템을
-- 판 순간 도감이 잠기고, 그러면 도감이 "본 것" 이 아니라 "지금 가진 것" 이 된다.
--
-- 결정론과 무관하다. 코어는 이 표를 모르고, 여기 있는 것은 화면이 무엇을 밝혀 보여줄지
-- 뿐이다 (R5).
CREATE TABLE IF NOT EXISTS account_discovery (
    account_id  BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    kind        TEXT        NOT NULL,
    ref_id      TEXT        NOT NULL,
    found_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, kind, ref_id)
);

-- ── 아이템 카탈로그 (설계/4_아이템 §15) ─────────────────────────────────
--
-- **정본이 DB 로 옮겨 왔다.** 관리자가 종류를 조회·등록·폐기할 수 있어야 하고, 아이템은
-- 브라우저 코어가 읽지 않는 유일한 자산이라 런타임 이관이 가능한 유일한 것이기도 하다
-- (로드아웃으로 합산돼 티켓에 얼려 들어간다).
--
-- `resources/balance/items.json` 은 이제 **파생물**이다. `scripts/export_items.py` 가
-- DB 에서 내보내고, 코어와 골든은 그 스냅샷을 읽는다 — 골든 재현이 DB 상태에 묶이지
-- 않게 하려는 배치다 (§15.7).

-- 등급. 접사 굴림 수를 등급이 정한다 — 이름표로만 두면 「유물 단검」이 「보통 단검」보다
-- 나은 점이 없어 등급이 뜻을 잃는다 (결정 #42).
CREATE TABLE IF NOT EXISTS item_grade (
    code        TEXT    PRIMARY KEY,
    rank        INT     NOT NULL,
    label_ko    TEXT    NOT NULL,
    -- 이 등급이 주는 봉인 칸 수 (§17). 등급이 성능에 하는 일은 이것 하나뿐이다.
    sealed_slots INT    NOT NULL DEFAULT 0
);

-- 카탈로그 한 줄. **지우지 않는다** — item_instance·원장·경매가 catalog_id 를 가리키므로
-- 지우면 과거 기록을 못 읽는다. `is_retired` 가 "새로 안 나온다" 만 뜻한다 (§15.7).
CREATE TABLE IF NOT EXISTS item_catalog (
    catalog_id        TEXT        PRIMARY KEY,
    kind              TEXT        NOT NULL,
    slot              TEXT,
    hands             TEXT,
    grade             TEXT        NOT NULL REFERENCES item_grade(code),
    label_ko          TEXT        NOT NULL,
    -- **코드가 읽는 태그는 이것 하나다** (§4). 소모품이 무엇으로 쓰이는가이며
    -- `USE_ITEM[kind]` 의 파라미터와 같은 값이다.
    use_tag           TEXT,
    -- 한 칸에 쌓을 수 있는 개수 (§5). **소모품이 스택으로 들어가려면 이 값이 필요하다** —
    -- 없으면 1 로 읽혀 물약 여섯 개가 여섯 칸을 먹는다.
    stack_max         INTEGER     NOT NULL DEFAULT 1,
    -- 표시 전용. 코드는 안 읽는다 — 화면이 묶어 보여 주는 데만 쓴다.
    tags              JSONB       NOT NULL DEFAULT '[]'::jsonb,
    affixes           JSONB       NOT NULL DEFAULT '[]'::jsonb,
    requirements      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    grants_skill      TEXT,
    -- 이 층부터 나온다 (D1). 1층에서 유물이 나오면 깊이 들어갈 이유가 없다.
    min_floor         INT         NOT NULL DEFAULT 1,
    -- 무기가 정하는 사거리 (§2.2). NULL 은 「사거리를 안 정한다」다 — 0 과 다르다.
    attack_range      INT,
    is_retired        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS item_catalog_live_idx ON item_catalog (grade) WHERE NOT is_retired;

-- 카탈로그 세대. 한 줄짜리 표다. 이 값이 core_version 의 `i` 축이 되고, 스냅샷 파일의
-- item_list_version 으로 나간다 — 관리자가 아이템을 고치는 것은 시즌을 가르는 일이며
-- 그 사실이 코어 버전 문자열에 남아야 한다 (§15.8).
CREATE TABLE IF NOT EXISTS catalog_generation (
    id          INT         PRIMARY KEY DEFAULT 1,
    generation  INT         NOT NULL DEFAULT 1,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (id = 1)
);

-- 드롭 소스. 어느 몬스터 종·어느 층에서 굴리는가. `ANY` 는 소스별 표가 없을 때의 바탕.
CREATE TABLE IF NOT EXISTS drop_source (
    id       BIGSERIAL PRIMARY KEY,
    kind     TEXT      NOT NULL,
    ref_id   TEXT      NOT NULL DEFAULT '',
    UNIQUE (kind, ref_id)
);

-- 1단계 — 등급 추첨. **몬스터 레벨이 여기에만 개입한다** (§15.2). 2단계에 개입시키면
-- "레벨 높은 적이 단검을 더 자주 준다" 같은, 아무도 설명할 수 없는 규칙이 생긴다.
CREATE TABLE IF NOT EXISTS drop_grade_weight (
    source_id        BIGINT NOT NULL REFERENCES drop_source(id) ON DELETE CASCADE,
    grade            TEXT   NOT NULL REFERENCES item_grade(code),
    weight           INT    NOT NULL DEFAULT 0,
    -- 레벨 1당 이 가중치가 몇 퍼센트씩 밀리는가. 수식은 나중에 정한다 (§15.6).
    level_scale_pct  INT    NOT NULL DEFAULT 0,
    PRIMARY KEY (source_id, grade)
);

-- 2단계 — 그 등급 안의 상대 비율. `(source_id, grade)` 로 묶이는 것이 두 단계를 스키마에
-- 박아 둔 것이다. 아이템을 더해도 이 줄만 늘고 등급 분포는 안 흔들린다 (§15.2).
CREATE TABLE IF NOT EXISTS drop_item_weight (
    source_id   BIGINT NOT NULL REFERENCES drop_source(id) ON DELETE CASCADE,
    grade       TEXT   NOT NULL REFERENCES item_grade(code),
    catalog_id  TEXT   NOT NULL REFERENCES item_catalog(catalog_id),
    weight      INT    NOT NULL DEFAULT 1,
    PRIMARY KEY (source_id, grade, catalog_id)
);

-- 천장 (D2). 확률만으로는 "나는 안 나온다" 를 못 막는다 — 운이 나쁜 사람이 이탈한다.
CREATE TABLE IF NOT EXISTS drop_pity (
    account_id  BIGINT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    grade       TEXT   NOT NULL REFERENCES item_grade(code),
    misses      INT    NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, grade)
);

-- 굴림 기록 (D4). **입력까지 남긴다.** 결과만 남기면 확률이 맞는지 사후에 증명할 수 없고,
-- 문의가 오면 답이 없다. 아이템이 안 나온 굴림도 남긴다 — 안 나온 것이 데이터다.
CREATE TABLE IF NOT EXISTS item_roll_log (
    id             BIGSERIAL   PRIMARY KEY,
    account_id     BIGINT      NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    submission_id  BIGINT,
    source_kind    TEXT        NOT NULL,
    source_ref     TEXT        NOT NULL DEFAULT '',
    monster_level  INT         NOT NULL DEFAULT 0,
    floor          INT         NOT NULL DEFAULT 1,
    generation     INT         NOT NULL DEFAULT 0,
    grade          TEXT,
    catalog_id     TEXT,
    detail         TEXT        NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS item_roll_log_account_idx ON item_roll_log (account_id, created_at DESC);

-- ── 콘텐츠 초안 (설계/4_아이템 §15.7 의 반대편) ─────────────────────────
--
-- **여기 있는 것은 아직 게임이 아니다.** 스킬·블록·밸런스·룸·적 규칙표는 두 코어가
-- 함께 읽는 실행 자산이고, 브라우저는 그것을 빌드 시점에 번들로 인라인한다. 그래서
-- 런타임에 DB 를 보게 만들면 **서버가 없으면 게임이 안 돈다** — 이 저장소가 지키는
-- 전제가 무너진다.
--
-- 그래서 흐름이 셋으로 갈린다.
--
--   1. 편집  관리자가 초안을 여기 저장한다. 게임에는 아무 영향이 없다
--   2. 검증  코어가 쓰는 그 로더로 읽어 본다. 여기서 막히면 배포가 서버를 죽였을 것이다
--   3. 발행  운영자가 파일로 내보내고, 커밋·배포해야 실제로 반영된다
--
-- 3번이 사람 손을 타는 것이 설계다. 자동으로 반영되면 순위표 시즌이 아무도 모르게
-- 갈린다.
CREATE TABLE IF NOT EXISTS content_draft (
    asset       TEXT        PRIMARY KEY,
    payload     JSONB       NOT NULL,
    note        TEXT        NOT NULL DEFAULT '',
    updated_by  BIGINT      REFERENCES account(id) ON DELETE SET NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 발행된 콘텐츠 (설계/4_아이템 §18) ───────────────────────────────────
--
-- 초안(`content_draft`)과 갈라 둔다. 초안은 게임에 영향이 없고, 이쪽은 **지금 돌고 있는
-- 것**이다.
--
-- **서버도 이것을 읽는다.** 브라우저만 팩을 쓰고 서버가 파일을 읽으면 재시뮬이 다른
-- 데이터로 돌고, 그것이 G3 가 잡으려는 바로 그 상태다.
--
-- 파일은 씨앗이자 폴백으로 남는다 — 발행된 것이 없으면 파일이 정본이고, 브라우저가
-- 서버에 못 닿으면 번들에 박힌 것으로 돈다. "서버가 없어도 게임은 돈다" 가 유지되는
-- 자리다.
CREATE TABLE IF NOT EXISTS content_published (
    asset         TEXT        PRIMARY KEY,
    payload       JSONB       NOT NULL,
    note          TEXT        NOT NULL DEFAULT '',
    published_by  BIGINT      REFERENCES account(id) ON DELETE SET NULL,
    published_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 팩 세대. 발행할 때마다 관리자가 입력한 값으로 올라간다. 이 값이 core_version 의
-- `p` 축이며, **여러 자산을 한 번에 발행해도 세대는 하나다** — 그것이 "몰아서 발행" 의
-- 뜻이다.
CREATE TABLE IF NOT EXISTS content_generation (
    id          INT         PRIMARY KEY DEFAULT 1,
    generation  INT         NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (id = 1)
);

-- ── 봇 (가상 유저) ────────────────────────────────────────────────────────
--
-- **표시하는 것이 설계다.** `설계/7_변조방지` T11 이 봇 파밍을 위협으로 적고 봇 판정
-- 기준(결정 #48)이 미결인데, 우리가 들인 봇을 표시하지 않으면 우리 손으로 만든 것과
-- 잡아야 할 것이 구별되지 않는다 — 나중에 골라낼 수도, 지울 수도 없다.
--
-- 봇은 **진짜 계정**이다. 같은 라우트로 티켓을 받고 같은 재시뮬로 확정받는다. 그래서
-- 봇이 낀 장비는 실제로 벌어서 낀 것이고(결정 #02), 봇이 못 하는 일도 사람과 같다.
ALTER TABLE account ADD COLUMN IF NOT EXISTS is_bot BOOLEAN NOT NULL DEFAULT FALSE;

-- 봇의 성격. **스펙을 손으로 박지 않는다** — 규칙표와 리듬과 실력만 다르게 주면
-- 장비·도달 층·도감은 굴러가면서 저절로 갈린다.
CREATE TABLE IF NOT EXISTS bot_profile (
    account_id    BIGINT      PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    -- 화면에 적히는 이름. 계정 handle 과 따로 두는 이유는 handle 이 유일해야 하기
    -- 때문이다 — 이름은 겹쳐도 되고, 겹치는 편이 사람처럼 보인다.
    label         TEXT        NOT NULL,
    -- 이 봇이 쓰는 규칙표 id. `benchmark.json`·`g0_examples.json` 에서 고른다.
    ruleset_id    TEXT        NOT NULL,
    -- 판 사이에 쉬는 시간(초). 리듬이 다르면 세계가 고르게 움직이지 않는다 — 그것이
    -- 사람이 여럿인 세계의 모습이다.
    cadence_sec   INT         NOT NULL DEFAULT 900,
    -- 실력(%). 100 이면 규칙표를 그대로 쓰고, 낮으면 규칙 몇 줄을 끄고 나간다.
    -- **못하는 봇이 있어야 한다** — 1층에서 죽는 쪽이 지속 몬스터를 먹인다.
    skill_pct     INT         NOT NULL DEFAULT 100,
    -- 기기 토큰. 봇은 로그인하지 않으므로 이것이 유일한 신원이다. 401 이면 다시 받는다.
    token         TEXT,
    -- 다음에 나갈 시각. 이것으로 리듬을 물린다 — 러너가 상시 돌아도 봇마다 제 박자다.
    next_run_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 돌고 있는가. **지우지 않고 멈춘다** — 지우면 그 봇이 벌어 둔 장비·도감·순위가 함께
-- 사라지고, 다시 세우면 다른 계정이 된다. 멈춤은 되돌릴 수 있어야 한다.
ALTER TABLE bot_profile ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 도플갱어는 지속 몬스터의 한 갈래다. **별도 테이블을 만들지 않는다** — 스냅샷·도감·
-- 되찾기·성장 상한이 전부 entity_record 위에 서 있고, 옆에 새 테이블을 두면 그 전부를
-- 두 번 써야 한다. 다른 점은 「플레이어 규칙표를 들고 하강한다」 하나뿐이다.
ALTER TABLE entity_record ADD COLUMN IF NOT EXISTS is_doppel BOOLEAN NOT NULL DEFAULT FALSE;

-- 누구의 그림자인가. 봇이 깊은 층에서 죽으면 그 빌드가 여기 남는다.
ALTER TABLE entity_record ADD COLUMN IF NOT EXISTS origin_account_id BIGINT
    REFERENCES account(id) ON DELETE SET NULL;

-- 도플갱어가 든 로드아웃. 스탯을 stat_json 에 얹지 않고 따로 두는 이유는 **그것이
-- 플레이어 형태이기 때문이다** — 몬스터 스탯 계산(등급×레벨)과 섞이면 둘 다 틀린다.
ALTER TABLE entity_record ADD COLUMN IF NOT EXISTS loadout_json JSONB;
-- 남은 목숨 (개정 2026-09-04). **한 번 잡았다고 사라지지 않는다.**
--
-- 처치가 자리를 비우게 한 직후에 나온 문제다: 봇들이 쉼 없이 싸우니 그림자가 서자마자
-- 지워져, 사람이 만날 새가 없었다. 그렇다고 안 지우면 자리가 굳는다 — 그것이 원래
-- 고치려던 병이다.
--
-- 목숨 셋이 그 사이를 잡는다. 잡을 때마다 하나 줄고 레벨이 감쇠하므로, **같은 그림자를
-- 세 번 만나되 만날 때마다 약해진다.** 「끝내 지웠다」가 한 판이 아니라 이야기가 된다.
--
-- 여느 몬스터는 1 이다 — 그쪽은 애초에 지워지지 않고 감쇠만 하므로 이 값을 안 본다.
ALTER TABLE entity_record ADD COLUMN IF NOT EXISTS lives SMALLINT NOT NULL DEFAULT 1;

