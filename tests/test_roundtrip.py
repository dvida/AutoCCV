import os
from autoccv import ccvgen

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EX = os.path.join(REPO, "examples")


def _count(tree):
    return sum(1 for s in tree.getroot().iter("section") if s.get("recordId"))


def test_roundtrip_preserves_records(tmp_path):
    for name in ("CCV-Denis_Vida.xml", "seed_minimal.xml"):
        path = os.path.join(EX, name)
        if not os.path.exists(path):
            continue
        tree = ccvgen.load(path)
        before = _count(tree)
        out = tmp_path / name
        ccvgen.serialize(tree, str(out))
        after = _count(ccvgen.load(str(out)))
        assert before == after, f"{name}: {before} -> {after}"


def test_clone_assigns_fresh_recordids():
    tree = ccvgen.load(os.path.join(REPO, "data", "skeleton.xml"))
    tmpl = ccvgen.find_template(tree, "Journal Articles")
    a, b = ccvgen.clone(tmpl), ccvgen.clone(tmpl)
    assert a.get("recordId") != b.get("recordId")
    assert len(a.get("recordId")) == 32
