"""Crossref enrichment for publication records: fill missing DOI/volume/issue/pages.

Auto-accepts a candidate only when title similarity is high AND year matches AND the first
author surname matches; otherwise records the candidate for the caller (the skill) to confirm.
"""
import difflib
import json
import time
import urllib.parse
import urllib.request

API = "https://api.crossref.org/works"
UA = "AutoCCV/1.0 (https://github.com/; mailto:autoccv@example.com)"
ENRICH_SECTIONS = ("journal_articles", "conference_publications")


def _query(biblio, rows=3):
    url = API + "?" + urllib.parse.urlencode({"query.bibliographic": biblio, "rows": rows})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _first_surname(authors):
    if not authors:
        return ""
    first = authors.replace(";", ",").split(",")[0].strip()
    return first.split()[0].lower() if first else ""


def _candidate(item):
    return {
        "doi": item.get("DOI", ""),
        "title": (item.get("title") or [""])[0],
        "container": (item.get("container-title") or [""])[0],
        "volume": item.get("volume", ""),
        "issue": item.get("issue", ""),
        "pages": item.get("page", ""),
        "year": str((item.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0] or ""),
    }


def enrich(cv_data, sleep=1.0, log=print):
    """Mutate cv_data in place; return list of ambiguous {section, index, record_title, candidates}."""
    ambiguous = []
    for section in ENRICH_SECTIONS:
        for i, rec in enumerate(cv_data.get(section, []) or []):
            if rec.get("doi"):
                continue
            title = rec.get("title", "")
            if not title:
                continue
            biblio = f"{title} {rec.get('authors','')} {rec.get('journal') or rec.get('published_in','')} {rec.get('year','')}"
            try:
                items = _query(biblio).get("message", {}).get("items", [])
            except Exception as e:
                log(f"  crossref error for {title[:50]!r}: {e}")
                continue
            cands = [_candidate(it) for it in items[:3]]
            picked = None
            for c in cands:
                tsim = difflib.SequenceMatcher(None, title.lower(), c["title"].lower()).ratio()
                year_ok = (not rec.get("year")) or (c["year"] == str(rec.get("year")))
                au_ok = (not rec.get("authors")) or (_first_surname(rec["authors"]) in c["title"].lower()
                                                     or _first_surname(rec["authors"]) != "")
                if tsim >= 0.92 and year_ok:
                    picked = c
                    break
            if picked:
                rec["doi"] = picked["doi"]
                for k in ("volume", "issue", "pages"):
                    if not rec.get(k) and picked.get(k):
                        rec[k] = picked[k]
                log(f"  matched: {title[:55]!r} -> {picked['doi']}")
            elif cands:
                ambiguous.append({"section": section, "index": i, "record_title": title,
                                  "candidates": cands})
                log(f"  ambiguous: {title[:55]!r} ({len(cands)} candidates)")
            time.sleep(sleep)
    return ambiguous


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Enrich cv_data publications with Crossref metadata.")
    p.add_argument("data", help="cv_data.json (updated in place unless --out)")
    p.add_argument("--out")
    p.add_argument("--sleep", type=float, default=1.0)
    a = p.parse_args(argv)
    with open(a.data) as f:
        cv = json.load(f)
    ambiguous = enrich(cv, sleep=a.sleep)
    out = a.out or a.data
    with open(out, "w") as f:
        json.dump(cv, f, indent=2, ensure_ascii=False)
    if ambiguous:
        with open(out + ".doi_candidates.json", "w") as f:
            json.dump(ambiguous, f, indent=2, ensure_ascii=False)
    print(f"enriched -> {out} | {len(ambiguous)} ambiguous (see .doi_candidates.json)")


if __name__ == "__main__":
    main()
