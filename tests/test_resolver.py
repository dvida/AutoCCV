from autoccv.resolver import Catalog

cat = Catalog()


def test_lov_exact():
    lid, label, conf = cat.resolve_lov("Degree Type", "Doctorate")
    assert lid == "00000000000000000000000000000073"
    assert conf == "exact"


def test_lov_case_insensitive():
    lid, _, conf = cat.resolve_lov("Funding Role", "co-investigator")
    assert lid == "00000000000000000000000100002801"


def test_lov_unknown_returns_none():
    lid, _, conf = cat.resolve_lov("Publishing Status", "In review")
    assert lid is None and conf is None


def test_reftable_org_exact():
    rid, chain, conf = cat.resolve_reftable("Organization", "University of Western Ontario")
    assert chain and chain[-1]["refOrLovId"] == "ee597e9073b6479b94f903ca08f81903"


def test_reftable_org_fuzzy():
    rid, chain, conf = cat.resolve_reftable("Organization", "Natural Sciences and Engineering Research Council of Canada")
    assert chain is not None


def test_reftable_discipline():
    rid, chain, conf = cat.resolve_reftable("Research Discipline", "Astronomy and Astrophysics")
    assert chain and chain[-1]["value"] == "Astronomy and Astrophysics"


def test_reftable_unknown_org_none():
    rid, chain, conf = cat.resolve_reftable("Organization", "Hogwarts School of Witchcraft")
    assert chain is None


def test_overlay_adds_org():
    cat2 = Catalog()
    chain = [{"label": "Organization", "value": "Tiny College", "refOrLovId": "abc123"}]
    cat2.add_org("Tiny College", chain)
    rid, got, conf = cat2.resolve_reftable("Organization", "Tiny College")
    assert got == chain
