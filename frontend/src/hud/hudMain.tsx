/**
 * 확인용 페이지의 컴포지션 루트. `/hud.html` 이 이 파일을 부른다.
 *
 * 제품 화면(`src/main.tsx`)·부품 카탈로그(`/ds.html`)·전투 화면 확인(`/battle.html`)과
 * 따로 두는 이유는 수명이 다르기 때문이다. 여기는 되감기와 사후 분석을 눈으로 확인하는
 * 자리이고, 다른 화면을 짜는 쪽과 파일을 나눠 쓰면 계속 충돌한다.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@design/styles.css'
// hud.css 는 `src/hud` 배럴이 스스로 싣는다. 여기서 또 부르면 같은 규칙이 두 번 들어간다.
import { HudCheck } from './index'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

createRoot(container).render(
  <StrictMode>
    <HudCheck />
  </StrictMode>,
)
