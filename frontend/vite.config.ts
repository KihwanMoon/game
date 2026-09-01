/// <reference types="node" />
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const repoRoot = fileURLToPath(new URL('..', import.meta.url))
const designDir = fileURLToPath(new URL('../design', import.meta.url))
const resourcesDir = fileURLToPath(new URL('../game/resources', import.meta.url))

// 개발 서버 포트는 8090 으로 고정한다. Cloudflare Tunnel 이 host:8090 으로 직접
// 들어오기 때문이다 (deploy/README.md).
const DEV_PORT = 8090

// 디자인 토큰(../design)과 밸런스 JSON(../game/resources)을 **복사하지 않고** 별칭으로
// 참조한다. 심볼릭 링크도 쓰지 않는다.
//   - 복사하면 사본이 둘이 되고, 파이썬 코어가 읽는 원본과 조용히 갈라진다. 그 순간
//     게이트 G3(두 코어 동일 결과)가 검증하는 대상이 서로 다른 데이터가 된다.
//   - design/ 은 이미 Claude Design 프로젝트의 사본이다(CLAUDE.md). 여기서 또 복사하면
//     정본에서 두 단계 떨어진 사본이 생긴다.
//   - 별칭은 빌드 시점에 해소되므로 산출물에는 값이 인라인되고, 런타임 경로 의존이 없다.
// 저장소 밖이 아니라 저장소 안의 상위 디렉터리이므로 server.fs.allow 에 루트를 열어 준다.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@design': designDir,
      '@resources': resourcesDir,
    },
  },
  // 진입점이 넷이다. index.html 은 제품 화면, ds.html 은 디자인 시스템 부품
  // 카탈로그(`src/ds/gallery.tsx`), battle.html 은 전투 화면 확인용 페이지
  // (`src/battle/BattleCheck.tsx`), hud.html 은 되감기·사후 분석 확인용 페이지
  // (`src/hud/HudCheck.tsx`)다. 카탈로그를 App.tsx 안에 숨기지 않은 이유는 수명이
  // 다르기 때문이다 — 부품을 보는 페이지와 부품을 쓰는 화면이 한 파일을 나눠 쓰면
  // 전투 화면 작업과 계속 충돌한다. 개발 서버는 설정 없이도 두 html 을 모두 서빙하지만,
  // 빌드는 여기에 적힌 것만 산출물에 넣는다.
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('index.html', import.meta.url)),
        ds: fileURLToPath(new URL('ds.html', import.meta.url)),
        battle: fileURLToPath(new URL('battle.html', import.meta.url)),
        hud: fileURLToPath(new URL('hud.html', import.meta.url)),
        admin: fileURLToPath(new URL('admin.html', import.meta.url)),
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: DEV_PORT,
    strictPort: true,
    fs: { allow: [repoRoot] },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})
