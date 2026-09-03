/**
 * 방 고르기 목록 — **id 만 늘어놓지 않는다.**
 *
 * 예전에는 `<select>` 가 `open_field`·`corridor` 같은 영문 id 서른한 줄이었다. 방마다
 * `purpose`(무엇을 시험하는 방인가)와 `min_floor`(어느 층부터 나오는가)가 데이터에
 * 이미 있는데 화면이 그것을 하나도 안 썼다 — **서버는 아는데 화면이 말하지 않는다.**
 *
 * 고르는 사람이 답해야 하는 질문은 「어느 방이 내 규칙표를 시험하는가」다. id 만으로는
 * 서른한 번 눌러 봐야 알 수 있고, 그러면 대부분은 맨 위 것을 그냥 쓴다.
 *
 * 그래서 층으로 묶고 한 줄에 뜻을 함께 적는다. 층으로 묶는 이유는 그것이 데이터가 이미
 * 정한 난이도 축이기 때문이다 — 새 축을 여기서 지어내면 그것이 또 어긋난다.
 */
import type { RoomTemplate } from '../core/schemas/room'

/** 한 줄에 넣을 뜻의 최대 길이. 넘으면 자르고 말줄임을 붙인다. */
export const PURPOSE_CLIP = 34

/** 층 묶음 하나. */
export interface RoomGroup {
  readonly minFloor: number
  readonly label: string
  readonly rooms: readonly RoomChoice[]
}

/** 고를 수 있는 방 한 줄. */
export interface RoomChoice {
  readonly templateId: string
  /** 목록에 보일 한 줄. id 와 뜻을 함께 적는다. */
  readonly label: string
  /** 마우스를 올렸을 때 보일 전문. 자르지 않는다. */
  readonly title: string
}

/**
 * 뜻을 한 줄 길이로 줄인다.
 *
 * 첫 문장만 쓴다. 방 설명은 「무엇을 시험하는가」가 앞에 오고 뒤는 부연이라, 첫 문장이
 * 고르는 데 필요한 전부다.
 *
 * @param purpose 방 설명 전문.
 * @returns 한 줄. 비어 있으면 빈 문자열.
 */
export function clipPurpose(purpose: string): string {
  const first = purpose.split('.')[0]?.trim() ?? ''
  if (first.length <= PURPOSE_CLIP) {
    return first
  }
  return `${first.slice(0, PURPOSE_CLIP)}…`
}

/**
 * 방 목록을 층별로 묶는다.
 *
 * **정렬은 층 → id 다.** 데이터 순서에 기대면 방을 더할 때 목록이 조용히 뒤바뀐다.
 *
 * @param templates 방 템플릿 전량.
 * @returns 얕은 층부터의 묶음들.
 */
export function buildRoomGroups(templates: readonly RoomTemplate[]): RoomGroup[] {
  const byFloor = new Map<number, RoomChoice[]>()
  for (const template of [...templates].sort(
    (left, right) =>
      left.minFloor - right.minFloor || left.templateId.localeCompare(right.templateId),
  )) {
    const purpose = clipPurpose(template.purpose)
    const rooms = byFloor.get(template.minFloor) ?? []
    rooms.push({
      templateId: template.templateId,
      label: purpose === '' ? template.templateId : `${template.templateId} · ${purpose}`,
      title: template.purpose,
    })
    byFloor.set(template.minFloor, rooms)
  }
  return [...byFloor.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([minFloor, rooms]) => ({
      minFloor,
      label: `${String(minFloor)}층부터`,
      rooms,
    }))
}
