/**
 * 카탈로그 관리 — 조회·등록·폐기 (설계/4_아이템 §15.7).
 *
 * **삭제 버튼이 없다.** 인스턴스·원장·경매가 `catalog_id` 를 가리키므로 지우면 과거
 * 기록을 못 읽는다. 폐기는 "새로 안 나온다" 만 뜻하고, 폐기된 것도 목록에 남는다.
 *
 * **접사·등급·분류는 여기서 못 고친다.** 고치면 이미 나온 아이템이 소급해 바뀐다 —
 * 인스턴스가 굴린 접사가 없으면 카탈로그 기본값을 쓰기 때문이다. 서버가 409 로 거절하고,
 * 화면은 그 사유를 그대로 적는다. 고칠 수 있는 것은 이름과 최소 층뿐이다.
 *
 * **세대를 머리에 적는다.** 아이템을 고치는 것은 순위표 시즌을 가르는 일이고, 그
 * 사실이 조작 전에 눈에 있어야 한다.
 */
import { useState } from 'react'

import { Button, CellGrid, GlyphState, Panel, Thumb, ValueExpr } from '../ds'
import type { CatalogAdminView } from '../storage'

export interface CatalogAdminPanelProps {
  readonly catalog: CatalogAdminView | undefined
  readonly detail: string
  readonly onRetire: (catalogId: string, isRetired: boolean, reason: string) => void
  readonly onRename: (catalogId: string, labelKo: string, minFloor: number, reason: string) => void
  /** 새 종류를 등록한다. 절은 서버의 파서가 검사한다 — 화면이 문법을 따로 알 필요가 없다. */
  readonly onCreate: (payload: Record<string, unknown>, reason: string) => void
}

/** 신규 등록 폼이 받는 props. */
export interface CatalogFormProps {
  readonly grades: readonly string[]
  readonly onCreate: (payload: Record<string, unknown>, reason: string) => void
}

/** 장비 슬롯. 카탈로그가 쓰는 값 그대로다 — 화면이 새 이름을 지으면 서버가 못 읽는다. */
const SLOTS: readonly string[] = [
  'WEAPON_MAIN',
  'WEAPON_OFF',
  'HEAD',
  'BODY',
  'FEET',
  'HANDS',
]

const KINDS: readonly string[] = ['EQUIPMENT', 'CONSUMABLE', 'QUEST']

/**
 * 접사가 붙을 수 있는 능력치.
 *
 * 이 목록은 `blocks.json` 의 `rhs_stats` 와 같아야 한다 — 규칙표가 읽지 못하는 능력치에
 * 접사를 붙이면 그 아이템은 성능이 있는데 규칙으로는 안 보인다.
 */
const AFFIX_STATS: readonly string[] = [
  'attack',
  'defense',
  'hp_max',
  'attack_range',
  'cpu_budget',
  'initiative',
]

const DECIMAL_RADIX = 10

/** 접사 한 줄. 칸은 글자로 들고 있다가 보낼 때 숫자로 바꾼다. */
export interface AffixRow {
  readonly stat: string
  readonly flat: string
  readonly percent: string
  readonly labelKo: string
}

/**
 * 접사 줄 하나를 고친다.
 *
 * @param rows 지금 줄들.
 * @param index 고칠 자리.
 * @param patch 덮어쓸 값.
 * @returns 새 줄들.
 */
export function buildAffixRows(
  rows: readonly AffixRow[],
  index: number,
  patch: Partial<AffixRow>,
): readonly AffixRow[] {
  return rows.map((row, at) => (at === index ? { ...row, ...patch } : row))
}

/**
 * 접사 줄들을 서버가 읽는 절로 바꾼다.
 *
 * **빈 줄은 버린다.** 능력치만 고르고 값을 안 넣은 줄을 보내면 아무 효과 없는 접사가
 * 아이템에 붙고, 화면에는 이름만 뜬다.
 *
 * @param rows 접사 줄들.
 * @returns 서버가 읽는 절들.
 */
export function buildAffixPayload(rows: readonly AffixRow[]): Record<string, unknown>[] {
  return rows
    .filter((row) => row.flat.trim() !== '' || row.percent.trim() !== '')
    .map((row) => ({
      stat: row.stat,
      flat: Number.parseInt(row.flat, DECIMAL_RADIX) || 0,
      percent: Number.parseInt(row.percent, DECIMAL_RADIX) || 0,
      label_ko: row.labelKo === '' ? row.stat : row.labelKo,
    }))
}

/**
 * 아이템 종류를 새로 등록하는 폼.
 *
 * **접사는 JSON 으로 받는다.** 접사는 개수가 정해져 있지 않고 stat·flat·percent·label 이
 * 함께 가는 절이라, 칸을 늘렸다 줄였다 하는 UI 를 만드는 것보다 절을 그대로 받고 서버의
 * 파서가 검사하게 하는 편이 정확하다 — 화면이 문법을 따로 알면 두 규칙이 생긴다.
 *
 * @param props 등급 목록과 콜백.
 * @returns 렌더 트리.
 */
