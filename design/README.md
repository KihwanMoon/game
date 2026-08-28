# 디자인 시스템

출처: Claude Design 프로젝트 `fae25530-140a-4873-b9f9-684645b541c6`
디자인 시스템 ID `design-system-7a323244-94a4-426b-a3b5-1bb1c949c195`
전역 네임스페이스 `DesignSystem_7a3232`

## 가져온 것 / 두고 온 것

| 대상 | 상태 | 이유 |
|:--|:--|:--|
| `tokens/*.css`, `styles.css` | **가져옴** | 코드가 직접 소비하는 값. 여기가 정본이 아니라 사본이다 |
| `_adherence.oxlintrc.json` | 두고 옴 | React 앱에 붙이는 린트 설정. Phase 3 에 앱이 생기면 그때 가져온다 |
| `_ds_bundle.js` | 두고 옴 | 컴파일된 번들. 소스가 아니라 빌드 산출물이다 |
| `*.dc.html` 시트 7종 | 두고 옴 | 디자인 참조. 원본을 보는 편이 정확하다 |

토큰을 고칠 일이 생기면 **이 파일이 아니라 Design 프로젝트를 고치고 다시 가져온다.**
표준 문서와 같은 원칙이다 — 사람이 보는 정본과 기계가 쓰는 사본을 나눈다.

## 성격

기계 도면(technical drawing)이다. 게임 UI 의 관습을 대부분 쓰지 않는다.

- **황동(`--brass`)은 화면의 유일한 광원이고 한 화면에 3곳까지.** 예산이다.
- **그림자가 시스템에 없다.** 층위는 명도차와 1px 괘선으로만 만든다.
- **모눈 한 칸이 4px.** 그 사이 값은 없다.
- **움직임은 명도 전환(90ms)과 틱 교체(140ms)뿐.** 등속, 바운스·오버슛 금지.
- **색은 정보의 유일한 채널이 될 수 없다.** 참/거짓은 색 + 글리프 + 명도 3중으로
  표기한다 — 흑백 인쇄와 색약 조건에서도 구분되어야 한다.
- 이모지 금지. 아이콘은 유니코드 도형만.
- `border-radius` 는 2px 고정.

## 전투 화면 골격

```
┌──────────────────────────────────────────────── 56px  TopBar
│ 320px      │  가변(818px)        │ 300px
│ RuleTable  │  PlanGrid           │ LogPanel
│            │  12×9 @ 64px        │
├──────────────────────────────────────────────── 48px  StatusBar
```

열 사이는 1px 괘선 하나(`--gap-col`). 기준 해상도 1440×900.

## 컴포넌트 계약

`_adherence.oxlintrc.json` 이 강제하는 선언 props 다. 선언되지 않은 prop 은 린트가 막는다.

| 컴포넌트 | props | 열거값 |
|:--|:--|:--|
| `Button` | variant, size, active, disabled, glyph, block | variant: primary·secondary·ghost / size: md·sm |
| `Panel` | title, meta, tone, padded, scroll | tone: panel·raised·plan |
| `GlyphState` | state, label, size | state: true·false·armed·danger·pending |
| `SegmentedGauge` | value, max, tone, label, readout | tone: cpu·hp·danger·dim |
| `ValueExpr` | text, size, dim | — |
| `HpGauge` | value, max, width | — |
| `ResourceCount` | label, count, max, glyph | — |
| `SpeedControl` | value, onChange | — |
| `StatusBar` | hp, hpMax, potions, potionsMax, threat | — |
| `ThreatNotice` | text, ticks, glyph, tone | tone: danger·neutral |
| `TopBar` | location, tick, speed, onSpeedChange | — |
| `LogPanel` | entries | — |
| `LogRow` | tick, rule, expr, outcome, delta, fired | — |
| `RuleTable` / `RuleRow` | index, state, condition, action, cpu, armed, onClick | state: true·false·pending |
| `PlanGrid` / `PlanActor` | x, y, kind, label | kind: self·charge·shoot·summon |

## 시뮬레이션 코어에 거는 요구

디자인이 UI 취향이 아니라 **코어의 출력 계약**을 정하는 지점들이다. Phase 1 에서
이벤트 로그를 설계할 때 이미 반영해야 한다 — 나중에 붙이면 RuleVM 을 다시 짜야 한다.

