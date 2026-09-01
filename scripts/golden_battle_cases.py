"""골든 리플레이 케이스 표와 세계 조립 (게이트 G3).

`export_golden.py` 에서 갈라 나왔다. 여기 있는 것은 **무엇을 돌릴 것인가** — 어떤
(시드 × 방 × 규칙표) 조합을 태우고 그 세계를 어떻게 세우는가다. 돌린 결과를 레코드로
받아 적는 것은 `export_golden.py` 쪽이다.
"""

from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
)
from game.app.simulation.engine import TickEngine
from game.app.simulation.scaling import build_floor_scale, get_scaled_enemy_stats
from game.app.simulation.state import FACTION_ENEMY, Entity
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import BlockCatalog, load_block_catalog
from game.schemas.room import RoomTemplate, load_room_templates
from game.schemas.ruleset import RuleSet, load_rulesets

# 플레이어 엔티티의 고정 id. 규칙표는 이 이름으로 걸린다.
PLAYER_ID = "player"

# 시간 초과로 끝나는 판도 대조 대상이다. 400 은 실제 실행값과 같다.
MAX_TICKS = 400

# 기본 층. 피해 공식의 방어 감쇠와 층 깊이 스케일이 이 값을 본다. 케이스마다 다를 수
# 있으므로 각 레코드가 자기 층을 함께 싣는다.
FLOOR = 1

# 방 다섯 개 전부. 지형·적 구성이 달라 서로 다른 코드 경로를 밟는다.
ROOM_IDS = ("open_field", "corridor", "pillars", "hazard_field", "spring_bait")

# 방마다 다른 시드를 준다. 같은 시드로 다섯 판을 돌리면 난수 소비 지점이 같은 순서로만
# 검증되어, 소비 횟수가 어긋나는 버그가 한 방향으로만 드러난다.
ROOM_SEEDS = (1, 12345, 7, 99, 2024)

# 대표 규칙표 3종 (g0_examples.json). 압박·카이팅·엄폐로 행동 경로가 갈린다.
PLAYER_RULESET_IDS = ("g0_pressure", "g0_kite", "g0_cover")

# 벤치마크 규칙표로 도는 추가 조합. (규칙표 id, 방 id, 시드).
# g0 3종이 쓰지 않는 행동 — 광역·원거리 스킬·샘 점거·문 지키기 — 를 여기서 태운다.
BENCHMARK_CASES = (
    ("sniper", "corridor", 4242),
    ("area_sweep", "open_field", 555),
    ("spring_camp", "spring_bait", 808),
    ("door_hold", "pillars", 31337),
    ("focus_summoner", "hazard_field", 20240931),
)