export function CatalogForm(props: CatalogFormProps): React.JSX.Element {
  const [id, setId] = useState('')
  const [kind, setKind] = useState('EQUIPMENT')
  const [slot, setSlot] = useState('HEAD')
  const [label, setLabel] = useState('')
  const [grade, setGrade] = useState('COMMON')
  const [minFloor, setMinFloor] = useState('1')
  // **한 줄로 시작한다.** 빈 채로 시작하면 「접사 추가」를 먼저 찾아야 하고, 그러면
  // 접사가 있다는 것 자체를 모른 채 아이템을 만든다. 안 채운 줄은 어차피 안 보내진다.
  const [affixRows, setAffixRows] = useState<readonly AffixRow[]>([
    { stat: AFFIX_STATS[0] ?? '', flat: '', percent: '', labelKo: '' },
  ])
  const [reason, setReason] = useState('')

  return (
    <div className="cat__detail">
      <span className="cat__name">새 종류 등록</span>
      {/* 수정이 막혀 있으므로 등록이 유일한 변경 경로다. 그 사실을 여기에 적는다. */}
      <ValueExpr
        text="접사·등급을 바꾸려면 여기서 새로 등록하고 옛 id 를 폐기한다"
        size="sm"
        dim
      />
      <label className="cat__field">
        <span>id</span>
        <input
          className="cat__input"
          value={id}
          placeholder="sword_long"
          onChange={(event) => {
            setId(event.target.value)
          }}
        />
      </label>
      <label className="cat__field">
        <span>이름</span>
        <input
          className="cat__input"
          value={label}
          placeholder="장검"
          onChange={(event) => {
            setLabel(event.target.value)
          }}
        />
      </label>
      <div className="cat__row">
        {KINDS.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={name === kind ? 'primary' : 'ghost'}
            onClick={() => {
              setKind(name)
            }}
          >
            {name}
          </Button>
        ))}
      </div>
      {kind !== 'EQUIPMENT' ? null : (
        <div className="cat__row">
          {SLOTS.map((name) => (
            <Button
              key={name}
              size="sm"
              variant={name === slot ? 'primary' : 'ghost'}
              onClick={() => {
                setSlot(name)
              }}
            >
              {name}
            </Button>
          ))}
        </div>
      )}
      <div className="cat__row">
        {props.grades.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={name === grade ? 'primary' : 'ghost'}
            onClick={() => {
              setGrade(name)
            }}
          >
            {name}
          </Button>
        ))}
      </div>
      <label className="cat__field">
        <span>최소 층</span>
        <input
          className="cat__input"
          inputMode="numeric"
          value={minFloor}
          onChange={(event) => {
            setMinFloor(event.target.value)
          }}
        />
      </label>
      {/* **접사를 칸으로 받는다.** JSON 을 손으로 치게 하면 따옴표 하나가 틀렸을 때
          서버가 거절하고, 그 사유는 아이템 이야기가 아니라 파서 이야기다. */}
      <span className="cat__name">접사</span>
      {affixRows.map((row, index) => (
        <div className="cat__row" key={`${String(index)}:${row.stat}`}>
          <select
            className="cat__input"
            aria-label={`접사 ${String(index + 1)} 능력치`}
            value={row.stat}
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { stat: event.target.value }))
            }}
          >
            {AFFIX_STATS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <input
            className="cat__input"
            inputMode="numeric"
            aria-label={`접사 ${String(index + 1)} 고정값`}
            value={row.flat}
            placeholder="고정"
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { flat: event.target.value }))
            }}
          />
          <input
            className="cat__input"
            inputMode="numeric"
            aria-label={`접사 ${String(index + 1)} 퍼센트`}
            value={row.percent}
            placeholder="%"
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { percent: event.target.value }))
            }}
          />
          <input
            className="cat__input"
            aria-label={`접사 ${String(index + 1)} 이름`}
            value={row.labelKo}
            placeholder="예리함"
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { labelKo: event.target.value }))
            }}
          />
        </div>
      ))}
      <Button
        size="sm"
        variant="ghost"
        glyph="＋"
        title="접사 칸을 하나 더 만든다"
        onClick={() => {
          setAffixRows([...affixRows, { stat: AFFIX_STATS[0] ?? '', flat: '', percent: '', labelKo: '' }])
        }}
      >
        접사 추가
      </Button>
      <label className="cat__field">
        <span>사유</span>
        <input
          className="cat__input"
          value={reason}
          placeholder="왜 넣는가 (4자 이상)"
          onChange={(event) => {
            setReason(event.target.value)
          }}
        />
      </label>
      <Button
        size="sm"
        variant="primary"
        disabled={id === ''}
        title="등록한다 — 코어 버전이 바뀌고 드롭 표에 오른다"
        onClick={() => {
          props.onCreate(
            {
              id,
              kind,
              label_ko: label === '' ? id : label,
              slot: kind === 'EQUIPMENT' ? slot : null,
              hands: slot.startsWith('WEAPON') ? 'ONE' : null,
              grade,
              min_floor: Number.parseInt(minFloor, 10) || 1,
              affixes: buildAffixPayload(affixRows),
            },
            reason,
          )
        }}
      >
        등록
      </Button>
    </div>
  )
}

