"""Make a CCV XML import-safe: transliterate non-ASCII -> ASCII, strip embedded line breaks,
collapse whitespace, emit a single-line file. The ccv-cvc.ca importer hangs on embedded
newlines in field values and on some non-ASCII diacritics; this pass fixes both.
"""
import re
import unicodedata
from lxml import etree

# characters that do NOT decompose under NFKD, plus punctuation normalisation
PREMAP = {
    "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "ß": "ss",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ı": "i", "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", "…": "...",
    " ": " ", " ": " ", " ": " ", "­": "",
}


def to_ascii(s):
    if not s:
        return s
    for k, v in PREMAP.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.encode("ascii", "ignore").decode("ascii")


def clean_text(s):
    if s is None:
        return s
    return re.sub(r"\s+", " ", to_ascii(s)).strip()


def clean_tree(tree):
    n = 0
    for el in tree.iter():
        if el.text and el.text.strip():
            new = clean_text(el.text)
            if new != el.text:
                el.text = new
                n += 1
        elif el.text is not None:
            el.text = None          # drop whitespace-only text -> single line
        if el.tail is not None:
            el.tail = None
    return n


def clean_file(in_path, out_path):
    tree = etree.parse(in_path)
    n = clean_tree(tree)
    body = etree.tostring(tree.getroot(), xml_declaration=False, encoding="UTF-8")
    with open(out_path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(body)
    return n


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Make a CCV XML import-safe (ASCII, single-line).")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    a = p.parse_args(argv)
    n = clean_file(a.input, a.output)
    print(f"cleaned {n} text nodes -> {a.output}")


if __name__ == "__main__":
    main()
