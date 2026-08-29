/**
 * 확인용 페이지의 컴포지션 루트. `/battle.html` 이 이 파일을 부른다.
 *
 * 제품 화면(`src/main.tsx`)·부품 카탈로그(`src/ds/galleryMain.tsx`)와 분리한 이유는 같다 —
 * 수명이 다른 것을 한 파일에 두면 서로의 작업을 막는다. 이 페이지는 W13 의 검증 자리이며,
 * 전투 화면이 제품 화면으로 들어갈 때 그대로 남아 회귀를 눈으로 잡는 용도가 된다.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@design/styles.css'
import '../styles/app.css'
import { BattleCheck } from '.'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

createRoot(container).render(
  <StrictMode>
    <BattleCheck />
  </StrictMode>,
)
