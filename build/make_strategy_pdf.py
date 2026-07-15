"""Generate the required ONE-PAGE strategy PDF from docs/strategy.md.

Uses matplotlib (available in the venv; no pandoc/reportlab needed). One figure == one page,
so the output is guaranteed single-page. Usage: python build/make_strategy_pdf.py [--out PATH]
"""
import argparse
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "docs" / "strategy.md"


def _clean(md):
    """Strip Markdown markup to plain text lines (keep bold markers as UPPER emphasis)."""
    out = []
    for raw in md.splitlines():
        s = raw.rstrip()
        if s.startswith("# "):
            out.append(("title", s[2:]))
            continue
        s = s.replace("`", "")
        # Strip Markdown emphasis FIRST (all '*' in the source are emphasis markers)...
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)  # bold
        s = re.sub(r"\*(.+?)\*", r"\1", s)      # italic
        s = s.replace("*", "")                   # any stray emphasis marker
        # ...THEN Unicode -> ASCII (introduces '*' for multiplication, no longer ambiguous).
        s = s.replace("’", "'").replace("—", "-").replace("·", "*").replace("≤", "<=")
        s = s.replace("→", "->").replace("×", "x").replace("ε", "eps").replace("−", "-")
        if s.startswith("- "):
            out.append(("bullet", s[2:]))
        elif s == "":
            out.append(("blank", ""))
        else:
            out.append(("para", s))
    return out


def render(out_path):
    lines = _clean(MD.read_text())
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    fig.subplots_adjust(left=0.08, right=0.95, top=0.96, bottom=0.05)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    y, x0, wrap = 0.965, 0.06, 108
    for kind, txt in lines:
        if kind == "title":
            ax.text(x0, y, txt, fontsize=15, fontweight="bold", va="top")
            y -= 0.032
        elif kind == "blank":
            y -= 0.012
        else:
            indent = "   * " if kind == "bullet" else ""
            for i, seg in enumerate(textwrap.wrap(txt, wrap) or [""]):
                if kind == "bullet":
                    prefix = indent if i == 0 else "     "
                else:
                    prefix = ""
                ax.text(x0, y, prefix + seg, fontsize=8.4, va="top", family="DejaVu Sans")
                y -= 0.0165
    with PdfPages(out_path) as pdf:
        pdf.savefig(fig)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "submission_staging" / "strategy.pdf"))
    args = ap.parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    render(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
