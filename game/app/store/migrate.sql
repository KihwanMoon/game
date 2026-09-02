-- 스키마 이행 (E단계). `schema.sql` 다음에 돈다.
--
-- **이것이 이 저장소의 첫 실제 마이그레이션이다.** connection.py 는 "컬럼을 지우거나
-- 형을 바꾸는 변경이 처음 생기는 날 도구를 들인다" 고 적어 두었고, 오늘이 그날이다.
-- 다만 도구(alembic 등)를 지금 들이지 않는다 — 이행이 하나뿐이고, 그 하나를 명시적인
-- SQL 로 두는 편이 도구의 자동 생성보다 읽기 쉽다. **두 번째 이행이 이만큼 복잡하면
-- 그때 도구를 들인다.**
--
-- 모든 문장이 멱등이다. 신규 DB 에서는 schema.sql 이 이미 목표 형태를 만들었으므로
-- 여기 있는 것이 전부 no-op 이 된다.

-- ── 1. 계정마다 PLAYER 개체를 만든다 ────────────────────────────────────
-- 아이템이 계정이 아니라 개체를 가리키게 되므로, 기존 계정에도 개체가 있어야 한다.
INSERT INTO entity_record (kind, owner_account_id, persistence)
SELECT 'PLAYER', a.id, 'PERSISTENT'
FROM account a
WHERE NOT EXISTS (SELECT 1 FROM entity_record e WHERE e.owner_account_id = a.id);

-- ── 2. 구 monster_record 를 옮긴다 ──────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'monster_record') THEN
        INSERT INTO entity_record (
            kind, catalog_id, tier, persistence, level, total_xp,
            zone_floor, entity_slot, alive, created_at
        )
        SELECT 'MONSTER', m.catalog_id, m.tier, m.persistence, m.level, m.total_xp,
               m.zone_floor, m.entity_slot, m.alive, m.created_at
        FROM monster_record m
        WHERE NOT EXISTS (
            SELECT 1 FROM entity_record e
            WHERE e.zone_floor = m.zone_floor AND e.entity_slot = m.entity_slot
        );
    END IF;
END $$;

-- ── 3. 아이템 소유자를 계정에서 개체로 옮긴다 ───────────────────────────
ALTER TABLE item_instance ADD COLUMN IF NOT EXISTS owner_entity_id BIGINT
    REFERENCES entity_record(id) ON DELETE CASCADE;
ALTER TABLE item_instance ADD COLUMN IF NOT EXISTS taken_from BIGINT
    REFERENCES account(id) ON DELETE SET NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'item_instance' AND column_name = 'owner_account_id'
    ) THEN
        UPDATE item_instance i SET owner_entity_id = e.id
        FROM entity_record e
        WHERE i.owner_entity_id IS NULL AND e.owner_account_id = i.owner_account_id;
    END IF;
END $$;

-- ── 4. 구 monster_trophy 를 아이템으로 옮긴다 ───────────────────────────
-- 전리품이 별도 표에 있으면 "몬스터가 내 장비를 들고 있다" 가 다시 특수 케이스가 된다.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'monster_trophy') THEN
        INSERT INTO item_instance (owner_entity_id, catalog_id, affixes, taken_from, created_at)
        SELECT e.id, t.catalog_id, t.affixes, t.taken_from, t.taken_at
        FROM monster_trophy t
        JOIN monster_record m ON m.id = t.record_id
        JOIN entity_record e
          ON e.zone_floor = m.zone_floor AND e.entity_slot = m.entity_slot
        WHERE NOT EXISTS (
            SELECT 1 FROM item_instance i
            WHERE i.owner_entity_id = e.id AND i.catalog_id = t.catalog_id
              AND i.taken_from IS NOT DISTINCT FROM t.taken_from
        );
    END IF;
END $$;

-- ── 5. 인벤토리·장비를 개체 기준으로 ────────────────────────────────────
ALTER TABLE inventory_slot ADD COLUMN IF NOT EXISTS entity_id BIGINT
    REFERENCES entity_record(id) ON DELETE CASCADE;
