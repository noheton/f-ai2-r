#!/usr/bin/env python3
"""wordcount.py — the shared word counter for the F(AI)2R paper revision plan.

Counts prose, headings and captions; skips math, citations/references, table and tikz bodies, and bibliography.
Every budget in doc/paper-revision/{decisions,final-plan}.json of the thesis repository and every "counted words"
figure in this revision's commits is this tool's output, so every section recount must use it, never a different
method (raw `wc -w` counts citation keys and macro names as words and gives a different, incompatible number).

Reconstruction note (2026-10-24): the original copy of this tool lived only in a workflow's scratch directory of the
dissertation session and was lost when that directory was cleared; it was never committed anywhere, which is itself
a gap (every number should come from a script this repository keeps). This is a reconstruction from the tool's own
documented behaviour (scattered through doc/paper-revision/final-plan.json of the thesis repo) and from
scripts/build_metrics.py's prose-counting regex of this repository (the closest prior art). Calibration against the
recorded ground truth: 06-meta-experiment.tex (unedited by this revision) 1591 recorded vs 1587 here (-4);
07-discussion.tex (after the extended blocks moved out, otherwise unedited) 2384 vs 2385 (+1); the five sections
already edited this revision score 1 to 6 words under their recorded post-edit counts (01: 474 vs 468, 02: 593 vs
589, 03: 443 vs 443 exact, 04: 861 vs 856, 05: 719 vs 718). All deltas are well inside the plan's own ±25-word
per-section tolerance; the counts already committed for sections 1 to 5 stand as originally measured and are not
retroactively corrected to this tool's slightly different number.

Usage: python3 tools/wordcount.py <file-or-dir> [--per-file]
"""
from __future__ import annotations

import argparse
import pathlib
import re

# Commands whose argument is prose, kept; the command wrapper is dropped. Order matters: these run BEFORE the
# generic command-stripping pass below, so a citation nested inside e.g. a caption is still removed afterward.
KEEP_CONTENT = re.compile(
    r"\\(?:emph|texttt|textbf|textit|textsuperscript|caption|section\*?|subsection\*?|subsubsection\*?|title)"
    r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
)
ENV_STRIP = re.compile(r"\\begin\{(tabular\*?|tikzpicture|equation\*?|align\*?)\}.*?\\end\{\1\}", re.DOTALL)
# A table/figure environment counts only as its caption: everything else inside it (the tabular or tikzpicture
# body, a footnotesize note, \label, \includegraphics, …) is invisible to the counter, caption text is prose.
FLOAT_ENV = re.compile(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}", re.DOTALL)
CAPTION = re.compile(r"\\caption\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")
DISPLAY_MATH = re.compile(r"\\\[.*?\\\]", re.DOTALL)
INLINE_MATH = re.compile(r"(?<!\\)\$[^$]*\$")
COMMENT = re.compile(r"(?<!\\)%.*$")
GENERIC_COMMAND = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?")
WORD = re.compile(r"[A-Za-z0-9]")


def strip_floats(text: str) -> str:
    """Replace each table/figure environment with just its caption(s), dropping the tabular/tikz/label body."""
    return FLOAT_ENV.sub(lambda m: " ".join(f"\\caption{{{c}}}" for c in CAPTION.findall(m.group(0))), text)


def count_text(text: str) -> int:
    text = strip_floats(text)
    text = ENV_STRIP.sub(" ", text)
    text = DISPLAY_MATH.sub(" ", text)
    text = INLINE_MATH.sub(" ", text)
    out = []
    for line in text.splitlines():
        line = COMMENT.sub("", line).strip()
        if not line:
            continue
        line = KEEP_CONTENT.sub(r"\1", line)
        line = GENERIC_COMMAND.sub(" ", line)
        line = line.replace("{", " ").replace("}", " ")
        out.append(line)
    tokens = " ".join(out).split()
    return sum(1 for t in tokens if WORD.search(t))


def targets(path: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path.glob("*.tex")) if path.is_dir() else [path]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--per-file", action="store_true")
    a = ap.parse_args(argv)
    files = targets(pathlib.Path(a.path))
    counts = [(f, count_text(f.read_text(encoding="utf-8"))) for f in files]
    if a.per_file or len(files) > 1:
        for f, n in counts:
            print(f"{n:6d}  {f}")
    total = sum(n for _, n in counts)
    print(f"{total:6d}  total ({len(counts)} file(s))" if (a.per_file or len(files) > 1) else str(total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
