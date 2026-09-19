/**
 * 관리 화면의 컴포지션 루트.
 *
 * **게임 화면에서 갈라 둔 이유는 폭이다.** 관리 화면은 표와 격자가 폭을 다 써야 하는데,
 * 게임 화면의 탭 하나는 좁아서 표와 격자가 폭을 다 쓰지 못했다.
 *
 * **경로의 존재는 드러나지만 데이터는 안 드러난다.** 관리 API 는 여전히 404 로 답하고,
 * 이 페이지는 관리자가 아니면 아무것도 못 그린다 — 그 사실만 말한다.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@design/styles.css'
import './styles/app.css'
import './editor/editor.css'
import { loadContentPack } from './content/pack'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

/**
 * 팩을 먼저 받고 그린다. 게임 화면과 같은 순서다 — 관리 화면도 지금 도는 자산을 봐야
 * 하고, 그러지 않으면 편집 대상이 화면과 어긋난다.
 */
async function startAdmin(): Promise<void> {
  await loadContentPack()
  // **앱을 여기서 들인다 — 정적 import 면 안 된다.** ESM 은 이 파일의 본문보다 import 한
  // 모듈의 본문을 먼저 돌린다. `AdminScreen` 을 위에서 정적으로 들이면 그 본문이
  // `loadContentPack()` 보다 **먼저** 돌고, 거기서 `readActivePack()` 으로 잡아 둔
  // 카탈로그·방·적·밸런스가 전부 번들로 굳는다 — 발행한 것이 화면에 한 번도 안 닿는다.
  //
  // 2026-09-19 에 「재주 이름을 고쳐 발행했는데 그대로다」로 드러났다. 이름만이 아니라
  // **팩 전체**가 안 닿고 있었고, 한 번도 발행한 적이 없어서(운영 `published=0`) 여태
  // 안 보였을 뿐이다. 늦게 들이면 화면과 그것이 끌어오는 모듈 전부가 갈아 끼운 뒤에 돈다.
  const { AdminScreen } = await import('./admin/AdminScreen')
  createRoot(container as HTMLElement).render(
    <StrictMode>
      <AdminScreen />
    </StrictMode>,
  )
}

void startAdmin()
