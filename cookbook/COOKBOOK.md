# Cancer Omics Browser — Cookbook

Real, runnable recipes against a running stack (`docker compose up`). Every example uses
`curl` against `http://localhost:8000`; pipe through `jq` for readable output.

> Numbers below come from the default **synthetic** dataset (seed = 42), so they're
> reproducible. With `DATA_SOURCE=gdc` the shapes are identical but values reflect real
> TCGA cases.

---

## Recipe 1 — "What are the top drivers in breast cancer?"

```bash
curl -s "http://localhost:8000/api/mutations/frequency?cancer_type=BRCA&top=8" | jq
```

```json
{
  "cancer_type": "BRCA",
  "total_patients": 200,
  "genes": [
    {"hugo_symbol": "PIK3CA", "mutated_patients": 71, "total_patients": 200, "frequency": 0.355},
    {"hugo_symbol": "TP53",   "mutated_patients": 60, "total_patients": 200, "frequency": 0.30},
    {"hugo_symbol": "CDH1",   "mutated_patients": 26, "total_patients": 200, "frequency": 0.13}
  ]
}
```

**Biology:** PIK3CA and TP53 topping the BRCA list matches the TCGA breast marker paper —
these are the two most recurrently mutated genes in breast cancer.

---

## Recipe 2 — End-to-end TP53 story in BRCA

TP53 is a tumor suppressor; loss-of-function mutation should (a) lower its expression and
(b) worsen survival. Walk all three endpoints:

```bash
# 1. How often is TP53 mutated?
curl -s "http://localhost:8000/api/mutations/frequency?cancer_type=BRCA&top=20" \
  | jq '.genes[] | select(.hugo_symbol=="TP53")'

# 2. Does mutation change TP53 expression? (compare group medians)
curl -s "http://localhost:8000/api/expression/boxplot?cancer_type=BRCA&gene=TP53" \
  | jq '{mutated_median: (.mutated | sort | .[(length/2|floor)]),
         wildtype_median: (.wildtype | sort | .[(length/2|floor)])}'

# 3. Does mutation change survival?
curl -s "http://localhost:8000/api/survival?cancer_type=BRCA&gene=TP53" \
  | jq '{logrank_p, groups: [.groups[] | {label, n, final_survival: .survival[-1]}]}'
```

Expected pattern: mutated-group median expression is **lower** than wild-type, and the
log-rank p-value is small with the mutated curve falling **below** wild-type — exactly the
tumor-suppressor signature.

---

## Recipe 3 — Compare the same gene across cancer types

TP53 is pan-cancer; KRAS is enriched in lung and colon. Loop over types:

```bash
for ct in BRCA LUAD COAD; do
  echo "== $ct =="
  curl -s "http://localhost:8000/api/mutations/frequency?cancer_type=$ct&top=20" \
    | jq -r '.genes[] | select(.hugo_symbol=="KRAS") | "KRAS: \(.frequency*100|round)%"'
done
```

You'll see KRAS frequency jump in LUAD and COAD relative to BRCA.

---

## Recipe 4 — Clinical sub-cohorts

Filters stack. Late-stage, older breast-cancer patients:

```bash
curl -s "http://localhost:8000/api/cohort?cancer_type=BRCA&min_age=60&tumor_stage=Stage%20III" | jq
```

Then re-run any chart endpoint with the same filters to analyze that exact sub-cohort:

```bash
curl -s "http://localhost:8000/api/mutations/frequency?cancer_type=BRCA&min_age=60&tumor_stage=Stage%20III&top=5" | jq '.genes'
```

---

## Recipe 5 — Discover what's queryable, then query it

```bash
# Which cancer types and how many patients?
curl -s "http://localhost:8000/api/cancer-types" | jq

# Which genes have BOTH mutation and expression data for COAD?
curl -s "http://localhost:8000/api/genes?cancer_type=COAD" | jq

# Pick one (APC — the classic colon-cancer driver) and inspect expression:
curl -s "http://localhost:8000/api/expression/boxplot?cancer_type=COAD&gene=APC" \
  | jq '{gene, n_mutated: (.mutated|length), n_wildtype: (.wildtype|length)}'
```

---

## Recipe 6 — Pull a real TCGA subset from GDC, then query it

```bash
# Reload the stack against the live GDC API (small, capped subset):
docker compose down -v
DATA_SOURCE=gdc docker compose up --build -d

# Watch the loader pull clinical, mutation, and expression data:
docker compose logs -f backend

# Once it reports rows loaded, the same endpoints now serve real data:
curl -s "http://localhost:8000/api/mutations/frequency?cancer_type=LUAD&top=5" | jq
```

Or run the puller directly with custom caps:

```bash
docker compose run --rm \
  -e DATABASE_URL=postgresql+psycopg2://omics:omics@db:5432/omics \
  backend python -m ingest.ingest_gdc --cases-per-type 80 --expr-samples 50
```

---

## Recipe 7 — Run the test suite

```bash
docker compose run --rm backend pytest -q
```

Tests spin up an in-memory SQLite DB seeded with the synthetic subset and assert API
contracts (KM monotonicity, frequency bounds/sorting, filter behavior, 404s).

---

## Programmatic client (Python)

```python
import requests

BASE = "http://localhost:8000/api"

def top_genes(cancer_type, n=10):
    r = requests.get(f"{BASE}/mutations/frequency",
                     params={"cancer_type": cancer_type, "top": n})
    r.raise_for_status()
    return [(g["hugo_symbol"], g["frequency"]) for g in r.json()["genes"]]

def survival_pvalue(cancer_type, gene):
    r = requests.get(f"{BASE}/survival",
                     params={"cancer_type": cancer_type, "gene": gene})
    r.raise_for_status()
    return r.json()["logrank_p"]

print(top_genes("BRCA"))
print("TP53 BRCA log-rank p =", survival_pvalue("BRCA", "TP53"))
```
