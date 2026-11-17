---
name: FreshEye
colors:
  seaglass: "#D5ECE8"
  seaglass-deep: "#C2E1DC"
  seaglass-soft: "#E8F4F1"
  paper: "#FCFBF9"
  paper-sunk: "#F1F4F1"
  navy: "#102A45"
  ink-soft: "#3F5468"
  ink-muted: "#52667A"
  coral: "#E86F51"
  coral-ink: "#AE3F26"
  coral-soft: "#FCECE8"
  level-very-fresh: "#17635F"
  level-fresh: "#1E6894"
  level-not-fresh: "#8F5508"
  level-none: "#52667A"
typography:
  display: { fontFamily: Playfair Display, fontSize: 60px, fontWeight: 800, lineHeight: 0.95 }
  page-title: { fontFamily: Playfair Display, fontSize: 40px, fontWeight: 700, lineHeight: 1.1 }
  title: { fontFamily: Playfair Display, fontSize: 24px, fontWeight: 700, lineHeight: 1.2 }
  row-title: { fontFamily: Playfair Display, fontSize: 20px, fontWeight: 700, lineHeight: 1.25 }
  numeral: { fontFamily: Be Vietnam Pro, fontSize: 34px, fontWeight: 600, lineHeight: 1 }
  body: { fontFamily: Be Vietnam Pro, fontSize: 16px, fontWeight: 400, lineHeight: 1.5 }
  small: { fontFamily: Be Vietnam Pro, fontSize: 14px, fontWeight: 400, lineHeight: 1.45 }
  caption: { fontFamily: Be Vietnam Pro, fontSize: 12px, fontWeight: 400, lineHeight: 1.4 }
  label: { fontFamily: Be Vietnam Pro, fontSize: 11px, fontWeight: 600, letterSpacing: 0.08em, textTransform: uppercase }
rounded: { card: 20px, control: 12px, pill: 9999px }
spacing: { gutter: 16px, card-pad: 20px, unit: 4px }
---

# FreshEye design system

Direction C, "Chợ cá biên tập": the printed label of a premium fishmonger. Light theme only.
Extracted from the eight Stitch screens in `design/stitch/` and normalised; machine-readable values
live in `tokens.css`, the rendered reference is `specimen/index.html`.

## Colour

- **Seaglass** is the page. **Paper** is every card. **Navy** is all text, all card outlines and the
  primary button. Nothing else is used for body text.
- **Coral** is the single accent: the active-tab mark, the "Phân tích" button, the circle behind the photo,
  large numerals. Coral never means a freshness level and never means an error.
- Small coral text uses **coral-ink**; plain coral fails contrast below 24 px.
- **ink-muted** is the lightest text allowed (4.8:1 on seaglass, 5.7:1 on paper).

### Freshness scale

| Level | Colour | Marker |
|---|---|---|
| Rất tươi | `#17635F` | filled circle |
| Tươi | `#1E6894` | half-filled circle |
| Không tươi | `#8F5508` | hollow ring |
| No conclusion (ASK_MORE, ABSTAIN) | `#52667A` | short dash, never a level colour |

The marker shape carries the level; colour only supports it. A level is always shown with its word.
All four colours reach at least 4.9:1 on seaglass and 5.8:1 on paper.

## Type

- **Playfair Display** for the verdict word, page titles, row titles and Latin species names (italic).
  **Be Vietnam Pro** for everything else, including every number.
- Numbers are never set in Playfair Display: its figures are old-style (digits rise and fall around the
  baseline) and the web font has no lining alternative. All digits must sit on one line at one height,
  because the audience includes middle-aged and older readers. Both ship a Vietnamese subset; verified by rendering
  "Kết quả kiểm tra, Rất tươi, Không tươi, Lượt, Ngưỡng, Ảnh lạ so với dữ liệu đã học".
- No text below 11 px. Numbers use tabular figures and the Vietnamese decimal comma ("0,35").
- The small uppercase label (11 px, tracked) names a card's content, as on the Stitch screens. No
  monospace face.

## Shape and depth

