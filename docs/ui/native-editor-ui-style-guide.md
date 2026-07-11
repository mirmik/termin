# Native Editor UI Style Guide

This document defines the visual contract for `termin-gui-native`. It is the
reference for widget defaults and editor composition; screenshots of the legacy
editor are inspiration, not an API to reproduce pixel-for-pixel.

## Direction

The editor is a dense professional tool. Its chrome should recede behind scene
content and data. Structure comes primarily from spacing, surface tone and
typography. Borders are reserved for focus, editable fields and boundaries that
would otherwise be ambiguous.

The target character is compact, quiet and contemporary:

- neutral dark surfaces, with one cool-blue interaction accent;
- 28 px compact controls and 18 px checkboxes;
- soft 3–4 px corner radii, never fully pill-shaped editor controls;
- one-pixel low-contrast borders where a border is necessary;
- filled selection and hover states instead of boxes around every item;
- colour communicates state; it is not decoration.

## Tokens

### Surfaces and colour

Use a small elevation ladder. Adjacent surfaces need only enough contrast to
remain legible: workspace, panel, inset/editor field, raised control, overlay.
Avoid alternating unrelated greys in the same hierarchy.

Text has three strengths: primary content, secondary labels and disabled/hint.
Pure white is not normal body text. Blue is for focus, primary action and
selection. Green is for success or enabled state, including a checked checkbox;
it must not be used as a generic outline.

### Geometry

The base spacing unit is 4 px. Common gaps are 4, 8, 12 and 16 px. Arbitrary
one-off gaps should be exceptional.

The style-level `corner_radius` token is authoritative. Defaults are 4 px for
buttons and overlays and 3 px for fields and checkboxes. Widgets must not embed
a private radius when their shape is theme-controlled.

Compact controls have a 28 px minimum height. Text fields may use 30–34 px when
editing comfort requires it. A checkbox's visual box is 18 px; its surrounding
row provides the larger pointer target.

### Borders and separators

Default buttons have no visible border. Editable fields use at most a subtle
1 px border. Focus changes the border colour without changing its width, so
layout and perceived weight remain stable. Container outlines are a last resort;
prefer an inset surface or a single separator between regions.

Splitters separate interaction geometry from visual weight. Their resize hit
area may be comfortably wide, while the visible divider remains a centered 1 px
line. Hover and drag use the interaction accent and a 2 px line without changing
panel layout.

## Interaction states

Every interactive primitive must define default, hovered, pressed, focused and
disabled appearances. Toggle controls additionally define checked. State changes
must not resize the control. Hover is a small surface lift; press is a darker or
accented fill; keyboard focus is the only routinely bright outline.

Primary action styling is contextual. A generic `Button` is neutral. Dialogs may
mark one affirmative action with the accent colour; destructive actions require
their own semantic colour. A dialog full of blue buttons has no hierarchy.

## Composition rules

- Align labels and controls to a shared grid inside inspector rows.
- Do not draw both a panel border and borders on every child row.
- Prefer whitespace and a section label over a framed group box.
- Selection is one filled row or tile, not simultaneous fill plus multiple
  outlines.
- Dialogs are raised surfaces with modest rounding; their content and footer
  establish hierarchy through spacing.
- Custom widgets should consume theme tokens before introducing local constants.

## Review checklist

When adding or porting a widget, verify it at 100% and high-DPI scaling, with
short and long text, in every interaction state, beside existing controls, and
inside the actual editor rather than only the showcase. A migration is visually
complete only when it removes redundant separators and local styling constants,
not merely when all controls are present.