ALTER TABLE equipment_slot ADD COLUMN IF NOT EXISTS entity_id BIGINT
    REFERENCES entity_record(id) ON DELETE CASCADE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'inventory_slot' AND column_name = 'account_id'
    ) THEN
        UPDATE inventory_slot s SET entity_id = e.id
        FROM entity_record e WHERE s.entity_id IS NULL AND e.owner_account_id = s.account_id;
        UPDATE equipment_slot s SET entity_id = e.id
        FROM entity_record e WHERE s.entity_id IS NULL AND e.owner_account_id = s.account_id;
    END IF;
END $$;

-- ── 5b. 아이템 이력도 개체 기준으로 ─────────────────────────────────────
ALTER TABLE item_event ADD COLUMN IF NOT EXISTS entity_id BIGINT
    REFERENCES entity_record(id) ON DELETE CASCADE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'item_event' AND column_name = 'account_id'
    ) THEN
        UPDATE item_event v SET entity_id = e.id
        FROM entity_record e WHERE v.entity_id IS NULL AND e.owner_account_id = v.account_id;
        -- 옮길 수 없는 줄(계정이 지워진 것)은 이력만 남기고 버린다.
        DELETE FROM item_event WHERE entity_id IS NULL;
    END IF;
END $$;

-- ── 6. 스냅샷·경험치 원장의 참조를 옮긴다 ───────────────────────────────
-- 외래키를 **먼저** 떼야 한다. 구 표를 가리키는 제약이 살아 있으면 새 id 로의 갱신이
-- 그 자리에서 막힌다 — 이행이 여기서 멈추는 것을 실제로 겪었다.
ALTER TABLE monster_snapshot DROP CONSTRAINT IF EXISTS monster_snapshot_record_id_fkey;
ALTER TABLE monster_kill DROP CONSTRAINT IF EXISTS monster_kill_record_id_fkey;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'monster_record') THEN
        UPDATE monster_snapshot s SET record_id = e.id
        FROM monster_record m
        JOIN entity_record e
          ON e.zone_floor = m.zone_floor AND e.entity_slot = m.entity_slot
        WHERE s.record_id = m.id AND s.record_id <> e.id;
        UPDATE monster_kill k SET record_id = e.id
        FROM monster_record m
        JOIN entity_record e
          ON e.zone_floor = m.zone_floor AND e.entity_slot = m.entity_slot
        WHERE k.record_id = m.id AND k.record_id <> e.id;
    END IF;
END $$;

