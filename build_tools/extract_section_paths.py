"""Map each top-level record-section LABEL to its container path (root-most first).

section_paths.json: {record_label: {"section_id": <id>, "path": [{"label":..,"id":..}, ...]}}
The path lists the container <section>s (no recordId) from root down to the record's parent.
Used to insert a new record at the correct depth when the working tree has no anchor of that label.
"""
import json
import os
from _common import EXAMPLES, DATA, parse, is_record, ancestor_sections


def main():
    paths = {}
    for path in EXAMPLES:
        if not os.path.exists(path):
            continue
        tree = parse(path)
        for s in tree.getroot().iter("section"):
            if not is_record(s):
                continue
            ancestors = ancestor_sections(s)
            # skip nested subsection records (an ancestor is itself a record)
            if any(is_record(a) for a in ancestors):
                continue
            label = s.get("label")
            if label in paths:
                continue
            paths[label] = {
                "section_id": s.get("id"),
                "path": [{"label": a.get("label"), "id": a.get("id")} for a in ancestors],
            }
    with open(os.path.join(DATA, "section_paths.json"), "w") as f:
        json.dump(paths, f, indent=2, ensure_ascii=False, sort_keys=True)
    print("top-level record sections:", len(paths))
    for k, v in sorted(paths.items()):
        print(f"  {k}: {' > '.join(p['label'] for p in v['path']) or '(root)'}")


if __name__ == "__main__":
    main()
