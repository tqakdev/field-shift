# Field Shift

NASA Space Apps Challenge 2026 — crop-rotation decision support using NASA Earth data.

**UI:** Streamlit multipage app (`app.py` + `views/`). **Core:** plain Python package `fieldshift/`.  
Routes: `/` (Home), `/field`, `/how-it-works`. Python **3.12** (see `.python-version`).

## Quick start

```bash
cp .env.example .env
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # runtime (Cloud / Docker)
# pip install -r requirements-dev.txt    # + pytest, ruff

# Optional: Earth Engine secrets (never commit)
# place service account JSON at secrets/ee-key.json
python scripts/make_secrets.py          # local .streamlit/secrets.toml (path-based)
python scripts/print_cloud_secrets.py   # secrets/cloud_secrets.toml for Cloud copy-paste

streamlit run app.py
```

Open http://localhost:8501

### Lint & tests

```bash
pip install -r requirements-dev.txt
ruff check fieldshift ui views scripts tests app.py
pytest
```

### Data layer CLI (Phase 2)

```bash
python -m fieldshift.data.extract --lat 42.0 --lon -93.6 --size-ha 60
```

### Verify Earth Engine datasets (§4)

```bash
python scripts/verify_ee.py
```

## Deploy — Streamlit Community Cloud

1. Push this repo to GitHub.
2. https://share.streamlit.io → **New app** · main file `app.py`.
3. **Advanced settings → Secrets:** paste from `.streamlit/secrets.toml.example` (or
   `secrets/cloud_secrets.toml` from `print_cloud_secrets.py`). Never commit real keys.
4. Deploy. Without secrets → demo/mock mode.

## Limitations & cut list

Cut order if late (never SI model or evidence tagging): (a) Punjab demo, (b) live drawn-field analysis,
(c) timelapse, (d) docker-compose polish, (e) How-it-works depth.

## AI use

See [`AI_USAGE.md`](./AI_USAGE.md).
