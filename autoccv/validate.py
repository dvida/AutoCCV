"""Structural validation + import-hang lint for a generated CCV XML."""
import re
from lxml import etree

HEX32 = re.compile(r"^[a-f0-9]{32}$")
NS = "http://www.cihr-irsc.gc.ca/generic-cv/1.0.0"


def validate_file(path, import_safe=True):
    """Return list of problems (empty == OK)."""
    problems = []
    try:
        tree = etree.parse(path)
    except etree.XMLSyntaxError as e:
        return [f"not well-formed XML: {e}"]

    root = tree.getroot()
    if root.tag != "{%s}generic-cv" % NS:
        problems.append(f"unexpected root element: {root.tag}")

    records = 0
    for sec in root.iter("section"):
        rid = sec.get("recordId")
        if rid is None:
            continue
        records += 1
        if not HEX32.match(rid):
            problems.append(f"bad recordId on {sec.get('label')}: {rid!r}")

    if records == 0:
        problems.append("no records found")

    if import_safe:
        raw = open(path, encoding="utf-8").read()
        # exactly one newline (after the XML declaration)
        if raw.count("\n") > 1:
            problems.append(f"file has {raw.count(chr(10))} newlines (expected 1 — embedded breaks?)")
        for el in tree.iter():
            if el.text:
                if any(ord(c) > 127 for c in el.text):
                    problems.append(f"non-ASCII text in <{el.tag} {el.get('label') or ''}>: {el.text[:40]!r}")
                    break
        for el in tree.iter():
            if el.text and ("\n" in el.text or "\t" in el.text):
                problems.append(f"embedded newline/tab in <{el.tag}>: {el.text[:40]!r}")
                break
    return problems


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Validate a CCV import XML.")
    p.add_argument("input")
    p.add_argument("--no-import-safe", action="store_true")
    a = p.parse_args(argv)
    probs = validate_file(a.input, import_safe=not a.no_import_safe)
    if not probs:
        print("OK — valid and import-safe")
        return 0
    print("PROBLEMS:")
    for x in probs:
        print(" -", x)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
