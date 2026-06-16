---
name: autoccv
description: Convert a PDF academic CV into an import-ready Canadian Common CV (CCV) generic-cv XML for ccv-cvc.ca. Use when the user points to a PDF CV and wants to populate or update their CCV. Requires a seed CCV export (user fills Personal Information on the portal first). Reads the PDF, extracts structured data to cv_data.json, enriches DOIs via Crossref, batches clarifying questions, then runs the deterministic generator + cleaner + validator to emit a clean import file plus NOTES.md.
---

# AutoCCV — PDF CV → Canadian Common CV XML

You convert a researcher's PDF CV into a valid, import-ready CCV XML. You own the *judgment*
(reading the PDF, deciding what each line is, asking the user); deterministic Python owns the
*XML* (generation, controlled-vocabulary resolution, cleaning, validation). The boundary is one
file: **`cv_data.json`** — you write it, Python consumes it. **Never hand-write CCV XML or IDs.**

## Prerequisites (check first)
1. **A PDF CV** — ask for the path if not given.
2. **A seed CCV export (REQUIRED)** — the user's own `.xml` exported from ccv-cvc.ca after they
   filled in **Personal Information** (Identification, Address, Email, Language). This gives correct
   identity records and any organization IDs they already entered, and is the base the new records
   are appended to.
   If absent, STOP and tell the user:
   > Log in at https://ccv-cvc.ca → CV → Generic → fill **Personal Information** → export the CV as
   > XML → put the file in this folder and re-run. (AutoCCV requires the seed so identity is correct.)
3. `lxml` installed (`pip install -r requirements.txt`). Run everything from the repo root.

## Procedure

### 1. Extract the PDF into cv_data.json
Read the PDF (Read tool, in page ranges). Produce `cv_data.json` conforming to
`schema/cv_data.schema.json`. Keys are canonical section names matching `data/section_map.json`.
Rules:
- Put each CV entry under the right section. Mapping cheatsheet:
  - Peer-reviewed papers → `journal_articles`; non-refereed journal/newsletter items (e.g. WGN,
    eMeteorNews) → `journal_articles` with `"refereed":"No"`.
  - Published conference proceedings → `conference_publications`; oral/poster *talks* → `presentations`.
  - Technical/observational reports, circulars, telegrams → `reports`.
  - Invited talks, public lectures, colloquia → `presentations` (`invited:"Yes"`).
  - Radio/TV appearances → `broadcast_interviews`; newspaper/online articles → `text_interviews`.
  - Open-source software, datasets, tools, deployed systems → `ktt`.
  - Awards, prizes, honours, named scholarships → `recognitions`.
  - Society/association memberships → `other_memberships`; committees/working groups → `committee_memberships`.
  - Journals you review for → `journal_reviews`; editorial board roles → `editorial_activities`.
  - Certifications/short courses → `credentials`.
  - Organizing/chairing conferences, workshops, symposia → `event_administration`.
  - International research partnerships/collaborations → `international_collaboration`.
  - Sitting on external/program review panels for institutions → `organizational_review`.
  - Career interruptions / parental or medical leave affecting research → `leaves_of_absence`.
  - Cross-appointments / adjunct or visiting positions at other institutions → `affiliations`.
  - Preprints / working papers not yet formally published → `working_papers`.
- Controlled-vocab values go in as **human labels** (e.g. `"Doctorate"`, `"Astronomy and
  Astrophysics"`, `"University of Toronto"`, `"Principal Supervisor"`). The resolver maps them.
  Allowed labels for each field are in `data/lov_catalog.json`; orgs/disciplines in
  `data/reftable_catalog.json`. Prefer a label that exists there; if unsure, use the closest real
  name — the resolver fuzzy-matches and anything unresolved is logged for the user.
- Dates: `yyyy/MM` (most), `yyyy` (publication/presentation year, report year), `yyyy-MM-dd`
  (interview/course dates), `MM/dd` (date of birth). Year-only when no month is known: leave
  month off (use the `yyyy` field) or omit; never invent a month.
- Author lists: keep as a single string, `"Surname, I; Surname, I; ..."`, abbreviate long lists
  with `et al.` Estimate `contribution` bucket from author position: sole/first ≈ `31-40`,
  2nd–3rd ≈ `11-20`/`21-30`, deep in a large collaboration ≈ `0-10` (only those 4 buckets exist).
- Empty/unknown → omit the key (or `null`/`""`). Do not fabricate.
- Set `meta.seed_export` to the seed file path.

### 2. Enrich DOIs (on by default)
Run: `python3 -m autoccv.doi cv_data.json`
It fills missing DOI/volume/issue/pages for `journal_articles` and `conference_publications` from
Crossref, auto-accepting only high-confidence title+year matches. Ambiguous ones are written to
`cv_data.json.doi_candidates.json`. Review that file; for each, either pick the right candidate and
write its `doi`/`volume`/`issue`/`pages` into `cv_data.json`, or leave blank. **Batch** any
genuinely unclear ones into one round of questions to the user (don't ask one at a time).

### 3. Batch clarifying questions
Use `AskUserQuestion` (grouped, a few rounds at most) ONLY for things Python cannot decide:
- Publication status when unclear (Published / Accepted / In review→leave blank).
- Contribution-% bucket when author position is ambiguous.
- Supervision role (Principal vs Co-Supervisor), funding role (PI vs Co-investigator).
- Organization type for non-catalogued orgs; broadcast vs text for a media item.
Apply answers back into `cv_data.json`.

### 4. Generate, clean, validate
```
python3 -m autoccv.generate --seed <seed.xml> --data cv_data.json --out CCV-output.raw.xml
python3 -m autoccv.clean    CCV-output.raw.xml -o CCV-output.xml
python3 -m autoccv.validate CCV-output.xml
```
`generate` prints per-section counts and writes `CCV-output.raw.xml.unresolved.json` (controlled-vocab
misses, free-text org fallbacks, in-review statuses, deduped items). `clean` makes it import-safe
(ASCII, single-line — the ccv-cvc.ca importer hangs otherwise). `validate` must print
`OK — valid and import-safe`; if not, fix and re-run.

### 5. Write NOTES.md
Summarize for the user: per-section counts; every entry in `unresolved.json` rephrased as an action
("set Publishing Status to *In review* for …", "pick an Organization for *University of Osijek* in
the UI", "verify Contribution % on first-author papers — capped at 31-40"); any items you skipped or
deduped; and the import instructions (CCV portal → Utilities → Import; keep the original export as a
backup). Use the tone/structure of a concise action list.

### 6. Hand off
Tell the user the deliverable is `CCV-output.xml`, point them to `NOTES.md`, and remind them to
review the flagged fields before importing.

## Notes & gotchas
- The seed is the base tree; generated records are appended at the correct container depth. Re-running
  is safe — dedup skips records already present (matched on title+year etc.).
- If an organization isn't in the catalog, the generator writes it as free-text `Other Organization`
  and flags it; the user sets the proper Organization dropdown in the UI (or adds it to their seed and
  re-exports so it resolves next time).
- All CCV `field id`/`section id`/`lov id`/org `refOrLovId` values are global constants harvested into
  `data/`; that's why generation works from just the seed + PDF.
- To support a CV section not yet in `data/section_map.json`, add a leaf-section block there (and, if
  it's an empty section type with no skeleton record, harvest one via `build_tools/` from any export
  that has it). No code changes needed.
