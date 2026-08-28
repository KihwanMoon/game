#!/usr/bin/env bash
# §12.1 — 디렉터리 이름은 역할을 말해야 한다.
# 프레임워크 이름과 무의미어를 금지한다. 저장소가 BANNED 에 이름을 더할 수 있다.
#
# git ls-files 를 쓰므로 서브모듈(gitlink)과 gitignore 된 경로는 자동으로 빠진다 —
# ruff 의 extend-exclude 와 달리 예외 경로를 따로 적지 않아도 되는 이유다 (7.1).
set -uo pipefail

# TODO(victor): 이 목록은 정본 문서의 PDF 내보내기에서 `etc` 뒤가 잘려 있었다.
# 정본 문서(Confluence 라벨 python-coding-standard) §8.9 의 BANNED 값을 확인해
# 뒷부분을 복원할 것. 지금 값은 확인된 앞부분까지만 담고 있다.
BANNED='fastapi|django|flask|tornado|starlette|express|nest|functions|misc|stuff|temp|tmp|etc'

BAD=$(git ls-files \
    | awk -F/ '{ for (i = 1; i < NF; i++) print $i }' \
    | sort -u \
    | grep -x -E "${BANNED}" || true)

if [[ -n "${BAD}" ]]; then
    printf '§12.1 위반 — 역할을 말하지 않는 디렉터리 이름:
'
    printf '  %s
' ${BAD}
    printf '12장의 구조를 참고해 이름을 바꾼다. 이관은 §10.5 의 순서를 따른다.
'
    exit 1
fi
exit 0
