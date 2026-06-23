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
    # pin the year so the recency filter (reports/supervision) is deterministic
    res = generate.generate(cv, seed, str(raw), this_year=2026)

    assert res["total_added"] == sum(res["counts"].values())
    # the in-review article has no resolvable Publishing Status -> dropped as incomplete
    assert res["counts"]["journal_articles"] == 1
    assert res["counts"]["degrees"] == 2

    # planted unknowns surface as unresolved
    reasons = [(u["section"], u["value"]) for u in res["unresolved"]]
    assert ("degrees", "University of Osijek") in reasons       # unknown org -> fallback
    # the in-review article is flagged incomplete (mandatory Publishing Status unmet)
    incomplete = [u for u in res["unresolved"]
                  if u["section"] == "journal_articles" and u["kind"] == "incomplete"]
    assert incomplete and "Publishing Status" in incomplete[0]["value"]

    # raw output is well-formed and structurally valid (pre-clean: allow non-ASCII)
    assert validate_file(str(raw), import_safe=False) == []

    # unique recordIds
    from lxml import etree
    ids = [s.get("recordId") for s in etree.parse(str(raw)).iter("section") if s.get("recordId")]
    assert len(ids) == len(set(ids))


def test_mandatory_fields_drop_malformed_entries(tmp_path):
    """Entries missing a mandatory field are skipped and flagged, not emitted blank."""
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    cv = {
        "conference_publications": [
            # complete -> emitted
            {"title": "Good paper", "publication_type": "Paper", "conference": "Some Conf",
             "status": "Published", "year": "2023", "refereed": "Yes", "invited": "No",
             "authors": "Doe, J"},
            # missing publication_type + invited -> dropped
            {"title": "Bad paper", "conference": "Some Conf", "status": "Published",
             "year": "2023", "refereed": "Yes", "authors": "Doe, J"},
        ],
    }
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw), this_year=2026)

    assert res["counts"]["conference_publications"] == 1
    inc = [u for u in res["unresolved"]
           if u["section"] == "conference_publications" and u["kind"] == "incomplete"]
    assert len(inc) == 1
    assert "Conference Publication Type" in inc[0]["value"]
    assert "Invited?" in inc[0]["value"]

    # every emitted conference publication carries the mandatory lov fields
    from lxml import etree
    for s in etree.parse(str(raw)).iter("section"):
        if s.get("label") == "Conference Publications" and s.get("recordId"):
            for lbl in ("Conference Publication Type", "Invited?", "Publishing Status", "Refereed?"):
                assert s.find("field[@label='%s']/lov" % lbl) is not None


def test_recency_filter_drops_old_entries(tmp_path):
    """Reports older than the 6-year window are skipped and flagged stale."""
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    cv = {
        "reports": [
            {"title": "Recent report", "year": "2024", "num_pages": 3, "authors": "Doe, J"},
            {"title": "Old report", "year": "2015", "num_pages": 3, "authors": "Doe, J"},
        ],
    }
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw), this_year=2026)

    assert res["counts"]["reports"] == 1
    stale = [u for u in res["unresolved"]
             if u["section"] == "reports" and u["kind"] == "stale"]
    assert len(stale) == 1 and "2015" in stale[0]["value"]


def test_user_profile_and_funding_sources_emitted(tmp_path):
    """Portal-mandatory structures are produced: User Profile keywords + a Funding Source per grant."""
    from lxml import etree
    with open(os.path.join(REPO, "examples", "sample_cv_data.json")) as f:
        cv = json.load(f)
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw), this_year=2026)
    tree = etree.parse(str(raw))

    # exactly one User Profile, carrying one keyword sub-record per supplied keyword
    ups = [s for s in tree.iter("section")
           if s.get("label") == "User Profile" and s.get("recordId")]
    assert len(ups) == 1
    kws = [c for c in ups[0].findall("section")
           if c.get("label") == "Research Specialization Keywords"]
    assert len(kws) == len(cv["user_profile"][0]["research_keywords"])
    assert kws[0].find("field[@label='Research Specialization Keywords']/value").text == "Meteor physics"

    # every grant has a Funding Source; the catalog funder resolved to an <lov>, the other to free text
    rfh = [s for s in tree.iter("section")
           if s.get("label") == "Research Funding History" and s.get("recordId")]
    assert len(rfh) == 2
    for g in rfh:
        srcs = [c for c in g.findall("section") if c.get("label") == "Funding Sources"]
        assert len(srcs) == 1
    assert tree.findall(".//section[@label='Funding Sources']"
                        "/field[@label='Funding Organization']/lov")
    assert tree.findall(".//section[@label='Funding Sources']"
                        "/field[@label='Other Funding Organization']/value")

    # with both structures present the file is import-valid
    assert validate_file(str(raw), import_safe=False) == []


def test_missing_funding_source_flagged_and_invalid(tmp_path):
    """A grant with no funding_sources is emitted but flagged incomplete, and validate rejects it."""
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    cv = {
        "research_funding": [
            {"funding_type": "Grant", "funding_title": "Sourceless grant",
             "role": "Principal Investigator", "status": "Awarded", "start": "2025/02"}
        ],
        "user_profile": [{"research_keywords": ["Astronomy"]}],
    }
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw), this_year=2026)
    assert res["counts"]["research_funding"] == 1            # kept, not dropped
    inc = [u for u in res["unresolved"]
           if u["section"] == "research_funding" and u["kind"] == "incomplete"]
    assert inc and "Funding Sources" in inc[0]["value"]
    probs = validate_file(str(raw), import_safe=False)
    assert any("Funding Source" in p for p in probs)


def test_missing_user_profile_flagged_and_invalid(tmp_path):
    """No User Profile keywords -> unresolved note + validate rejects the file."""
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    cv = {"presentations": [{"title": "Talk", "year": "2024"}]}
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw), this_year=2026)
    assert any(u["section"] == "user_profile" and u["kind"] == "incomplete"
               for u in res["unresolved"])
    probs = validate_file(str(raw), import_safe=False)
    assert any("User Profile" in p for p in probs)


def test_report_number_of_pages_defaults_to_one(tmp_path):
    seed = os.path.join(REPO, "examples", "seed_minimal.xml")
    cv = {"reports": [{"title": "No-page report", "year": "2024", "authors": "Doe, J"}]}
    raw = tmp_path / "gen.xml"
    res = generate.generate(cv, seed, str(raw), this_year=2026)
    assert res["counts"]["reports"] == 1
    from lxml import etree
    for s in etree.parse(str(raw)).iter("section"):
        if s.get("label") == "Reports" and s.get("recordId"):
            v = s.find("field[@label='Number of Pages']/value")
            assert v is not None and v.text == "1"
