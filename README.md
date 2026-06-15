# AutoCCV

**Turn a PDF academic CV into an import-ready [Canadian Common CV](https://ccv-cvc.ca) (CCV) XML — driven by Claude Code.**

Updating a CCV by hand through the web portal is painful for anything bulk: publications,
presentations, supervision, funding. AutoCCV reads your PDF CV, extracts every entry, maps it to the
correct CCV sections and controlled-vocabulary codes, enriches publications with DOIs, and emits a
single XML file you import in one shot.

The intelligence (reading the PDF, deciding what each line is, asking you when unsure) runs inside
**Claude Code** via a bundled skill. The XML generation, code resolution, cleaning, and validation
run as deterministic, tested Python — so the output is reproducible and the importer-breaking
gotchas (embedded line breaks, non-ASCII diacritics) are handled automatically.

---

## How it works (the short version)

```
PDF CV ──▶  Claude Code (SKILL)  ──▶  cv_data.json  ──▶  autoccv (Python)  ──▶  CCV-output.xml
                 │                         ▲                    │
          asks you when unsure       the contract        seed CCV export (your identity)
          enriches DOIs (Crossref)                       + shipped catalog of CCV codes
```

- **You provide:** your **PDF CV** and a **seed CCV export** (your CCV with *Personal Information*
  already filled, exported as XML from the portal).
- **Claude Code produces:** `cv_data.json` (structured CV), then runs the Python pipeline to produce
  **`CCV-output.xml`** plus **`NOTES.md`** (assumptions and fields to double-check before importing).

Every CCV field/section/code ID is a **global constant** (verified across multiple real CVs), so the
shipped catalog + your seed are all that's needed — no manual code lookups.

---

## Quick start (the intended flow)

1. **Fill Personal Information & export a seed.** Log in at <https://ccv-cvc.ca> → **CV → Generic** →
   fill the **Personal Information** section → **export** the CV as XML. Save it into this repo
   (e.g. `my-seed.xml`).
2. **Clone and open in Claude Code.**
   ```bash
   git clone https://github.com/<you>/AutoCCV.git
   cd AutoCCV
   pip install -r requirements.txt
   claude            # open Claude Code in this directory
   ```
3. **Point it at your CV.** In Claude Code:
   > Use the autoccv skill to convert `My-CV.pdf` into a CCV. My seed export is `my-seed.xml`.

   Claude Code reads the PDF, asks you a few grouped questions (publication status, co-author roles,
   ambiguous DOIs…), and runs the pipeline.
4. **Review & import.** Read `NOTES.md`, fix any flagged fields if you wish, then import
   `CCV-output.xml` at the portal (**Utilities → Import**). Keep your seed export as a backup.

> AutoCCV **requires** the seed export — it guarantees your identity records are correct and lets it
> reuse organization IDs you've already entered.

---

## Manual / scripted usage (no Claude Code)

If you write `cv_data.json` yourself (see `schema/cv_data.schema.json` and
`examples/sample_cv_data.json`), you can run the pipeline directly:

```bash
# 1. (optional) enrich publications with DOIs/volume/issue from Crossref
python3 -m autoccv.doi cv_data.json

# 2. generate the CCV XML from your seed + cv_data
python3 -m autoccv.generate --seed my-seed.xml --data cv_data.json --out CCV-output.raw.xml

# 3. make it import-safe (ASCII, single line)
python3 -m autoccv.clean CCV-output.raw.xml -o CCV-output.xml

# 4. validate
python3 -m autoccv.validate CCV-output.xml      # -> "OK — valid and import-safe"
```

(Installing the package via `pip install .` also gives the `autoccv-build/-clean/-validate/-doi` commands.)

---

## Repository layout

```
.claude/skills/autoccv/SKILL.md   the Claude Code skill (the procedure Claude follows)
autoccv/                          deterministic Python package
  ccvgen.py      lxml primitives: clone records, set value/lov/refTable/date, insert at right depth
  generate.py    data-driven generator: cv_data.json + skeleton + section_map -> XML
  resolver.py    maps human labels -> CCV lov ids / refTable chains (exact -> ascii -> fuzzy)
  clean.py       transliterate non-ASCII + strip line breaks + single-line (the import-hang fix)
  validate.py    well-formedness + recordId + import-safety lint
  merge.py       harvest org IDs from the seed; dedup vs existing records
  doi.py         Crossref enrichment
data/                             shipped, generated from the example CVs
  skeleton.xml          one blank template record per section (carries real field IDs)
  section_map.json      cv_data field -> CCV field label + type + lov/refTable rule, per section
  lov_catalog.json      CCV field label -> {human label -> code id}
  reftable_catalog.json organizations / geography / research-classification trees
  section_paths.json    where each section lives in the container hierarchy
schema/cv_data.schema.json        the LLM -> generator contract
build_tools/                      maintainer scripts that (re)build data/ from examples/
examples/                         real CCV exports + a sample cv_data.json + a minimal seed
tests/                            pytest suite
```

## How the data is built

The catalogs and skeleton are **harvested from real CCV exports** in `examples/`. To rebuild them
(e.g. after adding a richer example with more sections):

```bash
cd build_tools
python3 extract_catalogs.py        # -> data/lov_catalog.json, data/reftable_catalog.json
python3 extract_section_paths.py   # -> data/section_paths.json
python3 extract_skeleton.py        # -> data/skeleton.xml   (run after section_paths)
```

The more (and more complete) example CVs you add to `examples/`, the richer the catalog of
organizations, disciplines, and controlled-vocabulary options becomes.

> **Privacy:** real CCV exports contain personal data, so `examples/CCV-*.xml` are **git-ignored**
> and not published. The committed `data/` artifacts are derived and PII-free (the skeleton is
> blanked; the catalogs hold only organization/vocabulary names). Maintainers keep raw exports
> locally to rebuild `data/`. End users never need them — `data/` ships pre-built.

## Supported sections

Degrees · Academic & Non-academic Work Experience · Research Funding · Courses Taught ·
Student/Postdoctoral Supervision · Committee & Other Memberships · Recognitions ·
Editorial & Journal Review Activities · Credentials · Presentations · Journal Articles ·
Conference Publications · Reports · Books · Book Chapters · Text & Broadcast Interviews ·
Knowledge & Technology Translation · International Collaboration Activities · Event Administration ·
Organizational Review Activities · Leaves of Absence and Impact on Research.

Personal Information comes from your seed. Adding a new section is a JSON edit in
`data/section_map.json` (plus a skeleton record harvested from any export that has it) — no code change.

## What it handles for you

- **Controlled vocabulary** — degree types, funding/supervision roles, recognition types, organizations,
  research disciplines, etc. resolved to the exact CCV code IDs; unresolved values fall back to free
  text and are flagged in `NOTES.md`.
- **Import-hang prevention** — the CCV importer stalls on embedded line breaks and non-ASCII
  characters; `clean` removes both and `validate` re-checks.
- **DOI enrichment** — missing DOIs/volume/issue filled from Crossref with confidence-gated auto-accept.
- **Idempotent re-runs** — records already in your seed are de-duplicated, so you can iterate.

## Development

```bash
pip install -r requirements.txt
python3 -m pytest -q
```

## Disclaimer

AutoCCV is an unofficial tool and is not affiliated with the Canadian Common CV / CIHR. CCV field and
code identifiers were observed from real exports and may change if the CCV schema is updated; re-run
the `build_tools` extractors against a fresh export if imports start failing. Always review `NOTES.md`
and keep a backup of your existing CV before importing.

## License

MIT — see [LICENSE](LICENSE).
