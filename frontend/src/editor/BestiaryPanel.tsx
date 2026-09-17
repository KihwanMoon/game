/**
 * 도감 — **위키가 아니라 표적 목록** (docs/설계/6_몬스터 §8).
 *
 * 지속 몬스터가 도감의 성격을 바꿨다. "이 적은 이런 규칙을 쓴다" 만이 아니라 "지금 어디에
 * 있고, 얼마나 컸고, **내 아이템을 들고 있는가**" 를 말한다 — 그것이 되찾으러 가는
 * 동기이고 World Loop 이 성립하는 이유다.
 *
 * **규칙표를 그대로 낸다.** 줄 수로 접으면 카운터를 설계할 수 없다 — 도감이 표적 목록인
 * 이유가 바로 그것인데, 예전에는 화면이 「규칙 4줄」이라고만 적어 그 뜻이 사라져 있었다.
 * 서버는 처음부터 규칙표를 보내고 있었다.
 *
 * 등급을 색으로 칠하지 않는다. 의미색 셋이 이미 배정됐고 색은 정보의 유일한 채널이 될
 * 수 없다 — 등급은 글자로, "내 것" 은 글리프로 가른다.
 *
 * **격자는 가방과 같은 것을 쓴다** (2026-09-16). 개체마다 이름·스탯·접사·전리품·규칙표
 * 버튼이 펴져 있어 열 마리면 표적을 고르는 일이 스크롤이었다 — 도면 격자(`SlotBoard`)는
 * 칸에 상태만 그리고 규칙표는 고른 칸 아래 한 곳에 편다. 접는 버튼이 없어진 이유가
 * 그것이다: 펴는 자리가 하나면 접을 이유가 없고, 규칙표는 접지 않는 것이 이 화면의 뜻이다.
 * `ds/CellGrid` 는 지우지 않는다 — `tests/test_design_contract.py` 가 `ds/*.tsx` 전량을
 * 정본 계약과 대조한다.
 */
import { formatRuleText } from './ruleText'
import { GlyphState, Panel, ValueExpr } from '../ds'
import type { BestiaryEntry } from '../storage'

import { buildBestiaryCells } from './bestiaryCells'
import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'
import { GRID_PAGE, SlotBoard, SlotGrid, usePickedKey } from './SlotBoard'

export interface BestiaryPanelProps {
  readonly entries: readonly BestiaryEntry[] | undefined
  readonly link: LinkState
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '비각의 몬스터는 서버가 안다'
const EMPTY_HINT = '아직 비각에 지속 몬스터가 없다'

/** 아무 칸도 안 골랐을 때. 규칙표가 여기서 나온다는 것을 미리 말한다. */
const PICK_HINT = '칸을 고르면 규칙표가 그대로 뜬다 — 카운터는 거기서 나온다'

/**
 * 그 개체의 규칙표를 사람이 읽는 줄들로 만든다.
 *
 * **에디터와 같은 표기를 쓴다.** 도감이 다른 문법으로 적으면, 본 것을 그대로 자기
 * 규칙표에 옮길 수 없다 — 카운터 설계가 목적인데 옮겨 적기부터 막힌다.
 *
 * @param entry 도감 줄.
 * @returns 규칙 줄들. 규칙표가 없으면 빈 배열.
 */
export function listRuleLines(entry: BestiaryEntry): readonly string[] {
  if (entry.ruleset === undefined) {
    return []
  }
  // 첫 줄은 파일 머리말이라 뺀다 — 화면에는 규칙만 필요하다.
  return formatRuleText(entry.ruleset).split('\n').slice(1)
}

/**
 * 고른 개체 하나의 상세.
 *
 * 격자에서 갈라 둔 이유는 검사 때문만이 아니다 — 칸마다 규칙표를 펼치면 격자가 다시
 * 목록이 되고, 격자로 바꾼 이유가 사라진다.
 *
 * @param props 도감 줄 하나.
 * @returns 렌더 트리.
 */
export function BestiaryDetail(props: { readonly entry: BestiaryEntry }): React.JSX.Element {
  const { entry } = props
  return (
    <div className="cat__detail">
      <span className="cat__name">{entry.labelKo}</span>
      <ValueExpr
        text={`${entry.tier} · lv ${String(entry.level)}/${String(entry.levelCap)}`}
        size="sm"
      />

      {/* **얼마나 센가.** 규칙표만으로는 어떻게 싸우는지만 알 수 있고,
          이길 수 있는지는 알 수 없다. */}
      <ValueExpr
        text={`${String(entry.zoneFloor)}장 · hp ${String(entry.hpMax)} · 공 ${String(entry.attack)} · 방 ${String(entry.defense)}`}
        size="sm"
        dim
      />

      {entry.affixes.length === 0 ? null : (
        <ValueExpr text={`접사 ${entry.affixes.join(' · ')}`} size="sm" />
      )}

      {entry.holdsMine ? (
        <GlyphState
          state="armed"
          size="sm"
          label={`내 장비 보유 — ${entry.trophies.join(' · ')}`}
        />
      ) : null}

      {entry.ruleset === undefined ? null : (
        <>
          <ValueExpr text={`규칙표 ${String(entry.ruleset.rules.length)}줄`} size="sm" dim />
          <ol className="bst__rules">
            {listRuleLines(entry).map((line) => (
              <li className="bst__rule" key={line}>
                <ValueExpr text={line} size="sm" />
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}

/**
 * 도감 패널을 그린다.
 *
 * @param props 도감 줄들과 접속 상태.
 * @returns 패널 요소.
 */
export function BestiaryPanel(props: BestiaryPanelProps): React.JSX.Element {
  const { entries, link } = props
  const [pickedKey, togglePick] = usePickedKey()
  const cells = buildBestiaryCells(entries)
  const picked = cells.find((cell) => cell.key === pickedKey)
  const mine = cells.filter((cell) => cell.entry.holdsMine).length

  return (
    <Panel
      title="이문록 · 비각의 것들"
      meta={mine === 0 ? '' : `내 것 ${String(mine)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="bst">
        {!checkLinked(link) || entries === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : entries.length === 0 ? (
          <ValueExpr text={EMPTY_HINT} size="sm" dim />
        ) : (
          <SlotBoard
            hint={PICK_HINT}
            detail={picked === undefined ? undefined : <BestiaryDetail entry={picked.entry} />}
          >
            <SlotGrid
              title={`비각의 것들 ${String(cells.length)}${mine === 0 ? '' : ` · 내 것 ${String(mine)}`}`}
              shape="free"
              cells={cells}
              pickedKey={pickedKey}
              onPick={togglePick}
              // 서른여덟이 한 번에 깔린다 (2026-09-17 실측). 접사가 앞에 붙어 이름이
              // 길어지므로 종류(`catalogId`)로도 걸리게 둔다.
              filterText={(cell) => `${cell.entry.labelKo} ${cell.entry.catalogId}`}
              filterLabel="이름·종류로 찾기"
              unit="마리"
              // **한 장씩 깐다** (2026-09-17 실제 신고). 비각은 층을 내려갈수록 는다 — 18마리가 이미 한 화면이다.
              pageSize={GRID_PAGE}
            />
          </SlotBoard>
        )}
      </div>
    </Panel>
  )
}
