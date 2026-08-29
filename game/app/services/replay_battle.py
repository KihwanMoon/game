"""리플레이 — 시드와 규칙표만으로 같은 전투를 다시 돌린다 (TDD §9, GDD §8.3).

저장하는 것은 **(시드 + 규칙표 + 코어 버전)** 뿐이다. 틱마다의 상태를 적지 않는 이유가
용량(수 KB)만은 아니다. 상태를 적어 두면 그것이 정본이 되어 코어의 결정론이 검증되지
않은 채로 남는다 — 시드에서 다시 돌려 같은 로그가 나오는 것 자체가 R5 의 검사다.

핵심 용례는 **사망 직전 15틱 재생**이다. 죽은 뒤에 "무엇이 나를 죽였는가"를 그 구간의
로그와 피해 히트맵으로 답한다. 되감기가 아니라 처음부터 다시 돌린 뒤 끝을 잘라 보는
것이며, 그래서 되감기 버퍼가 필요 없다.

연쇄(방 여러 개)를 그대로 담는 이유는 재현성이다. 마지막 방만 담으면 앞 방에서 인계된
HP·포션·층 압력이 빠져 같은 시드로도 같은 전투가 되지 않는다.

배속·스텝 실행은 run_stepped_battle 에 있다. 재생은 그것을 1틱 단위로 써서 틱 전후의
좌표를 함께 받아 적는다 — 그래야 피해 히트맵이 "어느 칸에서 맞았는가" 를 답한다.

**예고판과 가시성 캐시는 아직 WorldState 밖에 있다.** 지금은 방을 처음부터 다시 돌리
므로 문제가 없지만, 중간 상태에서 이어 붙이는 저장이 생기면 그 둘을 함께 담아야 한다.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from game.app.core.event_log import EventLog, LogEntry
from game.app.services.analyze_battle import DamageHit, extract_damage_hits
from game.app.services.run_battle import BattleResult
from game.app.services.run_chain import run_room_chain
from game.app.services.run_stepped_battle import run_tick_batch
from game.app.simulation.engine import TickEngine
from game.app.simulation.phases import OUTCOME_ONGOING
from game.app.simulation.state import WorldState
from game.config import DEFAULT_MAX_TICKS
from game.schemas.blocks import BlockCatalog
from game.schemas.meta_save import build_ruleset_payload
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet, parse_ruleset

# 리플레이 파일의 형식 세대. 본문을 읽기 전에 이것부터 본다 (TDD §9).
REPLAY_FORMAT_VERSION = 1

# 시뮬레이션 코어의 세대. **틱의 의미가 바뀌면 올린다** — 페이즈 순서, 피해 공식,
# 난수 소비 지점처럼 같은 시드가 다른 결과를 내게 하는 변경이다. 값이 다른 리플레이는
# 재생하지 않고 "구버전" 으로 표시한다. 재생해서 다른 결과를 보여 주는 것이
# 재생하지 않는 것보다 나쁘다.
CORE_VERSION = 1

# GDD §8.3 — 사망 직전 이 만큼을 되돌려 본다.
DEATH_REPLAY_TICKS = 15


@dataclass(frozen=True)
class ReplayRecord:
    """리플레이 한 건. 이것만으로 전투가 완전히 재현된다."""

    seed: int
    room_ids: tuple[str, ...]
    ruleset: RuleSet | None = None
    max_ticks: int = DEFAULT_MAX_TICKS
    core_version: int = CORE_VERSION
    format_version: int = REPLAY_FORMAT_VERSION


@dataclass(frozen=True)
class RoomPlayback:
    """방 하나를 재생한 결과. 로그와 피격 좌표를 함께 든다."""

    room_id: str
    outcome: str
    ticks: int
    width: int
    height: int
    entries: tuple[LogEntry, ...]
    hits: tuple[DamageHit, ...]


@dataclass(frozen=True)
class ReplayPlayback:
    """리플레이 한 건을 끝까지 재생한 결과."""

    outcome: str
    total_ticks: int
    player_hp: int
    cleared_rooms: int
    rooms: tuple[RoomPlayback, ...]

    @property
    def last_room(self) -> RoomPlayback:
        """마지막으로 들어간 방. 사망 리플레이가 보는 곳이다."""
        return self.rooms[-1]


def is_current_core(record: ReplayRecord) -> bool:
    """이 코어가 그대로 재생할 수 있는 리플레이인가.

    Args:
        record: 확인할 리플레이.

    Returns:
        형식·코어 세대가 모두 현재 것이면 True.
    """
    return record.format_version == REPLAY_FORMAT_VERSION and record.core_version == CORE_VERSION


def build_replay_record(
    seed: int,
    room_ids: tuple[str, ...],
    ruleset: RuleSet | None = None,
    max_ticks: int = DEFAULT_MAX_TICKS,
) -> ReplayRecord:
    """이번 런을 재현할 리플레이를 만든다.

    Args:
        seed: 런 시드.
        room_ids: 순서대로 돈 방 id 들.
        ruleset: 플레이어 규칙표. None 이면 폴백 정책으로 돈 런이다.
        max_ticks: 방 하나의 틱 상한. 이것이 다르면 같은 시드라도 결과가 갈린다.

    Returns:
        현재 코어 세대가 찍힌 리플레이.
    """
    return ReplayRecord(seed=seed, room_ids=room_ids, ruleset=ruleset, max_ticks=max_ticks)


def build_replay_payload(record: ReplayRecord) -> dict:
    """리플레이를 JSON 으로 찍을 수 있는 모양으로 만든다.

    Args:
        record: 저장할 리플레이.

    Returns:
        직렬화 가능한 딕셔너리.
    """
    return {
        "format_version": record.format_version,
        "core_version": record.core_version,
        "seed": record.seed,
        "room_ids": list(record.room_ids),
        "max_ticks": record.max_ticks,
        "ruleset": None if record.ruleset is None else build_ruleset_payload(record.ruleset),
    }


def parse_replay(raw: dict) -> ReplayRecord:
    """딕셔너리에서 리플레이를 읽는다.

    세대가 달라도 읽기는 한다. 읽지 못하면 "구버전" 배지조차 붙일 수 없기 때문이다
    (TDD §9). 재생 가능 여부는 is_current_core 가 판정한다.

    Args:
        raw: build_replay_payload 가 만든 딕셔너리.

    Returns:
        읽어들인 리플레이.
    """
    ruleset = raw.get("ruleset")
    return ReplayRecord(
        seed=raw["seed"],
        room_ids=tuple(raw["room_ids"]),
        ruleset=None if ruleset is None else parse_ruleset(ruleset),
        max_ticks=raw.get("max_ticks", DEFAULT_MAX_TICKS),
        core_version=raw.get("core_version", CORE_VERSION),
        format_version=raw.get("format_version", REPLAY_FORMAT_VERSION),
    )


def save_replay(record: ReplayRecord, target_path: Path) -> None:
    """리플레이를 파일로 쓴다.

    키를 정렬해 찍는다. 같은 런이 실행마다 다른 파일이 되면 파일 비교로 같은 런인지
    볼 수 없다 (R5).

    Args:
        record: 저장할 리플레이.
        target_path: 쓸 경로. 없는 상위 디렉터리는 만든다.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(build_replay_payload(record), ensure_ascii=False, sort_keys=True)
    target_path.write_text(payload + "\n", encoding="utf-8")