const OFFLINE_HINT = '서버에 닿지 못했다 — 카탈로그는 서버가 안다'

/**
 * 카탈로그 관리 화면을 그린다.
 *
 * @param props 카탈로그와 조작 콜백.
 * @returns 패널 요소.
 */
export function CatalogAdminPanel(props: CatalogAdminPanelProps): React.JSX.Element | null {
  const { catalog } = props
  const [picked, setPicked] = useState('')
  const [reason, setReason] = useState('')

  if (catalog === undefined) {
    return (
      <Panel title="카탈로그 관리" tone="panel" padded>
        <ValueExpr text={OFFLINE_HINT} size="sm" dim />
      </Panel>
    )
  }

  const row = catalog.items.find((item) => item.catalogId === picked)

  return (
    <Panel
      title="카탈로그 관리"
      meta={`세대 ${String(catalog.generation)} · ${String(catalog.items.length)}종`}
      tone="panel"
      padded
      scroll
    >
      <div className="cat">
        <GlyphState
          state="danger"
          size="sm"
          label="고치면 코어 버전이 바뀐다 — 순위표 시즌이 갈린다"
        />
        {/* **고르기 전에 있어야 한다.** 상세 안에 두면 규칙을 아는 시점이 늦고, 그때는
            이미 "왜 안 되지" 를 겪은 뒤다. */}
        <ValueExpr
          text="접사·등급·분류는 여기서 못 고친다 — 새 id 로 등록하고 옛 id 를 폐기한다"
          size="sm"
          dim
        />
        {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}

        <CellGrid
          cells={catalog.items.map((item) => ({
            id: item.catalogId,
            thumb: (
              <Thumb
                kind={item.slot === '' ? item.kind : item.slot}
                label={item.labelKo}
                state={item.isRetired ? 'locked' : 'known'}
              />
            ),
            name: item.labelKo,
            meta: [
              `${item.grade} · ${String(item.minFloor)}층~`,
              item.isRetired ? '폐기' : `가중치 ${String(item.dropWeight)}`,
            ],
            isSelected: item.catalogId === picked,
          }))}
          onSelect={(id) => {
            setPicked(id)
          }}
          emptyText="카탈로그가 비어 있다"
        />

        <CatalogForm grades={catalog.grades} onCreate={props.onCreate} />

        {row === undefined ? null : (
          <div className="cat__detail">
            <span className="cat__name">{row.catalogId}</span>
            <ValueExpr
              text={`${row.kind}${row.slot === '' ? '' : ` · ${row.slot}`} · ${row.grade} · ${String(row.minFloor)}층~`}
              size="sm"
              dim
            />
            {row.affixes.length === 0 ? null : (
              <ValueExpr text={row.affixes.join(' · ')} size="sm" />
            )}
            {row.requirements.length === 0 ? null : (
              <ValueExpr text={`요구 ${row.requirements.join(' · ')}`} size="sm" dim />
            )}
            {/* 굴림에 걸리는 값이라 눈에 있어야 한다 — 0 이면 등록돼 있어도 안 나온다. */}
            <ValueExpr
              text={row.dropWeight === 0 ? '드롭 표에 없다 — 굴려도 안 나온다' : `드롭 가중치 ${String(row.dropWeight)}`}
              size="sm"
              dim={row.dropWeight > 0}
            />

            <label className="cat__field">
              <span>사유</span>
              <input
                className="cat__input"
                value={reason}
                onChange={(event) => {
                  setReason(event.target.value)
                }}
                placeholder="왜 고치는가 (4자 이상)"
              />
            </label>

            <div className="cat__row">
              <Button
                size="sm"
                variant={row.isRetired ? 'primary' : 'secondary'}
                title={
                  row.isRetired
                    ? '다시 나오게 한다'
                    : '새로 안 나오게 한다 — 이미 나온 것은 그대로 남는다'
                }
                onClick={() => {
                  props.onRetire(row.catalogId, !row.isRetired, reason)
                }}
              >
                {row.isRetired ? '되살리기' : '폐기'}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                title="최소 층을 한 층 올린다 — 앞으로의 굴림에만 걸린다"
                onClick={() => {
                  props.onRename(row.catalogId, row.labelKo, row.minFloor + 1, reason)
                }}
              >
                최소 층 +1
              </Button>
            </div>

          </div>
        )}
      </div>
    </Panel>
  )
}
