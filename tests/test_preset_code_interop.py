"""공유 코드가 두 코어 사이를 오가는지 본다 (M3).

`scripts/export_preset_code_golden.py` 가 파이썬이 구운 코드를 내려 주고 TS 테스트가
그것을 푼다. 이 파일은 **반대 방향**이다 — 브라우저(`frontend/src/storage/presetCode.ts`)가
구운 코드를 파이썬이 풀 수 있는지 본다.

두 테스트가 같은 파일 두 개를 본다. TS 쪽 압축이 바뀌면 `ts_preset_code.json` 을 다시
만들어야 하고(그쪽 테스트가 먼저 붉어진다), 다시 만든 코드가 여기서 풀리지 않으면 형식이
갈린 것이다. 그때 고칠 곳은 TS 다 — 파이썬이 정본이다.
"""

import json
from pathlib import Path

from game.schemas.meta_save import build_preset_payload
from game.schemas.preset_code import PRESET_CODE_PREFIX, parse_preset_code

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "frontend/src/storage/__golden__"
PYTHON_GOLDEN_PATH = GOLDEN_DIR / "preset_code.json"
TS_GOLDEN_PATH = GOLDEN_DIR / "ts_preset_code.json"


def read_golden(path):
    """기준값 파일을 읽는다."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_ts가_구운_코드를_파이썬이_푼다():
    cases = read_golden(PYTHON_GOLDEN_PATH)["cases"]
    codes = read_golden(TS_GOLDEN_PATH)
    assert len(codes) == len(cases)
    for case, code in zip(cases, codes, strict=True):
        assert code.startswith(PRESET_CODE_PREFIX)
        preset = parse_preset_code(code)
        assert build_preset_payload(preset) == case["payload"]


def test_같은_프리셋이면_두_구현이_같은_절을_낸다():
    cases = read_golden(PYTHON_GOLDEN_PATH)["cases"]
    codes = read_golden(TS_GOLDEN_PATH)
    for case, code in zip(cases, codes, strict=True):
        # 압축 바이트는 구현마다 다를 수 있다. 같아야 하는 것은 풀어 낸 내용이다.
        assert parse_preset_code(code) == parse_preset_code(case["code"])
