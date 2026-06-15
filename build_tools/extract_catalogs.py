"""Harvest lov_catalog.json and reftable_catalog.json from the example CCV exports.

lov_catalog:     {ccv_field_label: {lov_text: lov_id}}
reftable_catalog:{reftable_label: {"refValueId": <id-or-null>, "entries": {leaf_value: [linkedWith,...]}}}
                 each linkedWith = {"label":..., "value":..., "refOrLovId":...}; keyed by the LEAF value.
"""
import json
import os
from _common import EXAMPLES, DATA, parse


def main():
    lov = {}          # field label -> {text: id}
    reftab = {}       # reftable label -> {"refValueId":..., "entries": {leaf: chain}}

    for path in EXAMPLES:
        if not os.path.exists(path):
            continue
        tree = parse(path)
        for field in tree.getroot().iter("field"):
            flabel = field.get("label")
            if flabel is None:
                continue
            lel = field.find("lov")
            if lel is not None and lel.get("id"):
                txt = (lel.text or "").strip()
                if txt:
                    lov.setdefault(flabel, {}).setdefault(txt, lel.get("id"))
            rt = field.find("refTable")
            if rt is not None:
                rlabel = rt.get("label") or flabel
                chain = [{"label": lw.get("label"), "value": lw.get("value"),
                          "refOrLovId": lw.get("refOrLovId")}
                         for lw in rt.findall("linkedWith")]
                if not chain:
                    continue
                leaf = chain[-1]["value"]
                bucket = reftab.setdefault(rlabel, {"refValueId": rt.get("refValueId"), "entries": {}})
                bucket["entries"].setdefault(leaf, chain)

    with open(os.path.join(DATA, "lov_catalog.json"), "w") as f:
        json.dump(lov, f, indent=2, ensure_ascii=False, sort_keys=True)
    with open(os.path.join(DATA, "reftable_catalog.json"), "w") as f:
        json.dump(reftab, f, indent=2, ensure_ascii=False, sort_keys=True)

    print("lov fields:", len(lov), "| total lov values:", sum(len(v) for v in lov.values()))
    print("reftable types:", {k: len(v["entries"]) for k, v in reftab.items()})


if __name__ == "__main__":
    main()