# 템플릿에 없는 적을 덧붙여 도는 조합. (규칙표 id, 방 id, 시드, 덧붙일 적).
# 방 다섯 개의 스폰이 전부 고블린 3종이라, 이것이 없으면 폭탄 슬라임·수복사·대소환사·
# 장궁병의 규칙표가 한 번도 돌지 않는다. 예고(TELEGRAPH) 페이즈도 여기서만 로그에 남는다.
# 좌표는 전부 통행 가능하고 템플릿 스폰과 겹치지 않는 칸이다.
ADVANCED_CASES = (
    ("g0_kite", "open_field", 4242, (("bomb_slime", 5, 4), ("mender_acolyte", 6, 2))),
    ("g0_cover", "pillars", 555, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
    ("focus_ranged", "hazard_field", 808, (("longbow_archer", 6, 4),)),
    ("focus_lowest", "spring_bait", 31337, (("bomb_slime", 6, 6),)),
    ("focus_threat", "corridor", 20240931, (("mender_acolyte", 6, 2),)),
    # 블록 목록 v4 의 회복을 규칙표로 태우는 조합이다. 사제가 잡몹 무리 뒤에 서 있어
    # 사거리 2 안에 다친 아군이 계속 들어오고, 그래서 `HEAL @ALLY_WOUNDED` 가 실제로
    # 발동한다 — 다른 조합은 사제가 먼저 죽거나 아군이 사거리 밖에 있어 이 경로가 빈다.
    ("focus_threat", "spring_bait", 31337, (("mender_acolyte", 6, 6),)),
)

# min_floor 로 층 2~3 에 묶인 방들. 다섯 방을 여기서 처음 태운다 — 폭탄 슬라임·수복 사제·
# 장궁병·정예 돌격병·대소환사가 이제 룸 템플릿에 실제로 배치돼 있고, 그 방을 그 방이
# 나오는 층에서 돌려야 도감이 적은 것과 실행이 같아진다. (규칙표 id, 방 id, 시드, 층).
ROOM_FLOOR_CASES = (
    # 예고 타일을 읽고 비켜서는 규칙표. `위험 예고 타일 위에 있는가` 가 참이 되는
    # 유일한 조합이라 자폭 회피 경로가 여기서만 로그에 남는다.
    ("g0_cover", "blast_yard", 1, 1),
    # 같은 방·같은 시드인데 예고를 읽지 않는 규칙표. 폭발이 실제로 터진다.
    ("focus_ranged", "blast_yard", 1, 1),
    ("focus_threat", "chapel", 31337, 2),
    ("focus_lowest", "longshot", 808, 2),
    ("focus_lowest", "warlord_gate", 4242, 2),
    ("area_sweep", "summoner_vault", 555, 3),
)

# 층 깊이 스케일을 대조에 고정하는 조합. 같은 방을 층 3 에서 돌린다 — 적의 최대 HP 와
# 공격력이 정수 퍼센트로 얹히는 것이 두 코어에서 같아야 한다 (docs/04 P-1).
# 방 배치·소환물·추격자 세 경로를 각각 태운다. (규칙표 id, 방 id, 시드, 층).
DEPTH_CASES = (
    ("g0_pressure", "open_field", 300, 3),
    ("g0_kite", "pillars", 3003, 3),
    ("spring_camp", "spring_bait", 3007, 3),
)

# 새 방 20개 (로드맵 W3). **골든이 모든 방을 덮어야 한다** — 방마다 지형이 다르고,
# 지형은 시야·경로·포위도가 갈리는 자리다. 한 방이라도 빠지면 그 방에서 두 코어가
# 어긋나도 골든이 침묵한다.
#
# 각 방을 자기 `min_floor` 에서 돌린다. 그 층에서 실제로 나오는 방이므로, 층 스케일이
# 얹힌 채로 대조하는 것이 맞다. (규칙표 id, 방 id, 시드, 층).
NEW_ROOM_CASES = (
    ("g0_pressure", "twin_door", 5100, 1),
    ("g0_kite", "narrow_cross", 5137, 1),
    ("g0_cover", "open_pit", 5174, 2),
    ("g0_pressure", "cover_row", 5211, 2),
    ("g0_kite", "archer_nest", 5248, 3),
    ("g0_cover", "bomb_alley", 5285, 3),
    ("g0_pressure", "thorn_maze", 5322, 4),
    ("g0_kite", "spring_alcove", 5359, 4),
    ("g0_cover", "lava_bridge", 5396, 5),
    ("g0_pressure", "summon_pit", 5433, 5),
    ("g0_kite", "mender_wall", 5470, 6),
    ("g0_cover", "crossfire", 5507, 6),
    ("g0_pressure", "veteran_hall", 5544, 7),
    ("g0_kite", "bomb_garden", 5581, 7),
    ("g0_cover", "long_gallery", 5618, 8),
    ("g0_pressure", "double_summon", 5655, 8),
    ("g0_kite", "gauntlet", 5692, 9),
    ("g0_cover", "lava_ring", 5729, 9),
    ("g0_pressure", "spring_trap", 5766, 10),
    ("g0_kite", "last_gate", 5803, 10),
    # 보스. **방마다 골든을 두는 규칙에 보스도 예외가 아니다** — 사거리 2 와 재생 2 가
    # 두 코어에서 같은 답을 내는지 여기서 고정된다.
    ("g0_kite", "boss_hall", 5840, 10),
)

# 덧붙일 적이 없는 조합이 쓰는 빈 목록.
NO_EXTRAS: tuple[tuple[str, int, int], ...] = ()


def load_case_resources() -> tuple[dict, dict[str, RoomTemplate], BlockCatalog, dict[str, RuleSet]]:
    """케이스를 돌리는 데 필요한 리소스를 전부 읽는다.

    Returns:
        밸런스 딕셔너리, 방 id 대응표, 블록 카탈로그, 규칙표 id 대응표.
    """
    balance = load_balance(BALANCE_PATH)
    rooms = {
        template.template_id: template for template in load_room_templates(ROOM_TEMPLATES_PATH)
    }
    catalog = load_block_catalog(BLOCKS_PATH)
    rulesets = dict(load_rulesets(G0_RULESETS_PATH))
    rulesets.update(load_rulesets(BENCHMARK_RULESETS_PATH))
    return balance, rooms, catalog, rulesets


# 조합 하나. (방 id, 규칙표 id, 시드, 층, 덧붙일 적).
CasePlan = tuple[str, str, int, int, tuple[tuple[str, int, int], ...]]


def list_case_plans() -> list[CasePlan]:
    """돌릴 조합을 (방 id, 규칙표 id, 시드, 층, 덧붙일 적) 로 편다.

    Returns:
        조합 목록. 순서가 곧 기준 문서의 순서다.
    """
    plans: list[CasePlan] = [
        (room_id, ruleset_id, seed, FLOOR, NO_EXTRAS)
        for ruleset_id in PLAYER_RULESET_IDS
        for room_id, seed in zip(ROOM_IDS, ROOM_SEEDS, strict=True)
    ]
    plans.extend(
        (room_id, ruleset_id, seed, FLOOR, NO_EXTRAS)
        for ruleset_id, room_id, seed in BENCHMARK_CASES
    )
    plans.extend(
        (room_id, ruleset_id, seed, FLOOR, extras)
        for ruleset_id, room_id, seed, extras in ADVANCED_CASES
    )
    plans.extend(
        (room_id, ruleset_id, seed, floor, NO_EXTRAS)
        for ruleset_id, room_id, seed, floor in (
            *ROOM_FLOOR_CASES,
            *DEPTH_CASES,
            *NEW_ROOM_CASES,
        )
    )
    return plans


def add_extra_enemies(
    engine: TickEngine, balance: dict, extras: tuple[tuple[str, int, int], ...]
) -> None:
    """템플릿에 없는 적을 방에 덧붙인다.

    층 깊이 스케일을 방 배치와 같은 함수로 건다. 걸지 않으면 층 2 이상의 케이스에서
    덧붙인 적만 층 1 스탯으로 서서, 같은 방에 두 기준이 섞인 것을 기준 문서가 고정한다.

    id 는 `{종류}_x{순번}` 이다. 템플릿 스폰의 `_{index}` 와 겹치지 않아야 한 쪽이 조용히
    덮이지 않는다.

    Args:
        engine: 조립된 엔진.
        balance: 밸런스 딕셔너리.
        extras: (종류 id, x, y) 목록.
    """
    by_id = {kind["id"]: kind for kind in balance["enemies"]}
    scale = build_floor_scale(balance.get("floor_scale", {}))
    for index, (kind_id, x, y) in enumerate(extras):
        kind = by_id[kind_id]
        hp_max, attack = get_scaled_enemy_stats(kind, scale, engine.config.floor)
        entity_id = f"{kind_id}_x{index}"
        engine.state.entities[entity_id] = Entity(
            entity_id=entity_id,
            kind_id=kind_id,
            faction=FACTION_ENEMY,
            position=(x, y),
            hp=hp_max,
            hp_max=hp_max,
            attack=attack,
            defense=kind["defense"],
            attack_range=kind["attack_range"],
            initiative=kind["initiative"],
            regen_base=kind["regen_base"],
            cpu_budget=kind.get("cpu_budget", 0),
            consumables={"POTION": int(kind.get("potions", 0))},
        )
    engine.register_newcomers()


def build_case_engine(
    balance: dict,
    template: RoomTemplate,
    catalog: BlockCatalog,
    enemy_rulesets: dict[str, RuleSet],
    player_ruleset: RuleSet,
    seed: int,
    floor: int,
) -> TickEngine:
    """실제 플레이와 같은 배선으로 엔진을 조립한다.

    플레이어 규칙표를 먼저 걸고 적 규칙표를 나중에 붙인다. 순서를 바꾸면
    `assign_enemy_policies` 가 도는 `register_newcomers` 가 플레이어 자리를 먼저 채워
    규칙표가 조용히 덮인다.

    Args:
        balance: 밸런스 딕셔너리.
        template: 쓸 룸 템플릿.
        catalog: 동결된 블록 카탈로그.
        enemy_rulesets: 적 규칙표 대응표.
        player_ruleset: 플레이어가 쓸 규칙표.
        seed: 난수 시드.
        floor: 이 케이스의 층. 적 능력치에 층 깊이 스케일이 이 값으로 얹힌다.

    Returns:
        첫 틱을 돌릴 준비가 된 엔진.
    """
    engine = build_engine(template, balance, seed=seed, max_ticks=MAX_TICKS, floor=floor)
    engine.policies[PLAYER_ID] = build_rule_vm(player_ruleset, catalog, engine.config.kind_types)
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    return engine
