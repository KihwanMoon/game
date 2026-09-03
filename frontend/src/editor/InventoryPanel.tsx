/**
 * 인벤토리·장비 패널 (D단계).
 *
 * **요구조건에 실측값을 병기한다.** "장착할 수 없습니다" 만 띄우면 무엇이 얼마나 모자란지
 * 알 수 없고, 그것은 규칙 에디터의 조건문 표기(`적거리(2) <= 사거리(3)`)와 같은 이유로
 * P1 위반이다 (GDD §8.2).
 *
 * **등급을 색으로 칠하지 않는다.** 의미색 셋이 이미 배정돼 있고 색은 정보의 유일한
 * 채널이 될 수 없다 (design/README.md §성격). 파손·봉인은 글리프와 취소선으로 가른다.
 *
 * 자체 브레이크포인트를 두지 않는다. 높이는 `--btn-tap-h` 가 정하므로 터치 배치에서
 * 저절로 44px 가 된다.
 */
import { useState } from 'react'

import { Panel, ValueExpr } from '../ds'
import type { AffixView, InventoryView } from '../storage'

import { formatGradeClass, renderGrade } from './gradeBadge'
import { buildBagCells, buildEquipCells } from './inventoryCells'
import { InventoryGrid } from './InventoryGrid'
import { InventoryDetail, type CellChoice } from './InventoryDetail'

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export { formatGradeClass, renderGrade }

export interface InventoryPanelProps {
  readonly inventory: InventoryView | undefined
  readonly link: LinkState
  readonly detail: string
  readonly onEquip: (itemId: number, slot: string) => void
  readonly onUnequip: (slot: string) => void
  readonly onDiscard: (itemId: number) => void
  readonly onList: (itemId: number, price: number) => void
  readonly onUnseal: (itemId: number) => void
  /** 걸 때 떼는 수수료율(%). 걸기 전에 얼마가 나가는지 알아야 한다. */
  readonly feePercent: number
  readonly onRepair: (itemId: number) => void
}

const EMPTY_HINT = '아직 없다 — 판을 끝내면 서버가 전리품을 준다'
/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '아이템은 서버가 발급한다'

/**
 * 접사 하나를 사람이 읽는 한 줄로 만든다.
 *
 * **부호를 붙여 적는다.** 저주 접사는 음수이고(`설계/4_아이템` §9), 「방어 -3」과
 * 「방어 3」이 같아 보이면 저주가 장점으로 읽힌다.
 *
 * @param affix 볼 접사.
 * @returns 화면에 적을 문자열.
 */
export function formatAffix(affix: AffixView): string {
  const parts: string[] = []
  if (affix.flat !== 0) {
    parts.push(`${affix.flat > 0 ? '+' : ''}${String(affix.flat)}`)
  }
  if (affix.percent !== 0) {
    parts.push(`${affix.percent > 0 ? '+' : ''}${String(affix.percent)}%`)
  }
  const label = affix.statLabel || affix.stat
  const name = affix.labelKo
  // **이름이 능력치를 되풀이하면 한 번만 적는다.** 「공격력 · 공격력 +3」 은 아무것도 더
  // 말해 주지 않고, 관리자가 이름 칸을 비웠을 때 영어 키가 그대로 새던 자리이기도 하다.
  const head = name === '' || name === affix.stat || name === label ? label : `${name} · ${label}`
  return parts.length === 0 ? head : `${head} ${parts.join(' ')}`
}

/**
 * 인벤토리·장비 패널을 도면 격자로 그린다.
 *
 * 장비 여섯 칸 + 가방 스무 칸. 칸을 고르면 아래 상세에 그 아이템의 전부(능력치·요구
 * 조건·조작)가 모인다.
 *
 * @param props 인벤토리와 처리기.
 * @returns 패널 요소.
 */
export function InventoryPanel(props: InventoryPanelProps): React.JSX.Element {
  const { inventory, link } = props
  const [pickedKey, setPickedKey] = useState('')

  const equipCells = buildEquipCells(inventory)
  const bagCells = buildBagCells(inventory)
  const picked = [...equipCells, ...bagCells].find((cell) => cell.key === pickedKey)
  const choice: CellChoice | undefined =
    picked?.entry === undefined
      ? undefined
      : {
          kind: picked.key.startsWith('equip:') ? 'equip' : 'bag',
          slot: picked.key.startsWith('equip:') ? picked.key.slice('equip:'.length) : '',
          entry: picked.entry,
        }
  const filled = bagCells.filter((cell) => cell.entry !== undefined).length

  return (
    <Panel
      title="장비와 가방"
      meta={inventory === undefined ? '' : `화폐 ${String(inventory.balance)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="inv">
        {!checkLinked(link) || inventory === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            <InventoryGrid
              inventory={inventory}
              pickedKey={pickedKey}
              onPick={(target) => {
                setPickedKey((current) => (current === target.key ? '' : target.key))
              }}
            />
            {filled === 0 ? <ValueExpr text={EMPTY_HINT} size="sm" dim /> : null}
            {choice === undefined ? (
              <ValueExpr text="칸을 고르면 여기에 상세와 조작이 뜬다" size="sm" dim />
            ) : (
              <InventoryDetail
                choice={choice}
                link={link}
                repairCost={inventory.repairCost}
                feePercent={props.feePercent}
                onEquip={props.onEquip}
                onUnequip={props.onUnequip}
                onDiscard={props.onDiscard}
                onRepair={props.onRepair}
                onUnseal={props.onUnseal}
                onList={props.onList}
              />
            )}
            {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
          </>
        )}
      </div>
    </Panel>
  )
}
