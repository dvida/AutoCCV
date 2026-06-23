"""Data-driven CCV generator: cv_data.json + skeleton.xml + section_map.json -> populated XML.

The base tree is the user's seed export (carries identity); generated records are appended at the
correct container depth. One driver replaces per-section hand-coded builders; each section is
described once in section_map.json.
"""
import copy
import datetime
import json
import os
import re

from . import ccvgen
from .resolver import Catalog

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FMT = {"date": "yyyy-MM-dd", "yearmonth": "yyyy/MM", "year": "yyyy", "monthday": "MM/dd"}


def _norm_key(*parts):
    return "|".join((p or "").strip().lower() for p in parts)


def _effective(fspec, data):
    """Source value for a field, substituting the spec default when empty."""
    val = data.get(fspec["src"])
    if (val is None or val == "") and "default" in fspec:
        val = fspec["default"]
    return val


def _year_of(value):
    """Leading 4-digit year in a date/year/yearmonth string, or None."""
    m = re.search(r"\d{4}", str(value or ""))
    return int(m.group()) if m else None


def _too_old(spec, data, this_year):
    """True if a section with a `recency` rule has a date older than its window.

    Cutoff is Jan 1 of (this_year - years): an entry is kept iff its year >= that.
    Entries with no/undateable value are kept (presence is enforced separately by
    the required-field check); `keep_if_empty` documents that intent.
    """
    rec = spec.get("recency")
    if not rec:
        return False
    y = _year_of(data.get(rec["src"]))
    if y is None:
        return False
    return y < this_year - rec["years"]


def _missing_required(spec, data, catalog):
    """CCV labels of mandatory fields that are absent (so the entry is malformed).

    `required` is unconditional; `required_if: <src>` applies only when that source
    field is non-empty. An lov field counts as present only if its value resolves to
    a catalog value — a non-empty but unmatchable status (e.g. "In review") is treated
    as missing so the user is asked for a valid one.
    """
    missing = []
    for fspec in spec.get("fields", []):
        req = bool(fspec.get("required"))
        if not req and fspec.get("required_if"):
            dep = data.get(fspec["required_if"])
            req = dep is not None and str(dep).strip() != ""
        if not req:
            continue
        val = _effective(fspec, data)
        empty = val is None or str(val).strip() == ""
        if fspec["kind"] == "lov" and not empty:
            lid, _label, conf = catalog.resolve_lov(fspec["ccv"], str(val))
            if not (lid and conf in ("exact", "fuzzy", "suggest")):
                empty = True
        if empty:
            missing.append(fspec["ccv"])
    return missing


def _existing_keys(base_root, ccv_label, key_ccv_labels):
    keys = set()
    for sec in base_root.iter("section"):
        if sec.get("label") == ccv_label and sec.get("recordId") is not None:
            vals = []
            for kl in key_ccv_labels:
                f = ccvgen.field(sec, kl)
                v = f.find("value") if f is not None else None
                vals.append((v.text if v is not None else "") or "")
            keys.add(_norm_key(*vals))
    return keys


def _apply_field(record, fspec, data, catalog, unresolved, section):
    src, ccv, kind = fspec["src"], fspec["ccv"], fspec["kind"]
    val = _effective(fspec, data)
    if (val is None or val == "") and fspec.get("omit_if_empty"):
        ccvgen.remove_field(record, ccv)
        return
    if val is None:
        val = ""
    if kind in ("string", "bilingual"):
        ccvgen.set_value(record, ccv, str(val))
    elif kind in FMT:
        ccvgen.set_dated(record, ccv, str(val), FMT[kind])
    elif kind == "number":
        ccvgen.set_value(record, ccv, str(val))
    elif kind == "lov":
        lid, label, conf = catalog.resolve_lov(ccv, str(val))
        if lid and conf in ("exact", "fuzzy"):
            ccvgen.set_lov(record, ccv, lid, label)
        elif lid and conf == "suggest":
            ccvgen.set_lov(record, ccv, lid, label)
            unresolved.append({"section": section, "field": ccv, "value": val,
                               "kind": "lov", "reason": f"fuzzy guess '{label}' — verify"})
        else:
            ccvgen.clear_field(record, ccv)
            unresolved.append({"section": section, "field": ccv, "value": val,
                               "kind": "lov", "reason": "no lov match — set in UI"})
    elif kind == "reftable":
        rlabel = fspec["reftable"]
        rid, chain, conf = catalog.resolve_reftable(rlabel, str(val))
        if chain and conf in ("exact", "fuzzy"):
            ccvgen.set_reftable(record, ccv, rlabel, rid, chain)
        else:
            ccvgen.clear_field(record, ccv)
            if fspec.get("fallback_field"):
                try:
                    ccvgen.set_value(record, fspec["fallback_field"], str(val))
                except KeyError:
                    pass
            unresolved.append({"section": section, "field": ccv, "value": val,
                               "kind": "reftable", "reason": f"{rlabel} not in catalog — free text/blank"})


def _build_subsections(record, data, spec, catalog, unresolved, section):
    # capture subsection templates from the cloned record, then strip and rebuild
    templates = {}
    for sub in spec.get("subsections", []):
        t = ccvgen.find_subsection_template(record, sub["ccv"])
        if t is not None:
            templates[sub["ccv"]] = copy.deepcopy(t)
    ccvgen.strip_nested_sections(record)
    for sub in spec.get("subsections", []):
        items = data.get(sub["src"]) or []
        tmpl = templates.get(sub["ccv"])
        if tmpl is None or not items:
            continue
        for item in items:
            sub_rec = ccvgen.clone(tmpl)
            ccvgen.strip_nested_sections(sub_rec)
            item_data = {"_value": item} if sub.get("repeat_scalar") else item
            for fspec in sub["fields"]:
                _apply_field(sub_rec, fspec, item_data, catalog, unresolved, f"{section}/{sub['ccv']}")
            record.append(sub_rec)


