"""어뷰징 차단 — 시간을 끄는 쪽에 압력을 되돌린다 (GDD §7, 로드맵 W7).

v1 수식의 최적해는 "회복 타일 위 무한 대기 → 풀피로 처치" 였다. 실측(docs/05)에서도
`door_hold`·`spring_camp` 처럼 시간을 끄는 규칙표가 상위를 차지한다. 시간이 공짜인 한
그 전략은 언제나 옳으므로 여기서 **시간에 값을 매긴다** — 추격자·층 스케일·샘 잔여량.

수치의 정본은 balance.json 의 anti_abuse 절이다 (TDD §2). 이 모듈의 DEFAULT_* 는 그
절이 통째로 빠졌을 때의 안전망이며, 값을 바꿀 자리가 아니다.

전부 정수 연산이다. 퍼센트는 내림 나눗셈으로 접는다 — 부동소수는 플랫폼마다 결과가
갈려 리플레이를 깨뜨린다 (R5).
"""

from dataclasses import dataclass, field

from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.phases import PHASE_RESOLVE, PHASE_UPKEEP
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.schemas.room import TILE_DOOR, TILE_FLOOR, TILE_SPRING, WALKABLE_TILES

DEFAULT_HUNTER_SPAWN_TICK = 40
DEFAULT_HUNTER_INTERVAL_TICKS = 20
DEFAULT_HUNTER_ENTITY = "goblin_rusher"
DEFAULT_FLOOR_ATTACK_PCT = 1
DEFAULT_COMBAT_REGEN_PCT = 50
DEFAULT_SPRING_POOL = 30

# "+1%/10틱" 의 10틱. 이 단위 미만의 체류는 내림으로 버린다.
FLOOR_SCALE_TICK_UNIT = 10

PERCENT_BASE = 100

# 문이 막혔을 때 물러설 최소 거리. 플레이어 옆에 꽂히면 즉사 장치가 된다.
MIN_SPAWN_DISTANCE = 3

# 추격자임을 표시하는 플래그. 규칙표가 쓰는 FLAG_A~D 와 겹치지 않는다.
HUNTER_FLAG = "HUNTER"

# 특정 개체가 아니라 방 자체가 낸 이벤트의 주체.
WORLD_ENTITY_ID = "world"


@dataclass(frozen=True)
class PressureRules:
    """balance.json 의 anti_abuse 절을 그대로 담는 값."""

    hunter_spawn_tick: int = DEFAULT_HUNTER_SPAWN_TICK
    hunter_interval_ticks: int = DEFAULT_HUNTER_INTERVAL_TICKS
    hunter_entity: str = DEFAULT_HUNTER_ENTITY
    floor_attack_pct_per_10_ticks: int = DEFAULT_FLOOR_ATTACK_PCT
    combat_regen_pct: int = DEFAULT_COMBAT_REGEN_PCT
    spring_pool_default: int = DEFAULT_SPRING_POOL


def build_pressure_rules(anti_abuse: dict) -> PressureRules:
    """anti_abuse 절을 규칙 값으로 옮긴다.

    Args:
        anti_abuse: balance.json 의 anti_abuse 딕셔너리.

    Returns:
        읽어들인 규칙. 빠진 항목은 기본값으로 채운다.

    Raises:
        ValueError: 추격자 주기가 1틱 미만인 경우. 0 이면 한 틱에 무한히 스폰한다.
    """
    interval = int(anti_abuse.get("hunter_interval_ticks", DEFAULT_HUNTER_INTERVAL_TICKS))
    if interval < 1:
        raise ValueError(f"hunter_interval_ticks 는 1 이상이어야 한다: {interval}")
    return PressureRules(
        hunter_spawn_tick=int(anti_abuse.get("hunter_spawn_tick", DEFAULT_HUNTER_SPAWN_TICK)),
        hunter_interval_ticks=interval,
        hunter_entity=str(anti_abuse.get("hunter_entity", DEFAULT_HUNTER_ENTITY)),
        floor_attack_pct_per_10_ticks=int(
            anti_abuse.get("floor_attack_pct_per_10_ticks", DEFAULT_FLOOR_ATTACK_PCT)
        ),
        combat_regen_pct=int(anti_abuse.get("combat_regen_pct", DEFAULT_COMBAT_REGEN_PCT)),
        spring_pool_default=int(anti_abuse.get("spring_pool_default", DEFAULT_SPRING_POOL)),
    )


