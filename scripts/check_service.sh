#!/usr/bin/env bash
# 서비스 사슬 전체를 훑어 어디가 끊겼는지 알려 준다.
#
# 지금 구조에서 사람이 많아 무너질 일은 거의 없다. 무너진다면 컨테이너가 죽거나
# 터널이 끊겨서이고, **그것을 알아챌 수단이 없는 것**이 실제 위험이다.
#
# 사슬: 오리진 컨테이너 → edge-proxy → Cloudflare Tunnel → 공개 도메인
# 한 단계씩 따로 확인하므로 어디서 끊겼는지가 바로 드러난다.
#
#   ./scripts/check_service.sh            한 번 확인하고 끝
#   ./scripts/check_service.sh --quiet    이상이 있을 때만 출력 (cron 용)
#
# 종료 코드: 0 정상 / 1 이상 있음
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DOMAIN="${DOMAIN:-stock.nullmovie.com}"
ORIGIN="${ORIGIN:-http://localhost:8090/}"
LOG_DIR="volume/monitor"
LOG_FILE="${LOG_DIR}/service.log"
TIMEOUT=10

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1
mkdir -p "${LOG_DIR}"

FAILED=""
REPORT=""

check() {
    local name="$1" code="$2" want="$3"
    if [[ "${code}" == "${want}" ]]; then
        REPORT="${REPORT}  OK    ${name} (${code})"$'\n'
    else
        REPORT="${REPORT}  실패  ${name} (${code}, 기대 ${want})"$'\n'
        FAILED="${FAILED} ${name}"
    fi
}

# 1. 오리진 컨테이너
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${TIMEOUT}" "${ORIGIN}" 2>/dev/null)
check "오리진 8090" "${code}" "200"

# 2. edge-proxy (호스트 80, Host 헤더로 가상호스트 선택)
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${TIMEOUT}" \
    -H "Host: ${DOMAIN}" http://localhost/ 2>/dev/null)
check "edge-proxy" "${code}" "200"

# 3. 백엔드 자리표시자
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${TIMEOUT}" \
    -H "Host: ${DOMAIN}" http://localhost/api/health 2>/dev/null)
check "backend /api/health" "${code}" "200"

# 4. 공개 도메인 (터널까지 포함한 종단)
#    Cloudflare 가 비브라우저 UA 를 막으므로(error 1010) 브라우저 UA 로 부른다.
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${TIMEOUT}" \
    -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36" \
    "https://${DOMAIN}/" 2>/dev/null)
check "공개 도메인" "${code}" "200"

# 5. 컨테이너 상태 (헬스체크 결과를 함께 본다)
for name in game-frontend-1 game-backend-1 edge-proxy; do
    state=$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}' \
        "${name}" 2>/dev/null || echo "없음")
    case "${state}" in
        running/healthy|running/-)
            REPORT="${REPORT}  OK    ${name} (${state})"$'\n' ;;
        running/starting)
            # 헬스체크의 start_period 안이다. 재시작 직후 몇 초는 반드시 이 상태를
            # 지나므로 실패로 세면 배포할 때마다 오경보가 난다. 위의 HTTP 검사가
            # 실제 응답을 이미 보고 있으니 여기서는 알리기만 한다.
            REPORT="${REPORT}  시작중 ${name} (${state})"$'\n' ;;
        *)
            REPORT="${REPORT}  실패  ${name} (${state})"$'\n'; FAILED="${FAILED} ${name}" ;;
    esac
done

# 6. 터널
state=$(systemctl is-active cloudflared 2>/dev/null || echo "unknown")
check "cloudflared" "${state}" "active"

stamp=$(date '+%Y-%m-%d %H:%M:%S')
if [[ -n "${FAILED}" ]]; then
    printf '%s 이상:%s\n%s' "${stamp}" "${FAILED}" "${REPORT}" >> "${LOG_FILE}"
    printf '%s 이상:%s\n%s' "${stamp}" "${FAILED}" "${REPORT}"
    exit 1
fi

printf '%s 정상\n' "${stamp}" >> "${LOG_FILE}"
[[ "${QUIET}" -eq 1 ]] || printf '%s 정상\n%s' "${stamp}" "${REPORT}"
exit 0
