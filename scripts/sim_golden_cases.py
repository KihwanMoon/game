"""기준 전투 케이스 표 (게이트 G3).

내보내기 절차와 갈라 둔 이유는 **이 표가 계약이기 때문**이다. 값 하나를 바꾸면 저장된
기준 로그가 통째로 달라지고 그것으로 대조하던 리플레이가 전부 무효가 된다. 절차를 고칠
때와 표를 고칠 때의 무게가 다르므로 파일을 나눈다 (§4).

표를 늘리는 것은 안전하다 — **뒤에** 붙이는 한. 사이에 끼우면 그 뒤의 모든 기준 로그가
이유 없이 밀린다.
"""

from game.app.simulation.selectors import SELECTOR_ALLY_WOUNDED
from game.schemas.loadout import BASE_SKILL_POWER_PCT, PlayerLoadout
from game.schemas.monster_snapshot import MonsterSnapshot

POLICY_FALLBACK = "fallback"
POLICY_CYCLE = "cycle"

# 시간 초과로 끝나는 판도 대조 대상이다. 400 은 실제 실행값과 같다.
MAX_TICKS = 400

# 기본 층. 케이스마다 다를 수 있으므로 각 레코드가 자기 층을 함께 싣는다.
FLOOR = 1

# 동결된 행동 전부. 순서를 바꾸면 기준 로그가 통째로 달라진다. HEAL 은 v4, USE_SKILL 은
# v5 에서 **뒤에** 붙였다 — 사이에 끼우면 그 뒤의 모든 기준 로그가 이유 없이 밀린다.
ACTION_CYCLE = (
    "APPROACH",
    "ATTACK",
    "SKILL_2",
    "AREA_ATTACK",
    "RETREAT",
    "MOVE_TO_COVER",
    "SUMMON",
    "USE_POTION",
    "MOVE_TO_HEAL",
    "SET_FLAG",
    "MOVE_TO_EXIT",
    "HOLD",
    "SKILL_1",
    "HEAL",
    "USE_SKILL",
)

# 지속 몬스터 케이스. 스냅샷이 층 스케일을 **대체하는지**(얹는 것이 아니라) 가 여기서
# 드러난다 — 얹으면 같은 개체가 층마다 다른 값을 갖게 되어 스냅샷의 뜻이 사라진다.
SNAPSHOT_CASES: tuple[tuple[tuple[str, int, int], tuple[MonsterSnapshot, ...]], ...] = (
    (
        ("corridor", 31337, 1),
        (
            MonsterSnapshot(
                entity_id="goblin_rusher_0",
                record_id=1,
                kind_id="goblin_rusher",
                tier="ELITE",
                level=7,
                hp_max=96,
                attack=17,
                defense=5,
                rule_slots=4,
                cpu_budget=7,
            ),
        ),
    ),
    (
        # 층 5 인데도 스냅샷 값이 그대로 쓰이는지 본다. 층 스케일이 얹히면 여기서 갈린다.
        ("corridor", 31337, 5),
        (
            MonsterSnapshot(
                entity_id="goblin_archer_1",
                record_id=2,
                kind_id="goblin_archer",
                tier="BOSS",
                level=12,
                hp_max=140,
                attack=24,
                defense=9,
                rule_slots=6,
                cpu_budget=10,
            ),
        ),
    ),
)

# 로드아웃 케이스. 장비가 사거리를 바꾸면 **같은 규칙표가 다른 전투를 만든다** (P2) —
# 그것이 장비 전용 DSL 블록 없이 장비를 뜻있게 만드는 지점이므로, 사거리가 다른 둘을 둔다.
LOADOUT_CASES: tuple[tuple[tuple[str, int, int], PlayerLoadout], ...] = (
    (
        ("corridor", 8080, 1),
        PlayerLoadout(
            hp_max=132,
            attack=18,
            defense=8,
            attack_range=1,
            initiative=56,
            cpu_budget=11,
            rule_slots=6,
            skill_power_pct=BASE_SKILL_POWER_PCT,
            skills=("ATTACK", "GUARD_BRACE", "SKILL_1", "SKILL_2"),
        ),
    ),
    (
        # 사거리 4. 같은 시드·같은 방인데 결과가 달라야 한다.
        ("corridor", 8080, 1),
        PlayerLoadout(
            hp_max=96,
            attack=11,
            defense=4,
            attack_range=4,
            initiative=50,
            cpu_budget=8,
            rule_slots=5,
            skill_power_pct=BASE_SKILL_POWER_PCT,
            skills=("ATTACK", "SKILL_2"),
        ),
    ),
    (
        # 지능이 올린 스킬위력. 앞의 두 사례와 **공격력이 같은데** 피해가 달라야
        # 한다 — 그것이 지능이 실제로 전투에 닿는다는 증거다 (결정 #51).
        ("corridor", 8080, 1),
        PlayerLoadout(
            hp_max=96,
            attack=11,
            defense=4,
            attack_range=4,
            initiative=50,
            cpu_budget=8,
            rule_slots=5,
            skill_power_pct=160,
            skills=("ATTACK", "SKILL_2"),
        ),
    ),
)

