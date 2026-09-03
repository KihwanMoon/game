/**
 * 세계 패널 — 성장·순위·경매장 (F단계).
 *
 * **순위표의 점수는 누적 경험치다.** 한 판의 성적이 아니라 얼마나 멀리 왔는가를 잰다 —
 * 이 게임은 로그라이크가 아니라 던전 RPG 이고, 캐릭터가 이어지는 것이 전제다.
 *
 * **시즌 이름이 코어 버전이다** (결정 #06). 밸런스나 블록 목록이 바뀌면 과거 기록이
 * 재현되지 않으므로 순위표가 새로 시작한다 — 화면이 그 이유를 적어 둔다.
 *
 * 경매장은 **수수료율을 먼저 보여준다.** 걸기 전에 얼마가 나가는지 알아야 한다.
 */
import { useState } from "react";

import { buildAttributeBonus } from "../core/progression/attributes";
import { Button, GlyphState, Panel, ValueExpr } from "../ds";
import { formatAffix } from "./InventoryPanel";
import type { AuctionView, LeaderboardView, ProgressView } from "../storage";

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface WorldPanelProps {
  readonly progress: ProgressView | undefined;
  readonly leaderboard: LeaderboardView | undefined;
  readonly auction: AuctionView | undefined;
  readonly accountId: number | undefined;
  readonly link: LinkState;
  readonly detail: string;
  readonly onAllocate: (stats: Record<string, number>) => void;
  readonly onBuy: (listingId: number) => void;
  readonly onCancel: (listingId: number) => void;
  readonly onDaily: () => void;
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '순위와 경매는 서버가 안다'

/**
 * 이 배분이 지금 여는 것을 실측값으로 적는다 (결정 #51).
 *
 * **찍기 전에 보여야 한다.** 배분은 되돌릴 수 없고, "힘 +1" 만 적으면 그것이 공격력을
 * 얼마나 올리는지 유저가 알 수 없다. 디자인 §8.2 가 조건문에 각 항의 실측값을 병기하라고
 * 한 것과 같은 이유다.
 *
 * @param key 능력치 열쇠.
 * @param points 그 축에 찍힌 점수(확정분 + 대기분).
 * @returns 화면에 적을 문구. 0점이면 빈 문자열.
 */
export function formatAttributeEffect(key: string, points: number): string {
  if (points <= 0) {
    return "";
  }
  const bonus = buildAttributeBonus({ [key]: points });
  if (key === "str") {
    return `공격 +${String(bonus.attack)} · 체력 +${String(bonus.hpMax)}`;
  }
  if (key === "dex") {
    return `선공 +${String(bonus.initiative)} · 방어 +${String(bonus.defense)}`;
  }
  if (key === "int") {
    return `CPU +${String(bonus.cpuBudget)} · 스킬위력 ${String(bonus.skillPowerPct)}%`;
  }
  return "";
}
const STAT_LABELS: ReadonlyMap<string, string> = new Map([
  ["str", "힘"],
  ["dex", "민첩"],
  ["int", "지능"],
]);

/**
 * 세계 패널을 그린다.
 *
 * @param props 성장·순위·경매장과 처리기.
 * @returns 패널 요소.
 */
/**
 * 층이 적을 얼마나 세게 만드는지. **`balance.json` 의 `floor_scale` 과 같아야 한다** —
 * 화면이 다른 숫자를 말하면 사람은 그 숫자로 계획을 세운다.
 */
const FLOOR_HP_PCT = 25
const FLOOR_ATTACK_PCT = 20

export function WorldPanel(props: WorldPanelProps): React.JSX.Element {
  const { progress, leaderboard, auction, link } = props;
  const [pending, setPending] = useState<Record<string, number>>({});
  const left = (progress?.statPoints ?? 0) - (progress?.spentPoints ?? 0);
  const staged = Object.values(pending).reduce((sum, value) => sum + value, 0);

  /**
   * 능력치 하나를 한 점 올린다. 남은 포인트를 넘기지 않는다.
   *
   * @param key 능력치 열쇠.
   */
  function addPoint(key: string): void {
    if (staged >= left) {
      return;
    }
    setPending((current) => ({ ...current, [key]: (current[key] ?? 0) + 1 }));
  }

  return (
    <Panel
      title="세계"
      meta={leaderboard === undefined ? "" : `시즌 ${leaderboard.coreVersion}`}
      tone="panel"
      padded
      scroll
    >
      <div className="wld">
        {!checkLinked(link) || progress === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            <div className="wld__row">
              <span className="wld__label">레벨</span>
              <ValueExpr
                text={`${String(progress.level)} · ${String(progress.remainingXp)} / ${String(progress.nextXp)}`}
                size="sm"
              />
            </div>
            {/* **여기까지 내려가 봤다** (설계/6_몬스터 §3). 층이 오르면 적이 세지고
                더 깊은 방이 열리는데, 그 사실을 말하는 자리가 없으면 사람은 자기가
                어디까지 왔는지 모른 채 같은 판을 돈다. */}
            <div className="wld__row">
              <span className="wld__label">깊이</span>
              <ValueExpr
                text={`${String(progress.reachedFloor)} / ${String(progress.floorCap)}층`}
                size="sm"
              />
              <ValueExpr
                text={
                  progress.reachedFloor >= progress.floorCap
                    ? '끝까지 왔다'
                    : `층마다 적이 HP +${String(FLOOR_HP_PCT)}% · 공격 +${String(FLOOR_ATTACK_PCT)}% 로 세진다`
                }
                size="sm"
                dim
              />
            </div>
            <div className="wld__row">
              <span className="wld__label">표현력</span>
              <ValueExpr
                text={`슬롯 +${String(progress.bonusRuleSlots)} · CPU +${String(progress.bonusCpu)}`}
                size="sm"
                dim
              />
            </div>

            <div className="wld__head">
              능력치 · 남은 포인트 {String(left - staged)}
            </div>
            <ul className="wld__list">
              {progress.statKeys.map((key) => (
                <li className="wld__row" key={key}>
                  <span className="wld__label">
                    {STAT_LABELS.get(key) ?? key}
                  </span>
                  <ValueExpr
                    text={`${String((progress.stats[key] ?? 0) + (pending[key] ?? 0))}`}
                    size="sm"
                  />
                  <ValueExpr
                    text={formatAttributeEffect(
                      key,
                      (progress.stats[key] ?? 0) + (pending[key] ?? 0),
                    )}
                    size="sm"
                    dim
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    glyph="＋"
                    disabled={staged >= left}
                    onClick={() => {
                      addPoint(key);
                    }}
                  />
                </li>
              ))}
            </ul>
            {staged === 0 ? null : (
              <div className="wld__actions">
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    const next: Record<string, number> = { ...progress.stats };
                    for (const [key, value] of Object.entries(pending)) {
                      next[key] = (next[key] ?? 0) + value;
                    }
                    props.onAllocate(next);
                    setPending({});
                  }}
                >
                  배분 확정
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setPending({});
                  }}
                >
                  취소
                </Button>
              </div>
            )}

            <div className="wld__head">순위 — 점수는 누적 경험치다</div>
            {leaderboard === undefined || leaderboard.entries.length === 0 ? (
              <ValueExpr text="아직 기록이 없다" size="sm" dim />
            ) : (
              <ul className="wld__list">
                {leaderboard.entries.slice(0, 10).map((entry) => (
                  <li className="wld__row" key={entry.accountId}>
                    <span className="wld__label">{String(entry.rank)}</span>
                    <span className="wld__name">{entry.handle}</span>
                    <ValueExpr
                      text={`lv${String(entry.level)} · ${String(entry.score)}`}
                      size="sm"
                      dim
                    />
                    {entry.accountId === props.accountId ? (
                      <GlyphState state="true" size="sm" label="나" />
                    ) : null}
                  </li>
                ))}
              </ul>
            )}

            <div className="wld__head">
              경매장 · 수수료 {String(auction?.feePercent ?? 0)}%
            </div>
            {auction === undefined || auction.listings.length === 0 ? (
              <ValueExpr text="걸린 매물이 없다" size="sm" dim />
            ) : (
              <ul className="wld__list">
                {auction.listings.slice(0, 12).map((item) => (
                  // **세로에서는 줄을 쌓는다.** 한 줄에 이름·접사·값·만료·버튼을 다 넣으면
                  // 좁은 폭에서 오른쪽 끝의 버튼이 밀려 나가고, 그것이 가장 중요한 것이다.
                  <li className="wld__listing" key={item.listingId}>
                    <div className="wld__row">
                      <span className="wld__name">{item.labelKo}</span>
                      <ValueExpr text={`${String(item.price)} 화폐`} size="sm" />
                    </div>
                    {item.affixes.length === 0 ? null : (
                      // 저주 접사는 음수다. 모르고 사면 돈을 내고 약해진다.
                      <ValueExpr
                        text={item.affixes.map(formatAffix).join(' · ')}
                        size="sm"
                      />
                    )}
                    <div className="wld__row">
                      <ValueExpr
                        text={
                          item.isMine
                            ? `내 매물 · 수수료 ${String(item.fee)} 는 안 돌아온다`
                            : `${String(item.expiresInMinutes)}분 뒤 사라진다`
                        }
                        size="sm"
                        dim
                      />
                      {item.isMine ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          glyph="↰"
                          title="내린다 (수수료는 안 돌려준다)"
                          onClick={() => {
                            props.onCancel(item.listingId);
                          }}
                        >
                          내리기
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="primary"
                          glyph="↧"
                          disabled={(auction.balance ?? 0) < item.price}
                          onClick={() => {
                            props.onBuy(item.listingId);
                          }}
                        >
                          구매
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="wld__actions">
              <Button
                size="sm"
                variant="secondary"
                glyph="◷"
                onClick={props.onDaily}
              >
                오늘의 도전
              </Button>
            </div>
          </>
        )}
        {props.detail === "" ? null : (
          <div className="wld__warn">
            <GlyphState state="danger" size="sm" label={props.detail} />
          </div>
        )}
      </div>
    </Panel>
  );
}
