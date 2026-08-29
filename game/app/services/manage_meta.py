"""메타 세이브 유스케이스 — 런이 끝났을 때 무엇이 남는가 (GDD §2.3, TDD §9).

런 루프는 `런 시작(프리셋 로드) → 층 공략 → 사망 or 클리어 → 결산 → 영구 해금 →
재도전` 이고, 이 모듈은 그중 **결산과 영구 해금**을 맡는다. 층 진행도·장비·포션은
여기 오지 않는다 — 사망으로 잃는 것과 남는 것의 경계가 곧 이 파일의 경계다.

결산이 남기는 것이 왜 이 셋인지가 설계의 핵심이다. 해금 블록과 도감은 **다음 런의
규칙표를 더 잘 쓰게 하는 것**이지 캐릭터를 세게 만드는 것이 아니다. 스탯이 아니라
정보가 누적되므로, 진 런도 "적을 카운터하는 규칙" 이라는 자산을 남긴다 (P1).

세이브 파일은 통째로 갈아 끼운다. 부분 갱신이 아니라 새 MetaSave 를 만들어 저장하므로
결산 도중 예외가 나도 이전 세이브가 그대로 남는다.
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path

from game.config import PACKAGE_ROOT
from game.schemas.blocks import BlockCatalog
from game.schemas.meta_save import (
    FIRST_FLOOR,
    MAX_PRESET_SLOTS,
    MAX_SLOT_BONUS,
    BestiaryRecord,
    MetaSave,
    RulePreset,
    build_meta_payload,
    parse_meta_save,
)
from game.schemas.ruleset import RuleSet

# 저장 위치. 표준 §12 가 정한 데이터 디렉터리이며 gitignore 대상이다 — 세이브는
# 저장소 자산이 아니라 사용자 데이터다. 상수를 여기 둔 이유는 W5 가 config.py 를
# 건드리지 않기로 했기 때문이고, 통합에서 config.py 로 옮긴다.
SAVE_DIR = PACKAGE_ROOT.parent / "volume"
META_SAVE_PATH = SAVE_DIR / "meta_save.json"

# 교체 직전까지 쓰는 임시 파일의 접미어. 쓰다 죽어도 본 파일은 온전하다.
TEMP_SUFFIX = ".tmp"

JSON_INDENT = 2


@dataclass(frozen=True)
class RunSummary:
    """런 하나가 남긴 것. 결산의 입력이다.

    조우·처치 목록은 **항목 하나가 1회**다. 같은 종을 두 번 만났으면 두 번 적는다.
    처치 목록은 조우 목록의 부분집합으로 넘긴다 — 잡았으면 만난 것이다.
    """

    floor_reached: int = 0
    is_cleared: bool = False
    seen_perceptions: tuple[str, ...] = ()
    seen_actions: tuple[str, ...] = ()
    encountered_kinds: tuple[str, ...] = ()
    defeated_kinds: tuple[str, ...] = ()


def load_meta_save(source_path: Path = META_SAVE_PATH) -> MetaSave:
    """메타 세이브를 읽는다. 파일이 없으면 빈 세이브다.

    첫 실행과 "세이브가 깨져 못 읽었다" 는 다르다. 앞은 빈 세이브를 돌려주고 뒤는
    예외로 올린다 — 조용히 빈 세이브를 주면 해금 전량이 소리 없이 날아간다.

    Args:
        source_path: 세이브 파일 경로.

    Returns:
        읽어들인 세이브. 파일이 없으면 기본값 세이브.
    """
    if not source_path.exists():
        return MetaSave()
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    return parse_meta_save(raw)


def save_meta_save(meta: MetaSave, target_path: Path = META_SAVE_PATH) -> None:
    """메타 세이브를 파일에 쓴다.

    임시 파일에 다 쓴 뒤 이름을 바꾼다. 저장 도중 죽었을 때 반쯤 쓰인 파일이 남으면
    영구 진행도 전체를 잃는데, 그것은 이 게임에서 사망보다 무거운 손실이다.

    Args:
        meta: 저장할 세이브.
        target_path: 세이브 파일 경로.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(build_meta_payload(meta), ensure_ascii=False, indent=JSON_INDENT)
    temp_path = target_path.with_suffix(target_path.suffix + TEMP_SUFFIX)
    temp_path.write_text(text + "\n", encoding="utf-8")
    temp_path.replace(target_path)