def load_replay(source_path: Path) -> ReplayRecord:
    """리플레이 파일을 읽는다.

    Args:
        source_path: 읽을 경로.

    Returns:
        읽어들인 리플레이.
    """
    return parse_replay(json.loads(source_path.read_text(encoding="utf-8")))


def read_positions(state: WorldState) -> dict[str, tuple[int, int]]:
    """모든 엔티티의 현재 좌표를 읽는다.

    죽은 개체도 담는다. 죽인 그 한 방이 어느 칸에서 났는지가 히트맵에서 가장 중요한
    한 칸이며, 살아 있는 것만 담으면 그 칸이 빠진다.

    Args:
        state: 세계 상태.

    Returns:
        entity_id 에서 좌표로의 대응표. 조회용이며 순회 대상이 아니다.
    """
    return {entity_id: state.entities[entity_id].position for entity_id in sorted(state.entities)}


@dataclass
class BattleRecorder:
    """방을 한 틱씩 끊어 돌며 로그와 피격 좌표를 함께 받아 적는다.

    좌표가 로그에 없어서 필요한 것이다. 피해 히트맵은 "어느 칸에서 맞았는가" 를
    묻는데 로그는 "누가 얼마를 맞았는가" 까지만 남기므로, 틱 전후의 좌표를 그때
    같이 읽어 두지 않으면 나중에 복원할 수 없다.
    """

    rooms: list[RoomPlayback] = field(default_factory=list)

    def run_room(self, engine: TickEngine) -> BattleResult:
        """방 하나를 끝까지 돌린다. run_room_chain 이 이것을 부른다.

        Args:
            engine: 조립된 엔진.

        Returns:
            run_battle 과 같은 결과. 연쇄가 이 값으로 HP 를 인계한다.
        """
        hits: list[DamageHit] = []
        outcome = OUTCOME_ONGOING
        while outcome == OUTCOME_ONGOING:
            start_positions = read_positions(engine.state)
            batch = run_tick_batch(engine, 1)
            outcome = batch.outcome
            hits.extend(
                extract_damage_hits(batch.entries, start_positions, read_positions(engine.state))
            )
        room = engine.state.room
        self.rooms.append(
            RoomPlayback(
                room_id=room.template_id,
                outcome=outcome,
                ticks=engine.state.tick,
                width=room.width,
                height=room.height,
                entries=tuple(engine.log.entries),
                hits=tuple(hits),
            )
        )
        return BattleResult(
            outcome=outcome,
            ticks=engine.state.tick,
            player_hp=engine.state.entities["player"].hp,
            log_lines=engine.log.format_lines(),
        )


