---
name: State Talent Sheet
description: A comparison sheet of a state's talent ecosystem against its competitors and the U.S., with state profiles as its chapters.
colors:
  working-blue: "#2f5fd0"
  working-blue-ink: "#2a52b3"
  on-accent: "#ffffff"
  gain-green: "#17805a"
  loss-rust: "#b04a1c"
  caveat-amber: "#8a6100"
  us-grey: "#7c8494"
  series-1-focus: "#2f5fd0"
  series-2-orange: "#eb6834"
  series-3-green: "#1baf7a"
  series-4-violet: "#6250d6"
  series-5-pink: "#e87ba4"
  series-6-ochre: "#c98500"
  series-7-leaf: "#008300"
  series-8-red: "#e34948"
  series-rest: "#9aa1af"
  sheet-white: "#ffffff"
  panel-grey: "#f7f8fa"
  focus-tint: "#eef1f6"
  hover-tint: "#f3f5f9"
  ink: "#16181d"
  ink-2: "#464c59"
  ink-3: "#687082"
  rule: "#e3e6ec"
  rule-2: "#c2c8d2"
  tooltip: "#16181d"
  dark-sheet: "#15171c"
  dark-panel: "#1b1e24"
  dark-focus-tint: "#1f2636"
  dark-ink: "#e8eaef"
  dark-ink-3: "#959cab"
  dark-rule: "#2a2e37"
  dark-rule-2: "#3b404c"
  dark-working-blue: "#5585ee"
  dark-working-blue-ink: "#8fb0f7"
  dark-gain: "#4cc08f"
  dark-loss: "#f08a5d"
  dark-caveat: "#e0b24a"
  dark-series-2: "#d95926"
  dark-series-3: "#199e70"
  dark-series-4: "#9085e9"
  dark-series-5: "#d55181"
  dark-series-6: "#c98500"
typography:
  display:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "40px"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.005em"
  title:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "14.5px"
    fontWeight: 600
  brand:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 700
  lede:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "tnum"
  cell-value:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    fontFeature: "tnum"
  table:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    fontFeature: "tnum"
  control:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
  note:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.3
  cell-sub:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
    fontFeature: "tnum"
  chart:
    fontFamily: "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 400
rounded:
  mark: "2px"
  nav: "3px"
  control: "4px"
  pill: "999px"
spacing:
  hair: "3px"
  xs: "6px"
  sm: "8px"
  md: "10px"
  gutter: "16px"
  section: "22px"
  column: "32px"
components:
  button:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "32px"
  button-hover:
    backgroundColor: "{colors.hover-tint}"
    textColor: "{colors.ink}"
  button-primary:
    backgroundColor: "{colors.working-blue}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "32px"
  button-link:
    textColor: "{colors.working-blue-ink}"
    padding: "0 4px"
    height: "32px"
  segmented-option:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink-2}"
    typography: "{typography.control}"
    padding: "0 12px"
    height: "32px"
  segmented-option-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet-white}"
  select:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 28px 0 10px"
    height: "32px"
  input-search:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "32px"
  chip-competitor:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.pill}"
    padding: "0 6px 0 10px"
    height: "28px"
  chip-focus:
    backgroundColor: "{colors.working-blue}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.pill}"
    padding: "0 10px"
    height: "28px"
  sheet-cell:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    typography: "{typography.table}"
    padding: "7px 10px"
  sheet-cell-focus:
    backgroundColor: "{colors.focus-tint}"
    textColor: "{colors.ink}"
    padding: "7px 10px"
  section-nav-item:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.nav}"
    padding: "6px 10px"
  section-nav-item-current:
    backgroundColor: "{colors.focus-tint}"
    textColor: "{colors.ink}"
  tooltip:
    backgroundColor: "{colors.tooltip}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
---

# Design System: State Talent Sheet

## Overview

**Creative North Star: "The Comparison Sheet"**

The system is a white working sheet. Each chosen state gets a column, the U.S. gets the last one, and each measure gets a row. Every surface (the State Talent Sheet, the Flows view, the 51 state profiles) is read as a column of figures set against the columns beside it. The interface is ink on white with cool grey rules and one working blue. That blue marks the focus state wherever it appears (its tinted column, its thick trend line, its chip, the best-in-row dot) and colours links. Everything else is either neutral or a series colour tied to a competitor's identity.

Density is high but calm. Type is 11 to 15 px in one family (IBM Plex Sans, embedded so files work offline), set with tabular figures so columns align. Hierarchy comes from weight and 2 px ink rules, not from size jumps or boxes. Ornament is limited to the data. Charts are drawn in SVG, sit directly on the sheet with no card frame, and use the same series colours as the sheet header dots. Motion is functional. Sankey dots travel in the direction of flow, a disclosure caret rotates, and under reduced motion all of it stops.