def _record_event(log: EventLog, tick: int, expr: str, outcome: str, phase: str) -> None:
    """압력 이벤트 한 줄을 남긴다. expr 에는 실측값을 병기한다 (GDD §8.2)."""
    log.record(
        LogEntry(
            tick=tick,
            entity_id=WORLD_ENTITY_ID,
            phase=phase,
            expr=expr,
            outcome=outcome,
            fired=True,
        )
    )


def list_tiles_of_kind(state: WorldState, tile_id: int) -> tuple[tuple[int, int], ...]:
    """방에서 그 종류의 타일 좌표를 훑는다.

    Args:
        state: 세계 상태.
        tile_id: 찾을 타일 ID.

    Returns:
        y, x 순서로 훑은 좌표들. 순서가 고정이라 같은 방이면 같은 결과다 (R5).
    """
    return tuple(
        (x, y)
        for y in range(state.room.height)
        for x in range(state.room.width)
        if state.get_tile(x, y) == tile_id
    )


def init_spring_pools(state: WorldState, pool_size: int = DEFAULT_SPRING_POOL) -> int:
    """방의 생명의 샘마다 총 회복량을 채운다.

    **엔진 조립 직후 반드시 한 번 불러야 한다.** 채우지 않으면 잔여량이 늘 0 이라
    샘은 회복을 한 점도 못 낸 채 첫 RESOLVE 에서 소멸한다 — 차단이 아니라 고장이다.
    이미 값이 있는 좌표는 건드리지 않는다.

    Args:
        state: 세계 상태.
        pool_size: 샘 하나가 낼 총 회복량.

    Returns:
        새로 채운 샘의 수.
    """
    filled = 0
    for position in list_tiles_of_kind(state, TILE_SPRING):
        if position in state.spring_pools:
            continue
        state.spring_pools[position] = pool_size
        filled += 1
    return filled


def apply_spring_drain(state: WorldState, position: tuple[int, int], amount: int) -> int:
    """샘에서 회복량을 꺼내고 잔여량을 그만큼 깎는다.

    Args:
        state: 세계 상태.
        position: 샘 좌표.
        amount: 꺼내려는 양.

    Returns:
        실제로 꺼낸 양. 잔여량이 모자라면 남은 만큼만, 다 썼으면 0 이다.
    """
    pool = state.spring_pools.get(position, 0)
    drawn = max(0, min(amount, pool))
    if drawn > 0:
        state.spring_pools[position] = pool - drawn
    return drawn


def remove_drained_springs(
    state: WorldState, log: EventLog | None = None
) -> tuple[tuple[int, int], ...]:
    """잔여량이 바닥난 샘을 바닥 타일로 지운다 (페이즈 6 RESOLVE).

    Args:
        state: 세계 상태.
        log: 이벤트 로그. None 이면 남기지 않는다.

    Returns:
        이번에 소멸한 샘의 좌표들. 방 좌표 순서를 지킨다.
    """
    drained = tuple(
        position
        for position in list_tiles_of_kind(state, TILE_SPRING)
        if state.spring_pools.get(position, 0) <= 0
    )
    for position in drained:
        state.tile_overrides[position] = TILE_FLOOR
        if log is not None:
            _record_event(log, state.tick, f"샘 잔여량(0) {position}", "샘 소멸", PHASE_RESOLVE)
    return drained


def calculate_floor_bonus_pct(floor_ticks: int, pct_per_unit: int) -> int:
    """층 체류 틱이 만드는 적 공격력 보너스 퍼센트.

    Args:
        floor_ticks: 이 층에서 보낸 틱 수.
        pct_per_unit: FLOOR_SCALE_TICK_UNIT 틱마다 얹을 퍼센트.

    Returns:
        보너스 퍼센트. 단위 미만은 내림으로 버린다.
    """
    return max(0, floor_ticks) // FLOOR_SCALE_TICK_UNIT * pct_per_unit