- Cards: paper, 1.5 px navy outline, 20 px radius, 20 px padding, no shadow.
- Controls: 12 px radius, 52 px minimum height. Chips are pills with a 1.5 px navy outline.
- Dividers inside cards are 1 px navy at 16% opacity.
- Focus: 3 px coral-ink outline, 2 px offset (4.5:1 on seaglass; plain coral reaches only 2.4:1).

## Components (see the specimen)

Primary button (navy fill), accent button (coral fill, navy text), secondary button (outline), chip and
active chip, text link, verdict card with three probability rows, unfamiliarity gauge with threshold tick,
history row, bottom navigation with coral active mark, the standing notice.

## Deviations from the Stitch screens

1. One background, one coral, one card colour. Stitch used five slightly different seaglass values and five
   corals across the eight screens.
2. A real three-step freshness scale. Stitch coloured "Tươi" with the coral accent and "Không tươi" with the
   same grey as "Từ chối kết luận", so the worst level looked neutral and the accent doubled as a status.
3. Higher text contrast. Stitch set secondary text as navy at 40–60% opacity (2.4:1 to 3.8:1) and small text
   in plain coral (3.0:1); these are replaced by ink-soft, ink-muted and coral-ink.
4. Minimum text size 11 px. Stitch used 9–10 px labels in several places.
5. The highlighted probability row uses a neutral seaglass tint instead of a coral tint.
6. No monospace face for small data.
7. Numbers are set in Be Vietnam Pro, not the serif (student decision, 2026-10-05).
8. Content the model does not produce is not carried over: the "Đạt chuẩn thương phẩm" badge, the line
   "Thấu kính trong suốt, giác mạc sáng", the common names "Cá đù vàng / Yellow Croaker", and "Mã vạch".
   The app only shows what the API returns.
9. No model internals in the interface (student decision, 2026-10-08). The unfamiliarity score, its
   threshold and the nearest species are never shown, on any screen. "Cần chụp thêm ảnh" and "Chưa thể
   kết luận" explain themselves in plain words only, with no confidence, score or threshold figures. The
   user only needs to know whether to take another photo.
10. The assistant is reached through a floating mark (white speech bubble with the robot, 72 px, soft
    shadow, no coral disc) and through two tappable starter questions under the explanation. The
    "Hỏi thêm" link is gone.

## States (F1.6, not designed in Stitch)

- **Whole-screen states** (loading, cannot connect, not found) use `StatePanel`: a 64 px outlined disc with
  one icon, a serif title, one sentence in ink-soft, and at most one action.
- **Inline problems** use `Alert`: coral-soft fill, coral-ink outline and text (5.2:1), warning icon. The
  text always says what happened and what to do next. An alert replaces the hint line it sits in; it never
  stacks on top of it.
- **The action follows the problem**: connection trouble keeps the same button for a retry; an unusable photo
  disables "Phân tích" until another photo is chosen; a finished inspection swaps it for "Lượt mới".
- **Waiting**: the analysing overlay adds "Lâu hơn thường lệ, bạn chờ thêm chút nhé." after 8 s.
- Messages never show status codes or technical terms.

## Charts (F3.2)

- Built in plain HTML and CSS; no chart library. Bars are 12 px thick, columns at most 24 px wide, both
  with a rounded data end and a square baseline end; tracks are navy at 10%.
- One series, one colour: every bar and column is navy. Identity comes from the label beside the bar (and
  the level marker for freshness), never from bar colour. Values are text in ink colours.
- The daily chart highlights the selected day in coral-ink and names it in a line of text above the plot;
  touching or hovering a column changes the selection. A screen-reader table carries every value.
- No confidence distribution and no threshold (student decision, 2026-10-08).

## Quality pass (F4.1)

- Checked at 360x640, 375x667, 390x844, 412x915 and 430x932 on every screen: no horizontal overflow, every
  control at least 44 px, no text under 11 px, no clipped labels, every text pair at or above WCAG AA.
- Keyboard: every control is reachable in reading order and shows the focus ring; the question field shows
  it on its pill; the daily chart takes focus and moves its selection with the left and right arrow keys.
- Reduced motion: with `prefers-reduced-motion`, spinners, typing dots and transitions hold still.
- Each screen names the browser tab after its heading.
- Known limit: at 320 px wide the floating assistant mark overlaps the edge of "Chụp thêm ảnh".
