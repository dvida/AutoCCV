from autoccv import clean
from autoccv.validate import validate_file

DIRTY = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<generic-cv:generic-cv xmlns:generic-cv="http://www.cihr-irsc.gc.ca/generic-cv/1.0.0" lang="en">'
    '<section id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" label="Recognitions" '
    'recordId="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb">'
    '<field id="cccccccccccccccccccccccccccccccc" label="Recognition Name">'
    '<value type="String">Borovička Šegon “prize”\n\nsecond line</value>'
    '</field></section></generic-cv:generic-cv>'
)


def test_clean_makes_ascii_singleline(tmp_path):
    src = tmp_path / "dirty.xml"
    src.write_text(DIRTY, encoding="utf-8")
    out = tmp_path / "clean.xml"
    clean.clean_file(str(src), str(out))

    raw = out.read_text(encoding="utf-8")
    assert raw.count("\n") == 1                      # only after the declaration
    assert all(ord(c) < 128 for c in raw)            # pure ASCII
    assert "Borovicka" in raw and "Segon" in raw     # transliterated
    assert "second line" in raw and "\n\nsecond" not in raw
    # a fragment, not a full CV: check import-safety only, not portal submit-readiness
    assert validate_file(str(out), import_safe=True, submit_ready=False) == []


def test_to_ascii_map():
    assert clean.to_ascii("Šegon Đuriš łódź “q”–r") == 'Segon Duris lodz "q"-r'
