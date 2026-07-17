"""Guard: every COMMITTED submission bundle must match the CURRENT src/hw3.

Two kinds of submission .py are committed here, and they are checked differently:

1. The BENCH bundle (placeholder ids) is built by this repo's own bundler, so it must
   byte-equal a fresh rebuild from src/hw3. On failure someone edited src/hw3 without
   rebuilding -> rerun:
       PYTHONPATH=src python build/make_submission.py --id1 <ID1> --id2 <ID2>

2. The VENDORED real-id submission is a copy of the file actually uploaded for grading,
   kept here so grader.yml runs the byte-exact artifact. It is built by the private repo's
   bundler, whose header names the course, whereas this repo's bundler emits a neutral
   header. It therefore CANNOT byte-equal a local rebuild. What must hold is that it is the
   same CODE: identical to the fresh bundle once ids and the module docstring are normalised.
   If that drifts, the cloud grader is measuring something other than what we submit.
"""
import importlib.util
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH_IDS = ("123456789", "987654321")


def _build_bundle(id1, id2):
    spec = importlib.util.spec_from_file_location("bundle", ROOT / "build" / "bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_bundle(id1, id2)


def _committed_pys():
    tracked = subprocess.run(
        ["git", "ls-files", "submission_staging/id_*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert tracked, "no committed submission .py found"
    return [ROOT / t for t in tracked]


def _ids_of(py):
    _, id1, id2 = py.stem.split("_")  # id_<id1>_<id2>
    return id1, id2


def _normalise(text, id1, id2):
    """Strip the identity of a bundle: its ids and its module docstring header."""
    text = text.replace(f"{id1}_{id2}", "PAIR_ID").replace(f"{id1}, {id2}", "PAIR_IDS")
    return re.sub(r'\A""".*?"""', '"""HEADER"""', text, count=1, flags=re.S)


def test_bench_bundle_py_matches_current_src():
    id1, id2 = BENCH_IDS
    py = ROOT / "submission_staging" / f"id_{id1}_{id2}.py"
    assert py.exists(), f"{py.name} is missing"
    assert py.read_text() == _build_bundle(id1, id2), (
        "Committed bench bundle .py is STALE vs src/hw3. Rebuild + commit: "
        f"PYTHONPATH=src python build/make_submission.py --id1 {id1} --id2 {id2}"
    )


def test_bench_zip_holds_current_bundle():
    id1, id2 = BENCH_IDS
    fresh = _build_bundle(id1, id2)
    zpath = ROOT / "submission_staging" / f"{id1}_{id2}.zip"
    with zipfile.ZipFile(zpath) as z:
        inzip = z.read(f"id_{id1}_{id2}.py").decode()
    assert inzip == fresh, (
        f"The .py inside the committed zip {zpath.name} is stale vs src/hw3 -- rebuild it: "
        f"PYTHONPATH=src python build/make_submission.py --id1 {id1} --id2 {id2}"
    )


def test_vendored_real_submission_is_the_same_code_as_src():
    """Any real-id bundle vendored for grader.yml must be the current src, modulo identity.

    It is deliberately NOT byte-equal (different bundler header), so compare normalised text.
    """
    bench_id1, bench_id2 = BENCH_IDS
    fresh_norm = _normalise(_build_bundle(bench_id1, bench_id2), bench_id1, bench_id2)
    vendored = [p for p in _committed_pys() if _ids_of(p) != BENCH_IDS]
    for py in vendored:
        id1, id2 = _ids_of(py)
        assert _normalise(py.read_text(), id1, id2) == fresh_norm, (
            f"Vendored submission {py.name} has DRIFTED from src/hw3 -- the cloud grader would "
            "measure code we are not submitting. Rebuild it from the private repo and re-vendor."
        )
