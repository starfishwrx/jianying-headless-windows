# Centered subtitle layout

New `jy14-headless-plan/v1` text segments support `alignment` (integer 0=left,
1=center, 2=right) and `max_line_width` (finite screen-width fraction .1–1).
Both are optional for ordinary titles. Subtitle segments default to centered
alignment and an 80% line width. Explicit new fields are verified on readback;
old completed plans without them retain their original inspection contract.

Example:

```json
{"text":"第一行\n第二行","duration_us":3000000,"size":8,
 "subtitle":true,"alignment":1,"max_line_width":0.8,"x":0,"y":-0.55}
```

The native writer sets `alignment`, `line_max_width`, and
`force_apply_line_max_width=true`. The calling application measures actual font
widths, inserts display line breaks and accounts for multiline height before
building the plan. This backend does not certify the application's safe-area
geometry or change narration timestamps.

`production_library.TEXT_LAYOUT_SCHEMA = centered-safe-subtitles/v1` identifies
this capability for preflight. The existing source pins were refreshed after
unit/package checks and isolated Windows native build/readback. No installed
production backend or home index was changed. Original engine/codec identities
remain required; parameter checks are not a native pixel-render acceptance.
