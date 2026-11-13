# FinSight web client — design rules

Binding for everything under `web/`. Rules are taken from Apple's Human Interface Guidelines
(citations are `file.md › Heading` in the apple-design-review references) and the
apple-design-motion skill. This is a web app, so Apple's principles and foundations apply;
native-only conventions do not.

## Departures from the HIG

These are the owner's explicit choices. Each one overrides the HIG default for that topic.

- Custom fonts. Inter and JetBrains Mono are used instead of the system font stack.
- Glass on content. Cards and sections use the glass surface, not only floating bars and dialogs.
- Dark-first brand look. Dark is the signature theme. Light carries the same color roles.

## Thesis and signature

- The app answers one question first: how much can I safely spend today?
- Signature element: the Safe-to-Spend figure on Home, set in large tabular numerals, with one
  horizontal breakdown bar beneath it (cash, minus card dues, minus upcoming bills, minus goal
  locks). Every segment has a text label and amount; color is never the only carrier.
- Everything else is quiet: one UI typeface, neutral surfaces, one accent.

## Accessibility (failures block acceptance)

- Text contrast at least 4.5:1; 3:1 only for text 18px+ or bold. Dark theme: 4.5:1 minimum,
  aim for 7:1 on small text. `accessibility.md › Vision`, `dark-mode.md › Best practices`
- Contrast is computed from the token hex values in a test, never estimated.
- All sizes in `rem`; layout survives 200% text zoom with rows growing and columns stacking.
  `typography.md › Supporting Dynamic Type`, `layout.md › Adaptability`
- Hit targets at least 44x44 CSS px on touch widths; never below 28x28. `buttons.md › Best practices`
- Nothing by color alone: amounts carry a sign or the words "in"/"out"; status has text or an icon
  with a label. `color.md › Inclusive color`
- Icon-only controls have an `aria-label`. Everything works from the keyboard with a visible
  `:focus-visible` ring. `accessibility.md › Vision`, `accessibility.md › Speech`
- Any swipe has a button alternative. Nothing auto-dismisses on a timer. `accessibility.md › Mobility`,
  `accessibility.md › Cognitive`

## Layout

- Layout follows available width, not device. One column on narrow widths, two equal tracks on Home
  from 64rem, and content capped at 68rem. Same functions at every width. The Home KPI row is the one
  three-track row, from 48rem. `layout.md › Size classes`
- Home order, top to bottom: the Safe to Spend hero across the full width; a row of three KPI tiles
  (Net Worth, This Month's Spending, This Month's Income); Spending by Category beside Six-Month Trend;
  Highlights beside Upcoming Bills; then a slim full-width Review row. The two pairs stack below 64rem.