def build_section(base_tree, skeleton, section_name, records, spec, catalog, section_paths,
                  unresolved, this_year):
    label = spec["ccv_section_label"]
    template = ccvgen.find_template(skeleton, label)
    # dedup only on keys that map to an actual CCV field (so existing records can be read back)
    src_to_ccv = {fs["src"]: fs["ccv"] for fs in spec["fields"]}
    key_src = [s for s in (spec.get("dedup_key") or []) if s in src_to_ccv]
    seen = set()
    if key_src:
        key_ccv = [src_to_ccv[s] for s in key_src]
        seen = _existing_keys(base_tree.getroot(), label, key_ccv)
    built = []
    for data in records:
        if key_src:
            k = _norm_key(*[str(data.get(s, "")) for s in key_src])
            if k in seen:
                unresolved.append({"section": section_name, "field": "(dedup)", "value": k,
                                   "kind": "dup", "reason": "already in seed — skipped"})
                continue
            seen.add(k)
        if _too_old(spec, data, this_year):
            rec_spec = spec["recency"]
            unresolved.append({"section": section_name, "field": "(recency)",
                               "value": str(data.get(rec_spec["src"], "")),
                               "kind": "stale",
                               "reason": "older than %d-year window (cutoff %d) — skipped"
                                         % (rec_spec["years"], this_year - rec_spec["years"])})
            continue
        missing = _missing_required(spec, data, catalog)
        if missing:
            ident = data.get("title") or data.get("student_name") or data.get("topic") or "(entry)"
            unresolved.append({"section": section_name, "field": "(incomplete)",
                               "value": "%s — missing: %s" % (ident, ", ".join(missing)),
                               "kind": "incomplete",
                               "reason": "mandatory field(s) missing — skipped; ask user to supply "
                                         "or confirm dropping the entry"})
            continue
        rec = ccvgen.clone(template)
        if not spec.get("subsections"):
            ccvgen.strip_nested_sections(rec)
        for fspec in spec["fields"]:
            _apply_field(rec, fspec, data, catalog, unresolved, section_name)
        if spec.get("subsections"):
            _build_subsections(rec, data, spec, catalog, unresolved, section_name)
            # a subsection marked required must yield >=1 item, else the record is
            # malformed for the portal (e.g. a grant with no Funding Source). Keep the
            # record but flag it so the user supplies the missing data and regenerates.
            for sub in spec["subsections"]:
                if sub.get("required") and not (data.get(sub["src"]) or []):
                    ident = (data.get("funding_title") or data.get("title")
                             or data.get("student_name") or "(entry)")
                    unresolved.append({"section": section_name, "field": "(incomplete)",
                                       "value": "%s — missing required %s" % (ident, sub["ccv"]),
                                       "kind": "incomplete",
                                       "reason": "required sub-record missing — supply it (ask the "
                                                 "user) and regenerate, or the CCV will not submit"})
        built.append(rec)
    ccvgen.insert_records(base_tree, label, built, section_paths)
    return len(built)


def generate(cv_data, seed_path, out_path, data_dir=DATA, this_year=None):
    if this_year is None:
        this_year = datetime.date.today().year
    if not isinstance(cv_data, dict):
        raise TypeError("cv_data must be a JSON object (got %s) — check cv_data.json" % type(cv_data).__name__)
    with open(os.path.join(data_dir, "section_map.json")) as f:
        section_map = json.load(f)
    with open(os.path.join(data_dir, "section_paths.json")) as f:
        section_paths = json.load(f)
    skeleton = ccvgen.load(os.path.join(data_dir, "skeleton.xml"))
    base = ccvgen.load(seed_path)
    catalog = Catalog(data_dir)

    from .merge import harvest_orgs
    harvest_orgs(base, catalog)

    counts, unresolved = {}, []
    for section_name, spec in section_map.items():
        records = cv_data.get(section_name)
        if not records:
            continue
        counts[section_name] = build_section(
            base, skeleton, section_name, records, spec, catalog, section_paths, unresolved, this_year)

    # User Profile + >=1 Research Specialization Keyword is mandatory for portal submit. If the
    # section is absent entirely (so build_section never ran), flag it here so it reaches NOTES.
    up = cv_data.get("user_profile") or []
    if not any((rec.get("research_keywords") or []) for rec in up if isinstance(rec, dict)):
        unresolved.append({"section": "user_profile", "field": "(incomplete)",
                           "value": "User Profile — no Research Specialization Keywords",
                           "kind": "incomplete",
                           "reason": "required to submit — ask the user for keywords (suggest some "
                                     "from their research areas), add to cv_data.json, regenerate"})

    ccvgen.serialize(base, out_path)
    return {"counts": counts, "unresolved": unresolved, "total_added": sum(counts.values())}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Generate a CCV import XML from cv_data + seed.")
    p.add_argument("--seed", required=True, help="user's CCV export (base tree with identity)")
    p.add_argument("--data", required=True, help="cv_data.json")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    with open(a.data) as f:
        cv_data = json.load(f)
    res = generate(cv_data, a.seed, a.out)
    print("added per section:", json.dumps(res["counts"], indent=2))
    print("total added:", res["total_added"], "| unresolved:", len(res["unresolved"]))
    if res["unresolved"]:
        with open(a.out + ".unresolved.json", "w") as f:
            json.dump(res["unresolved"], f, indent=2)
        print("unresolved -> ", a.out + ".unresolved.json")


if __name__ == "__main__":
    main()
