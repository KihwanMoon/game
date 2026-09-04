/**
 * 소모품 칸을 서버와 주고받는다 (설계/4_아이템 §5).
 *
 * **가방과 다른 화면이다.** 가방은 「가진 것」이고 칸은 「들고 갈 것」이다. 예전에는
 * 가방에 든 것을 전부 세서 들고 갔고, 그래서 「몇 개를 들고 갈까」가 선택이 아니었다.
 *
 * `serverSync.ts` 에서 갈라 나온 것이 아니라 처음부터 따로 둔다 — 저쪽은 이미 길고,
 * 이쪽은 라우트 넷과 값 하나만 안다.
 */
import type { AffixView, InventoryView, RawAffix } from './serverSync'
import {
  TOKEN_HEADER,
  readAffixRows,
  readErrorDetail,
  readInventory,
  sendRequest,
} from './serverSync'

/** 칸 하나. */
export interface ConsumableSlotView {
  readonly useTag: string
  readonly slotIndex: number
  /** 끼운 소모품. 빈 문자열이면 빈 칸이다. */
  readonly catalogId: string
  readonly labelKo: string
  readonly grade: string
  readonly charges: number
  readonly chargeMax: number
  /** 이 칸을 가득 채우는 값. 빈 칸은 0 이다. */
  readonly refillCost: number
  /** 끼우고 있는 동안 붙는 부가 옵션. 충전이 0 이면 비어 있다. */
  readonly affixes: readonly string[]
  /**
   * 같은 옵션의 구조화된 절. **견줌이 이것을 쓴다.**
   *
   * `affixes` 는 「튼튼함 · 최대체력 +8」 처럼 구운 문자열이라 능력치 축이 안 담긴다 —
   * 그것만 있으면 두 소모품을 스탯별로 견줄 수 없고, 문자열 두 벌을 나란히 놓는 것이
   * 화면이 할 수 있는 전부가 된다. 가방은 이미 구조화된 절로 견준다.
   */
  readonly affixRows: readonly AffixView[]
}

/** 가방에 있어 끼울 수 있는 소모품 한 종류. */
export interface ConsumableOptionView {
  readonly catalogId: string
  readonly labelKo: string
  readonly grade: string
  readonly useTag: string
  readonly charges: number
  readonly stock: number
  readonly sellPrice: number
  /** 끼우면 붙는 부가 옵션. */
  readonly affixes: readonly string[]
  /** 같은 옵션의 구조화된 절. 견줌이 이것을 쓴다. */
  readonly affixRows: readonly AffixView[]
}

/** 소모품 칸 화면 전체. */
export interface ConsumableView {
  readonly slots: readonly ConsumableSlotView[]
  readonly options: readonly ConsumableOptionView[]
  readonly balance: number
  readonly freeCharges: number
  /** 런이 도는 중이면 참. 이때는 끼우기·보충이 막힌다. */
  readonly isRunOpen: boolean
}

interface RawSlot {
  use_tag: string
  slot_index: number
  catalog_id: string | null
  label_ko: string
  grade: string
  charges: number
  charge_max: number
  refill_cost: number
  affixes: string[]
  affix_rows?: RawAffix[]
}

interface RawOption {
  catalog_id: string
  label_ko: string
  grade: string
  use_tag: string
  charges: number
  stock: number
  sell_price: number
  affixes: string[]
  affix_rows?: RawAffix[]
}

interface RawBody {
  slots: RawSlot[]
  options: RawOption[]
  balance: number
  free_charges: number
  is_run_open: boolean
}

/**
 * 서버가 보낸 절을 화면 값으로 만든다.
 *
 * @param body 서버 응답.
 * @returns 화면이 그릴 값.
 */
export function buildConsumableView(body: RawBody): ConsumableView {
  return {
    slots: body.slots.map((raw) => ({
      useTag: raw.use_tag,
      slotIndex: raw.slot_index,
      catalogId: raw.catalog_id ?? '',
      labelKo: raw.label_ko,
      grade: raw.grade,
      charges: raw.charges,
      chargeMax: raw.charge_max,
      refillCost: raw.refill_cost,
      affixes: raw.affixes,
      affixRows: readAffixRows(raw.affix_rows),
    })),
    options: body.options.map((raw) => ({
      catalogId: raw.catalog_id,
      labelKo: raw.label_ko,
      grade: raw.grade,
      useTag: raw.use_tag,
      charges: raw.charges,
      stock: raw.stock,
      sellPrice: raw.sell_price,
      affixes: raw.affixes,
      affixRows: readAffixRows(raw.affix_rows),
    })),
    balance: body.balance,
    freeCharges: body.free_charges,
    isRunOpen: body.is_run_open,
  }
}

/**
 * 소모품 칸을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 칸 화면. 서버에 닿지 못했으면 undefined.
 */
export async function readConsumables(token: string): Promise<ConsumableView | undefined> {
  const response = await sendRequest('/consumables', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return buildConsumableView((await response.json()) as RawBody)
}

/**
 * 칸을 조작한다. 성공하면 갱신된 화면이 돌아온다.
 *
 * **실패 사유를 그대로 돌려준다.** 「서버는 아는데 화면이 말하지 않는다」가 이 저장소에서
 * 여덟 번 났고, 그중 여럿이 조용히 삼킨 오류였다.
 *
 * @param token 기기 토큰.
 * @param path `/consumable/load` 같은 경로.
 * @param body 보낼 절.
 * @returns 갱신된 화면과 사유. 실패하면 화면이 undefined 다.
 */
export async function applyConsumableAction(
  token: string,
  path: string,
  body: Record<string, unknown>,
): Promise<{ view: ConsumableView | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { view: undefined, detail: await readErrorDetail(response) }
  }
  return { view: buildConsumableView((await response.json()) as RawBody), detail: '' }
}


/** 가방과 소모품 칸을 함께 담은 값. */
export interface BagState {
  readonly inventory: InventoryView | undefined
  readonly consumables: ConsumableView | undefined
}

/**
 * 가방과 소모품 칸을 **한 번에** 읽는다.
 *
 * **문을 하나로 둔 이유가 있다.** 둘을 따로 읽으면 어느 한 경로에서 하나를 빠뜨리기
 * 쉽고, 실제로 부팅 경로가 가방만 읽어 소모품 칸이 영원히 「서버에 닿지 못했다」로
 * 굳어 있었다 — 화면에는 칸이 뜨는데 아무것도 끼울 수 없었다.
 *
 * 둘은 한 몸이다. 끼우면 가방에서 빠지고 칸이 차며, 팔면 가방이 줄고 지갑이 는다.
 *
 * @param token 기기 토큰.
 * @returns 가방과 칸. 서버에 못 닿은 쪽은 undefined 다.
 */
export async function readBagState(token: string): Promise<BagState> {
  const [inventory, consumables] = await Promise.all([
    readInventory(token),
    readConsumables(token),
  ])
  return { inventory, consumables }
}
