# Cancer Omics Browser

A full-stack web app to explore **TCGA pan-cancer** somatic mutations, gene expression,
and survival across three cancer types — **BRCA** (breast), **LUAD** (lung adenocarcinoma),
and **COAD** (colon adenocarcinoma).

| Layer    | Tech                                              |
| -------- | ------------------------------------------------- |
| Backend  | FastAPI + SQLAlchemy, `lifelines` for survival    |
| Database | PostgreSQL 16                                      |
| Frontend | React + Vite, Plotly.js                            |
| Ingest   | GDC API puller + offline synthetic fallback       |
| Orchestr | Docker Compose                                     |

---

## Quick start

```bash
docker compose up --build
```

Then open:

- **App UI** → http://localhost:5173
- **API docs (Swagger)** → http://localhost:8000/docs

On first boot the backend creates the schema and loads data. By default it loads an
**offline synthetic subset** (anchored to real TCGA mutation frequencies) so the app
works with zero network access. To pull a **real** small subset from the GDC API:

```bash
DATA_SOURCE=gdc docker compose up --build
```

The load is idempotent — restarting won't duplicate data. To reload from scratch:

```bash
docker compose down -v && docker compose up --build
```

### Run in GitHub Codespaces

This repo ships a [`.devcontainer`](.devcontainer/devcontainer.json) with
Docker-in-Docker, so you can run the whole stack in the cloud with no local Docker:

1. On GitHub: **Code ▸ Codespaces ▸ Create codespace on main**.
2. Wait for the container to build (it pre-builds the images via `postCreateCommand`).
3. In the Codespace terminal: `docker compose up`.
4. When the **5173** port is forwarded, open it (Codespaces pops a browser tab). The
   API is on the forwarded **8000** port (`/docs` for Swagger).

The frontend proxies `/api` to the `backend` service inside the Compose network, so only
port 5173 needs to be public.

---

## The four charts (and why each matters biologically)

1. **Cohort selector** — filter patients by cancer type, gender, age range, and tumor
   stage. *Defining the right cohort is the first step of any genomics analysis; comparisons are only meaningful within a coherent patient group.*
2. **Mutation frequency bar chart** — % of the cohort mutated in each top gene.
   *Recurrently mutated genes are the candidate drivers and drug targets of a cancer type.*
3. **Expression boxplot stratified by mutation status** — a gene's expression in
   mutated vs wild-type tumors. *It reveals whether a mutation changes expression — e.g. loss-of-function mutations often lower a tumor suppressor's expression.*
4. **Kaplan–Meier survival curve** — overall survival split by mutation status, with a
   log-rank p-value. *It answers the clinical bottom line: does carrying this mutation change how long patients live?*

---

## Hosted deployment (GitHub Pages + Render)

The app can run with **no Codespace and no local Docker**: the static frontend on
**GitHub Pages**, the API + Postgres on **Render's free tier**.

