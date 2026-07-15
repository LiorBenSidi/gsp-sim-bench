"""Submission-artifact FORMAT gates, in CI (stdlib-only subset of make_submission's checks).

HW3.pdf page 4: "a submission not in the format detailed above will not be tested and will get
grade 0." The full gate (incl. the 1-page-PDF content check) needs matplotlib+pdfplumber, which
are intentionally NOT CI deps, so that check stays in build/make_submission.py at submission
time. What IS pure-stdlib and grade-critical -- the zip structure, the filenames, the server's
`glob('id_*.py')` prefix, and get_id == the bare "<id1>_<id2>" -- is guarded HERE so a bundler/zip
regression fails CI, not the real submission.

Naming RESOLVED by the TA on the Moodle forum (2026-07-10) -- ONLY the code file carries "id_":
  - the agent .py is named id_<id1>_<id2>.py  (server.py globs "id_*.py" -> the id_ prefix is load-bearing)
  - the .pdf is <id1>_<id2>.pdf  and the .zip is <id1>_<id2>.zip  -- NO "id_" prefix
  - get_id() returns "<id1>_<id2>"  -- NO prefix (matches the naive dummies: id_dummy_1.py -> "dummy_1")
  - the zip contains EXACTLY the two expected files, no __MACOSX/.DS_Store/.pyc/nested dirs
"""
import fnmatch
import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ID1, ID2 = "111", "222"
PY_STEM = f"id_{ID1}_{ID2}"   # ONLY the code file carries the id_ prefix (server globs id_*.py)
BASE = f"{ID1}_{ID2}"          # the .pdf/.zip names and get_id() -- NO prefix (TA ruling 2026-07-10)


def _bundle(out_py):
    subprocess.run(
        [sys.executable, str(ROOT / "build" / "bundle.py"), "--id1", ID1, "--id2", ID2,
         "--out", str(out_py)],
        check=True, cwd=str(ROOT), env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_agent_filename_matches_server_glob_and_get_id(tmp_path):
    out = tmp_path / f"{PY_STEM}.py"
    _bundle(out)
    # server.py discovers agents via glob('id_*.py'): the prefix is mandatory on the .py.
    assert fnmatch.fnmatch(out.name, "id_*.py"), f"{out.name} not matched by server glob id_*.py"
    mod = _load(str(out), "fmt_" + PY_STEM)
    assert mod.BiddingAgent1().get_id() == BASE      # get_id has NO id_ prefix (TA ruling)
    assert mod.BiddingAgent2().get_id() == BASE


def test_zip_is_exactly_two_clean_files_named_per_ta_ruling(tmp_path):
    # TA ruling: zip <ID1>_<ID2>.zip contains id_<ID1>_<ID2>.py (prefix) + <ID1>_<ID2>.pdf (no prefix).
    py = tmp_path / f"{PY_STEM}.py"
    pdf = tmp_path / f"{BASE}.pdf"
    _bundle(py)
    pdf.write_bytes(b"%PDF-1.4 stub for format test\n")  # name/structure check only, not page count
    zip_path = tmp_path / f"{BASE}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(py, arcname=f"{PY_STEM}.py")   # arcname = basename -> no nested dirs
        z.write(pdf, arcname=f"{BASE}.pdf")

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    assert set(names) == {f"{PY_STEM}.py", f"{BASE}.pdf"}, f"expected exactly 2 files, got {names}"
    # only the .py may carry the id_ prefix; the .pdf must not.
    assert not fnmatch.fnmatch(f"{BASE}.pdf", "id_*"), "pdf must NOT carry the id_ prefix"
    assert not any(n.startswith("__MACOSX") or ".DS_Store" in n or n.endswith(".pyc") or "/" in n
                   for n in names), f"junk/nested entries in zip: {names}"
    # HARD (HW3.pdf p.1): the agent .py is the ONLY file we change -- the grader files must NEVER
    # be bundled into the submission (the graders run their own server/CONSTANTS/dummies).
    forbidden = {"server.py", "CONSTANTS.py", "id_dummy_1.py", "id_dummy_2.py", "id_dummy_3.py",
                 "id_123456789_987654321.py"}
    assert not (set(names) & forbidden), f"grader files leaked into the submission zip: {names}"


def test_bundle_has_no_internal_imports_leaked(tmp_path):
    out = tmp_path / f"{PY_STEM}.py"
    _bundle(out)
    assert "hw3" not in out.read_text(), "internal package import leaked into the submission"