The world replaces the earlier "Tabbed Reference Manual" (archived in `archive/templates/old_manual/`), including its per-section colour boards. None of that vocabulary belongs to this system.

**Key Characteristics:**
- One working blue, reserved for the focus state and links.
- Competitor colours are fixed to a state's identity while it stays in the set.
- Change reads by sign first, then by gain green or loss rust.
- Flat white sheet with cool rules. Popovers are the only surfaces with a shadow.
- IBM Plex Sans throughout, with tabular figures.
- Light and dark themes share every role. Dark swaps values, not structure.

## Colors

The palette is cool and nearly achromatic: ink and grey rules on white, one working blue, two semantic change colours, and a validated eight-slot series palette for the chosen states.

### Primary
- **Working Blue** (series-1-focus / working-blue): marks the focus state. It is the colour of the thick trend line, the focus chip fill, the focus sparkline and best-in-row dot, the active section-nav bar and the focus ring. In dark mode it becomes Dark Working Blue.
- **Working Blue Ink** (working-blue-ink): link text and in-text tags. It is a slightly deeper blue so links pass contrast on white (Dark Working Blue Ink on the dark sheet).

### Secondary
- **Gain Green** (gain-green) and **Loss Rust** (loss-rust): the colour of a change figure (a "+1.4 pts" or "−0.5 pts"), always after its sign. Dark mode uses lifted Dark Gain and Dark Loss.
- **Caveat Amber** (caveat-amber, token `--caveat`): reserved for data caveats only: the superscript p on provisional years, the † on states whose totals include a nationwide online university, and the profile's "Read with care" box. It is kept apart from Loss Rust so a caveat never reads as a decline. Dark mode uses Dark Caveat (#e0b24a). Contrast 5.5:1 on white, 9.1:1 on the dark ground.
- **Series palette** (series-2-orange, series-3-green, series-4-violet, series-5-pink, series-6-ochre, then series-7-leaf, series-8-red): competitor colours in slot order. The light and dark sets were checked with the dataviz palette validator. Slots 2 to 6 are the validated working set. Slots 7 and 8 are overflow for larger sets.
- **U.S. Grey** (us-grey): the United States column dot and its line, which is always dashed.
- **Rest Grey** (series-rest): every state not in the chosen set (ranking bars, scatter dots, "Other states" Sankey nodes, "Other fields"), plus competitor sparklines.

### Neutral
- **Sheet White** (sheet-white): page, sticky header, table header, controls.
- **Panel Grey** (panel-grey): a rare quiet fill.
- **Focus Tint** (focus-tint): the focus state's column in the sheet and the profile facts table, and the current section in the profile nav.
- **Hover Tint** (hover-tint): row hover, button hover, empty bar tracks, n/a matrix cells.
- **Ink** (ink): text, and the 2 px rules under table heads, group rows, open panels and profile sections. It is also the fill of the selected segmented option.
- **Ink 2 / Ink 3** (ink-2, ink-3): secondary copy and ledes / labels, ranks, notes, axis text, sources.
- **Rule / Rule 2** (rule, rule-2): 1 px row dividers / control borders, header bottom, dashed year markers.

### Named Rules
**The One Working Blue Rule.** Blue means "the focus state" or "a link", nothing else. A competitor never gets slot 1, and blue is never used for decoration.

**The Identity Colour Rule.** A competitor keeps its series slot for as long as it stays in the set. Removing one state never repaints the others, and a newly added state takes the lowest free slot from 2 to 8.

**The Sign First Rule.** A change figure always carries an explicit sign (+, −, ±0.0). Gain green or loss rust comes second, as reinforcement. The figure must still read correctly in greyscale.

## Typography

**Display Font:** IBM Plex Sans (with Helvetica Neue, Arial, sans-serif)
**Body Font:** IBM Plex Sans
**Label/Mono Font:** IBM Plex Sans. A monospace stack is defined but unused in shipped surfaces.

**Character:** A single grotesque used in four weights (400, 500, 600, 700, embedded as woff2), with tabular numerals applied globally. It reads like a well-set statistical table, not a marketing page.

