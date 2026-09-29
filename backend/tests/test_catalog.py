import pytest

from app.catalog import parse_compounding_today, parse_medisca

MEDISCA_CSV = (
    '"Formula Number","API(s) & Strength","Route of Delivery","Dosage Form","Base","Duplicate Formula Number","Source Page"\n'
    '"F000001","Examplamide 5 mg/mL Oral Liquid (Suspension, 100 mL)","Oral","Liquid","Vehicle X","No","1"\n'
    '"F000002","Examplamide 10%, Otherazole 2% Topical Cream (Emulsion, 30 g)","Topical","Cream","","No","1"\n'
    '"F000003","Nystatinoid 200 000 IU Oral Troches (Solid Suspension, 30 Troches)","Oral","Troches","","No","2"\n'
).encode()
CT_CSV = (
    "CompoundingToday ID,Formula title,Catalog URL\n"
    '11,Examplamide 10-mg/mL in Syrup Vehicle™ [Vendor],https://compoundingtoday.com/Formulation/FormulaInfo.cfm?ID=11\n'
    '12,"Otherazole 1% and Examplamide 2% Topical Gel, Preserved",https://evil.example/x\n'
).encode()


@pytest.mark.parametrize("title, route, form, expected", [
    ("Levetiracetam 300 mg/5 mL Oral Liquid (Solution, 100 mL)", "Oral", "Liquid",
     ("Levetiracetam", "300 mg/5 mL", "Oral solution", "100 mL")),
    ("Ketoconazole 2%, Minoxidil 7% Topical Serum", "Topical", "Serum",
     ("Ketoconazole, Minoxidil", "2%, 7%", "Topical serum", "")),
    ("Nystatin 500 000 IU Oral Capsules (Powder Blend, 100 x Size #1 Capsules)", "Oral", "Capsules",
     ("Nystatin", "500 000 IU", "Oral capsules", "100 x Size #1 Capsules")),
    ("Progesterone 40 mg per mL Topical Cream", "Topical", "Cream",
     ("Progesterone", "40 mg per mL", "Topical cream", "")),
    ("Baclofen 10 mg per 5 mL Oral Liquid (MAZ)", "Oral", "Liquid",
     ("Baclofen", "10 mg per 5 mL", "Oral liquid", "")),
])
def test_parse_medisca(title, route, form, expected):
    p = parse_medisca(title, route, form)
    assert (p.active_ingredient, p.strength, p.dosage_form, p.final_quantity) == expected


@pytest.mark.parametrize("title, expected", [
    ("Baclofen 10-mg/mL in Ora-Plus™ and Ora-Sweet™ [Paddock Perrigo]", ("Baclofen", "10 mg/mL", "")),
    ("Erythromycin 10-mg/gram and Neomycin Sulfate 3.5-mg/gram Ointment",
     ("Erythromycin, Neomycin Sulfate", "10 mg/gram, 3.5 mg/gram", "Ointment")),
    ("5-Aminolevulinic Acid Hydrochloride 20% in Cream Base [Fagron]", ("5-Aminolevulinic Acid Hydrochloride", "20%", "Cream")),
    ("Heparin Sodium 5,000-Units/gram in Aquabase™", ("Heparin Sodium", "5,000 Units/gram", "")),
    ("Lansoprazole 3-mg/mL Oral Suspension, Formula 2", ("Lansoprazole", "3 mg/mL", "Oral suspension")),
])
def test_parse_compounding_today(title, expected):
    p = parse_compounding_today(title)
    assert (p.active_ingredient, p.strength, p.dosage_form) == expected


def _import(api, data, name="catalog.csv"):
    return api.c.post("/api/catalog/import", headers={"X-Requested-With": "fm"},
                      files={"file": (name, data, "text/csv")})


def test_import_detects_source_and_replaces(client):
    admin = client("admin")
    assert _import(admin, MEDISCA_CSV).json() == {"source": "MEDISCA", "count": 3}
    assert _import(admin, CT_CSV).json() == {"source": "CompoundingToday", "count": 2}
    assert _import(admin, MEDISCA_CSV).json()["count"] == 3  # re-import replaces, no duplicates
    counts = {s["source"]: s["count"] for s in admin.get("/api/catalog/summary").json()}
    assert counts == {"MEDISCA": 3, "CompoundingToday": 2}
    r = _import(admin, b"name,other\nx,y\n")
    assert r.status_code == 422 and "Unrecognised" in r.json()["detail"]


def test_only_admin_imports(client):
    assert _import(client("tech"), MEDISCA_CSV).status_code == 403


def test_search_matches_every_word_across_sources(client):
    _import(client("admin"), MEDISCA_CSV)
    _import(client("admin"), CT_CSV)
    api = client("tech")
    hits = api.get("/api/catalog/search", params={"q": "examplamide 10"}).json()
    ids = [(h["source"], h["formula_id"]) for h in hits]
    assert {("MEDISCA", "F000002"), ("CompoundingToday", "11")} <= set(ids)
    assert api.get("/api/catalog/search", params={"q": "examplamide 10%"}).json()[0]["formula_id"] == "F000002"
    # CompoundingToday's "10-mg/mL" is found by "10 mg/ml", and vice versa.
    assert api.get("/api/catalog/search", params={"q": "10 mg/ml"}).json()[0]["formula_id"] == "11"
    assert [h["formula_id"] for h in api.get("/api/catalog/search", params={"q": "10-mg/mL syrup"}).json()] == ["11"]
    # Words match from their start only.
    assert api.get("/api/catalog/search", params={"q": "plamide"}).json() == []
    assert api.get("/api/catalog/search", params={"q": "trOcheS"}).json()[0]["strength"] == "200 000 IU"
    assert api.get("/api/catalog/search", params={"q": "x"}).json() == []
    assert api.get("/api/catalog/search", params={"q": "100%_"}).json() == []  # LIKE wildcards are literal
    ct = api.get("/api/catalog/search", params={"q": "otherazole", "source": "CompoundingToday"}).json()
    assert ct[0]["url"] == ""  # only compoundingtoday.com links are kept


def test_request_keeps_catalog_ref(client):
    _import(client("admin"), MEDISCA_CSV)
    api = client("tech")
    hit = api.get("/api/catalog/search", params={"q": "examplamide oral"}).json()[0]
    ref = {"source": hit["source"], "formula_id": hit["formula_id"], "title": hit["title"], "url": hit["url"]}
    req = api.post("/api/requests", json={"active_ingredient": hit["active_ingredient"], "strength": hit["strength"],
                                          "dosage_form": hit["dosage_form"], "sources": [], "catalog_ref": ref})
    assert req.status_code == 201, req.text
    assert api.get(f"/api/requests/{req.json()['id']}").json()["catalog_ref"] == ref
    # Re-importing the catalog does not touch the request's copy.
    _import(client("admin"), MEDISCA_CSV)
    assert api.get(f"/api/requests/{req.json()['id']}").json()["catalog_ref"] == ref


def test_admin_edits_email(client, users):
    admin = client("admin")
    r = admin.patch(f"/api/users/{users['tech'].id}", json={"email": "Tech.New@Example.test"})
    assert r.status_code == 200 and r.json()["email"] == "tech.new@example.test"
    dup = admin.patch(f"/api/users/{users['tech'].id}", json={"email": "pharm@example.test"})
    assert dup.status_code == 409
    assert admin.patch(f"/api/users/{users['tech'].id}", json={"email": "not-an-email"}).status_code == 422