- Each KPI tile is a glass card with an eyebrow label, a mono amount (24px bold, 28px from 64rem) and
  at most one context line. Net Worth has no context line. Spending shows its share of income ("N% of
  this month's income"). Income shows "Saved" or "Overspent" with the difference.
- Transactions filters sit in one glass toolbar card (`.tx-filters`, `transactions.css`). Below 48rem they
  stack. From 48rem the search spans the top row and the two selects and the checkbox share the row below.
- Most important content top and leading. Respect `env(safe-area-inset-*)`. `layout.md › Visual hierarchy`,
  `layout.md › Guides and safe areas`
- Page gutter 16px; no horizontal page scroll at 320px wide.

## Navigation

- Five tabs: Home, Transactions, Accounts, Plan, Assistant. Tabs navigate; they never perform
  actions. `tab-bars.md › Best practices`
- Below 48rem (768px): the header is a plain brand row with no glass. The five tabs are a fixed glass
  bar at the bottom, always visible. Each tab is an icon above a single-word label (11px, or 10px at
  22.5rem and below). Labels never wrap (`white-space: nowrap`). The page reserves room for the bar, so
  content is never hidden under it. `tab-bars.md › Phone (iOS)`
- At 48rem (768px) and wider: the header becomes a floating glass pill across the top, centred to the
  content width, with the brand on the left, the five tabs in a row on a `--well` fill, and Sign Out at
  the far right. The current tab is a filled accent pill. There is no sidebar. From 48rem to 60rem the
  wordmark is hidden from sight and kept for screen readers; the icons and labels stay.
  `tab-bars.md › Tablet (iPadOS)`
- Sign Out is a plain button (`.btn-plain`) in the app header on every page. It is not a tab and not part
  of any page. Below 48rem it sits at the right end of the brand row.
- Never hide or disable a tab; an empty section explains itself and offers the next step.
  `tab-bars.md › Best practices`, `writing.md › Best practices`
- The current tab is marked with `aria-current="page"` and by weight (700), not color alone.

## Typography

- Two typefaces, both loaded in `web/src/main.tsx` through `@fontsource-variable`:
  - UI: `--font-ui` is `"Inter Variable"`, then Inter, then the system stack
    (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif`).
  - Figures: `--font-mono` is `"JetBrains Mono Variable"`, then JetBrains Mono, then `ui-monospace`,
    `"Cascadia Mono"`, Consolas, monospace.
- Money uses the mono font with `font-variant-numeric: tabular-nums` (the `.num` class). Large titles
  also use tabular numerals.
- Scale (px / line-height), as rem, from `base.css`: Large Title 34/44 (2.125 / 2.75rem, bold; the line
  height is `--header-height`), Title 28/34 (bold), Title 2 22/28 (650), Headline 17/22 (semibold),
  Subhead 15/20 (semibold), Footnote 13/18, Eyebrow 11.52/16 (0.72rem, semibold 600, uppercase, card
  labels). Body is the default 16px with line-height 1.5. Nothing below 11px, except the tab labels at
  22.5rem (360px) and below, which are 10px. `typography.md › Specifications`
- Weights: 400 (body, the default), 500 (tab labels), 600, 650 and 700 are used. The rule was Regular,
  Medium, Semibold, Bold only. The 650 weight (Title 2 and the wordmark) is a known exception that the
  variable font allows. `typography.md › Ensuring legibility`
- Row text may wrap; do not truncate inside scrolling lists. `typography.md › Supporting Dynamic Type`

## Color

- Colors are CSS custom properties named by role; components never use raw hex. One color means
  one thing. `color.md › System colors`, `color.md › Best practices`
- Light and dark follow `prefers-color-scheme`; there is no in-app theme switch.
  `dark-mode.md › Best practices`
- Dark is not an inversion: dimmer surfaces, brighter text. `dark-mode.md › Dark Mode colors`
- Palette: sky blue accent, white for contrast, black as the quiet base.
- Token values from `web/src/styles/tokens.css` (light / dark):

  | Token | Light | Dark |
  |---|---|---|
  | `--surface` | #FFFFFF | #0E1319 |
  | `--surface-grouped` | #EEF3F8 | #05080C |
  | `--text` | #0A0F14 | #F5F9FC |
  | `--text-secondary` | #46535F | #A9B6C2 |
  | `--separator` | #C5CFD9 | #232C36 (never used for text) |
  | `--accent` | #0064A8 | #5CC8FF (primary actions, links, current tab) |
  | `--positive` | #0A6B2E | #86E08F |
  | `--negative` | #B3261E | #FF9C92 |
  | `--warning` | #7A4A00 | #F2C66D |
  | `--on-accent` | #FFFFFF | #021523 (text on accent fills) |

- `src/styles/contrast.test.ts` parses these hex values. It checks every text role against its
  surface at 4.5:1, and `--on-accent` against `--accent` and `--accent-fill-top`. If a pair fails,
  adjust the value, not the threshold.
- `prefers-contrast: more`: solid surfaces, 1px borders in `--text` on cards, controls and the tab
  bar, and a 2px outline on the current tab.

## Glass, spacing and alignment

- One glass recipe, in `base.css`. Cards, sections and the sign-in card share it: a `--glass` fill,
  1px `--border`, `--radius-lg` corners, an inset top highlight in `--glass-edge`, `--shadow-raised`,
  and `backdrop-filter: blur(var(--glass-blur)) saturate(160%)`. Blur is 28px in light and 32px in dark.
- Floating chrome (the bottom tab bar on narrow widths, the header pill on wide widths, and dialogs)
  uses `--glass-strong` and `--shadow-float`.
- Spacing comes only from `--space-1` to `--space-6` (0.25rem to 2rem), `--card-pad` (1.25rem) and
  `--section-gap` (1rem). The page edge uses `--gutter` (1rem). The style sheets contain no literal
  rem spacing values; the only px values are 1px borders and hairlines.
- Every page renders inside one `.page` column (`AppShell.tsx`), centred and capped at `--content-wide`
  (68rem), with the same gutters as the header.
- Grids use `minmax(0, 1fr)` tracks. Home switches to two equal tracks from 64rem. Cards in the same row
  stretch to share their top and bottom edges. Accounts summary lists use two tracks from 600px.
- One card header pattern: an uppercase accent label with a leading rule (`.eyebrow`). The sections
  `.section-title` and `.plan-section-title` share its style.
- One header height, `--header-height` (2.75rem), in `base.css`. The page title (`.large-title`) uses it
  as its line height, and the card labels and card headers (`.eyebrow`, `.section-title`, `.section-header`)
  use it as their minimum height, so their centre lines match. The header Sign Out button uses the same
  2.75rem, but its `.btn` rule writes the value out and does not read the token.
- The ambient background (`body::before`, `base.css`) is three static radial glows and a faint static
  grid. Nothing in it animates. It is hidden under `prefers-contrast: more`.
- `prefers-reduced-transparency: reduce` (and browsers without `backdrop-filter`) sets `--glass` and
  `--glass-strong` to the solid `--surface` and removes the blur. `prefers-contrast: more` follows the
  rules above. `motion.md › Best practices`

## Brand

- `web/src/components/BrandMark.tsx` draws the mark: a 32 by 32 SVG with a lens ring that opens at the
  top right, a line that rises through the opening, and a spark at its end. The ring and line use
  `currentColor`. The spark uses `--glint` (#38B6FF light, #C4ECFF dark) with a soft glow.
- `BrandLockup` sets the mark beside the wordmark "FinSight", with "Sight" in the accent color. The
  wordmark is real text, so it scales and screen readers read it once.
- Where it appears: the app header (`AppShell.tsx`, mark 1.75rem square) and the sign-in and setup
  screens (`AuthLayout.tsx`).
- Used alone, a mark with a `title` has `role="img"` and that label. Without a title it is `aria-hidden`.

## Assistant

The Assistant tab (`web/src/pages/AssistantPage.tsx`) has three cards.

- Local AI card. Shows one of five states: Checking, Ready (with the model name), Model missing (with
  `ollama pull <model>` and a Copy Command button), Not running (install steps), or Unavailable (with the
  server message). Check Again runs the check again. The card ends with the privacy line: "Your data
  never leaves this device. The assistant reads your numbers; it cannot change them."
- This Month card. Always shows the rule-based highlights, which need no model. When the AI is ready, a
  "Summarise My Month" button asks for a written summary: a headline, key observations, suggested
  actions and the disclaimer. Without the AI it says the summary is available once the AI is ready.
- Ask the Assistant card. Four suggestion chips each send their question. The question box takes up to
  500 characters. Enter sends and Shift+Enter adds a line. Each new question carries the last six
  messages. Clear Conversation empties the log. A failure shows its message with Try Again.
- One request at a time. While a chat or a summary runs, Send, the chips, the summary button and Clear
  Conversation are disabled. The server also refuses a second request while one runs.
- When the AI is not ready, the question box and chips are disabled, and the hint points to the status card.
- The disclaimer is shown only with monthly summaries. Chat answers do not show it.
- The conversation is kept in the page only. Reloading the page clears it.
- Answers are plain text. Line breaks are kept, and model output is never rendered as HTML.
- While a request runs, the page says it can take up to two minutes, which matches the default timeout.

## Buttons and forms

- One prominent (filled accent) button per view; destructive actions are never the prominent
  one. `buttons.md › Style`, `buttons.md › Role`
- Disabled prominent button (`.btn-primary:disabled`): the accent fill fades to 45% strength and the
  label stays fully opaque. Other disabled buttons (`.btn:disabled`) drop to 55% opacity as a whole.
- Labels start with a verb and say what happens ("Add Expense", "Sign In"); title-case for
  buttons and titles, sentence case for body and errors. `buttons.md › Content`, `writing.md › Best practices`
- Every field has a visible `<label>`; placeholders only show format. `text-fields.md › Best practices`
- Never prefill a password. Use the right `type`, `inputmode` and `autocomplete`.
  `entering-data.md › Best practices`
- Offer a select when options are known. Validate on blur; show the error beside the field,
  say how to fix it, no "oops", no blame. `entering-data.md › Best practices`, `writing.md › Best practices`
- A slow action disables its button and changes its label ("Signing In…"). `buttons.md › Platform considerations`
- Money input: the user types rupees; convert to integer paise with string math, never floats.

## Lists, charts, feedback

- Transactions are text rows grouped by date; a row that opens detail shows a chevron.
  `lists-and-tables.md › Best practices`
- Charts only where they beat a list; bar or line; a one-line takeaway above; every chart has a
  text alternative (labels and values in the DOM). `charting-data.md › Best practices`
- Show a skeleton or the cached view immediately while loading. `loading.md › Best practices`
- Status stays next to its item; confirm only unexpected, irreversible loss.
  `feedback.md › Best practices`
- Empty states name the next step and give a button for it. `writing.md › Best practices`

## Motion

- Press feedback starts on pointer-down: `transform: scale(0.97)`, 120ms ease-out (`--t-fast`, `--ease-out`).
  Card links lift 1px on hover, only with a fine pointer.
- Only `transform` and `opacity` animate. No decorative or looping motion.
- `prefers-reduced-motion: reduce`: no transforms; no animation; opacity cross-fades of 150ms at most.
- `prefers-reduced-transparency: reduce`: no blur or translucent bars; solid surfaces.
  (apple-design-motion › Response, Frame-level smoothness, Reduced motion; `motion.md › Best practices`)