### Hierarchy
- **Display** (700, 40px, 1.05, −0.015em; 32px below 860px): the state name at the top of a profile, and only there.
- **Headline** (700, 22px, −0.005em): profile section titles. The Flows view heading uses the same weight at 20px.
- **Title** (600, 13.5 to 15px): chart and card titles (14.5px for profile figures, 13.5px for in-row panel cards, 15px for flow cards).
- **Brand** (700, 16px): the product name in the sticky bar.
- **Lede** (400, 15px, 1.55, max 82ch): the one-paragraph plain-language reading under a profile section. Key figures inside it are set in 600 ink.
- **Body / Cell value** (400 / 500, 14px): sheet cell values are 500. The focus column's values are 700.
- **Table** (13.5px): sheet and facts table text. **Control** (13px): buttons, selects, chips, segmented options.
- **Note** (12.5px, ink-3): chart subtitles, footers (max 90 to 110ch), the Sankey key.
- **Label** (500, 12px, ink-3, sentence case): control labels such as "State", "Compared with" and "Base year".
- **Cell sub** (11.5px, ink-3): the rank and change line under each value, and measure year/unit lines. **Chart** (11px, ink-3): axis and data labels. Direct data labels are 600 ink.

### Named Rules
**The Tabular Figures Rule.** Every number is set with tabular numerals and right-aligned in its column, so values compare down a column without the eye having to move sideways.

**The Weight Not Size Rule.** Inside the sheet, emphasis comes from weight (the focus column is 700, other values 500) and colour, never from a larger size.

## Layout

There are two layouts, and both have a sticky control bar on top. The header bar wraps controls as label + control groups (gap 6px inside a group, 8 to 10px between groups). The page gutter is 16px, widened to the safe-area insets.

- **Sheet:** a full-width table with a 280px measure column and one right-aligned column per state plus the U.S. The table head sticks under the control bar. Measures are grouped under bold group rows. A clicked row opens in place into a two-column comparison panel (1.25fr / 1fr, gaps 18 / 28px) holding the trend, the all-51 ranking strip, a 12-column tile map and a scatter against another measure. The Flows view switches the same page into Sankey cards in a two-column grid (gap 32px), one column below 900px.
- **Profile:** a 190px sticky section nav beside a content column, max width 1560px with a 32px gap. Sections are separated by 2px ink rules with 22px top padding. Figures sit in a two-column grid (gaps 26 / 32px), with wide figures spanning both columns. At 1100px and below the grid becomes one column. At 860px and below the nav becomes a horizontal scrolling strip.
- **Mobile (below 900px):** the sheet scrolls sideways, with a "Swipe the table sideways" hint. The measure column narrows to 150px and hides its info marks. The open panel pins to the viewport width and stacks to one column.

Row rhythm is 7px cells, 16px above a group row, and 18px under an open panel.

## Elevation & Depth

The system is flat. Depth comes from tone (the focus tint column, hover tint) and from rules: 1px cool rules separate rows, and 2px ink rules close a header, group, open panel or section. The only shadow belongs to transient popovers.

### Shadow Vocabulary
- **Popover** (`box-shadow: 0 8px 28px -10px rgba(22,24,29,.28)`; dark `rgba(0,0,0,.6)`): the tooltip and the toast, and nothing else.

### Named Rules
**The Popover-Only Shadow Rule.** A shadow means "this is floating above the sheet for a moment". Cards, charts, controls and panels never cast one.

## Shapes

Corners are nearly square. Chart marks have slightly softened ends (2px: tiles, legend swatches, Sankey node bars, bar ends, matrix cells). The section nav uses 3px. Every control, tooltip, toast and the errata box uses 4px. Chips are the one fully rounded form (999px), and their colour dot is a circle (8px). The state dots in table heads are 8 to 9px circles. Icons are inline SVG line glyphs, 16px, 1.7 stroke, round caps and joins, in currentColor.

## Components

### Buttons
- **Shape:** gently squared (4px), 32px tall, 13px 500 text, optional leading 16px line icon with a 6px gap.
- **Default:** white with a Rule 2 border and ink text. On hover the border darkens to Ink 3 and the fill becomes Hover Tint.
- **Primary:** Working Blue fill and border with white text. On hover it brightens slightly (brightness 1.06).
- **Link:** borderless, Working Blue Ink text, 4px side padding (for example "Similar size").
- **Focus:** a 2px Working Blue outline at a 2px offset, applied globally.

### Segmented control
- **Style:** one 4px bordered strip of 32px options separated by Rule 2 hairlines, with Ink 2 text.
- **State:** the selected option fills solid Ink with white 500 text. Disabled options drop to 45% opacity. It is used for Value / Change / Rank, degree level, Sheet / Flows and per-chart level switches.

### Chips (competitor set)
- **Style:** a 28px pill with a Rule 2 border, a leading 8px dot in the state's series colour, and a 20px round remove button that tints on hover.
- **Focus variant:** filled Working Blue, white text, no remove button.

