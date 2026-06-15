"""Harvest organisation refTable chains from a seed export into the resolver's overlay, so
institutions the user already entered on the portal resolve even if not in the shipped catalog.
"""
from . import ccvgen


def harvest_orgs(seed_tree, catalog):
    root = seed_tree.getroot() if hasattr(seed_tree, "getroot") else seed_tree
    n = 0
    for rt in root.iter("refTable"):
        if rt.get("label") != "Organization":
            continue
        chain = [{"label": lw.get("label"), "value": lw.get("value"),
                  "refOrLovId": lw.get("refOrLovId")} for lw in rt.findall("linkedWith")]
        if chain:
            catalog.add_org(chain[-1]["value"], chain)
            n += 1
    return n
