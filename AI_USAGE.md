# AI usage log — Field Shift (NASA Space Apps 2026)

Hackathon disclosure: parts of this project were generated or assisted by **Cursor** (Composer / agent).

| Date | Phase | What was AI-assisted | How |
|------|-------|----------------------|-----|
| 2026-11-13 | Spec review | Read `PROJECT_SPEC.md`; summary, risks, Phase 1 file list | Cursor agent, human-approved decisions before coding |
| 2026-11-13 | Phase 1 (React) | FastAPI + Vite scaffold (superseded) | Cursor agent |
| 2026-11-13 | Spec pivot | Streamlit + `fieldshift` package; §§2, 3, 7, 8, 10, 12 | Cursor agent from human brief |
| 2026-11-13 | Spec polish | Strategy-card UX; §§4/9/11 | Cursor agent from human instructions |
| 2026-11-13 | Streamlit Phase 1 | Scaffold, `make_secrets.py`, `init_ee`, `verify_ee.py` | Cursor agent; human owns EE key material; secrets never logged |
| 2026-11-13 | Routing cleanup | Removed React/FastAPI trees; `st.navigation` routes (`/`, `/field`, `/how-it-works`) | Cursor agent |
| 2026-11-13 | Cloud secrets | Inline JSON secrets template + `print_cloud_secrets.py`; harden `init_ee` for inline JSON | Cursor agent |
| 2026-11-13 | Phase 2 data | `verify_ee` fix (filterBounds/timeouts); POWER + EE extract; harmonize; timelapse; CLI; fixture tests; requirements split | Cursor agent; human OK required before §4 spec edits |
| 2026-11-13 | Phase 2 follow-ups + Phase 3 | Per-variable windows; POWER/IMERG rain; climatology sanity; crops.json + engine (features/anomalies/candidates/scoring/scenarios/explain) + tests | Cursor agent |
| 2026-11-13 | Phase 3 agronomic fixes | FAO-56 ET0; income/cover scoring; bare calendar; candidate gates; growing-season anomalies; Iowa/KS/Punjab cards | Cursor agent |

**Human-owned:** architecture pivots, cut list, credentials, deploy accounts, judging pitch.

**Rules followed:** no invented EE dataset IDs without verification; mock data labelled MOCK; secrets/ and `.streamlit/secrets.toml` gitignored; secret file contents never printed.
