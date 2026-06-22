# Phase 1 — UI Review: StrategyOptimizerPage Layout Audit

**Audited:** 2026-06-15
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md found)
**Screenshots:** not captured (no dev server running)
**Source:** `apps/dsa-web/src/pages/StrategyOptimizerPage.tsx` (808 lines)
**Report:** "底部菜单和输入框混乱" — bottom menu/tab and input fields disordered

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All labels contextual Chinese, no generic English labels |
| 2. Visuals | 3/4 | SignalFilter 5-field grid asymmetry; arbitrary `text-[11px]` |
| 3. Color | 4/4 | All colors via Tailwind semantic classes / CSS vars; no hardcoded hex |
| 4. Typography | 3/4 | `text-[11px]` outside design system scale; 5 sizes + 3 weights borderline |
| 5. Spacing | 2/4 | Double padding eats ~20% mobile viewport; SignalFilter unbalanced grid; inconsistent result list spacing |
| 6. Experience Design | 3/4 | Tab switcher no overflow strategy; tools section no error boundary; no aria-labels on tabs |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **BLOCKER: SignalFilter grid asymmetry** — 5 fields in `grid-cols-1 sm:grid-cols-2` leaves 6th cell empty → bottom row has 1 field floating alone. **Fix:** Add a 6th field (e.g., "备注" or "信号强度") or change to `grid-cols-1` for mobile parity and only use `md:grid-cols-2` with `grid-cols-1` fallback and adjust field count to even.

2. **BLOCKER: Tab switcher no overflow handling at narrow widths** — `w-fit` on the tab container (line 575) will hang off-screen if viewport < ~280px content area. **Fix:** Add `flex-wrap justify-center` or `overflow-x-auto max-w-full` to the tab container. Consider `sticky top-0 z-10` to keep tabs accessible on scroll (mitigates "bottom menu" confusion).

3. **WARNING: Double padding wastes mobile space** — Shell applies `px-3` (line 86) then page applies `p-6` (line 548) → 36px per side on mobile = 72px total lost from 375px viewport. **Fix:** Remove `p-6` from page container and use `px-0` with vertical padding only, or consume shell padding via negative margins.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

No issues. All CTAs and labels use domain-specific Chinese:
- Buttons: "执行纪律检查", "信号过滤检查", "刷新" — descriptive, not generic
- Placeholders: "如 000001", "如 3.2" — concrete examples
- Empty states: "暂无来源权重数据", "暂无优化参数" — contextual
- Error messages: "网络请求失败，请重试" — human-readable

No generic English labels (`Submit`, `Cancel`, `OK`, `Click Here`) found.

### Pillar 2: Visuals (3/4)

**WARNING: SignalFilter grid asymmetry**
- `StrategyOptimizerPage.tsx:397` — `grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4`
- 5 fields: code Input, source Select, sentiment_score Input, bias_ma5 Input, vol_ratio Input
- Odd count in 2-column grid → 6th cell empty, bottom row visually orphaned
- DisciplineChecker (same layout) has 6 fields → 3 clean rows → contrast makes SignalFilter look broken

| Row | Column 1 | Column 2 |
|-----|----------|----------|
| 1 | 股票代码 (Input) | 来源 (Select) |
| 2 | 情绪评分 (Input) | 乖离率MA5 (Input) |
| 3 | 量比 (Input) | **EMPTY** ← orphans |

**WARNING: Arbitrary value `text-[11px]`**
- `StrategyOptimizerPage.tsx:720, 763` — footnote text uses `text-[11px]` instead of `text-xs` (12px)
- Design system has `text-xs` (12px) as the smallest standard size
- Causes visual inconsistency with rest of app

**PASS:** Card layout consistent — both tools use `Card variant="glass" padding="lg" className="h-full"`
**PASS:** Tab active state uses cyan highlight — clear which tab is selected
**PASS:** Icon + label pairing in tabs consistent

### Pillar 3: Color (4/4)

- All colors via Tailwind classes: `text-cyan-400`, `text-emerald-400`, `text-red-400`, `bg-gray-800/50`, etc.
- Semantic mapping: danger→red, success→emerald, warning→amber, primary→cyan
- Health gauge uses CSS variable `hc.stroke` — dynamic but within system
- No hardcoded hex `#[0-9a-fA-F]{6}` found in page
- Opacity values all Tailwind-native (e.g. `/20`, `/80`)

### Pillar 4: Typography (3/4)

**Font sizes in use:**
| Size | Count | Usage |
|------|-------|-------|
| text-[11px] | 2 | Footnote text (lines 720, 763) — arbitrary, not in design system |
| text-xs (12px) | 13 | Table headers, metadata, badges |
| text-sm (14px) | 15 | Body text, input labels, table cells |
| text-lg (18px) | 6 | Card titles |
| text-xl (20px) | 1 | Stop param values |
| text-2xl (24px) | 2 | StatCard values |
| text-3xl (30px) | 1 | Page header title |

**Font weights:**
| Weight | Count |
|--------|-------|
| font-medium | 21 |
| font-semibold | 11 |
| font-bold | 5 |

**Issues:**
- `text-[11px]` at lines 720, 763 breaks the scale — use `text-xs` or remove arbitrary values
- 6 distinct font sizes + 3 weights is borderline for a utility-first CSS stack — maintainable but watch for inflation