def calculate_scaled_attack(base_attack: int, bonus_pct: int) -> int:
    """보너스 퍼센트를 얹은 공격력.

    Args:
        base_attack: 스케일 전 공격력.
        bonus_pct: 얹을 퍼센트.

    Returns:
        내림 정수로 접은 공격력.
    """
    return base_attack * (PERCENT_BASE + bonus_pct) // PERCENT_BASE


def list_hunter_spawns(state: WorldState) -> tuple[tuple[int, int], ...]:
    """추격자가 들어설 수 있는 칸을 우선순위대로 모은다.

    문이 1순위다. 방 밖에서 쫓아온 것이 벽 안쪽에 솟으면 대비할 방법이 없다.
    문이 막혔을 때만 플레이어에게서 떨어진 빈 칸으로 물러난다.

    Args:
        state: 세계 상태.

    Returns:
        후보 좌표들. 방 좌표 순서라 같은 상황이면 같은 순서다 (R5). 없으면 빈 튜플.
    """
    occupied = frozenset(actor.position for actor in state.list_actors())
    doors = tuple(pos for pos in list_tiles_of_kind(state, TILE_DOOR) if pos not in occupied)
    if doors:
        return doors

    free = tuple(
        (x, y)
        for y in range(state.room.height)
        for x in range(state.room.width)
        if state.get_tile(x, y) in WALKABLE_TILES and (x, y) not in occupied
    )
    players = tuple(a for a in state.list_actors() if a.faction == FACTION_PLAYER)
    far = tuple(
        pos
        for pos in free
        if all(get_manhattan_distance(pos, p.position) >= MIN_SPAWN_DISTANCE for p in players)
    )
    return far or free