1. **조건문에 실측값을 병기한다.** `RuleRow.condition` 이 받는 문자열은
   `적거리(2) <= 사거리(3)` 형태다. 즉 RuleVM 은 참/거짓만이 아니라 **각 항이 실제로
   무슨 값이었는지**를 함께 내보내야 한다. GDD §8.2 가 요구하는 것과 같고, P1(실패는
   정보다)의 실현 수단이다.
2. **규칙 하나의 상태가 3종이다** — 참·발동(`armed`), 참·미발동, 거짓. "더 높은
   우선순위가 이미 발동해서 실행되지 않았다"를 UI 가 구분해 보여주므로, 코어도
   그 구분을 내보내야 한다.
3. **CPU 예산 초과 상태를 값으로 낸다.** `cpu 10 / 8` 처럼 초과분을 그대로 표시하고
   그 상태에서도 편집이 계속 가능하다. 코어는 초과를 오류로 막지 말고 수치로 보고한다.
4. **텔레그래프는 남은 틱 수를 낸다.** `ThreatNotice.ticks`.
5. **`LogRow` 가 `tick, rule, expr, outcome, delta, fired` 를 받는다.** 이벤트 로그
   레코드의 필드가 사실상 여기서 정해졌다.

## 검토 결과 — 기획서와 어긋나는 지점

디자인을 읽으면서 나온 것이다. 어느 쪽이 맞는지는 결정이 필요하다.

### D-1. 적 유형이 3종만 표현된다

`PlanActor.kind` 는 `self · charge · shoot · summon` 뿐이다. GDD §5 는 적을 6종으로
정의한다 — 돌진·사격·소환·**자폭·치유·보스**. 뒤 세 종은 도면에 그릴 방법이 없다.

자폭형은 GDD §4.2 텔레그래프의 주 사용처이고 보스는 페이즈별 규칙표 교체가 핵심이므로,
빠뜨린 것이 아니라면 Phase 1 범위(적 3종)에 맞춘 것으로 보인다. Phase 4 에서 8종 +
보스 3종을 채울 때 `kind` 열거를 확장해야 한다.

### D-2. 도면 격자가 12×9 로 고정이다

토큰이 `--plan-cols:12`, `--plan-rows:9`, `--plan-cell:64px` 로 못박혀 있다.
GDD §9 의 룸 템플릿 12×9 와는 일치하지만, **TDD §6 은 방 크기를 최대 20×15 로 적었다.**

기준 해상도에서 가운데 열 가용 폭은 `1440 - 320 - 300 - 2 = 818px` 이다.

| 방 크기 | 64px 셀 기준 | 결과 |
|:--|:--|:--|
| 12×9 | 768×576 | 들어감 |
| 16×12 | 1024×768 | 넘침 |
| 20×15 | 1280×960 | 넘침 |

셀 크기를 고정한 채로는 12×9 를 넘길 수 없다. 방 크기 상한을 12×9 로 내리든지,
셀 크기를 가변으로 바꾸든지 둘 중 하나를 정해야 한다. 후자를 고르면 4px 모듈 규칙과
충돌하므로(64px 은 4의 배수지만 가변 셀은 아니게 된다) 디자인 쪽 결정이 필요하다.

### D-3. 플랫폼이 갈린다

GDD §1 은 플랫폼을 **"PC (웹 빌드 우선, 이후 Steam)"** 로 적었는데, Design 프로젝트에는
`모바일 화면.dc.html` 과 `모바일 시뮬레이션.dc.html` 이 있다. 토큰은 전부 1440×900
기준 고정 px 이고 브레이크포인트가 없다 — 모바일 화면은 다른 배율 체계를 쓸 것이다.

모바일이 정식 타깃이면 GDD §1 과 활자 계단(§ 활자배율 M)을 함께 고쳐야 한다.

### D-4. 디자인은 전투 화면만 덮는다

컴포넌트 17종이 전부 전투 화면·규칙표·로그용이다. 로드맵 Phase 2 가 요구하는
**몬스터 도감, 보상 선택, 프리셋 8슬롯, 사후 분석 리플레이 슬라이더**에 대응하는
컴포넌트가 없다. W5·W8 에 들어가기 전에 디자인이 필요하다.
