/**
 * 현재 배치(데스크톱 / 모바일 세로 / 모바일 가로)를 알려 준다.
 *
 * 모바일은 데스크톱 3열을 축소한 것이 아니라 **재배치**한 것이라, CSS 만으로는 끝나지
 * 않는다 — 세로에서는 규칙표와 로그가 탭으로 바뀌고 규칙 편집이 전용 전체 화면이 된다.
 * 그러려면 화면 코드가 지금 어느 배치인지 알아야 한다.
 *
 * **브레이크포인트를 여기에 다시 적지 않는다.** 경계는 `design/tokens/spacing.css` 의
 * 미디어쿼리 한 곳에만 있고, 그것이 `--layout-mode` 토큰에 이름을 남긴다. 이 훅은 그
 * 이름을 읽을 뿐이다. 값을 두 벌로 두면 CSS 가 바뀐 배치와 JS 가 믿는 배치가 어긋나고,
 * 그 어긋남은 특정 폭에서만 드러나 재현이 어렵다.
 */
import { useEffect, useState } from 'react'

/** 배치 이름. `--layout-mode` 토큰의 값과 같다. */
export type LayoutMode = 'desktop' | 'portrait' | 'landscape'

/** 토큰이 낼 수 있는 배치 이름 전부. 모르는 값이 오면 데스크톱으로 접는다. */
export const LAYOUT_MODES: readonly LayoutMode[] = ['desktop', 'portrait', 'landscape']

/** 배치 이름이 실린 토큰. */
export const LAYOUT_MODE_TOKEN = '--layout-mode'

/** 아직 읽지 못했을 때의 배치. 서버 렌더에는 화면이 없다. */
export const DEFAULT_LAYOUT_MODE: LayoutMode = 'desktop'

/** 토큰 이름 하나를 값으로 바꾸는 함수. 테스트가 이 자리에 가짜를 끼운다. */
export type TokenRead = (name: string) => string

/**
 * 배치가 바뀔 만한 사건을 구독한다.
 *
 * 창 크기와 기기 방향 둘 다 봐야 한다 — `orientationchange` 만 보면 데스크톱에서 창을
 * 줄일 때 놓치고, `resize` 만 보면 일부 모바일 브라우저가 회전 직후 크기를 늦게 알린다.
 * 구독을 한 곳에 모아 둔 이유는 화면마다 다른 사건을 듣기 시작하면 어떤 화면은 회전에
 * 따라오고 어떤 화면은 안 따라오는 상태가 되기 때문이다.
 *
 * @param onChange 사건이 났을 때 부를 함수.
 * @returns 구독을 끊는 함수.
 */
export function watchViewport(onChange: () => void): () => void {
  window.addEventListener('resize', onChange)
  window.addEventListener('orientationchange', onChange)
  return () => {
    window.removeEventListener('resize', onChange)
    window.removeEventListener('orientationchange', onChange)
  }
}

/**
 * 토큰 값을 배치 이름으로 읽는다.
 *
 * @param read 토큰 읽기 함수.
 * @returns 배치 이름. 토큰이 비었거나 모르는 값이면 데스크톱.
 */
export function readLayoutMode(read: TokenRead): LayoutMode {
  const value = read(LAYOUT_MODE_TOKEN).trim()
  return LAYOUT_MODES.find((mode) => mode === value) ?? DEFAULT_LAYOUT_MODE
}

/**
 * 문서 루트에서 배치 이름을 읽는다.
 *
 * @returns 배치 이름.
 */
function readDocumentLayoutMode(): LayoutMode {
  return readLayoutMode((name) => getComputedStyle(document.documentElement).getPropertyValue(name))
}

/**
 * 지금 배치를 따라간다. 창 크기가 바뀌거나 기기를 돌리면 값이 따라 바뀐다.
 *
 * @returns 현재 배치 이름.
 */
export function useViewportMode(): LayoutMode {
  const [mode, setMode] = useState<LayoutMode>(DEFAULT_LAYOUT_MODE)

  useEffect(() => {
    const update = (): void => {
      setMode(readDocumentLayoutMode())
    }
    update()
    return watchViewport(update)
  }, [])

  return mode
}
