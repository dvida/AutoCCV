"""Low-level lxml primitives for building CCV generic-cv XML.

A CCV export is a tree of <section> elements. Container sections have no recordId; record
sections have a 32-hex recordId. Each <field id label> holds a <value>, a <lov>, or a <refTable>.
Records are cloned from a skeleton template, populated, and inserted into a base (seed) tree.
"""
import copy
import uuid
from lxml import etree

NS = "http://www.cihr-irsc.gc.ca/generic-cv/1.0.0"


def load(path):
    return etree.parse(path)


def newid():
    """32-hex recordId, matching CCV's format."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------- lookups
def find_template(tree_or_el, label):
    """First record-section with this label anywhere under tree_or_el."""
    root = tree_or_el.getroot() if hasattr(tree_or_el, "getroot") else tree_or_el
    for el in root.iter("section"):
        if el.get("label") == label and el.get("recordId") is not None:
            return el
    raise KeyError(f"no template section labelled {label!r}")


def find_subsection_template(record, label):
    """First nested record-section with `label` directly relevant to a parent record."""
    for el in record.iter("section"):
        if el is not record and el.get("label") == label and el.get("recordId") is not None:
            return el
    return None


def field(record, label):
    """Direct <field> child of `record` by label (not descending into subsections)."""
    for f in record.findall("field"):
        if f.get("label") == label:
            return f
    return None


# ---------------------------------------------------------------- cloning
def clone(template):
    """Deep copy a record and assign fresh recordIds to it and every nested record-section."""
    c = copy.deepcopy(template)
    c.set("recordId", newid())
    for sub in c.iter("section"):
        if sub is not c and sub.get("recordId") is not None:
            sub.set("recordId", newid())
    return c


def strip_nested_sections(record):
    """Remove all direct-child <section> elements (template's example subsections)."""
    for sub in list(record):
        if sub.tag == "section":
            record.remove(sub)


# ---------------------------------------------------------------- field setters
def _ensure_value(f, value_type=None, fmt=None):
    v = f.find("value")
    if v is None:
        v = etree.SubElement(f, "value")
        if value_type:
            v.set("type", value_type)
        if fmt:
            v.set("format", fmt)
    return v


def set_value(record, label, text):
    """Set a String/Bilingual <value> (mirrors Bilingual into <english>)."""
    f = field(record, label)
    if f is None:
        raise KeyError(f"field {label!r} not in record")
    v = _ensure_value(f, "String")
    v.text = text or ""
    bil = f.find("bilingual")
    if v.get("type") == "Bilingual" or bil is not None:
        if bil is None:
            bil = etree.SubElement(f, "bilingual")
        en = bil.find("english")
        if en is None:
            en = etree.SubElement(bil, "english")
        en.text = text or ""
    return f


def set_dated(record, label, text, fmt):
    """Set a date-like value (yyyy-MM-dd / yyyy/MM / yyyy / MM/dd). Empty text leaves it blank."""
    f = field(record, label)
    if f is None:
        raise KeyError(f"field {label!r} not in record")
    type_for = {"yyyy-MM-dd": "Date", "yyyy/MM": "YearMonth", "yyyy": "Year", "MM/dd": "MonthDay"}
    v = _ensure_value(f, type_for.get(fmt, "Date"), fmt)
    v.text = text or ""
    return f


def set_lov(record, label, lov_id, lov_text):
    f = field(record, label)
    if f is None:
        raise KeyError(f"field {label!r} not in record")
    for ch in list(f):
        f.remove(ch)
    lov = etree.SubElement(f, "lov")
    lov.set("id", lov_id)
    lov.text = lov_text
    return f


def set_reftable(record, label, reftable_label, ref_value_id, chain):
    """Build a <refTable refValueId label> with ordered <linkedWith> children.

    chain: list of {"label","value","refOrLovId"}.
    """
    f = field(record, label)
    if f is None:
        raise KeyError(f"field {label!r} not in record")
    for ch in list(f):
        f.remove(ch)
    rt = etree.SubElement(f, "refTable")
    if ref_value_id:
        rt.set("refValueId", ref_value_id)
    rt.set("label", reftable_label)
    for lw in chain:
        e = etree.SubElement(rt, "linkedWith")
        e.set("label", lw["label"])
        e.set("value", lw["value"])
        e.set("refOrLovId", lw["refOrLovId"])
    return f


def clear_field(record, label):
    """Empty a field (remove value/lov/refTable children) -> valid 'unset' state."""
    f = field(record, label)
    if f is not None:
        for ch in list(f):
            f.remove(ch)


def remove_field(record, label):
    """Remove the field element entirely (matches how exports omit empty optional fields)."""
    f = field(record, label)
    if f is not None:
        record.remove(f)


# ---------------------------------------------------------------- insertion
def _last_record_of(parent_or_root, label):
    last = None
    for el in parent_or_root.iter("section"):
        if el.get("label") == label and el.get("recordId") is not None:
            last = el
    return last


def _ensure_container_path(root, path):
    """Create/find a container chain [{label,id}, ...] under root; return deepest container."""
    parent = root
    for c in path:
        found = None
        for ch in parent.findall("section"):
            if ch.get("id") == c["id"] and ch.get("recordId") is None:
                found = ch
                break
        if found is None:
            found = etree.SubElement(parent, "section")
            found.set("id", c["id"])
            found.set("label", c["label"])
        parent = found
    return parent


def insert_records(tree, label, records, section_paths):
    """Insert `records` (same label) into the working tree at the correct container depth.

    If an existing record of this label is present, insert after the last one; otherwise build
    the container path from section_paths and append there.
    """
    if not records:
        return
    root = tree.getroot()
    anchor = _last_record_of(root, label)
    if anchor is not None:
        parent = anchor.getparent()
        idx = list(parent).index(anchor)
        for i, r in enumerate(records, 1):
            parent.insert(idx + i, r)
        return
    info = section_paths.get(label)
    if info is None:
        raise KeyError(f"no section path known for {label!r}")
    container = _ensure_container_path(root, info["path"])
    for r in records:
        container.append(r)


# ---------------------------------------------------------------- output
def serialize(tree_or_root, path):
    el = tree_or_root.getroot() if hasattr(tree_or_root, "getroot") else tree_or_root
    body = etree.tostring(el, xml_declaration=False, encoding="UTF-8")
    with open(path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(body)
