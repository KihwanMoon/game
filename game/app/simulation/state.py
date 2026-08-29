"""세계 상태 — 엔티티와 방의 현재 모습.

순회 순서를 이니셔티브 내림차순, 동률이면 entity_id 사전순으로 고정한다. 딕셔너리
삽입 순서에 기대면 스폰 순서가 바뀔 때 결과가 흔들려 리플레이가 깨진다 (R5).
"""

from dataclasses import dataclass, field

from game.app.core.rng import DeterministicRng
from game.schemas.room import RoomTemplate

FACTION_PLAYER = "player"
FACTION_ENEMY = "enemy"


@dataclass
class Entity:
    """전투에 참여하는 개체 하나 (TDD §3.1)."""

    entity_id: str
    kind_id: str
    faction: str
    position: tuple[int, int]
    hp: int
    hp_max: int
    attack: int
    defense: int
    attack_range: int
    initiative: int
    regen_base: int = 0
    cpu_budget: int = 0
    potions: int = 0
    # 누가 불러냈는가. 소환 상한을 소환사별로 세기 위해 필요하다.
    summoner_id: str | None = None
    cooldowns: dict[str, int] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        """HP 가 남아 있는가."""
        return self.hp > 0

    @property
    def hp_percent(self) -> int:
        """현재 HP 비율. 정수 퍼센트다 — 부동소수를 쓰지 않는다 (R5)."""
        return self.hp * 100 // self.hp_max


@dataclass
class WorldState:
    """한 방의 전체 상태."""

    room: RoomTemplate
    rng: DeterministicRng
    entities: dict[str, Entity] = field(default_factory=dict)
    tick: int = 0
    # 소환된 개체에 붙일 일련번호. 시간이나 난수가 아니라 단조 증가여야
    # 같은 시드가 같은 id 를 만든다 (R5).
    spawn_counter: int = 0
    tile_overrides: dict[tuple[int, int], int] = field(default_factory=dict)
    spring_pools: dict[tuple[int, int], int] = field(default_factory=dict)
    # 이번 틱에 예고를 걸어 둔 시전자들. TELEGRAPH 페이즈가 정렬해 채운다.
    # 셀렉터 CASTING 과 인지 변수 `대상이 시전 중인가` 가 이 값을 읽는다 — 예고판을
    # 엔진이 들고 있어 selectors·rule_vm 이 닿지 못하므로 세계 상태로 내린다.
    casting_ids: tuple[str, ...] = ()

    def get_tile(self, x: int, y: int) -> int:
        """좌표의 현재 타일 ID. 파괴된 벽 등 변경분을 반영한다.

        Args:
            x: 가로 좌표.
            y: 세로 좌표.

        Returns:
            타일 ID.
        """
        override = self.tile_overrides.get((x, y))
        return override if override is not None else self.room.get_tile(x, y)

    def list_actors(self) -> tuple[Entity, ...]:
        """살아 있는 엔티티를 행동 순서대로 돌려준다.

        이동 충돌은 이니셔티브로 가른다(TDD §4.2). 동률이면 entity_id 사전순이며,
        그래도 같은 경우는 없다 — id 가 유일하기 때문이다.

        Returns:
            이니셔티브 내림차순으로 정렬된 엔티티들.
        """
        alive = [entity for entity in self.entities.values() if entity.is_alive]
        return tuple(sorted(alive, key=lambda e: (-e.initiative, e.entity_id)))

    def find_entity_at(self, position: tuple[int, int]) -> Entity | None:
        """그 칸에 서 있는 살아 있는 엔티티를 찾는다.

        Args:
            position: 찾을 좌표.

        Returns:
            찾은 엔티티. 없으면 None.

        """
        for entity in self.list_actors():
            if entity.position == position:
                return entity
        return None

    def list_hostiles(self, viewer: Entity) -> tuple[Entity, ...]:
        """상대 진영의 살아 있는 엔티티들.

        Args:
            viewer: 기준 엔티티.

        Returns:
            진영이 다른 엔티티들. 순서는 list_actors 와 같다.
        """
        return tuple(e for e in self.list_actors() if e.faction != viewer.faction)
