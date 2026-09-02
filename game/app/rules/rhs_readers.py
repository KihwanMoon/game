"""조건 우변의 자기 스탯 읽기 (F-2, 블록 v7).

`rule_vm.py` 에서 갈라 나왔다 — 파일이 400줄 상한을 넘은 것이 계기였지만, 이 표는
블록 카탈로그의 `rhs_stats` 와 짝이라 홀로 서는 편이 맞다. 여기 없는 이름은 검증기가
막는다 — 닫힌 목록이 오타를 조용한 거짓으로 만들지 않는 방벽이다.
"""

from collections.abc import Callable

from game.app.simulation.state import Entity

RHS_STAT_READERS: dict[str, Callable[[Entity], int]] = {
    "attack_range": lambda actor: actor.attack_range,
    "attack": lambda actor: actor.attack,
    "defense": lambda actor: actor.defense,
    "hp_max": lambda actor: actor.hp_max,
    "cpu_budget": lambda actor: actor.cpu_budget,
    "potions": lambda actor: actor.count_item("POTION"),
    "scrolls": lambda actor: actor.count_item("SCROLL"),
}