**1. Deploy the backend to Render (one-time, needs your Render login):**
   - Go to [render.com](https://render.com) → **New ▸ Blueprint** → connect this repo.
   - Render reads [`render.yaml`](render.yaml) and provisions the `cancer-omics-api`
     web service + a free `cancer-omics-db` Postgres. Click **Apply**.
   - When live, copy the service URL, e.g. `https://cancer-omics-api.onrender.com`.

**2. Point the frontend at it:**
   - In this GitHub repo: **Settings ▸ Secrets and variables ▸ Actions ▸ Variables**,
     add a repository variable `VITE_API_BASE` = the Render URL (no trailing slash).
   - **Settings ▸ Pages ▸ Source → GitHub Actions.**

**3. Deploy the frontend:** the [`pages.yml`](.github/workflows/pages.yml) workflow runs
   on push (or **Actions ▸ Deploy frontend to GitHub Pages ▸ Run workflow**). It builds
   with `VITE_API_BASE` baked in and publishes to
   `https://<user>.github.io/cancer-omics-browser/`.

Notes: CORS on the API is open (`*`), so the Pages origin can call Render directly. The
Render free web service sleeps after ~15 min idle — the first request cold-starts in
~30-60s, then it's fast.

## Data schema

Three tables (see [`backend/app/models.py`](backend/app/models.py)).

### `patients` — one row per patient (clinical + survival)

| Column            | Type    | Notes                                            |
| ----------------- | ------- | ------------------------------------------------ |
| `patient_barcode` | text PK | e.g. `TCGA-A1-A0SB`                              |
| `cancer_type`     | text    | `BRCA` / `LUAD` / `COAD`                          |
| `gender`          | text    | `male` / `female`                                |
| `age_at_diagnosis`| int     | years                                            |
| `tumor_stage`     | text    | `Stage I`…`Stage IV` / `Unknown`                 |
| `vital_status`    | text    | `Alive` / `Dead`                                 |
| `os_time`         | int     | overall-survival time in days                    |
| `os_event`        | int     | `1` = death observed, `0` = censored             |

### `mutations` — one row per variant per patient (MC3 MAF subset)

| Column                   | Type | Notes                                  |
| ------------------------ | ---- | -------------------------------------- |
| `id`                     | PK   |                                        |
| `patient_barcode`        | FK   | → `patients`                           |
| `cancer_type`            | text |                                        |
| `hugo_symbol`            | text | gene, e.g. `TP53`                      |
| `variant_classification` | text | `Missense_Mutation`, `Nonsense_…`, …   |
| `variant_type`           | text | `SNP` / `INS` / `DEL`                  |
| `chromosome`             | text |                                        |
| `start_position`         | int  |                                        |
| `hgvsp_short`            | text | protein change, e.g. `p.R175H`         |

### `expression` — one row per (patient, gene) in long format

| Column            | Type  | Notes                       |
| ----------------- | ----- | --------------------------- |
| `id`              | PK    |                             |
| `patient_barcode` | FK    | → `patients`                |
| `cancer_type`     | text  |                             |
| `gene`            | text  |                             |
| `value`           | float | `log2(TPM + 1)`             |

---

## API endpoints

Base URL: `http://localhost:8000`. Full interactive docs at `/docs`.

### `GET /api/health`
```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

### `GET /api/cancer-types`
List cancer types with patient counts.
```bash
curl http://localhost:8000/api/cancer-types
# [{"cancer_type":"BRCA","patient_count":200}, ...]
```

### `GET /api/cohort`
Summarize a filtered cohort. Filters: `cancer_type` (required), `gender`, `min_age`,
`max_age`, `tumor_stage`, `vital_status`.
```bash
curl "http://localhost:8000/api/cohort?cancer_type=BRCA&gender=female&min_age=50"
# {"cancer_type":"BRCA","patient_count":83,"mutated_patient_count":80,"filters_applied":{...}}
```

### `GET /api/genes?cancer_type=BRCA`
Genes that have both mutation and expression data.
```bash
curl "http://localhost:8000/api/genes?cancer_type=LUAD"
# ["BRAF","EGFR","KEAP1","KRAS","MET","NF1","STK11","TP53"]
```

### `GET /api/mutations/frequency`
Per-gene mutation frequency in a cohort. Same filters as `/api/cohort`, plus `top` (1–100).
```bash
curl "http://localhost:8000/api/mutations/frequency?cancer_type=BRCA&top=5"
# {"cancer_type":"BRCA","total_patients":200,"genes":[
#   {"hugo_symbol":"PIK3CA","mutated_patients":71,"total_patients":200,"frequency":0.355}, ...]}
```

### `GET /api/expression/boxplot?gene=TP53&cancer_type=BRCA`
Expression values split by mutation status of the gene.
```bash
curl "http://localhost:8000/api/expression/boxplot?cancer_type=BRCA&gene=TP53"
# {"gene":"TP53","cancer_type":"BRCA","mutated":[5.9,...],"wildtype":[8.7,...],"unit":"log2(TPM+1)"}
```

### `GET /api/survival?gene=TP53&cancer_type=BRCA`
Kaplan–Meier curves (mutated vs wild-type) and the log-rank p-value.
```bash
curl "http://localhost:8000/api/survival?cancer_type=BRCA&gene=TP53"
# {"gene":"TP53","cancer_type":"BRCA","groups":[
#   {"label":"Mutated","n":60,"timeline":[...],"survival":[...]},
#   {"label":"Wild-type","n":140,"timeline":[...],"survival":[...]}],
#  "logrank_p":0.0123}
```

More worked examples (including a full BRCA TP53 walk-through and a real-data pull) live
in [`cookbook/COOKBOOK.md`](cookbook/COOKBOOK.md).

---

## Local development (without Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Point at a local Postgres, or run one via: docker compose up db
export DATABASE_URL=postgresql+psycopg2://omics:omics@localhost:5432/omics

python -m ingest.run                 # create tables + seed synthetic data
uvicorn app.main:app --reload        # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
VITE_API_TARGET=http://localhost:8000 npm run dev   # http://localhost:5173
```

### Pull real TCGA data from GDC
```bash
cd backend
python -m ingest.ingest_gdc --cases-per-type 60 --expr-samples 40
```

---

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -q          # runs against an in-memory SQLite DB, no Postgres needed
```

Or inside the container:
```bash
docker compose run --rm backend pytest -q
```

---

## Project layout

```
cancer-omics-browser/
├── docker-compose.yml
├── backend/
│   ├── app/            # FastAPI app: models, schemas, routers, KM analytics
│   ├── ingest/         # GDC API puller + synthetic seed + loader entrypoint
│   └── tests/          # pytest API tests
├── frontend/           # React + Vite + Plotly
└── cookbook/           # worked end-to-end examples
```

## Data provenance & caveats

The default dataset is **synthetic** — randomized but anchored to canonical TCGA
marker-paper mutation frequencies (e.g. PIK3CA/TP53 in BRCA, KRAS in LUAD/COAD, APC in
COAD), with expression and survival deliberately correlated to mutation status so the
charts are illustrative. For real analysis, run with `DATA_SOURCE=gdc`, which pulls
open-access data from the [NCI GDC](https://gdc.cancer.gov/) API. The real subset is
intentionally small (capped cases/samples) for fast, reproducible demos — it is not a
complete cohort.
