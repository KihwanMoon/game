#!/usr/bin/env bash
# 저장소 전량 게이트. **검사 내용의 유일한 정의**이며, 무엇이 이것을 부르는지(§8.5.1 의
# 트리거)와는 분리돼 있다. 트리거가 바뀌어도 검사는 여기 하나로 남는다.
#
# 1장의 예외 경로는 도구마다 반영 지점이 다르다 — ruff 는 ruff.toml, pydoclint 는 아래
# --exclude, check_naming.py 는 아래 grep. 한 곳만 고치면 나머지가 그 코드에서 실패한다.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

FAILED=""

step() {
    printf '
── %s
' "$1"
    shift
    if ! "$@"; then
        FAILED="${FAILED} $1"
    fi
}

step "ruff check" ruff check .
step "ruff format" ruff format --check .

# pydoclint 옵션 네 개는 모두 정본 문서와의 충돌을 막기 위한 것이다.
# 하나라도 빼면 문서가 요구하는 것을 검사가 거부해 저장소가 영구히 막힌다 (7.1).
#
# --arg-type-hints-in-docstring=False
#     5장이 "타입은 타입 힌트로 표현하고 독스트링에 중복 기재하지 않는다" 인데
#     pydoclint 기본값은 독스트링에 타입을 요구한다.
# --check-return-types=False
#     같은 이유로 반환 타입도 독스트링에 요구하지 않는다.
# --allow-init-docstring=True
#     5장과 ruff D107 이 __init__ 독스트링을 요구하는데, pydoclint 기본값은 그것을
#     클래스 독스트링에 합치라고 한다(DOC301). 이 옵션이 없으면 붙여도 떼어도 실패한다.
# --skip-checking-raises=True
#     5장이 "전파가 곧 계약인 경계 함수는 전파되는 예외도 적는다" 인데 pydoclint 는
#     몸통의 raise 문만 보므로(DOC502) 그 문서화를 오탐으로 막는다. Raises 정확성은
#     리뷰가 본다(§7 표에 "사람 판단"으로 적혀 있다).
#
# --exclude 는 **ruff 와 대상 범위가 다르다** — ruff 는 gitignore 된 경로를 자동 제외하고
# 서브모듈은 ruff.toml 이 걸러 주지만, pydoclint 는 경로를 직접 받으므로 둘 다 걸러지지
# 않는다. 가상환경을 빠뜨리면 서드파티 패키지 전체를, 서브모듈을 빠뜨리면 우리가 고칠 수
# 없는 코드를 검사한다. 아래 값에 저장소의 서브모듈 경로를 덧붙인다(§8.1 과 같은 기준).
# 테스트를 제외하는 이유는 1장에 있다 — §8.1 이 테스트에 D·ANN 을 면제하는데 pydoclint 가
# 검사하는 것이 정확히 그 둘이다.
step "pydoclint" pydoclint --style=google \
    --arg-type-hints-in-docstring=False \
    --check-return-types=False \
    --allow-init-docstring=True \
    --skip-checking-raises=True \
    --exclude '\.git|\.tox|\.venv|venv|\.direnv|node_modules|(^|/)tests/' \
    .

# 타입 검사는 §8.9 를 도입한 저장소만 둔다. ANN 은 애너테이션의 존재만 보므로
# 정확성까지 기계로 보려면 이 단계가 필요하다. 존량이 있으면 관대한 설정에서
# 시작해 단계적으로 좁힌다 — 처음부터 strict 로 켜면 §10.5 의 3단계를 건너뛴 것과 같다.
step "mypy" mypy --ignore-missing-imports --no-strict-optional .

# 1장의 예외 경로는 여기서도 제외한다. ruff 는 per-file-ignores 로 걸러지지만 이 검사는
# 파일 목록을 직접 받으므로 걸러지지 않는다. 서브모듈은 git ls-files 가 gitlink 만 내므로
# 자동으로 빠진다. xargs -r 은 대상이 0건일 때 인자 없이 실행되어 통과한 것처럼 보이는
# 것을 막는다.
printf '
── check_naming
'
# 정본 문서 §8.5 대비 두 곳을 고쳤다. 정본 개정(RULESET_VERSION 15) 후 되돌린다.
#  1) `python` -> `python3`. 다수의 리눅스 배포판은 `python3` 만 제공한다.
#     §8.3 주석이 같은 함정을 이미 경고하는데 §8.5 에는 반영돼 있지 않았다.
#  2) grep 에 `|| true`. grep 은 선택된 줄이 0개면 1 을 반환하는데, 이 파이프라인이
#     set -o pipefail 아래에 있어 "검사 대상 없음"이 곧 게이트 실패가 된다.
#     추적 중인 .py 가 없거나 전부 예외 경로일 때 저장소가 영구히 막힌다.
if ! git ls-files '*.py' \
    | { grep -v -E '((^|/)tests/|(^|/)migrations/|_pb2\.py$)' || true; } \
    | xargs -r python3 tools/check_naming.py; then
    FAILED="${FAILED} check_naming"
fi

# 구조 검사는 §8.9 를 도입한 저장소만 둔다. 없으면 이 블록을 지운다.
if [[ -x tools/check_structure.sh ]]; then
    step "check_structure" ./tools/check_structure.sh
fi

if [[ -n "${FAILED}" ]]; then
    printf '
실패:%s
' "${FAILED}"
    exit 1
fi
printf '
전부 통과
'
exit 0
