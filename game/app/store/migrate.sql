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
