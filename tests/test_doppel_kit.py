"""그림자가 무엇을 들고 나오는가 (설계/6_몬스터).

`test_api_doppel.py` 에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 **아이템이
사람에게 안 간다**를 지키고, 이쪽은 **그림자가 무엇을 들고 싸우는가**를 지킨다.
"""


def test_a_doppel_carries_no_potions():
    """★ 그림자는 물약을 안 쓴다 (2026-09-06).

    원본 봇이 들고 다니던 것이 그대로 얼어붙어 있었다. 그림자는 목숨 셋을 쓰며 세 번
    만나는 개체인데 거기에 회복까지 붙으면 한 판이 아니라 **소모전**이 된다 — 잡을 수
    있어야 「끝내 지웠다」가 성립한다.
    """
    from game.app.bots.doppel import DOPPEL_KIND_ID
    from game.app.store.monster_snapshots import build_monster_snapshot
    from game.app.store.monsters import MonsterRecord

    def build(catalog_id):
        record = MonsterRecord(
            record_id=1,
            catalog_id=catalog_id,
            tier="NORMAL",
            zone_floor=4,
            entity_slot="probe_0",
            total_xp=0,
            level=3,
            alive=True,
            stat_json={"potions": 7},
        )
        return build_monster_snapshot(
            record,
            {
                "id": catalog_id,
                "hp_max": 10,
                "attack": 1,
                "defense": 0,
                "attack_range": 1,
                "potions": 2,
                "rule_slots": 0,
                "cpu_budget": 0,
            },
            {},
        )

    assert build(DOPPEL_KIND_ID).potions == 0, "그림자가 물약을 들고 있다"
    # 여느 몬스터는 얼려 둔 것을 그대로 쓴다 — 그림자만 다르다.
    assert build("goblin_rusher").potions == 7
