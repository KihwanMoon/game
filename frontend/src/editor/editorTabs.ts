/**
 * 규칙표 탭의 계약 — `RuleEditor` 와 `RuleEditMobile` 이 함께 쓴다.
 *
 * **따로 사는 이유는 순환 참조다.** 에디터가 모바일 화면을 부르고 모바일 화면이 탭
 * 계약을 읽으므로, 계약이 에디터 안에 있으면 값(`COMBAT_TAB_ID`)을 가져오는 순간 두
 * 모듈이 서로를 부른다.
 */
import type { ReactNode } from 'react'

/**
 * 에디터 탭 하나 — **세 열을 통째로 갈아 끼운다.**
 *
 * 규칙표가 한 벌이 아니게 됐다. 전투 규칙(결정론 코어가 돌린다)과 정비 규칙(티켓이 닫힐
 * 때 서버가 돌린다)은 **같은 종류의 물건**이다 — 둘 다 행 순서가 실행 순서인 조립물이다.
 * 그런데 정비는 가방 탭 안에 드롭다운 목록으로 있었고, 그래서 같은 문법의 두 규칙표가
 * 화면의 서로 다른 두 곳에서 다른 모양으로 편집됐다.
 *
 * **팔레트·본문·검증을 함께 받는 이유**는 셋이 한 몸이기 때문이다. 본문만 갈아 끼우면
 * 정비 규칙을 고치는 동안 왼쪽에 전투 블록 팔레트가 남고, 그것을 누르면 **안 보이는
 * 규칙표가 바뀐다.**
 */
export interface EditorTab {
  readonly id: string
  readonly label: string
  /** 왼쪽 팔레트 열. */
  readonly palette: ReactNode
  /** 가운데 본문 열. */
  readonly main: ReactNode
  /** 오른쪽 검증 열. */
  readonly check: ReactNode
  /** 상단 바의 계량. 전투는 CPU 게이지, 정비는 행 수·잔액이 여기 선다. */
  readonly gauge?: ReactNode
  /** 하단 바의 안내. */
  readonly foot?: ReactNode
}

/** 전투 규칙 탭의 id. 처음 열리는 탭이다 — 이 게임의 규칙표는 여전히 전투가 중심이다. */
export const COMBAT_TAB_ID = 'combat'
