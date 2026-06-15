import json
import os
from autoccv import generate
from autoccv.validate import validate_file

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def test_generate_then_validate(tmp_path):
    with open(os.path.join(REPO, "examples", "sample_cv_data.json")) as f:
        cv = json.load(f)
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw))

    assert res["total_added"] == sum(res["counts"].values())
    assert res["counts"]["journal_articles"] == 2
    assert res["counts"]["degrees"] == 2

    # planted unknowns surface as unresolved
    reasons = [(u["section"], u["value"]) for u in res["unresolved"]]
    assert ("degrees", "University of Osijek") in reasons       # unknown org -> fallback
    assert ("journal_articles", "In review") in reasons          # in-review status omitted

    # raw output is well-formed and structurally valid (pre-clean: allow non-ASCII)
    assert validate_file(str(raw), import_safe=False) == []

    # unique recordIds
    from lxml import etree
    ids = [s.get("recordId") for s in etree.parse(str(raw)).iter("section") if s.get("recordId")]
    assert len(ids) == len(set(ids))


def test_in_review_article_omits_publishing_status(tmp_path):
    with open(os.path.join(REPO, "examples", "sample_cv_data.json")) as f:
        cv = json.load(f)
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    raw = tmp_path / "gen.xml"
    generate.generate(cv, seed, str(raw))
    from lxml import etree
    t = etree.parse(str(raw))
    for s in t.iter("section"):
        if s.get("label") == "Journal Articles":
            title = s.find("field[@label='Article Title']/value")
            if title is not None and title.text and "in-review" in title.text:
                ps = s.find("field[@label='Publishing Status']")
                # field may exist but must carry no <lov>
                assert ps is None or ps.find("lov") is None
