/** 컴포지션 루트. 디자인 토큰과 앱 스타일을 이 지점에서 배선한다. */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// 토큰 CSS 는 별칭 `@design` 으로 원본을 직접 읽는다. 사본을 두지 않으려는 것이다.
import '@design/styles.css'
import './styles/app.css'
// ds.css 는 `src/ds` 배럴이 스스로 싣는다. 여기서 또 부르면 같은 규칙이 두 번 들어간다.
import './editor/editor.css'
import { App } from './App'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
