"""Build data/skeleton.xml: one blanked, maximal-field representative record per top-level
record section, placed under its correct container path. Serves as the template library the
generator clones from. Run AFTER extract_section_paths.py.
"""
import copy
import json
import os
from lxml import etree
from _common import EXAMPLES, DATA, parse, is_record, ancestor_sections

NS = "http://www.cihr-irsc.gc.ca/generic-cv/1.0.0"


def field_count(section):
    return sum(1 for _ in section.iter("field"))


def blank(section):
    """Empty all data from a record while preserving field structure + date scaffolding."""
    for v in section.iter("value"):
        v.text = None
    for tag in ("english", "french"):
        for e in section.iter(tag):
            e.text = None
    for lov in list(section.iter("lov")):
        lov.getparent().remove(lov)
    for rt in list(section.iter("refTable")):
        rt.getparent().remove(rt)
    return section


def main():
    with open(os.path.join(DATA, "section_paths.json")) as f:
        paths = json.load(f)

    # pick the maximal-field representative record per top-level label across examples
    best = {}  # label -> (count, element)
    root_attrs = None
    for path in EXAMPLES:
        if not os.path.exists(path):
            continue
        tree = parse(path)
        if root_attrs is None:
            root_attrs = dict(tree.getroot().attrib)
        for s in tree.getroot().iter("section"):
            if not is_record(s) or any(is_record(a) for a in ancestor_sections(s)):
                continue
            label = s.get("label")
            n = field_count(s)
            if label not in best or n > best[label][0]:
                best[label] = (n, s)

    # build skeleton root
    root = etree.Element("{%s}generic-cv" % NS, nsmap={"generic-cv": NS})
    root.set("lang", (root_attrs or {}).get("lang", "en"))

    def ensure_container(chain):
        """Create/find the nested container path under root; return the deepest container (or root)."""
        parent = root
        for c in chain:
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

    for label, (_, rec) in sorted(best.items()):
        info = paths.get(label, {"path": []})
        container = ensure_container(info["path"])
        clone = blank(copy.deepcopy(rec))
        container.append(clone)

    body = etree.tostring(root, xml_declaration=False, encoding="UTF-8", pretty_print=True)
    with open(os.path.join(DATA, "skeleton.xml"), "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(body)
    print("skeleton sections:", len(best))


if __name__ == "__main__":
    main()
