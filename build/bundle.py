"""Bundle the modular ``src/hw3`` package into the single required submission file.

The HW must be submitted as ONE stdlib-only file ``id_<ID1>_<ID2>.py`` containing the
classes ``BiddingAgent1`` and ``BiddingAgent2``. We develop in clean modules and inline
them here via the AST: per module drop the module docstring + internal imports, keep the
bodies, emit one deduplicated external-import block. We then (1) VERIFY each grader-facing
method signature is byte-identical to ``fixtures/id_123456789_987654321.py`` (class-scoped,
so the two classes' identically-named methods never collide -- the HW2 bundler bug), (2)
inject the real IDs into ``self.id`` in both classes, and (3) assert the result is stdlib-only.

Usage:  python build/bundle.py --id1 <ID1> --id2 <ID2> [--out submission_staging/id_<ID1>_<ID2>.py]
"""
import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "hw3"
TEMPLATE = ROOT / "fixtures" / "id_123456789_987654321.py"
PLACEHOLDER_ID = "123456789_987654321"

# strategy + descent first so helper functions/classes are defined before the classes that use
# them (agent1 subclasses descent.DescentAgent1; agent2 calls strategy.choose_bid).
MODULES = ["strategy", "descent", "agent1", "agent2"]
LABELS = {
    "strategy": "Shared GSP bidding logic",
    "descent": "Distribution-EU + targeted descent (BiddingAgent1's policy engine)",
    "agent1": "Task 1 -- BiddingAgent1 (no budget)",
    "agent2": "Task 2 -- BiddingAgent2 (budget-constrained)",
}
# (class, method) signatures kept byte-identical to the template. __init__ included so the
# no-arg constructor is guaranteed; grader calls the rest positionally.
REQUIRED_SIGS = [
    ("BiddingAgent1", "__init__"), ("BiddingAgent1", "start_simulation"),
    ("BiddingAgent1", "get_bid"), ("BiddingAgent1", "notify_round_results"),
    ("BiddingAgent1", "get_id"),
    ("BiddingAgent2", "__init__"), ("BiddingAgent2", "start_simulation"),
    ("BiddingAgent2", "get_bid"), ("BiddingAgent2", "notify_round_results"),
    ("BiddingAgent2", "get_id"),
]


def _method_args(source, cls, method):
    """Ordered parameter names of a class method (the grader binds positionally, so param
    COUNT/order is what must match). Robust to comments, wrapping, and annotations."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for m in node.body:
                if isinstance(m, ast.FunctionDef) and m.name == method:
                    a = m.args
                    names = ([p.arg for p in getattr(a, "posonlyargs", [])]
                             + [p.arg for p in a.args]
                             + ([a.vararg.arg] if a.vararg else [])
                             + [p.arg for p in a.kwonlyargs]
                             + ([a.kwarg.arg] if a.kwarg else []))
                    return tuple(names)
    return None


def _verify_signatures(text):
    """Fail loudly if any grader-facing method's parameters drift from the template."""
    tmpl = TEMPLATE.read_text()
    for cls, method in REQUIRED_SIGS:
        want, have = _method_args(tmpl, cls, method), _method_args(text, cls, method)
        if have is None:
            raise RuntimeError(f"bundled file is missing {cls}.{method}")
        if want is not None and want != have:
            raise RuntimeError(
                f"parameter drift on {cls}.{method}:\n  template: {want}\n  source:   {have}\n"
                f"Keep src/hw3 method parameters identical to the template."
            )


def _strip(src):
    """Return (body-without-docstring-or-internal-imports, external-import-strings)."""
    tree = ast.parse(src)
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # drop module docstring
    kept, imports = [], []
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("hw3"):
            continue  # internal import -> same file now
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))
            continue
        kept.append(node)
    return ast.unparse(ast.Module(body=kept, type_ignores=[])), imports


def _assert_stdlib_only(text):
    """The grader forbids third-party libs; a stray import makes it silently skip our file."""
    tree = ast.parse(text)
    stdlib = getattr(sys, "stdlib_module_names", set())
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods = [node.module.split(".")[0]]
        for m in mods:
            if stdlib and m not in stdlib:
                raise RuntimeError(f"non-stdlib import in bundle: {m!r} (grader is stdlib-only)")


def build_bundle(id1, id2):
    ext_imports = {}
    sections = []
    for mod in MODULES:
        body, imports = _strip((SRC / f"{mod}.py").read_text())
        for imp in imports:
            ext_imports[imp] = None  # dedupe, preserve first-seen order
        sections.append(f"# ===================== {LABELS[mod]} =====================\n{body}")

    header = (f'"""HW3 -- GSP ad-auction simulation. GSP ad-auction bidding bot.\n'
              f'BiddingAgent1 (no budget) + BiddingAgent2 (budget). Submitted by {id1}, {id2}."""')
    text = "\n".join([header, "\n".join(ext_imports), "\n\n\n".join(sections)]) + "\n"

    _verify_signatures(text)
    # Inject real IDs into self.id (quote-agnostic: ast.unparse may use single quotes).
    if PLACEHOLDER_ID not in text:
        raise RuntimeError("placeholder id not found in bundle -- cannot inject real IDs")
    text = text.replace(PLACEHOLDER_ID, f"{id1}_{id2}")
    _assert_stdlib_only(text)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id1", required=True)
    ap.add_argument("--id2", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    default_out = ROOT / "submission_staging" / f"id_{args.id1}_{args.id2}.py"
    out = Path(args.out) if args.out else default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_bundle(args.id1, args.id2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
