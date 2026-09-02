"""전략 공간과 어뷰징 차단의 회귀 (R2·G2, docs/05).

`docs/05_전략공간_실측.md` 가 1,000 런으로 낸 판정 중 값이 바뀌면 곧바로 거짓이 되는
것들만 여기에 못박는다. 승률 절대값이 아니라 **판정을 떠받치는 부등호**를 검사한다 —
밸런스를 만지면 절대값은 움직여도 되지만 부등호가 뒤집히면 문서를 고쳐야 한다.
"""

import pytest

from game.app.services.run_batch import run_batch, run_floor_batch
from game.app.services.run_battle import load_balance
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets, parse_ruleset

BATCH_RUNS = 12
FLOOR_BATCH_RUNS = 20

# 방 하나를 이만큼 끌면 이긴 런에서는 볼 수 없는 길이다 (이긴 런의 최장이 59틱).
LONG_ROOM_TICKS = 100

# run_room_chain 의 기본 상한. 여기에 닿으면 전투가 끝나지 않은 것이다.
TICK_CAP = 400


@pytest.fixture(scope="module")
def parts():
    templates = load_room_templates(ROOM_TEMPLATES_PATH)
    player = load_rulesets(G0_RULESETS_PATH)
    player.update(load_rulesets(BENCHMARK_RULESETS_PATH))
    return {
        "catalog": load_block_catalog(BLOCKS_PATH),
        "balance": load_balance(BALANCE_PATH),
        "rooms": {t.template_id: t for t in templates},
        "templates": templates,
        "player": player,
        "enemy": load_rulesets(ENEMY_RULESETS_PATH),
    }


def run_room_with(parts, ruleset_id, room_id, runs=BATCH_RUNS):
    """방 하나를 규칙표 하나로 돌려 통계를 낸다."""
    return run_batch(
        ruleset_id,
        (parts["rooms"][room_id],),
        parts["balance"],
        parts["catalog"],
        parts["player"][ruleset_id],
        parts["enemy"],
        runs=runs,
        base_seed=1,
    )


def test_floor_batch_does_not_collapse_to_zero_or_hundred(parts):
    # 고정 연쇄는 방도 적 배치도 시드와 무관하게 같아 승률이 0%/100% 로만 나온다.
    # 층을 시드마다 새로 만들어야 R2 가 볼 수 있는 분포가 생긴다.
    #
    # **프로브는 중간 성적의 규칙표여야 한다.** 실측 재배치(room v4)로 1층이 순해져
    # g0_kite 는 98% 를 이긴다 — 20런 표본에서는 100% 로 접혀 이 검사가 못 본다.
    # g0_pressure 는 pillars 가 섞인 판만 지므로 분포가 표본 안에 들어온다.
    stats = run_floor_batch(
        "g0_pressure",
        parts["templates"],
        parts["balance"],
        parts["catalog"],
        parts["player"]["g0_pressure"],
        parts["enemy"],
        runs=FLOOR_BATCH_RUNS,
        base_seed=1,
    )
    assert 0 < stats.win_rate_pct < 100


def test_bestiary_counter_wins_the_room_that_kiting_loses(parts):
    # 도감이 공개하는 것: ai_summoner 는 사거리 3 안에서만 SUMMON 한다. 사거리 4 의
    # 사격은 그 밖에서 닿으므로, 카이팅의 사격 대상만 소환사로 돌리면 소환이 돌지
    # 않는다. GDD §2.3 "실패한 런조차 자산을 남긴다" 가 성립하는지 보는 자리다.
    kite = run_room_with(parts, "g0_kite", "spring_bait")
    counter = run_room_with(parts, "kite_summoner", "spring_bait")
    assert kite.win_rate_pct == 0
    assert counter.win_rate_pct == 100