-- 옮긴 뒤 새 표를 가리키는 제약을 다시 건다.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'monster_snapshot_record_id_fkey'
    ) THEN
        ALTER TABLE monster_snapshot ADD CONSTRAINT monster_snapshot_record_id_fkey
            FOREIGN KEY (record_id) REFERENCES entity_record(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'monster_kill_record_id_fkey'
    ) THEN
        ALTER TABLE monster_kill ADD CONSTRAINT monster_kill_record_id_fkey
            FOREIGN KEY (record_id) REFERENCES entity_record(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ── 7. 옮긴 뒤 구 표를 지운다 ───────────────────────────────────────────
-- **마지막에 한다.** 앞 단계가 실패하면 원본이 남아 다시 시도할 수 있다.
DROP TABLE IF EXISTS monster_trophy;
DROP TABLE IF EXISTS monster_record CASCADE;
ALTER TABLE item_instance DROP COLUMN IF EXISTS owner_account_id;
ALTER TABLE inventory_slot DROP COLUMN IF EXISTS account_id;
ALTER TABLE equipment_slot DROP COLUMN IF EXISTS account_id;
ALTER TABLE item_event DROP COLUMN IF EXISTS account_id;

-- 옮기고 나서야 NOT NULL 을 건다. 먼저 걸면 백필 중에 막힌다.
ALTER TABLE item_instance ALTER COLUMN owner_entity_id SET NOT NULL;
ALTER TABLE inventory_slot ALTER COLUMN entity_id SET NOT NULL;
ALTER TABLE equipment_slot ALTER COLUMN entity_id SET NOT NULL;
ALTER TABLE item_event ALTER COLUMN entity_id SET NOT NULL;

-- ── 8. 새 컬럼을 참조하는 인덱스 ────────────────────────────────────────
-- schema.sql 에 두면 기존 DB 에서 컬럼이 생기기 전에 돌아 실패한다.
CREATE INDEX IF NOT EXISTS item_instance_owner_idx ON item_instance (owner_entity_id, id);
CREATE INDEX IF NOT EXISTS item_instance_taken_idx ON item_instance (taken_from);
CREATE INDEX IF NOT EXISTS item_event_entity_idx ON item_event (entity_id, at DESC);

-- ── 아이템 인스턴스에 등급을 새긴다 (설계/4_아이템 §15.5) ────────────────
--
-- **카탈로그를 참조하지 않고 복사한다.** 참조로 두면 카탈로그의 등급을 고칠 때 이미
-- 나온 아이템의 등급까지 소급해 바뀐다 — 접사에서 이미 같은 함정을 겪었다.
ALTER TABLE item_instance ADD COLUMN IF NOT EXISTS grade TEXT;

-- ── 계정 비활성화 ───────────────────────────────────────────────────────
--
-- **지우지 않는다.** 계정을 지우면 그 계정이 남긴 것(제출·원장·경매 이력)이 함께
-- 사라지고, 그러면 "이 아이템이 어디서 왔는가" 를 나중에 못 읽는다. 아이템 카탈로그를
-- 폐기로 다루는 것과 같은 규율이다 (설계/4_아이템 §15.7).
--
-- 비운 값(NULL)이 활성이다. 불리언과 시각을 함께 두면 둘이 어긋나는 날이 오고, 그때
-- 어느 쪽이 옳은지 아무도 모른다.
ALTER TABLE account ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS account_active_idx ON account (id) WHERE deactivated_at IS NULL;

-- ── 봉인된 옵션 칸 (설계/4_아이템 §17) ──────────────────────────────────
--
-- 등급이 올라가면 옵션 칸이 하나씩 는다. 획득 시점에는 **봉인돼 있고**, 화폐를 내면
-- 서버가 무작위 옵션 하나를 굴려 붙인다.
--
-- **남은 칸 수만 센다.** 무엇이 들어올지를 미리 정해 두면 그것이 클라이언트에 실려 나가고,
-- 그 순간 "열기 전에 아는" 것이 된다 — 열 이유가 사라진다.
ALTER TABLE item_instance ADD COLUMN IF NOT EXISTS sealed_slots INT NOT NULL DEFAULT 0;

-- 봉인을 열 때 뽑는 옵션 풀. 서버만 읽는다 — 굴림이 코어 밖이라 리플레이가 안 흔들린다.
CREATE TABLE IF NOT EXISTS affix_pool (
    id           BIGSERIAL PRIMARY KEY,
    stat         TEXT      NOT NULL,
    label_ko     TEXT      NOT NULL,
    flat_min     INT       NOT NULL DEFAULT 0,
    flat_max     INT       NOT NULL DEFAULT 0,
    percent_min  INT       NOT NULL DEFAULT 0,
    percent_max  INT       NOT NULL DEFAULT 0,
    weight       INT       NOT NULL DEFAULT 1,
    is_retired   BOOLEAN   NOT NULL DEFAULT FALSE
);

-- ── 인스턴스가 자기 접사를 갖게 한다 (설계/4_아이템 §15.11) ─────────────
--
-- **이 한 줄이 카탈로그 편집을 열어 준다.** 지금까지 인스턴스의 접사가 비어 있으면 읽는
-- 쪽이 카탈로그 기본값으로 메웠고, 그래서 카탈로그를 고치면 남의 가방에 있는 아이템의
-- 성능이 소급해 바뀌었다 — 그 때문에 접사·등급 수정을 통째로 막아 뒀다.
--
-- 비어 있던 것을 **지금 해석되는 값 그대로** 채운다. 동작은 하나도 안 바뀐다. 그러고
-- 나면 읽는 쪽이 카탈로그를 안 봐도 되고, 카탈로그는 앞으로 나올 것에만 걸린다.
UPDATE item_instance i
SET affixes = c.affixes
FROM item_catalog c
WHERE c.catalog_id = i.catalog_id
  AND i.affixes = '[]'::jsonb
  AND c.affixes <> '[]'::jsonb;


-- ── 등급이 뜻하는 것을 하나로 (설계/4_아이템 §15.4, §17) ────────────────
--
-- `affix_min`·`affix_max` 는 「등급이 접사 개수를 정한다」의 잔재다. 그 체계는 카탈로그가
-- 좋은 접사를 먼저 적어 두는 탓에 **잘리는 쪽이 늘 저주였고**, 대검의 과부하와 장궁의
-- 페널티가 한 번도 발급되지 않았다. 이제 고정 접사는 전부 붙고, 등급이 성능에 하는 일은
-- 봉인 칸 수 하나뿐이다.
--
-- 두 칸은 쓰는 데가 없으면서 정본처럼 보인다 — 다음 사람이 그것을 규칙으로 읽기 전에
-- 지운다.
ALTER TABLE item_grade ADD COLUMN IF NOT EXISTS sealed_slots INT NOT NULL DEFAULT 0;
ALTER TABLE item_grade DROP COLUMN IF EXISTS affix_min;
ALTER TABLE item_grade DROP COLUMN IF EXISTS affix_max;


-- ── 사거리를 무기의 1급 필드로 (설계/4_아이템 §2.2) ─────────────────────
--
-- 예전에는 사거리를 접사로 흉내냈다. 접사는 굴림에서 잘릴 수 있어 **활이 근접무기가 되는**
-- 경로가 있었고, 실제로 장궁은 사거리 접사 하나에 목숨을 걸고 있었다. `hands` 가 손을
-- 정하듯 사거리도 무기가 정한다.
ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS attack_range INT;

-- 씨앗 무기에 사거리를 박고, 그 일을 대신하던 접사를 뺀다. **둘 다 두면 값이 두 번
-- 붙는다** — 장궁이 4 가 아니라 7 이 된다.
UPDATE item_catalog SET attack_range = 4 WHERE catalog_id = 'bow_long' AND attack_range IS NULL;
UPDATE item_catalog SET attack_range = 1
 WHERE catalog_id IN ('sword_short', 'sword_great') AND attack_range IS NULL;

-- 이미 나온 것에서도 뺀다. 안 빼면 지금 가방에 있는 장궁만 사거리 7 이 된다.
UPDATE item_catalog
   SET affixes = (
       SELECT COALESCE(jsonb_agg(item), '[]'::jsonb)
         FROM jsonb_array_elements(affixes) AS item
        WHERE item->>'stat' <> 'attack_range'
   )
 WHERE attack_range IS NOT NULL AND affixes @> '[{"stat": "attack_range"}]'::jsonb;

UPDATE item_instance i
   SET affixes = (
       SELECT COALESCE(jsonb_agg(item), '[]'::jsonb)
         FROM jsonb_array_elements(i.affixes) AS item
        WHERE item->>'stat' <> 'attack_range'
   )
  FROM item_catalog c
 WHERE c.catalog_id = i.catalog_id
   AND c.attack_range IS NOT NULL
   AND i.affixes @> '[{"stat": "attack_range"}]'::jsonb;


-- ── 태그를 코드용과 표시용으로 가른다 (설계/4_아이템 §4) ────────────────
--
-- `tags` 한 목록이 두 가지 일을 겸하고 있었다. `POTION`·`SCROLL` 은 코드가 읽어 소모품
-- 개수를 세는 데 썼고, `MELEE`·`SHIELD`·`CURSED` 는 아무 데서도 안 읽었다. 그래서 물약에
-- 분류용 이름표를 하나 더 붙이면 **그 이름표까지 소모품 종류가 됐다.**
--
-- 코드가 읽는 것을 한 칸으로 뺀다. 남은 `tags` 는 표시 전용이라 무엇을 적어도 규칙이
-- 안 바뀐다.
ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS use_tag TEXT;

-- 지금 코드가 실제로 읽던 두 태그만 옮긴다. 나머지는 표시용이 맞다.
UPDATE item_catalog SET use_tag = 'POTION'
 WHERE use_tag IS NULL AND kind = 'CONSUMABLE' AND tags @> '["POTION"]'::jsonb;
UPDATE item_catalog SET use_tag = 'SCROLL'
 WHERE use_tag IS NULL AND kind = 'CONSUMABLE' AND tags @> '["SCROLL"]'::jsonb;


-- ── 등급 없이 발급된 아이템에 등급을 준다 (설계/4_아이템 §15.5) ─────────
--
-- 등급이 생기기 전에 발급된 줄이 50개 남아 있었다. 등급이 비어 있으면 화면이 **색도
-- 이름표도 안 붙인다** — 사람 눈에는 "등급 표기가 반영 안 됐다" 로 보인다.
--
-- 보통으로 채운다. 그때는 등급이 하나뿐이었으므로 이것이 사실이고, 봉인 칸은 보통이
-- 0 칸이라 이미 0 인 값과 어긋나지 않는다.
UPDATE item_instance SET grade = 'COMMON' WHERE grade IS NULL OR grade = '';


-- ── 층이 실제로 오르게 한다 (설계/6_몬스터 §3) ──────────────────────────
--
-- 층 스케일 수식(층당 HP +25% · 공격 +20%)은 처음부터 있었는데 **한 번도 발동한 적이
-- 없었다** — 클라이언트가 티켓 요청에 층을 안 실어서 늘 1층이었다.
--
-- 도달 층을 개체에 둔다. `zone_floor` 와 가르는 이유는 뜻이 다르기 때문이다.
ALTER TABLE entity_record ADD COLUMN IF NOT EXISTS reached_floor INTEGER NOT NULL DEFAULT 1;


-- ── 한 런이 하강 전체가 된다 (로드맵 W14) ────────────────────────────────
--
-- 예전에는 한 티켓이 한 층(방 셋)이었다. 층마다 따로 제출하면 층 사이에 인계되는 HP 를
-- 클라이언트가 보고하게 되고, 그러면 "나는 만피로 시작했다" 를 적어 보내는 것이 곧
-- 진행이 된다 (T9). 한 티켓으로 하강 전체를 재시뮬하는 것이 그것을 막는다.
--
-- 층당 방 수를 티켓에 얼린다. 상수로 두면 상수를 고치는 순간 이미 발급한 티켓의 방
-- 목록이 조용히 다른 층 배치로 읽힌다.
ALTER TABLE run_ticket ADD COLUMN IF NOT EXISTS rooms_per_floor INTEGER NOT NULL DEFAULT 0;


-- ── 층 단위 보상 (로드맵 W14) ────────────────────────────────────────────
--
-- 층을 깰 때마다 경험치·화폐·아이템을 주려면 한 티켓으로 여러 번 제출해야 한다. T6 의
-- 「한 티켓 한 제출」을 **「더 깊은 층으로만 나아갈 수 있다」**로 다시 세운다 — 같은 층을
-- 두 번 제출해 보상을 두 번 받는 길을 이 값이 막는다.
--
-- 인계 HP 는 여전히 클라이언트가 안 보낸다. 서버가 **매번 처음부터** 그 층까지 재시뮬해
-- 확정하므로 "나는 만피로 시작했다" 를 적어 보낼 자리가 없다 (T9).
ALTER TABLE run_ticket ADD COLUMN IF NOT EXISTS cleared_floor INTEGER NOT NULL DEFAULT 0;


-- 한 티켓에 제출이 여럿이 된다 (로드맵 W14). 「한 티켓 한 제출」이 막던 것은
-- `run_ticket.cleared_floor` 가 막는다 — 더 깊은 층으로만 나아갈 수 있다.
--
-- 제약 이름은 PostgreSQL 이 자동으로 붙인 것이다. 없으면 조용히 넘어간다 — 새 DB 는
-- schema.sql 로 서므로 애초에 없다.
ALTER TABLE run_submission DROP CONSTRAINT IF EXISTS run_submission_ticket_id_key;

CREATE INDEX IF NOT EXISTS run_submission_ticket_idx ON run_submission (ticket_id, submitted_at);


-- ── 가방에 쌓이지 않은 소모품을 스택으로 옮긴다 (설계/4_아이템 §5) ──────
--
-- 소모품 발급이 인스턴스로 들어가고 있었다. **세는 쪽은 스택만 본다** — 그래서 물약을
-- 여섯 개 들고도 전투에는 기본 지급 두 개만 나갔다. 「가방에 있는 소모품을 못 쓴다」의
-- 정체다.
--
-- 이미 들어와 있는 것을 옮긴다. 한 칸에 하나씩이라 칸 수는 그대로이고, 세는 쪽이
-- 비로소 그것을 본다. 스택 상한을 넘겨 합치지는 않는다 — 합치려면 칸을 비워야 하고,
-- 그 조작이 실패하면 아이템이 사라진다.
UPDATE inventory_slot s
   SET stack_catalog_id = i.catalog_id,
       stack_count = 1,
       item_id = NULL
  FROM item_instance i, item_catalog c
 WHERE i.id = s.item_id
   AND c.catalog_id = i.catalog_id
   AND c.kind = 'CONSUMABLE';

-- 옮기고 난 인스턴스는 어느 칸도 안 가리키므로 화면에 안 뜬다. **지우지 않는다** —
-- 원장(`item_event`)과 굴림 기록이 그 id 를 가리키므로 지우면 과거를 못 읽는다.


-- ── 스택 상한이 DB 로 안 넘어와 있었다 (설계/4_아이템 §5) ────────────────
--
-- 카탈로그가 파일에서 DB 로 옮겨 올 때 `stack_max` 가 빠졌다. 그래서 상한이 1 로 읽혀
-- **소모품이 칸마다 하나씩 흩어졌다** — 물약 여섯 개가 가방 스무 칸 중 여섯을 먹는다.
ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS stack_max INTEGER NOT NULL DEFAULT 1;

-- 씨앗의 값을 채운다. 소모품만 1 보다 크다.
UPDATE item_catalog SET stack_max = 9 WHERE catalog_id = 'potion_heal' AND stack_max <= 1;
UPDATE item_catalog SET stack_max = 5 WHERE catalog_id = 'scroll_shield' AND stack_max <= 1;


-- ── 소모품이 「가진 것」에서 「들고 갈 것」이 됐다 (설계/4_아이템 §5) ────────
--
-- 칸 하나가 담는 충전 수는 카탈로그가 정한다. 등급이 장비에서 봉인 칸을 정하듯,
-- 소모품에서는 이것을 정한다.
ALTER TABLE item_catalog ADD COLUMN IF NOT EXISTS charges INTEGER NOT NULL DEFAULT 1;

UPDATE item_catalog SET charges = 2 WHERE catalog_id = 'potion_heal' AND charges <= 1;


-- ── 소모품의 부가 옵션이 DB 로 안 넘어와 있었다 (설계/4_아이템 §5) ──────────
--
-- 카탈로그 씨앗은 **없는 줄만 심고 있는 줄은 안 고친다** — 관리자가 DB 에서 고친 것이
-- 배포 한 번에 사라지면 정본이 DB 라는 말이 거짓이 되기 때문이다. 그래서 이미 있는
-- 소모품에 옵션을 더하면 파일에만 남는다.
--
-- **비어 있을 때만 채운다.** 관리자가 손댄 줄은 그대로 둔다. `stack_max`·`charges` 와
-- 같은 자리이며, 「파일에 있는데 DB 에 없다」는 이 저장소에서 네 번째다.
UPDATE item_catalog SET affixes = '[{"stat": "hp_max", "flat": 4, "percent": 0, "label_ko": "든든함"}]'::jsonb
 WHERE catalog_id = 'potion_heal' AND coalesce(jsonb_array_length(affixes), 0) = 0;
UPDATE item_catalog SET affixes = '[{"stat": "defense", "flat": 1, "percent": 0, "label_ko": "지킴"}]'::jsonb
 WHERE catalog_id = 'scroll_shield' AND coalesce(jsonb_array_length(affixes), 0) = 0;
UPDATE item_catalog SET affixes = '[{"stat": "hp_max", "flat": 12, "percent": 0, "label_ko": "든든함"}]'::jsonb
 WHERE catalog_id = 'potion_greater' AND coalesce(jsonb_array_length(affixes), 0) = 0;
UPDATE item_catalog SET affixes = '[{"stat": "hp_max", "flat": 25, "percent": 0, "label_ko": "든든함"}]'::jsonb
 WHERE catalog_id = 'potion_elixir' AND coalesce(jsonb_array_length(affixes), 0) = 0;
UPDATE item_catalog SET affixes = '[{"stat": "defense", "flat": 3, "percent": 0, "label_ko": "지킴"}]'::jsonb
 WHERE catalog_id = 'scroll_ward' AND coalesce(jsonb_array_length(affixes), 0) = 0;
