"""전투 수식 — 전량 정수 연산 (TDD §8, GDD §6.4).

TDD §8 은 계수를 실수로 적었지만 TDD §12 R5 는 정수 연산 원칙을 요구한다. 충돌하므로
정수 쪽을 택했다 — 부동소수는 플랫폼마다 결과가 갈려 골든 리플레이를 무너뜨린다.
계수는 balance.json 에 정수 퍼센트로 들어 있고 이 모듈은 그것을 받아 쓴다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DamageRules:
    """damage_formula 절이 담고 있는 상수들."""

    soft_cap_base: int
    soft_cap_per_floor: int
    surround_step_pct: int
    surround_cap_pct: int
    min_damage: int


def build_damage_rules(raw: dict) -> DamageRules:
    """balance.json 의 damage_formula 절에서 상수를 뽑는다.

    Args:
        raw: damage_formula 딕셔너리.

    Returns:
        수식 상수 묶음.
    """
    return DamageRules(
        soft_cap_base=raw["soft_cap_base"],
        soft_cap_per_floor=raw["soft_cap_per_floor"],
        surround_step_pct=raw["surround_step_pct"],
        surround_cap_pct=raw["surround_cap_pct"],
        min_damage=raw["min_damage"],
    )


def calculate_damage(
    attack: int,
    skill_coef_pct: int,
    defense: int,
    floor: int,
    adjacent_enemies: int,
    rules: DamageRules,
) -> int:
    """한 번의 타격이 주는 피해를 계산한다.

    방어력은 감쇠식을 쓰고 층 항을 포함한다 — 층이 오를수록 방어 효율이 낮아져
    스탯 뭉개기가 억제된다 (GDD §7).

    Args:
        attack: 공격자의 최종 공격력.
        skill_coef_pct: 스킬 계수. 정수 퍼센트다 (100 = 1.0배).
        defense: 피격자의 최종 방어력.
        floor: 현재 층. 1 부터 센다.
        adjacent_enemies: 피격자에게 인접한 적 수. 1 이면 가산 없음.
        rules: 수식 상수.

    Returns:
        최소 min_damage 이상의 피해량.
    """
    denominator = defense + rules.soft_cap_base + rules.soft_cap_per_floor * floor
    raw = (attack * skill_coef_pct * (denominator - defense)) // (100 * denominator)
    surround_pct = min(
        rules.surround_cap_pct,
        100 + rules.surround_step_pct * (max(1, adjacent_enemies) - 1),
    )
    return max(rules.min_damage, raw * surround_pct // 100)
