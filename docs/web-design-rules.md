# FinSight web client — design rules

Binding for everything under `web/`. Rules are taken from Apple's Human Interface Guidelines
(citations are `file.md › Heading` in the apple-design-review references) and the
apple-design-motion skill. This is a web app, so Apple's principles and foundations apply;
native-only conventions do not.

## Thesis and signature

- The app answers one question first: how much can I safely spend today?
- Signature element: the Safe-to-Spend figure on Home, set in large tabular numerals, with one
  horizontal breakdown bar beneath it (cash, minus card dues, minus upcoming bills, minus goal
  locks). Every segment has a text label and amount; color is never the only carrier.
- Everything else is quiet: system type, neutral surfaces, one accent.

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

- Layout follows available width, not device: one column below 600px, wider content with a
  max readable width above. Same functions at every width. `layout.md › Size classes`
- Most important content top and leading. Respect `env(safe-area-inset-*)`. `layout.md › Visual hierarchy`,
  `layout.md › Guides and safe areas`
- Page gutter 16px; no horizontal page scroll at 320px wide.

## Navigation

- Five tabs: Home, Transactions, Accounts, Plan, Assistant. Tabs navigate; they never perform
  actions. `tab-bars.md › Best practices`
- Below 768px: tab bar fixed at the bottom, always visible, single-word labels with an icon.
  At 768px and wider: the same five items become a leading sidebar. `tab-bars.md › Phone (iOS)`,
  `tab-bars.md › Tablet (iPadOS)`
- Never hide or disable a tab; an empty section explains itself and offers the next step.
  `tab-bars.md › Best practices`, `writing.md › Best practices`
- The current tab is marked with `aria-current="page"` and by weight, not color alone.

## Typography

- System font stack only: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif`.
  Money uses `font-variant-numeric: tabular-nums`.
- Scale (px / line-height), as rem: Large Title 34/41, Title 28/34, Title 2 22/28, Headline 17/22
  semibold, Body 17/22, Subhead 15/20, Footnote 13/18, Caption 12/16. Nothing below 11px.
  `typography.md › Specifications`
- Weights Regular, Medium, Semibold, Bold only. `typography.md › Ensuring legibility`
- Row text may wrap; do not truncate inside scrolling lists. `typography.md › Supporting Dynamic Type`

## Color

- Colors are CSS custom properties named by role; components never use raw hex. One color means
  one thing. `color.md › System colors`, `color.md › Best practices`
- Light and dark follow `prefers-color-scheme`; there is no in-app theme switch.
  `dark-mode.md › Best practices`
- Dark is not an inversion: dimmer surfaces, brighter text. `dark-mode.md › Dark Mode colors`
- Starting tokens (light / dark). Verify every text-on-surface pair in the contrast test and
  adjust the value, not the threshold, if one fails:
  - `--surface` #FFFFFF / #1C1C1E, `--surface-grouped` #F2F2F7 / #000000
  - `--text` #1C1C1E / #F2F2F7, `--text-secondary` #5A5A60 / #AEAEB2
  - `--separator` #C6C6C8 / #38383A (never used for text)
  - `--accent` #0B57D0 / #7FB0FF (primary actions, links, current tab)
  - `--positive` #0A6B2E / #5DD68A, `--negative` #B3261E / #FF8A80, `--warning` #8A5300 / #FFC266
- `prefers-contrast: more`: solid surfaces, 1px borders in `--text` on controls and cards.

## Buttons and forms

- One prominent (filled accent) button per view; destructive actions are never the prominent
  one. `buttons.md › Style`, `buttons.md › Role`
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

- Press feedback starts on pointer-down: `transform: scale(0.97)`, 100ms ease-out.
- Only `transform` and `opacity` animate. No decorative or looping motion.
- `prefers-reduced-motion: reduce`: no transforms; opacity cross-fades of 150ms at most.
- `prefers-reduced-transparency: reduce`: no blur or translucent bars; solid surfaces.
  (apple-design-motion › Response, Frame-level smoothness, Reduced motion; `motion.md › Best practices`)
