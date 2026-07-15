"""Guard: the COMMITTED submission bundle must equal a fresh bundle of the CURRENT src/hw3.

The team commits the real-ID submission bundle to the repo so both partners always pull the current
file. That only stays true if the committed bundle can't silently drift from the strategy source.
This test rebuilds the bundle from src/ and byte-compares it to the committed .py (and the .py inside
the committed .zip). On failure someone edited src/hw3 without rebuilding -> rerun:
    PYTHONPATH=src python build/make_submission.py --id1 <ID1> --id2 <ID2>
and commit submission_staging/.
"""
import importlib.util
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _build_bundle(id1, id2):
    spec = importlib.util.spec_from_file_location("bundle", ROOT / "build" / "bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_bundle(id1, id2)


def _committed_py():
    tracked = subprocess.run(
        ["git", "ls-files", "submission_staging/id_*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert len(tracked) == 1, f"expected exactly one committed submission .py, got {tracked}"
    return ROOT / tracked[0]


def test_committed_bundle_py_matches_current_src():
    py = _committed_py()
    _, id1, id2 = py.stem.split("_")  # id_<id1>_<id2>
    fresh = _build_bundle(id1, id2)
    assert py.read_text() == fresh, (
        f"Committed submission .py is STALE vs src/hw3. Rebuild + commit: "
        f"PYTHONPATH=src python build/make_submission.py --id1 {id1} --id2 {id2}"
    )


def test_committed_zip_holds_current_bundle():
    py = _committed_py()
    _, id1, id2 = py.stem.split("_")
    fresh = _build_bundle(id1, id2)
    zpath = ROOT / "submission_staging" / f"{id1}_{id2}.zip"
    with zipfile.ZipFile(zpath) as z:
        inzip = z.read(f"id_{id1}_{id2}.py").decode()
    assert inzip == fresh, (
        f"The .py inside the committed zip {zpath.name} is stale vs src/hw3 -- rebuild the zip: "
        f"PYTHONPATH=src python build/make_submission.py --id1 {id1} --id2 {id2}"
    )
