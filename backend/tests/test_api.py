def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_cancer_types(client):
    r = client.get("/api/cancer-types")
    assert r.status_code == 200
    data = r.json()
    types = {d["cancer_type"] for d in data}
    assert {"BRCA", "LUAD", "COAD"} <= types
    for d in data:
        assert d["patient_count"] > 0


def test_cohort_summary_and_filters(client):
    r = client.get("/api/cohort", params={"cancer_type": "BRCA"})
    assert r.status_code == 200
    full = r.json()
    assert full["patient_count"] > 0
    assert full["mutated_patient_count"] <= full["patient_count"]

    # Age filter must shrink (or keep equal) the cohort.
    r2 = client.get("/api/cohort", params={"cancer_type": "BRCA", "min_age": 70})
    assert r2.status_code == 200
    assert r2.json()["patient_count"] <= full["patient_count"]
    assert r2.json()["filters_applied"]["min_age"] == 70


def test_genes_intersection(client):
    r = client.get("/api/genes", params={"cancer_type": "LUAD"})
    assert r.status_code == 200
    genes = r.json()
    assert "TP53" in genes and "KRAS" in genes


def test_mutation_frequency_sorted_and_bounded(client):
    r = client.get("/api/mutations/frequency", params={"cancer_type": "BRCA", "top": 5})
    assert r.status_code == 200
    body = r.json()
    genes = body["genes"]
    assert len(genes) <= 5
    freqs = [g["frequency"] for g in genes]
    assert freqs == sorted(freqs, reverse=True)
    for g in genes:
        assert 0.0 <= g["frequency"] <= 1.0
        assert g["mutated_patients"] <= g["total_patients"]


def test_expression_boxplot_groups(client):
    r = client.get(
        "/api/expression/boxplot", params={"cancer_type": "BRCA", "gene": "TP53"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["gene"] == "TP53"
    # Both groups should contain values for a commonly mutated gene.
    assert len(body["mutated"]) > 0
    assert len(body["wildtype"]) > 0
    assert body["unit"] == "log2(TPM+1)"


def test_expression_boxplot_unknown_gene_404(client):
    r = client.get(
        "/api/expression/boxplot", params={"cancer_type": "BRCA", "gene": "NOTAGENE"}
    )
    assert r.status_code == 404


def test_survival_curve_and_logrank(client):
    r = client.get("/api/survival", params={"cancer_type": "BRCA", "gene": "TP53"})
    assert r.status_code == 200
    body = r.json()
    labels = {g["label"] for g in body["groups"]}
    assert labels == {"Mutated", "Wild-type"}
    for g in body["groups"]:
        # KM survival is monotonically non-increasing and within [0, 1].
        surv = g["survival"]
        assert all(0.0 <= s <= 1.0 for s in surv)
        assert all(earlier >= later for earlier, later in zip(surv, surv[1:]))
    assert body["logrank_p"] is None or 0.0 <= body["logrank_p"] <= 1.0


def test_unknown_cancer_type_empty_cohort(client):
    r = client.get("/api/cohort", params={"cancer_type": "XXXX"})
    assert r.status_code == 200
    assert r.json()["patient_count"] == 0