def get_slot_bonus(best_floor: int) -> int:
    """층 도달 기록이 주는 시작 규칙 슬롯 보너스 (GDD §2.3).

    Args:
        best_floor: 지금까지 도달한 가장 깊은 층.

    Returns:
        더해지는 슬롯 수. 층 1 까지는 0 이고 최대 +4 에서 멈춘다.
    """
    if best_floor <= FIRST_FLOOR:
        return 0
    return min(MAX_SLOT_BONUS, best_floor - FIRST_FLOOR)


def get_rule_slot_cap(meta: MetaSave, base_slots: int) -> int:
    """이 세이브로 시작하는 런의 규칙 슬롯 상한.

    Args:
        meta: 현재 메타 세이브.
        base_slots: balance.json 의 기본 슬롯 수.

    Returns:
        기본값에 층 기록 보너스를 더한 값.
    """
    return base_slots + get_slot_bonus(meta.best_floor)


def list_ruleset_blocks(ruleset: RuleSet) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """규칙표가 쓰는 인지 변수와 행동을 모은다.

    도감이 적의 규칙표를 그대로 보여주므로, 적을 만나는 것이 곧 그 규칙표가 쓰는
    블록을 "접하는" 것이다. 결산이 해금 목록을 만들 때 이 함수를 쓴다.

    Args:
        ruleset: 훑을 규칙표.

    Returns:
        (인지 변수, 행동) 두 정렬된 튜플.
    """
    perceptions = {term.lhs for rule in ruleset.rules for term in rule.conditions.terms}
    actions = {rule.action for rule in ruleset.rules}
    return tuple(sorted(perceptions)), tuple(sorted(actions))


def _merge_unlocked(
    current: tuple[str, ...], seen: tuple[str, ...], allowed: frozenset[str] | None
) -> tuple[str, ...]:
    """이미 해금된 것과 이번 런에 접한 것을 합친다.

    Args:
        current: 지금까지 해금된 블록 id.
        seen: 이번 런에 접한 블록 id.
        allowed: 카탈로그가 아는 id 목록. None 이면 거르지 않는다.

    Returns:
        정렬된 해금 목록.
    """
    merged = set(current)
    # 오타 난 id 가 들어오면 영영 쓸 수 없는 해금이 세이브에 남는다. 카탈로그를
    # 받은 경우에만 거른다 — 카탈로그 없이 부르는 쪽이 판단을 미룰 수 있게.
    merged.update(block_id for block_id in seen if allowed is None or block_id in allowed)
    return tuple(sorted(merged))


def _merge_bestiary(
    records: tuple[BestiaryRecord, ...],
    encountered: tuple[str, ...],
    defeated: tuple[str, ...],
) -> tuple[BestiaryRecord, ...]:
    """도감에 이번 런의 조우·처치를 더한다.

    Args:
        records: 기존 도감.
        encountered: 이번 런에 만난 적 종류 id.
        defeated: 이번 런에 잡은 적 종류 id.

    Returns:
        kind_id 순으로 정렬된 도감.
    """
    counts = {record.kind_id: [record.encounters, record.defeats] for record in records}
    for kind_id in encountered:
        counts.setdefault(kind_id, [0, 0])[0] += 1
    for kind_id in defeated:
        counts.setdefault(kind_id, [0, 0])[1] += 1
    # 정렬해서 꺼낸다. 딕셔너리 순회 순서가 세이브 파일에 새어 나가면 안 된다 (R5).
    return tuple(
        BestiaryRecord(kind_id=kind_id, encounters=tally[0], defeats=tally[1])
        for kind_id, tally in sorted(counts.items())
    )