def run_replay(
    record: ReplayRecord,
    templates: dict[str, RoomTemplate],
    balance: dict,
    catalog: BlockCatalog,
    enemy_rulesets: dict[str, RuleSet],
) -> ReplayPlayback:
    """리플레이를 처음부터 다시 돌린다.

    연쇄 진행은 run_room_chain 이 그대로 맡고, 이 함수는 방마다의 관찰자만 끼운다.
    여기서 진행 규칙을 다시 구현하면 원본과 재생이 갈려 재현이 아니게 된다.

    Args:
        record: 재생할 리플레이.
        templates: template_id 에서 룸 템플릿으로의 대응표.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        enemy_rulesets: 적 규칙표들.

    Returns:
        방별 로그와 피격 좌표까지 담은 재생 결과.

    Raises:
        ValueError: 이 코어가 재생할 수 없는 세대인 경우.
        KeyError: 리플레이가 가리키는 방 id 가 templates 에 없는 경우.
    """
    if not is_current_core(record):
        raise ValueError(
            f"이 코어가 재생할 수 없는 리플레이다: "
            f"형식 v{record.format_version} / 코어 v{record.core_version}"
        )
    recorder = BattleRecorder()
    chain = run_room_chain(
        tuple(templates[room_id] for room_id in record.room_ids),
        balance,
        catalog,
        record.ruleset,
        enemy_rulesets,
        seed=record.seed,
        max_ticks=record.max_ticks,
        run_room=recorder.run_room,
    )
    return ReplayPlayback(
        outcome=chain.outcome,
        total_ticks=chain.total_ticks,
        player_hp=chain.player_hp,
        cleared_rooms=chain.cleared_rooms,
        rooms=tuple(recorder.rooms),
    )


def filter_recent_entries(
    entries: tuple[LogEntry, ...], ticks: int = DEATH_REPLAY_TICKS
) -> tuple[LogEntry, ...]:
    """마지막 몇 틱의 로그만 남긴다 (GDD §8.3 사망 리플레이).

    Args:
        entries: 방 하나의 전체 로그.
        ticks: 남길 틱 수. 0 이하면 아무것도 남기지 않는다.

    Returns:
        마지막 틱에서 ticks 만큼 거슬러 올라간 구간의 로그. 순서는 원본 그대로다.
    """
    if not entries or ticks <= 0:
        return ()
    last_tick = max(entry.tick for entry in entries)
    first_tick = last_tick - ticks + 1
    return tuple(entry for entry in entries if entry.tick >= first_tick)


def format_playback_lines(entries: tuple[LogEntry, ...]) -> tuple[str, ...]:
    """재생 로그를 터미널 출력용 문자열로 편다.

    펴는 방식은 EventLog 가 정본이다. 여기서 다시 짜면 화면 두 곳의 로그 모양이
    갈려, 같은 사건을 두 표기로 보게 된다.

    Args:
        entries: 출력할 로그.

    Returns:
        format_lines 와 같은 형식의 줄들.
    """
    return EventLog(entries=list(entries)).format_lines()
