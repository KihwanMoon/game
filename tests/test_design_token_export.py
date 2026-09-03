"""디자인 토큰 내보내기 (피그마 Tokens Studio).

**손으로 옮기면 또 어긋난다.** `design/` 은 정본의 사본이고, 실제로 열한 개가 어긋나
있었다(X8·X9). 피그마 쪽에서 그것을 되풀이하지 않으려면 내보내기가 기계여야 한다.

여기서 지키는 것은 셋이다 — 반응형이 모드로 살아남는가, 별칭이 참조가 되는가,
별칭이 제 타입을 얻는가.
"""

import json

from scripts.export_design_tokens import (
    BASE_MODE,
    MODE_BY_MARK,
    build_metadata,
    build_token_sets,
    read_declarations,
    resolve_type,
)

SAMPLE = """
:root{
  --brass:#C89A4E;
  --text-accent:var(--brass);
  --plan-cell:64px;
  --plan-cols:12;        /* @kind other */
  --bw:1px;              /* @kind spacing */
  --border:var(--bw) solid var(--brass); /* @kind other */
}

@media (max-width:840px){
  :root{
    --plan-cell:30px;
}
}

@media (max-width:1023px) and (max-height:559px) and (orientation:landscape){
  :root{
    --plan-cell:32px;
}
}
"""


def build_sample():
    """표본 CSS 를 셋으로 만든다.

    Returns:
        셋 대응표.
    """
    return build_token_sets(read_declarations(SAMPLE))


def test_a_media_value_becomes_a_mode():
    """★ **반응형이 모드로 살아남는다.**

    이름만 모으면 같은 토큰의 세 값이 서로를 덮어써서 반응형이 통째로 사라진다 —
    피그마 변수에는 미디어쿼리가 없고 모드가 있다.
    """
    sets = build_sample()
    assert sets["layout/desktop"]["plan-cell"]["$value"] == "64px"
    assert sets["layout/portrait"]["plan-cell"]["$value"] == "30px"
    assert sets["layout/landscape"]["plan-cell"]["$value"] == "32px"


def test_every_mode_carries_every_layout_token():
    """★ 모드마다 전량이 있어야 한다.

    피그마는 모드에 값이 없으면 그 모드에서 비어 버리는데, CSS 는 재정의하지 않은 값이
    이어지는 것을 전제로 쓰여 있다.
    """
    sets = build_sample()
    names = {name for name in sets[f"layout/{BASE_MODE}"]}
    for _mark, mode in MODE_BY_MARK:
        assert set(sets[f"layout/{mode}"]) == names, mode


def test_an_alias_becomes_a_reference():
    """★ `var()` 가 Tokens Studio 참조가 된다 — 아니면 별칭 구조가 통째로 납작해진다."""
    assert build_sample()["semantic"]["text-accent"]["$value"] == "{primitive.brass}"


def test_an_alias_inherits_its_type():
    """★ **별칭은 제 타입을 모른다.**

    값이 참조 한 개라 모양만 봐서는 색인지 알 수 없다. `other` 로 올라간 색은 피그마에서
    색상 변수가 아니라 문자열 변수가 된다.
    """
    assert build_sample()["semantic"]["text-accent"]["$type"] == "color"


def test_a_composite_value_keeps_its_shape():
    """합성값은 안쪽만 바꾼다 — 통째로 버리면 괘선 토큰이 값을 잃는다."""
    border = build_sample()["primitive"]["border"]
    assert border["$value"] == "{primitive.bw} solid {primitive.brass}"


def test_the_kind_annotation_wins():
    """★ 저장소가 적어 둔 `@kind` 가 값 모양보다 먼저다.

    `--plan-cols:12` 는 숫자처럼 보이지만 치수가 아니라 격자 칸 수다.
    """
    assert resolve_type("12", "@kind other") == "other"
    assert resolve_type("12", "") == "number"
    assert resolve_type("1px", "@kind spacing") == "dimension"


def test_the_metadata_lists_every_set():
    """플러그인이 셋 순서를 읽는다. 빠지면 그 셋이 안 켜진다."""
    document = build_metadata(build_sample())
    order = document["$metadata"]["tokenSetOrder"]
    for name in ("primitive", "semantic", f"layout/{BASE_MODE}"):
        assert name in order, name
    assert [theme["id"] for theme in document["$themes"]] == [
        BASE_MODE,
        *[mode for _mark, mode in MODE_BY_MARK],
    ]


def test_the_shipped_file_is_current():
    """★ 내보낸 파일이 지금 토큰과 같다.

    스크립트가 있어도 안 돌리면 파일이 낡는다 — 낡은 파일은 없는 것보다 나쁘다.
    그것이 이 내보내기가 막으려던 바로 그 드리프트다.
    """
    from scripts.export_design_tokens import OUTPUT_PATH, TOKENS_DIR

    declarations = []
    for path in sorted(TOKENS_DIR.glob("*.css")):
        declarations.extend(read_declarations(path.read_text(encoding="utf-8")))
    expected = build_metadata(build_token_sets(declarations))
    assert json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) == expected
