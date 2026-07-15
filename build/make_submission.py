"""Build + verify the final HW3 submission zip.

Naming (RESOLVED by the TA on the Moodle forum, 2026-07-10 -- HW3.pdf was ambiguous):
ONLY the code file carries the "id_" prefix; the pdf and zip do NOT. For a pair ID1, ID2:
  - code : id_<ID1>_<ID2>.py   (server.py globs id_*.py, so the prefix is mandatory here)
  - pdf  : <ID1>_<ID2>.pdf      (no prefix)
  - zip  : <ID1>_<ID2>.zip      (no prefix)
  - get_id() returns "<ID1>_<ID2>" (no prefix, matching the naive dummies).

Zips with Python's zipfile -- which, unlike macOS `zip`/Finder, never injects __MACOSX/ or
.DS_Store -- and runs HARD gates: exactly two entries with the right names, the .py loads in
isolation with both classes and a matching get_id, and the pdf is exactly one page. Everything
lands in submission_staging/ (gitignored).

Usage: python build/make_submission.py --id1 <ID1> --id2 <ID2>
"""
import argparse
import importlib.util
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import bundle as bundler  # noqa: E402
import make_strategy_pdf as pdfgen  # noqa: E402


def _load_isolated(py_path, modname):
    spec = importlib.util.spec_from_file_location(modname, py_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def build(id1, id2):
    py_stem = f"id_{id1}_{id2}"   # ONLY the code file carries the id_ prefix (server globs id_*.py)
    base = f"{id1}_{id2}"          # pdf + zip drop the prefix (TA ruling); get_id() == base too
    staging = ROOT / "submission_staging"
    staging.mkdir(parents=True, exist_ok=True)
    py_path = staging / f"{py_stem}.py"
    pdf_path = staging / f"{base}.pdf"
    zip_path = staging / f"{base}.zip"

    py_path.write_text(bundler.build_bundle(id1, id2))
    pdfgen.render(str(pdf_path))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(py_path, arcname=f"{py_stem}.py")   # arcname = basename only -> no nested dirs
        z.write(pdf_path, arcname=f"{base}.pdf")

    _gate(zip_path, py_path, pdf_path, py_stem, base)
    return zip_path


def _gate(zip_path, py_path, pdf_path, py_stem, base):
    import pdfplumber

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    assert set(names) == {f"{py_stem}.py", f"{base}.pdf"}, f"zip must be exactly 2 files: {names}"
    assert not any(n.startswith("__MACOSX") or ".DS_Store" in n or "/" in n for n in names), names

    mod = _load_isolated(str(py_path), "final_" + py_stem)
    a1, a2 = mod.BiddingAgent1(), mod.BiddingAgent2()
    assert a1.get_id() == a2.get_id() == base, f"get_id must be {base}"
    text = py_path.read_text()
    assert "hw3" not in text, "internal imports leaked into the bundle"

    with pdfplumber.open(pdf_path) as pdf:
        assert len(pdf.pages) == 1, f"strategy pdf must be EXACTLY 1 page, got {len(pdf.pages)}"
    print(f"OK  {zip_path.name}: {py_stem}.py + {base}.pdf, no junk, get_id={base}, pdf=1 page")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id1", required=True)
    ap.add_argument("--id2", required=True)
    args = ap.parse_args()
    zp = build(args.id1, args.id2)
    print(f"wrote {zp}")


if __name__ == "__main__":
    main()
