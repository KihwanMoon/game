#!/usr/bin/env bash
# PostToolUse 훅. Claude Code 가 파이썬 파일을 쓴 직후 포맷·린트를 적용하고,
# 자동 수정으로 해결되지 않는 위반은 exit 2 로 Claude 에게 되돌려 준다.
#
# PostToolUse 는 도구를 되돌리지 못한다. exit 2 의 효과는 stderr 를 Claude 에게
# 보여 주는 것뿐이며, Claude 는 그것을 읽고 곧바로 파일을 고친다.
set -uo pipefail

# 훅 입력은 stdin 으로 들어오는 JSON 이다. 파일 경로를 담은 환경변수는 없다.
INPUT=$(cat)
FILE_PATH=$(printf '%s' "${INPUT}" | jq -r '.tool_input.file_path // empty')

# 대상이 없거나 파이썬이 아니면 조용히 통과한다.
if [[ -z "${FILE_PATH}" || "${FILE_PATH}" != *.py || ! -f "${FILE_PATH}" ]]; then
    exit 0
fi

# 1장의 예외 경로. §8.1 per-file-ignores 및 §8.5 게이트와 같은 기준을 유지한다.
# 서브모듈·가상환경 경로가 있으면 여기에도 함께 적는다.
case "${FILE_PATH}" in
    */migrations/*|*_pb2.py) exit 0 ;;
esac

# 자동 수정 단계. 출력은 버린다 — 컨텍스트에 넣을 값이 없다.
ruff format "${FILE_PATH}" >/dev/null 2>&1 || true
ruff check --fix "${FILE_PATH}" >/dev/null 2>&1 || true

# 보고 단계. 자동 수정 후에도 남은 것만 Claude 에게 전달한다.
# 테스트는 네이밍 검사 대상이 아니다 (1장).
case "${FILE_PATH}" in
    */tests/*) NAMING_OUTPUT=""; NAMING_STATUS=0 ;;
    *)
        NAMING_OUTPUT=$(python3 "${CLAUDE_PROJECT_DIR}/tools/check_naming.py" "${FILE_PATH}" 2>&1)
        NAMING_STATUS=$?
        ;;
esac
RUFF_OUTPUT=$(ruff check --output-format concise "${FILE_PATH}" 2>&1)
RUFF_STATUS=$?

if [[ ${NAMING_STATUS} -ne 0 || ${RUFF_STATUS} -ne 0 ]]; then
    {
        [[ -n "${NAMING_OUTPUT}" ]] && printf '%s
' "${NAMING_OUTPUT}"
        [[ -n "${RUFF_OUTPUT}" ]] && printf '%s
' "${RUFF_OUTPUT}"
        printf '%s
' "위 위반을 지금 수정할 것. 억제 주석으로 넘기지 말 것."
    } >&2
    exit 2
fi

exit 0