### Inputs / Selects
- **Style:** 32px, 4px radius, Rule 2 border, white fill, 13px text. Selects carry a drawn grey chevron with 28px right padding. The placeholder is Ink 3.
- **Hover / Focus:** the border goes to Ink 3, and the global blue focus outline applies.

### Comparison Sheet (signature)
- **Head:** sticky, 600 weight, a series dot before each state name, the state name linking to its profile, closed by a 2px ink rule. The focus column is tinted.
- **Cell:** value (14px 500, 700 in the focus column), a 1.4px sparkline (focus in blue, others in Rest Grey, with a 2px end dot), then the sub-line "#rank · change" with the sign-led coloured change. The focus tint runs the full column height.
- **Row:** hover tints the row, and a rotating SVG caret signals it can be expanded. An expanded row drops its rule and opens the comparison panel, closed by a 2px ink rule.
- **Marks:** provisional years carry a superscript "p". Online-institution states carry a "†". Both have a title and a footer key.

### Section nav (profile)
- **Style:** 13.5px Ink 2 links with 6 / 10px padding and a 3px radius. Hover gives Hover Tint. The current section gets Focus Tint, 600 ink text and a 2px Working Blue inset bar on the left.

### Charts
- **Lines:** focus 3px, competitors 1.8 to 2px, U.S. dashed (5 4). Base and latest years show as dashed Rule 2 verticals. Charts end in direct labels at the right edge.
- **Ranking strip / scatter / tile map:** every state is drawn. Chosen states are in their series colour, the rest in Rest Grey. The U.S. is a dashed reference line labelled "U.S. value".
- **Legend:** 12.5px Ink 2, 12px square swatches, 16px line or dashed swatches.

### Sankey (signature)
- **Nodes:** saturated vertical bars, 14px wide, 2px radius, heights proportional to flow.
- **Ribbons:** source-coloured strokes at 0.16 opacity. On hover the active ribbons go to 0.42 and the rest to 0.06, with a tooltip giving the size and share of the source.
- **Dots:** circles at 0.85 opacity travel source to target at a constant 70 px/s. The number of dots is proportional to flow (1 to 40 per ribbon). Under prefers-reduced-motion the dots are placed once and stay still.
- **Labels:** "Name value" (600 name, Ink 3 value), drawn above the dot layer with a sheet-coloured halo and nudged apart by 15px, with leader lines when moved.
- **Narrow mode:** below 2 × label width + 300px, columns move to the edges, labels go inside beside their bars, and any label that collides is dropped into a legend-style key below the chart.

### Tooltip / Toast
- Ink fill with white text (inverted in dark mode), 4px radius, 8 / 10px padding, 12px text at 1.45 line height, max width 300px, carrying the popover shadow.

## Do's and Don'ts

### Do:
- **Do** give the focus state slot 1 (Working Blue), the tinted column and the heaviest line on every surface where it appears.
- **Do** keep each competitor's series slot fixed for as long as it stays in the set, and use the same colour for its chip dot, header dot, lines, bars and Sankey nodes.
- **Do** write every change with its sign first and colour it gain green or loss rust second.
- **Do** draw the U.S. as dashed U.S. Grey, and every unchosen state in Rest Grey.
- **Do** separate structure with 1px cool rules and close groups and sections with 2px ink rules.
- **Do** set all numbers in tabular IBM Plex Sans, right-aligned.
- **Do** mark provisional years with a superscript "p" and online-institution states with "†", each with a title and footer key.
- **Do** stop all motion under prefers-reduced-motion. Sankey dots are drawn once and stay still.

### Don't:
- **Don't** use Working Blue for anything except the focus state, links and focus rings.
- **Don't** put shadows on cards, charts, panels or controls. Shadows are only for tooltips and toasts.
- **Don't** frame charts in cards or boxes. They sit directly on the sheet under a title and note.
- **Don't** repaint competitors when the set changes, or reuse a slot while its state is still in the set.
- **Don't** bring back the archived manual's per-section colour boards.
- **Don't** use text characters as icons. Icons are 16px inline SVG line glyphs.


## Peer-set menu

The "Compared with" line opens with a menu button naming the current set ("Similar enrollment", or
"Custom" once the chips are edited by hand), followed by the competitor chips and "+ Add state". The
menu is a popover (the only other surface allowed a shadow besides tooltips), max height the viewport
less 90 px, grouped "From IPEDS" then "From other public data (used only to choose states)". Each item
is a 13px/600 label, a 12px ink-3 description and an accent-ink preview of the states it would pick
for the current state; the active item has the focus tint. Arrow keys move, Escape closes. The same
component (`ipeds_clean/templates/peers.js`) serves the sheet and the profiles; on the profiles the
"Open in the sheet" and "All states" links sit at the top of the section list so the header stays one
line.