@dataclass
class PressureTracker:
    """방·층 체류 틱을 세고 그만큼의 압력을 되돌린다.

    엔진이 아니라 이쪽이 체류 틱을 센다. 방을 옮겨도 층 체류는 이어져야 하는데
    (GDD §7 층 지연) 엔진은 방 하나의 수명만 살기 때문이다.
    """

    rules: PressureRules = field(default_factory=PressureRules)
    # kind_id -> balance.json 의 적 스탯. 추격자를 만들 때만 읽는다.
    enemy_stats: dict[str, dict] = field(default_factory=dict)
    room_ticks: int = 0
    floor_ticks: int = 0  # 방을 옮겨도 이어진다 (GDD §7 층 지연).
    hunter_count: int = 0
    # 스케일 전 공격력. 매 틱 현재값에 곱하면 복리가 되어 수십 틱 만에 발산한다.
    base_attacks: dict[str, int] = field(default_factory=dict)
    applied_pct: int = 0  # 로그를 값이 바뀐 틱에만 남기려고 든다.

    def add_tick(self) -> None:
        """방·층 체류 틱을 1 올린다."""
        self.room_ticks += 1
        self.floor_ticks += 1

    def reset_room(self) -> None:
        """새 방에 들어설 때의 초기화. 층 체류 틱은 남는다.

        기준 공격력을 함께 지운다. 어느 방에나 goblin_rusher_0 이 있으므로
        남겨 두면 다른 개체의 값을 그 id 로 읽는다.
        """
        self.room_ticks = 0
        self.hunter_count = 0
        self.applied_pct = 0
        self.base_attacks.clear()

    def reset_floor(self) -> None:
        """새 층에 내려설 때의 초기화. 층 체류 틱까지 지운다."""
        self.floor_ticks = 0
        self.reset_room()

    def is_hunter_due(self) -> bool:
        """이번 틱이 추격자를 낼 틱인가.

        Returns:
            체류가 hunter_spawn_tick 을 넘긴 첫 틱과, 그 뒤 주기마다 True.
        """
        elapsed = self.room_ticks - self.rules.hunter_spawn_tick
        if elapsed <= 0:
            return False
        return (elapsed - 1) % self.rules.hunter_interval_ticks == 0

    def get_bonus_pct(self) -> int:
        """지금 적 공격력에 얹히는 보너스 퍼센트.

        Returns:
            층 체류 틱에서 계산한 퍼센트.
        """
        return calculate_floor_bonus_pct(self.floor_ticks, self.rules.floor_attack_pct_per_10_ticks)

    def apply_scale(self, state: WorldState, log: EventLog | None = None) -> int:
        """층 체류 시간만큼 적 공격력을 올린다.

        플레이어는 대상이 아니다. 양쪽이 함께 오르면 상대 압력이 0 이 된다.

        Args:
            state: 세계 상태.
            log: 이벤트 로그. None 이면 남기지 않는다.

        Returns:
            이번에 적용한 보너스 퍼센트.
        """
        bonus_pct = self.get_bonus_pct()
        for actor in state.list_actors():
            if actor.faction == FACTION_PLAYER:
                continue
            base = self.base_attacks.setdefault(actor.entity_id, actor.attack)
            actor.attack = calculate_scaled_attack(base, bonus_pct)
        if log is not None and bonus_pct != self.applied_pct:
            _record_event(
                log,
                state.tick,
                f"층 체류({self.floor_ticks}) / 단위({FLOOR_SCALE_TICK_UNIT})",
                f"적 공격력 +{bonus_pct}%",
                PHASE_UPKEEP,
            )
        self.applied_pct = bonus_pct
        return bonus_pct

    def create_hunter(self, state: WorldState, log: EventLog | None = None) -> Entity | None:
        """추격자 하나를 방에 들인다.

        스폰 위치는 후보 목록에서 WorldState.rng 로 고른다. 방 좌표 순서로 모은
        목록이라 같은 시드가 같은 자리를 낸다 (R5).

        Args:
            state: 세계 상태.
            log: 이벤트 로그. None 이면 남기지 않는다.

        Returns:
            등장한 추격자. 스탯이 없거나 설 자리가 없으면 None.
        """
        stats = self.enemy_stats.get(self.rules.hunter_entity)
        expr = f"방 체류({self.room_ticks}) > 한계({self.rules.hunter_spawn_tick})"
        if stats is None:
            if log is not None:
                _record_event(log, state.tick, expr, "추격자 스탯 없음", PHASE_UPKEEP)
            return None
        spawns = list_hunter_spawns(state)
        if not spawns:
            if log is not None:
                _record_event(log, state.tick, expr, "빈 칸 없음 — 등장 실패", PHASE_UPKEEP)
            return None

        position = state.rng.get_choice(spawns)
        # 소환물과 같은 일련번호를 쓴다. id 가 겹치면 한쪽이 조용히 덮인다.
        state.spawn_counter += 1
        self.hunter_count += 1
        hunter = Entity(
            entity_id=f"{self.rules.hunter_entity}_h{state.spawn_counter}",
            kind_id=self.rules.hunter_entity,
            faction=FACTION_ENEMY,
            position=position,
            hp=stats["hp_max"],
            hp_max=stats["hp_max"],
            attack=stats["attack"],
            defense=stats["defense"],
            attack_range=stats["attack_range"],
            initiative=stats["initiative"],
            regen_base=stats.get("regen_base", 0),
            cpu_budget=stats.get("cpu_budget", 0),
            flags={HUNTER_FLAG: True},
        )
        state.entities[hunter.entity_id] = hunter
        if log is not None:
            _record_event(
                log,
                state.tick,
                expr,
                f"추격자 {hunter.entity_id} 등장 {position}",
                PHASE_UPKEEP,
            )
        return hunter

    def run_upkeep(self, state: WorldState, log: EventLog | None = None) -> tuple[Entity, ...]:
        """체류 틱을 올리고 이번 틱의 압력을 적용한다 (페이즈 1 UPKEEP).

        추격자를 먼저 들이고 스케일을 나중에 건다. 반대로 하면 갓 등장한 추격자만
        그 틱의 보너스를 놓친다.

        Args:
            state: 세계 상태.
            log: 이벤트 로그. None 이면 남기지 않는다.

        Returns:
            이번 틱에 등장한 추격자들. 없으면 빈 튜플.
        """
        self.add_tick()
        hunters: list[Entity] = []
        if self.is_hunter_due():
            hunter = self.create_hunter(state, log)
            if hunter is not None:
                hunters.append(hunter)
        self.apply_scale(state, log)
        return tuple(hunters)