def apply_run_result(
    meta: MetaSave, summary: RunSummary, catalog: BlockCatalog | None = None
) -> MetaSave:
    """런 결산을 메타 세이브에 반영한다 (GDD §2.3).

    해금과 도감은 누적이고 층 기록은 최대값이다. 이번 런이 더 얕게 죽었다고 해서
    슬롯 상한이 줄지 않는다 — 줄면 재도전이 벌이 되고 P1 이 무너진다.

    Args:
        meta: 지금까지의 세이브.
        summary: 이번 런의 결산 입력.
        catalog: 동결된 블록 카탈로그. 주면 모르는 블록 id 를 걸러낸다.

    Returns:
        갱신된 새 세이브. 인자로 받은 세이브는 그대로 둔다.
    """
    perception_ids = frozenset(catalog.perceptions) if catalog else None
    action_ids = frozenset(catalog.actions) if catalog else None
    return replace(
        meta,
        best_floor=max(meta.best_floor, summary.floor_reached),
        unlocked_perceptions=_merge_unlocked(
            meta.unlocked_perceptions, summary.seen_perceptions, perception_ids
        ),
        unlocked_actions=_merge_unlocked(meta.unlocked_actions, summary.seen_actions, action_ids),
        bestiary=_merge_bestiary(meta.bestiary, summary.encountered_kinds, summary.defeated_kinds),
    )


def find_preset(meta: MetaSave, name: str) -> RulePreset | None:
    """이름으로 프리셋 슬롯을 찾는다.

    Args:
        meta: 현재 메타 세이브.
        name: 찾을 프리셋 이름.

    Returns:
        찾은 프리셋. 없으면 None.
    """
    for preset in meta.presets:
        if preset.name == name:
            return preset
    return None


def add_preset(meta: MetaSave, preset: RulePreset) -> MetaSave:
    """프리셋을 코드 라이브러리에 넣는다. 같은 이름이면 그 슬롯을 덮어쓴다.

    Args:
        meta: 현재 메타 세이브.
        preset: 넣을 프리셋.

    Returns:
        갱신된 새 세이브.

    Raises:
        ValueError: 슬롯이 가득 찬 상태에서 새 이름을 넣으려는 경우. 어느 슬롯을
            버릴지는 플레이어가 정할 일이라 여기서 고르지 않는다.
    """
    slots = list(meta.presets)
    for index, existing in enumerate(slots):
        if existing.name == preset.name:
            slots[index] = preset
            return replace(meta, presets=tuple(slots))
    if len(slots) >= MAX_PRESET_SLOTS:
        raise ValueError(f"프리셋 슬롯이 가득 찼다 (최대 {MAX_PRESET_SLOTS})")
    slots.append(preset)
    return replace(meta, presets=tuple(slots))


def remove_preset(meta: MetaSave, name: str) -> MetaSave:
    """프리셋 슬롯을 비운다. 없는 이름이면 아무것도 하지 않는다.

    Args:
        meta: 현재 메타 세이브.
        name: 지울 프리셋 이름.

    Returns:
        갱신된 새 세이브.
    """
    kept = tuple(preset for preset in meta.presets if preset.name != name)
    return replace(meta, presets=kept)


def _is_rule_unlocked(rule_action: str, term_ids: tuple[str, ...], meta: MetaSave) -> bool:
    """규칙 하나가 해금된 블록만 쓰는지 본다.

    Args:
        rule_action: 규칙의 행동 id.
        term_ids: 규칙 조건이 쓰는 인지 변수 id.
        meta: 해금 목록을 가진 세이브.

    Returns:
        전부 해금돼 있으면 True.
    """
    if rule_action not in meta.unlocked_actions:
        return False
    return all(term_id in meta.unlocked_perceptions for term_id in term_ids)


def filter_preset_rules(preset: RulePreset, meta: MetaSave) -> RulePreset:
    """미해금 블록을 쓰는 규칙을 걷어낸다 (TDD §9 마이그레이션 정책).

    남의 공유 코드를 받으면 아직 해금하지 못한 블록이 섞여 있다. 통째로 거부하면
    코드를 주고받는 의미가 없으므로, 못 쓰는 줄만 빼고 나머지를 로드한다.

    Args:
        preset: 걸러낼 프리셋.
        meta: 해금 목록을 가진 세이브.

    Returns:
        해금된 규칙만 남긴 새 프리셋. 우선순위 순서는 그대로다.
    """
    kept = tuple(
        rule
        for rule in preset.ruleset.rules
        if _is_rule_unlocked(rule.action, tuple(term.lhs for term in rule.conditions.terms), meta)
    )
    return replace(preset, ruleset=replace(preset.ruleset, rules=kept))