def test_dragging_the_room_out_ends_in_death(parts):
    """★ 버티기만 하면 **오래 끌다 죽는다** — 시간을 끌어 이기는 구멍이 없다 (G2).

    **절대 틱수로 재지 않는다.** 예전에는 100틱을 넘는지를 봤는데, 그 숫자의 상당 부분이
    **스톨 자체**였다 — 시야에 막힌 원거리 공격이 매 틱 같은 규칙을 다시 뽑아 캐릭터가
    굳은 채로 틱이 쌓였다. 그것을 고치자 모든 판이 짧아졌고, 임계값은 뜻을 잃었다.

    남는 주장은 둘이다: **이기지 못하고**, **싸운 판보다 오래 끈다.** 뒤엣것이 있어야
    「즉사」와 「끌다 죽음」이 갈린다.
    """
    from game.config import BENCHMARK_RULESETS_PATH
    from game.schemas.ruleset import parse_ruleset

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    common = dict(
        templates=(parts["rooms"]["corridor"],),
        balance=parts["balance"],
        catalog=parts["catalog"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    # 절대 때리지 않고 영원히 물러나는 규칙표. 계측기이므로 벤치마크가 아니라 여기 산다.
    probe = parse_ruleset(next(item for item in ABUSE_PROBES if item["ruleset_id"] == "abuse_kite"))
    dragged = run_batch("abuse_kite", player_ruleset=probe, **common)
    fought = run_batch("spring_camp", player_ruleset=bench["spring_camp"], **common)

    assert dragged.win_rate_pct == 0, dragged
    assert fought.win_rate_pct == 100, "싸운 쪽이 져 버리면 비교가 뜻을 잃는다"
    assert dragged.average_ticks > fought.average_ticks, (dragged, fought)


# 어뷰징 시험용 규칙표 (G2 첫 조건, docs/05 §5.1). 벤치마크가 아니라 계측기이므로
# game/resources/ 에 두지 않는다 — 배치 러너의 표에 섞이면 전략 공간을 잘못 읽게 된다.
ABUSE_PROBES = (
    {
        "ruleset_id": "abuse_kite",
        "version": 1,
        "strategy_ko": "어뷰징 시험 — 절대 때리지 않고 영원히 물러난다.",
        "rules": [
            {
                "priority": 1,
                "cpu_cost": 1,
                "action": "RETREAT",
                "target": "NEAREST",
                "conditions": {
                    "op": "SINGLE",
                    "terms": [
                        {"lhs": "target_distance", "lhs_param": "NEAREST", "cmp": "<=", "rhs": 99}
                    ],
                },
            }
        ],
    },
    {
        "ruleset_id": "abuse_spring",
        "version": 1,
        "strategy_ko": "어뷰징 시험 — 회복타일 위에서 버티며 때리지 않는다.",
        "rules": [
            {
                "priority": 1,
                "cpu_cost": 2,
                "action": "USE_POTION",
                "target": None,
                "conditions": {
                    "op": "AND",
                    "terms": [
                        {"lhs": "self_hp_percent", "cmp": "<", "rhs": 90},
                        {"lhs": "self_potion_count", "cmp": ">", "rhs": 0},
                    ],
                },
            },
            {
                "priority": 2,
                "cpu_cost": 2,
                "action": "MOVE_TO_HEAL",
                "target": None,
                "conditions": {
                    "op": "AND",
                    "terms": [
                        {"lhs": "self_hp_percent", "cmp": "<", "rhs": 99},
                        {
                            "lhs": "nearest_tile_distance",
                            "lhs_param": "SPRING",
                            "cmp": ">=",
                            "rhs": 0,
                        },
                    ],
                },
            },
            {
                "priority": 3,
                "cpu_cost": 1,
                "action": "RETREAT",
                "target": "NEAREST",
                "conditions": {
                    "op": "SINGLE",
                    "terms": [
                        {"lhs": "target_distance", "lhs_param": "NEAREST", "cmp": "<=", "rhs": 99}
                    ],
                },
            },
        ],
    },
)

HOLD_PROBE = {
    "ruleset_id": "abuse_hold",
    "version": 1,
    "strategy_ko": "어뷰징 시험 — 아무것도 하지 않는다.",
    "rules": [
        {
            "priority": 1,
            "cpu_cost": 1,
            "action": "HOLD",
            "target": None,
            "conditions": {
                "op": "SINGLE",
                "terms": [{"lhs": "room_elapsed_ticks", "cmp": ">=", "rhs": 0}],
            },
        }
    ],
}

# 자폭형만 배치된 방. 적이 스스로 죽으므로 어뷰징 판정에서 따로 다룬다.
BOMBER_ROOM_ID = "blast_yard"

# 층 배치에서 어뷰징이 넘지 못해야 하는 선. 시드 200개 중 둘(40·47)이 전투 노드가
# 전부 blast_yard 인 층이라 0 이 아니다.
ABUSE_FLOOR_CEILING_PCT = 5
FLOOR_ABUSE_RUNS = 50

# 어뷰징 시험은 승패만 보면 되므로 시드를 적게 쓴다.
PROBE_RUNS = 3

# 층 1 에 나오는 방들. 어뷰징이 통하는지 보려면 회복타일이 있는 방이 반드시 들어가야 한다.
FLOOR_ONE_ROOM_IDS = (
    "open_field",
    "corridor",
    "pillars",
    "hazard_field",
    "spring_bait",
    "blast_yard",
)


def run_probe(parts, probe, room_id):
    """계측용 규칙표로 방 하나를 돌린다."""
    return run_batch(
        probe.ruleset_id,
        (parts["rooms"][room_id],),
        parts["balance"],
        parts["catalog"],
        probe,
        parts["enemy"],
        runs=PROBE_RUNS,
        base_seed=1,
    )


def test_abuse_probes_lose_every_room_but_the_bomber_room(parts):
    # 무한 카이팅도 회복 어뷰징도 이기는 길이 아니어야 한다 (G2 첫 조건).
    # 방이 유한하고 추격자가 10틱마다 붙으므로 물러나기만 하면 구석에서 끝난다.
    # blast_yard 는 예외이며 그 이유는 아래 테스트가 못박는다.
    for raw in ABUSE_PROBES:
        probe = parse_ruleset(raw)
        for room_id in FLOOR_ONE_ROOM_IDS:
            if room_id == BOMBER_ROOM_ID:
                continue
            stats = run_probe(parts, probe, room_id)
            assert stats.win_rate_pct == 0, f"{probe.ruleset_id} @ {room_id}"


def test_the_bomber_room_clears_itself(parts):
    # **알려진 구멍이다** (docs/05 §5.1). 폭탄 슬라임은 예고 뒤 자폭으로 스스로 죽고,
    # blast_yard 에는 그 둘밖에 없다. 그래서 아무것도 하지 않는 규칙표가 이 방을
    # 클리어한다 — 대가는 HP 36 뿐이다. 이 테스트는 통과가 목적이 아니라 구멍이
    # 남아 있음을 눈에 보이게 두는 것이 목적이며, 방 구성이 고쳐지면 여기서 깨진다.
    stats = run_probe(parts, parse_ruleset(HOLD_PROBE), BOMBER_ROOM_ID)
    assert stats.win_rate_pct == 100, "구멍이 막혔다면 docs/05 §5.1 을 고쳐라"


def test_abuse_probes_cannot_clear_a_floor(parts):
    # 방 하나의 구멍이 런의 구멍은 아니다. 층 하나를 도는 데 필요한 전투 노드가
    # 전부 blast_yard 인 층에서만 통하므로 층 승률이 한 자리에 머문다.
    stats = run_floor_batch(
        "abuse_hold",
        parts["templates"],
        parts["balance"],
        parts["catalog"],
        parse_ruleset(HOLD_PROBE),
        parts["enemy"],
        runs=FLOOR_ABUSE_RUNS,
        base_seed=1,
    )
    assert stats.win_rate_pct <= ABUSE_FLOOR_CEILING_PCT


def test_no_room_run_reaches_the_tick_cap(parts):
    # 틱 상한에 닿는 런이 있으면 "시간을 끌어 비긴다" 가 성립한다. 이긴 런은 60틱
    # 안쪽에서 끝나고 끌린 런은 그 전에 죽는 것이 GDD §7 이 노린 상태다.
    for ruleset_id in ("g0_kite", "g0_pressure", "g0_cover"):
        for room_id in FLOOR_ONE_ROOM_IDS:
            assert run_room_with(parts, ruleset_id, room_id, runs=3).average_ticks < TICK_CAP
