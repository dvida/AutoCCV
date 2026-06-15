"""Shared helpers for the build-time extractors."""
import os
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EXAMPLES = [
    os.path.join(REPO, "examples", "CCV-Denis_Vida.xml"),     # primary (rich, recent)
    os.path.join(REPO, "examples", "CCV-Peter_Brown.xml"),    # supplemental coverage
]
DATA = os.path.join(REPO, "data")


def parse(path):
    return etree.parse(path)


def is_record(section):
    """A <section> that represents a data record (has a recordId)."""
    return section.get("recordId") is not None


def is_container(section):
    """A <section> with no recordId — a structural wrapper (Education, Activities, ...)."""
    return section.tag == "section" and section.get("recordId") is None


def ancestor_sections(el):
    """List of ancestor <section> elements, root-most first."""
    out = []
    p = el.getparent()
    while p is not None:
        if p.tag == "section":
            out.append(p)
        p = p.getparent()
    out.reverse()
    return out


def is_top_level_record(section):
    """True if this record-section is not nested inside another record-section."""
    if not is_record(section):
        return False
    return not any(is_record(a) for a in ancestor_sections(section))


def iter_records(tree):
    for s in tree.getroot().iter("section"):
        if is_record(s):
            yield s
