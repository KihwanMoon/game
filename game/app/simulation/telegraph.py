"""텔레그래프(예고 공격) — TELEGRAPH 페이즈의 카운트다운과 발동 (GDD §4.2, TDD §4.1).

보스·정예는 피격 예정 타일을 N틱 전에 표시하고, 그 사이에 비켜서면 피해가 없다.
관전의 지루함을 푸는 장치이면서(로드맵 R3) `위험 예고 타일 위에 있는가` 조건이
성립하는 근거다 — 예고가 없으면 그 인지 변수는 영원히 거짓이고, 회피 규칙은
플레이어가 아무리 잘 짜도 발동하지 않는 죽은 코드가 된다.

**등록됐다고 곧바로 보이지는 않는다.** 남은 틱이 그 예고의 인지 폭 안에 들어와야
인지 변수가 참이 된다. 폭을 넓히는 것이 GDD §6.2 의 예측 회로이고, 조회 함수가 받는
foresight_ticks 가 그 자리다.

폭을 예고마다 두는 것은 §4.2 와 §6.2 의 충돌을 푸는 자리다. §4.2 는 "N틱 전에 표시"를
요구하는데 그대로 하면 예고가 처음부터 끝까지 보여 "1틱 더 일찍"이 더할 것이 없어진다.
그래서 전 구간을 붉히려는 예고는 visible_ticks 에 lead_ticks 를 그대로 넘기고,
예측 회로에 값을 주려는 예고는 그보다 좁게 잡는다.

피해는 방어력 감쇠를 거치지 않는 고정값이다. 예고의 유일한 정답이 회피여야
`위험 예고 타일 위에 있는가` 가 전술이 된다 — 맞고 버티는 선택지가 성립하면
그 조건은 다시 무의미해지고 텔레그래프는 연출로 전락한다.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.phases import PHASE_TELEGRAPH
from game.app.simulation.state import Entity, WorldState

# GDD §5 자폭형 — 접근 후 2틱 예고 뒤 폭발.
DEFAULT_LEAD_TICKS = 2

# 등록과 동시에 터지는 예고는 회피할 틈이 없어 예고가 아니다.
MIN_LEAD_TICKS = 1

# 기본 인지 폭. 남은 틱이 이 값 이하일 때만 인지 변수가 참이 된다.
VISIBLE_TICKS = 1

# GDD §6.2 예측 회로가 주는 보너스. 인지 폭을 이만큼 넓힌다.
PREDICTOR_BONUS_TICKS = 1

# 예측 회로 보유 여부를 담는 플래그 이름. 규칙표가 쓰는 A~D 와 겹치지 않는다.
FORESIGHT_FLAG = "FORESIGHT"

# 이 이하로 남으면 경고를 danger 로 올린다 (design/README.md ThreatNotice).
IMMINENT_TICKS = 1

TONE_DANGER = "danger"
TONE_NEUTRAL = "neutral"

# 색은 정보의 유일한 채널이 될 수 없다 — 글리프를 함께 낸다 (design/README.md).
# 이모지를 쓰지 않는 것도 같은 문서의 규칙이다.
GLYPH_IMMINENT = "▲"
GLYPH_PENDING = "△"


@dataclass(frozen=True)
class ThreatNotice:
    """UI 의 ThreatNotice 가 그대로 받는 값 (design/README.md 컴포넌트 계약).

    LogEntry 가 LogRow 에 대응하듯 이것은 경고 배너에 대응한다. 코어가 남은 틱을
    내지 않으면 UI 는 `3틱 후 피격` 을 그릴 수 없다.
    """

    text: str
    ticks: int
    glyph: str
    tone: str


@dataclass
class Telegraph:
    """예고 한 건. 남은 틱이 0 이 되는 틱에 발동한다."""

    telegraph_id: str
    caster_id: str
    skill_id: str
    # 정렬된 좌표다. 집합으로 들고 있으면 발동 로그의 순서가 흔들린다 (R5).
    tiles: tuple[tuple[int, int], ...]
    remaining_ticks: int
    damage: int
    # 남은 틱이 이 값 이하일 때부터 인지 변수에 잡힌다. lead_ticks 와 같게 두면
    # 등록 순간부터 전 구간이 보인다 (GDD §4.2 의 "N틱 전에 표시").
    visible_ticks: int = VISIBLE_TICKS
    # 시전자를 먼저 죽이는 것이 예고에 대한 또 하나의 답이다. 보스의 확정
    # 광역기처럼 그 답을 막아야 하는 예고만 False 로 등록한다.
    cancel_on_death: bool = True

    def has_tile(self, position: tuple[int, int]) -> bool:
        """그 좌표가 피격 예정 타일인가.

        Args:
            position: 확인할 좌표.

        Returns:
            피격 예정이면 True.
        """
        return position in self.tiles

    def is_visible_within(self, foresight_ticks: int) -> bool:
        """지금 인지 가능한가.

        Args:
            foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

        Returns:
            남은 틱이 인지 폭 안이면 True.
        """
        return self.remaining_ticks <= self.visible_ticks + foresight_ticks


def get_foresight_ticks(entity: Entity) -> int:
    """그 엔티티의 예고 인지 보너스 틱 (GDD §6.2 예측 회로).

    아이템 모듈 접사는 아직 없다. 지금은 플래그 하나로 켜고 끄되 조회 지점을
    여기 하나로 모아 둔다 — 흩어 놓으면 모듈 시스템이 붙을 때 전부 찾아야 한다.

    Args:
        entity: 기준 엔티티.

    Returns:
        인지 폭에 더할 틱 수. 예측 회로가 없으면 0.
    """
    return PREDICTOR_BONUS_TICKS if entity.flags.get(FORESIGHT_FLAG, False) else 0


def build_blast_tiles(center: tuple[int, int], radius: int) -> tuple[tuple[int, int], ...]:
    """중심에서 맨해튼 반경 안의 좌표를 모은다.

    거리는 이동과 같은 맨해튼이다 (F-5 결정). 체비셰프로 재면 대각으로 한 칸
    물러난 자리가 안전해 보이는데 실제로는 두 칸이라 회피 판단이 어긋난다.

    Args:
        center: 중심 좌표.
        radius: 맨해튼 반경. 0 이면 중심 한 칸이다.

    Returns:
        정렬된 좌표들. 벽·방 밖은 거르지 않는다 — 무엇을 표시할지는 호출자가 정한다.
    """
    x0, y0 = center
    return tuple(
        sorted(
            (x, y)
            for y in range(y0 - radius, y0 + radius + 1)
            for x in range(x0 - radius, x0 + radius + 1)
            if get_manhattan_distance(center, (x, y)) <= radius
        )
    )


@dataclass
class TelegraphBoard:
    """진행 중인 예고들. 등록 순서를 유지한다.

    집합·딕셔너리에 담으면 같은 틱에 여러 예고가 터질 때 피해 순서가 흔들려
    같은 시드가 다른 결과를 낸다 (R5). 그래서 리스트다.
    """

    pending: list[Telegraph] = field(default_factory=list)
    # 예고 id 의 일련번호. 시간이나 난수가 아니라 단조 증가여야 같은 시드가
    # 같은 id 를 만든다 (R5). WorldState.spawn_counter 와 같은 이유다.
    issued_count: int = 0

    def register(
        self,
        caster_id: str,
        skill_id: str,
        tiles: Sequence[tuple[int, int]],
        damage: int,
        lead_ticks: int = DEFAULT_LEAD_TICKS,
        *,
        visible_ticks: int = VISIBLE_TICKS,
        cancel_on_death: bool = True,
    ) -> Telegraph:
        """예고를 등록한다. 이 틱에는 터지지 않는다.

        Args:
            caster_id: 시전자 id.
            skill_id: 예고를 낸 스킬 id.
            tiles: 피격 예정 좌표들. 중복은 합치고 정렬해 보관한다.
            damage: 발동 시 피해량. 방어력 감쇠를 받지 않는다.
            lead_ticks: 발동까지 남은 틱. MIN_LEAD_TICKS 아래로는 내려가지 않는다.
            visible_ticks: 인지 폭. lead_ticks 를 넘기면 전 구간이 보인다.
            cancel_on_death: 시전자가 죽으면 취소할 것인가.

        Returns:
            등록된 예고.
        """
        self.issued_count += 1
        telegraph = Telegraph(
            telegraph_id=f"{caster_id}#{skill_id}#{self.issued_count}",
            caster_id=caster_id,
            skill_id=skill_id,
            tiles=tuple(sorted(set(tiles))),
            remaining_ticks=max(MIN_LEAD_TICKS, lead_ticks),
            damage=damage,
            visible_ticks=visible_ticks,
            cancel_on_death=cancel_on_death,
        )
        self.pending.append(telegraph)
        return telegraph

    def run_countdown(self, state: WorldState, log: EventLog) -> tuple[Telegraph, ...]:
        """모든 예고를 1틱 진행하고 만기된 것을 터뜨린다 (페이즈 2).

        이 페이즈는 PERCEPTION 보다 앞이다. 그래서 카운트다운이 끝난 값을 그 틱의
        인지 변수가 읽고, 규칙표는 남은 틱을 보고 회피를 결정할 수 있다.

        Args:
            state: 세계 상태.
            log: 이벤트 로그.

        Returns:
            이번 틱에 발동한 예고들. 등록 순서를 유지한다.
        """
        survivors: list[Telegraph] = []
        fired: list[Telegraph] = []
        for telegraph in self.pending:
            if telegraph.cancel_on_death and not self._is_caster_alive(state, telegraph):
                expr = f"{telegraph.skill_id} 예고 취소"
                self._record(state, log, telegraph, expr, "시전자 사망", None)
                continue
            telegraph.remaining_ticks -= 1
            if telegraph.remaining_ticks > 0:
                survivors.append(telegraph)
                continue
            self._apply_blast(state, log, telegraph)
            fired.append(telegraph)
        self.pending = survivors
        return tuple(fired)

    def list_active(self) -> tuple[Telegraph, ...]:
        """진행 중인 예고들.

        Returns:
            등록 순서대로의 예고들.
        """
        return tuple(self.pending)

    def list_marked(self, *, foresight_ticks: int = 0) -> tuple[tuple[int, int], ...]:
        """지금 붉게 표시되는 타일 전부 (GDD §4.2).

        Args:
            foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

        Returns:
            정렬된 좌표들. 겹친 예고는 한 번만 센다.
        """
        marked = {
            tile
            for telegraph in self.pending
            if telegraph.is_visible_within(foresight_ticks)
            for tile in telegraph.tiles
        }
        return tuple(sorted(marked))

    def get_remaining(self, position: tuple[int, int], *, foresight_ticks: int = 0) -> int | None:
        """그 칸에 걸린 예고 중 가장 급한 것의 남은 틱 (ThreatNotice.ticks).

        Args:
            position: 확인할 좌표.
            foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

        Returns:
            남은 틱. 인지 가능한 예고가 없으면 None — 0 으로 채우면
            "위험 없음"과 "이번 틱에 터짐"이 구분되지 않는다.
        """
        remaining = [
            telegraph.remaining_ticks
            for telegraph in self.pending
            if telegraph.has_tile(position) and telegraph.is_visible_within(foresight_ticks)
        ]
        return min(remaining) if remaining else None

    def is_marked(self, position: tuple[int, int], *, foresight_ticks: int = 0) -> bool:
        """그 칸이 인지 가능한 예고 아래에 있는가 (self_on_hazard_telegraph).

        Args:
            position: 확인할 좌표.
            foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

        Returns:
            예고 타일 위면 True.
        """
        return self.get_remaining(position, foresight_ticks=foresight_ticks) is not None

    def is_casting(self, entity_id: str) -> bool:
        """그 엔티티가 예고를 걸어 둔 상태인가 (target_is_casting).

        인지 폭을 보지 않는다. 시전 동작은 예고 타일이 붉어지기 전부터 보이며,
        그 차이가 센서 모듈(GDD §6.2)이 파는 가치다.

        Args:
            entity_id: 확인할 엔티티 id.

        Returns:
            진행 중인 예고가 하나라도 있으면 True.
        """
        return any(telegraph.caster_id == entity_id for telegraph in self.pending)

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _is_caster_alive(self, state: WorldState, telegraph: Telegraph) -> bool:
        """시전자가 아직 살아 있는가.

        Args:
            state: 세계 상태.
            telegraph: 확인할 예고.

        Returns:
            살아 있으면 True.
        """
        caster = state.entities.get(telegraph.caster_id)
        return caster is not None and caster.is_alive

    def _apply_blast(self, state: WorldState, log: EventLog, telegraph: Telegraph) -> None:
        """예고 타일 위의 엔티티에게 피해를 넣는다.

        진영을 가리지 않는다. 예고는 좌표에 떨어지는 것이므로 시전자의 아군도
        맞으며, 그래야 통로로 유인하는 전술이 성립한다 (GDD §4.3).

        Args:
            state: 세계 상태.
            log: 이벤트 로그.
            telegraph: 발동한 예고.
        """
        # 포함 검사에만 쓴다. 이것을 순회해 상태를 만들면 순서가 흔들린다 (R5).
        marked = frozenset(telegraph.tiles)
        victims = [entity for entity in state.list_actors() if entity.position in marked]
        expr = f"{telegraph.skill_id} 예고 발동 ({len(telegraph.tiles)}칸)"
        if not victims:
            # 회피 성공도 남긴다. 아무 일이 없었다는 사실이 규칙표를 고칠 때
            # 가장 필요한 정보다 (P1 실패는 정보다).
            self._record(state, log, telegraph, expr, "예고 타일 비어 있음 — 회피 성공", None)
            return
        for victim in victims:
            victim.hp = max(0, victim.hp - telegraph.damage)
            outcome = f"{victim.entity_id} HP {victim.hp}/{victim.hp_max}" + (
                "" if victim.is_alive else " 사망"
            )
            self._record(state, log, telegraph, expr, outcome, -telegraph.damage, victim.entity_id)

    def _record(
        self,
        state: WorldState,
        log: EventLog,
        telegraph: Telegraph,
        expr: str,
        outcome: str,
        delta: int | None,
        target_id: str | None = None,
    ) -> None:
        """예고 관련 이벤트 한 줄을 남긴다.

        Args:
            state: 세계 상태. 틱 번호를 읽는다.
            log: 이벤트 로그.
            telegraph: 대상 예고.
            expr: 조건 자리에 남길 문자열.
            outcome: 결과 설명.
            delta: 수치 변화. 없으면 None.
            target_id: 피해를 받은 쪽. 피해가 아닌 이벤트면 None.
        """
        log.record(
            LogEntry(
                tick=state.tick,
                entity_id=telegraph.caster_id,
                phase=PHASE_TELEGRAPH,
                expr=expr,
                outcome=outcome,
                delta=delta,
                fired=True,
                target_id=target_id,
            )
        )


def build_threat_notice(
    board: TelegraphBoard, position: tuple[int, int], *, foresight_ticks: int = 0
) -> ThreatNotice | None:
    """그 칸에 대한 경고 배너를 만든다 (design/README.md ThreatNotice).

    Args:
        board: 예고 보드.
        position: 기준 좌표. 보통 플레이어가 선 자리다.
        foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

    Returns:
        표시할 경고. 인지 가능한 위험이 없으면 None.
    """
    ticks = board.get_remaining(position, foresight_ticks=foresight_ticks)
    if ticks is None:
        return None
    is_imminent = ticks <= IMMINENT_TICKS
    return ThreatNotice(
        text=f"위험 예고 — {ticks}틱 후 피격",
        ticks=ticks,
        glyph=GLYPH_IMMINENT if is_imminent else GLYPH_PENDING,
        tone=TONE_DANGER if is_imminent else TONE_NEUTRAL,
    )
