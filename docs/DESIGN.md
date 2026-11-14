# Field Shift design system

Single source of truth: `ui/theme.py` (tokens + CSS) and `.streamlit/config.toml`.
Enforce with `tests/test_design.py`.

## Layout

- Page: max content width **1100 px**, centered. **No page border or page card.**
- Section separation: **48 px** space + heading. No horizontal rules through content.
- Spacing tokens only: **8, 16, 24, 32, 48 px**.
- Grouping: 8–16 px inside a group; 32–48 px between groups.
- Cards (1 px `#E3DDCF` border, 8 px radius, 16–24 px padding, **no shadow**) only for:
  fact cards, strategy cards, frost card. Never nest a card in a card.
- Prose max ~70 characters (~**640 px**) even in wide layout.
- Responsive: columns stack below **700 px**; nothing overflows at **400 px**.

## Typography

- One sans-serif family (Source Sans 3).
- Scale: page title **32**, section **22**, card value **26** bold, body **16**, caption **13**.
- Line height: **1.5** body, **1.2** headings.
- Sentence case. No all-caps except tiny overlines (eyebrow).
- No monospace outside code.

## Colour

| Token | Hex |
|-------|-----|
| background | `#FBF8F2` |
| surface | `#FFFFFF` |
| sidebar | `#F0EAD9` |
| text | `#2B2B2B` |
| muted | `#5C5C5C` (AA-safe) |
| primary | `#3F7D3A` |
| warning | `#B26A00` |
| danger | `#B23A3A` |
| info | `#3A7CA5` |
| card border | `#E3DDCF` |

- WCAG 2.2 AA: body ≥ 4.5:1; large text / chart marks ≥ 3:1.
- Status is never colour-only: always **icon + word** (e.g. “✓ Best fit”).
- Charts: **Okabe–Ito** palette; one fixed colour per variable; lines also differ by dash/marker.

### Fixed chart / criterion colours

| Variable | Colour |
|----------|--------|
| Plant greenness | `#009E73` |
| Rain | `#56B4E9` |
| Water balance | `#0072B2` |
| Water score | `#56B4E9` |
| Soil health | `#009E73` |
| Erosion | `#E69F00` |
| Pest break | `#CC79A7` |
| Climate fit | `#0072B2` |
| Income | `#D55E00` |

## Charts (data-ink)

- No chart borders or background fills; light horizontal gridlines only.
- Axis titles with units; legend horizontal above; sensible rounding + units.
- Hover: value + unit + source.
- Every chart has a one-sentence **takeaway** above it, generated from the data.

## Hierarchy + usability

- Field page primary element: recommendation banner, then **Best fit** card.
- At most one primary button per view.
- Spinner with step text for work > 1 s; plain-language success/error + next step.
- Same component for the same job (`fact_chips`, strategy cards, `source_caption`, badge).
- Glossary constants: `ui/glossary.py`.
- Tooltip (`help=`) on every input and technical term.
- Controls ≥ **44 px** tall; visible keyboard focus.

## Strategy cards

- Always show **Your rotation today** (baseline) before advised options when present.
- Overall label is **Overall** only — no Strong/Good/Fair next to it (tiers carry that meaning).
- Peer cards share equal structure (reserved bands) so demos compare cleanly.
- No empty “—” values in fact cards — use plain language (e.g. “Rarely frosts”).

## Audit leftovers (could not fully eliminate)

Checked Home, Field (Iowa + Punjab), and How it works against this doc after the design pass:

1. **Streamlit fragment chrome** — In some Streamlit versions, `@st.fragment` still paints a faint panel edge around imagery/options blocks. CSS strips borders on `stVerticalBlockBorderWrapper`, but a residual edge can appear from Streamlit’s own emotion styles; not fully removable without dropping fragments (which would hurt performance).
2. **Plotly legend / right-axis crowding** — On narrow viewports the seasonal chart legend can truncate (“Water balance…”) and the right y-axis min label can clip; mitigated with wider margins but not perfect at ~400 px width.
3. **Folium attribution** — Leaflet/Esri credit text inside the map iframe can still clip at the map frame edge (third-party control; outside our HTML).
4. **How it works pipeline diagram** — Remains a simplified Plotly schematic; not yet a full card-free editorial layout.
5. **Demo card image row** — Home demo thumbs still use Streamlit `st.image` in columns (not the fact-card component); visually consistent but not the same CSS card primitive.
