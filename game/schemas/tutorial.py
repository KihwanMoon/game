"""튜토리얼 스테이지 (로드맵 W20, 결정 #17).

**각 단계는 시작 규칙표로는 지고 해답 규칙표로는 이겨야 한다.** 그 대비가 가르치는
내용 자체이며, 둘 중 하나라도 어긋나면 그 단계는 아무것도 가르치지 못한다 —
`tests/test_tutorial.py` 가 매 커밋 그것을 확인한다.

스테이지는 밸런스와 함께 움직인다. 적 스탯이나 수식이 바뀌면 "지던 것이 이기게" 될 수
있으므로, 밸런스를 고칠 때 이 검사가 함께 빨개지는 것이 정상이다.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StageGoal:
    """단계를 통과했다고 볼 조건."""

    outcome: str
    # 규칙표가 써도 되는 최대 CPU. None 이면 기본 예산만 본다.
    max_cpu: int | None = None
    # 통과에 요구하는 최소 잔여 HP. 무피해를 요구할 때 쓴다.
    min_player_hp: int | None = None


@dataclass(frozen=True)
class TutorialStage:
    """단계 하나."""

    stage_id: str
    title_ko: str
    teaches_ko: str
    brief_ko: str
    hint_ko: str
    room_id: str
    seed: int
    start_rules: tuple[dict, ...]
    solution_rules: tuple[dict, ...]
    goal: StageGoal

    def build_ruleset(self, rules: tuple[dict, ...]) -> dict:
        """이 단계의 규칙표 절을 만든다.

        Args:
            rules: 규칙 목록.

        Returns:
            `parse_ruleset` 이 읽는 절.
        """
        return {"ruleset_id": self.stage_id, "version": 1, "rules": [dict(r) for r in rules]}


def load_tutorial_stages(path: Path) -> tuple[TutorialStage, ...]:
    """스테이지 파일을 읽는다.

    Args:
        path: `stages.json` 경로.

    Returns:
        파일에 적힌 순서 그대로의 단계들. **순서가 곧 진행 순서다.**
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(parse_tutorial_stage(item) for item in raw["stages"])


def parse_tutorial_stage(raw: dict) -> TutorialStage:
    """단계 한 줄을 읽는다.

    Args:
        raw: 단계 절.

    Returns:
        만들어진 단계.
    """
    goal = raw["goal"]
    return TutorialStage(
        stage_id=str(raw["stage_id"]),
        title_ko=str(raw["title_ko"]),
        teaches_ko=str(raw["teaches_ko"]),
        brief_ko=str(raw["brief_ko"]),
        hint_ko=str(raw["hint_ko"]),
        room_id=str(raw["room_id"]),
        seed=int(raw["seed"]),
        start_rules=tuple(raw["start_rules"]),
        solution_rules=tuple(raw["solution_rules"]),
        goal=StageGoal(
            outcome=str(goal["outcome"]),
            max_cpu=goal.get("max_cpu"),
            min_player_hp=goal.get("min_player_hp"),
        ),
    )