### Pillar 5: Spacing (2/4)

**BLOCKER: Double padding on mobile**
- Shell.tsx:86 — outer container `px-3 py-3 sm:px-4 sm:py-4 lg:px-5`
- StrategyOptimizerPage.tsx:548 — inner container `p-6 max-w-7xl mx-auto space-y-6`
- Combined horizontal padding at 375px viewport: 12px (shell) + 24px (page) = **36px per side = 72px total**
- Usable width: **303px** from 375px — 19% of viewport consumed by padding
- At 320px (iPhone SE): only **248px** usable → inputs cramped, labels may wrap

**BLOCKER: SignalFilter unbalanced grid spacing**
- Same grid structure as DisciplineChecker (gap-3, col-span) but with 5 items
- `StrategyOptimizerPage.tsx:397-413`
- Results in orphaned last item, wasting 50% of bottom row space

**WARNING: Inconsistent result list spacing**
- DisciplineChecker (`StrategyOptimizerPage.tsx:329`): `space-y-1.5`
- SignalFilter (`StrategyOptimizerPage.tsx:443`): `space-y-1`
- Same section (result display), different spacing — users perceive inconsistency

**WARNING: Tab switcher lacks bottom margin**
- `StrategyOptimizerPage.tsx:575` — tab switcher has no `mb-*` class
- Relies on parent `space-y-6` for spacing from both header above and content below
- If content above or below changes height, the 24px gap may appear inconsistent

**WARNING: Arbitrary spacing value**
- `StrategyOptimizerPage.tsx:117` — `hover:bg-white/[0.03]` (arbitrary opacity)
- Not in design system — use `hover:bg-white/5` instead if needed

**PASS:** Most grid layouts use consistent `gap-3`, `gap-6` values
**PASS:** StopParam grid uses `gap-3` consistent with other card grids
**PASS:** Issues/suggestions lists use consistent `gap-3` within items

### Pillar 6: Experience Design (3/4)

**WARNING: Tab switcher no responsive overflow protection**
- `StrategyOptimizerPage.tsx:575` — `flex gap-1 ... w-fit`
- No `flex-wrap`, no `overflow-x-auto`, no scroll behavior
- At 280–320px viewports, tab buttons will overflow right edge
- User reported "底部菜单混乱" may refer to tabs appearing cut off or out of place

**WARNING: No error boundary for interactive tools**
- `StrategyOptimizerPage.tsx:798-803` — DisciplineChecker and SignalFilter rendered directly
- If either throws during render (e.g., API state corruption), the entire tools tab or page crashes
- Should wrap each in `<ErrorBoundary>` with fallback UI

**WARNING: Tab buttons lack `aria-label`**
- Lines 577, 589 — `<button>` with only icon + text, no `aria-label`
- Screen readers read "策略仪表盘" correctly (good), but on narrow layouts where only icon might show, this is ambiguous
- Add `aria-label="切换至策略仪表盘"` and `role="tab"` / `aria-selected`

**PASS:** Loading state — `DashboardSkeleton` renders cleanly
**PASS:** Error state — `EmptyState` with retry button, specific error message
**PASS:** Empty data — weights (line 718), stop params (line 761), no-issues state (line 785) all handled
**PASS:** Disabled states — Input/Select `disabled` during API calls, Button `disabled` when `!code`
**PASS:** InlineAlert for report.errors shown in page header

---

## Files Audited

| File | Lines |
|------|-------|
| `apps/dsa-web/src/pages/StrategyOptimizerPage.tsx` | 808 |
| `apps/dsa-web/src/components/layout/Shell.tsx` | 127 |
| `apps/dsa-web/src/components/layout/SidebarNav.tsx` | 174 |
| `apps/dsa-web/src/components/common/Input.tsx` | 182 |
| `apps/dsa-web/src/components/common/Select.tsx` | 82 |
| `apps/dsa-web/src/components/common/Card.tsx` | 101 |
| `apps/dsa-web/src/components/common/PageHeader.tsx` | 31 |
| `apps/dsa-web/src/components/common/StatCard.tsx` | 47 |
| `apps/dsa-web/src/components/common/Button.tsx` | 141 |
| `apps/dsa-web/src/index.css` | 1022 |
| `apps/dsa-web/tailwind.config.js` | 178 |

---

## Recommendation Summary

| Priority | File | Line(s) | Issue | Severity |
|----------|------|---------|-------|----------|
| 1 | StrategyOptimizerPage.tsx | 397-413 | SignalFilter 5-field grid asymmetry | BLOCKER |
| 2 | StrategyOptimizerPage.tsx | 575 | Tab switcher `w-fit` no overflow handling | BLOCKER |
| 3 | Shell.tsx + StrategyOptimizerPage.tsx | 86 + 548 | Double padding on mobile | WARNING |
| 4 | StrategyOptimizerPage.tsx | 329 vs 443 | Inconsistent result list spacing | WARNING |
| 5 | StrategyOptimizerPage.tsx | 720, 763 | `text-[11px]` outside design system | WARNING |
| 6 | StrategyOptimizerPage.tsx | 577, 589 | Tab buttons missing `aria-label`/`role="tab"` | WARNING |
| 7 | StrategyOptimizerPage.tsx | 798-803 | No error boundary for tools components | WARNING |