# USE_SKILL 이 실행할 스킬. 이 정책은 규칙표를 타지 않으므로 여기서 정한다.
# 사거리 4 인 사격을 고른 이유는 근접 스킬과 결과가 갈려야 대조에 뜻이 있기 때문이다.
CYCLE_SKILL = "SKILL_2"

# 행동별 대상 셀렉터. 이 정책은 규칙표를 타지 않으므로 진영을 여기서 맞춘다 —
# 전부 NEAREST 로 두면 HEAL 이 적을 회복해 기준 로그가 뜻 없는 것을 고정한다.
CYCLE_SELECTORS = {"HEAL": SELECTOR_ALLY_WOUNDED}

# SET_FLAG 가 세울 플래그. 규칙표가 쓰는 A~D 안에서 고른다.
CYCLE_FLAG = "A=true"

# 템플릿 id · 시드 · 층. 템플릿마다 적 구성과 지형이 달라 서로 다른 코드 경로를 밟는다.
# 뒤의 다섯은 min_floor 로 층 2~3 에 묶인 방이며, 그 방이 나오는 층에서 돌린다 — 폭탄
# 슬라임·수복 사제·장궁병·정예 돌격병·대소환사가 룸 템플릿에 배치되면서 생긴 자리다.
FALLBACK_CASES = (
    ("open_field", 1, 1),
    ("corridor", 12345, 1),
    ("pillars", 7, 1),
    ("hazard_field", 99, 1),
    ("spring_bait", 2024, 1),
    ("blast_yard", 606, 1),
    ("chapel", 707, 2),
    ("longshot", 909, 2),
    ("warlord_gate", 1212, 2),
    ("summoner_vault", 1515, 3),
)

# 템플릿 id · 시드 · 덧붙일 적. 좌표는 전부 통행 가능하고 스폰과 겹치지 않는 칸이다.
# 폭탄 슬라임과 대소환사를 넣는 것은 예고·자폭·소환이 이 조합에서만 돌기 때문이다.
# 템플릿 id · 시드 · 층 · 덧붙일 적.
CYCLE_CASES = (
    ("open_field", 4242, 1, (("bomb_slime", 5, 4), ("mender_acolyte", 6, 2))),
    ("pillars", 555, 1, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
    ("hazard_field", 808, 1, (("longbow_archer", 6, 4),)),
    ("spring_bait", 31337, 1, (("bomb_slime", 6, 6),)),
    # 층 깊이 스케일이 걸린 채로 행동 14개를 다 돌린다. 방 배치·소환·덧붙인 적이 모두
    # 같은 기준으로 서는지 여기서 고정된다 (docs/04 P-1).
    ("pillars", 3131, 3, (("arch_summoner", 7, 4), ("veteran_rusher", 4, 6))),
)


# 능력치 변환 대조 사례 (결정 #51). 브라우저는 배분 결과를 **미리보기**로 보여 주므로
# 변환표 사본을 갖는데, 두 사본이 갈라지면 화면이 거짓말을 한다. 실제 전투는 서버가
# 계산하므로 갈라져도 판정은 맞지만, 유저는 찍기 전에 본 숫자를 믿고 찍는다.
ATTRIBUTE_CASES: tuple[dict[str, int], ...] = (
    {},
    {"str": 10},
    {"dex": 7},
    # CPU 상한을 넘긴다 — 상한이 양쪽에 같이 있는지 본다.
    {"int": 40},
    {"str": 5, "dex": 5, "int": 5},
    # 손상된 값. 음수 배분이 스탯을 깎으면 안 된다.
    {"str": -3, "dex": 0, "int": 2},
)
