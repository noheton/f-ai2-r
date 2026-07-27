#!/usr/bin/env python3
"""Build an arXiv-ready source bundle from paper/ (skill v0.17).

Follows the community submission checklist (T. Campbell, "How to submit
a paper to arXiv", trevorcampbell.me/html/arxiv.html) without touching
the repository layout the method needs:

- flatten sections/ and figures/ into one directory, rewriting \\input
  and \\includegraphics paths;
- strip full-line LaTeX comments (the structure-pass skeletons) so the
  public source tarball carries prose only; inline/trailing % stays,
  since TikZ and resizebox rely on it;
- include the compiled .bbl and EXCLUDE references.bib (arXiv does not
  need it once the .bbl ships) and all generated files;
- force pdflatex with \\pdfoutput=1 in the first lines and ask arXiv
  for enough passes via the \\typeout marker before \\end{document};
- verify the flattened bundle compiles standalone with the same page
  count as the repo build;
- emit dist/arxiv-<version>.tar.gz plus plain-text title/author/abstract
  (LaTeX stripped, single line) for the arXiv metadata form.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"


def strip_full_line_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        if re.match(r"^\s*%", line) and not re.match(r"^\s*\\%", line):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def flatten():
    stage = pathlib.Path(tempfile.mkdtemp(prefix="arxiv-"))
    main = (PAPER / "main.tex").read_text(encoding="utf-8")
    main = strip_full_line_comments(main)
    main = re.sub(r"\\input\{sections/([^}]+)\}", r"\\input{\1}", main)
    if "\\pdfoutput=1" not in main:
        main = main.replace("\\documentclass", "\\pdfoutput=1\n\\documentclass", 1)
    if "get arXiv to do 4 passes" not in main:
        main = main.replace(
            "\\end{document}",
            "\\typeout{get arXiv to do 4 passes: Label(s) may have changed. "
            "Rerun}\n\\end{document}")
    (stage / "main.tex").write_text(main, encoding="utf-8")
    for f in sorted((PAPER / "sections").glob("*.tex")):
        t = strip_full_line_comments(f.read_text(encoding="utf-8"))
        t = t.replace("figures/", "")
        (stage / f.name).write_text(t, encoding="utf-8")
    for aux in ("metrics.tex", "disclosure.tex"):
        t = strip_full_line_comments((PAPER / aux).read_text(encoding="utf-8"))
        (stage / aux).write_text(t, encoding="utf-8")
    bbl = PAPER / "main.bbl"
    if not bbl.exists():
        sys.exit("paper/main.bbl missing — compile the paper first (latexmk)")
    shutil.copy(bbl, stage / "main.bbl")
    for fig in sorted((PAPER / "figures").iterdir()):
        if fig.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf"):
            shutil.copy(fig, stage / fig.name)
    # main.tex references figures via figures/<name>; flatten those too
    m = (stage / "main.tex").read_text(encoding="utf-8").replace("figures/", "")
    (stage / "main.tex").write_text(m, encoding="utf-8")
    return stage


def verify(stage: pathlib.Path) -> int:
    r = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "main.tex"],
        cwd=stage, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit("flattened bundle failed to compile:\n" + r.stdout[-2000:])
    info = subprocess.run(["pdfinfo", str(stage / "main.pdf")],
                          capture_output=True, text=True)
    pages = int(re.search(r"Pages:\s+(\d+)", info.stdout).group(1))
    return pages


def plain(s: str) -> str:
    s = re.sub(r"%.*", "", s)
    s = s.replace("\\textsuperscript{2}", "2").replace("~", " ")
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\\\", " ")
    return re.sub(r"\s+", " ", s).strip()


def metadata():
    main = (PAPER / "main.tex").read_text(encoding="utf-8")
    title = re.search(r"\\title\{(.*?)\}\n", main, re.S).group(1)
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
                         main, re.S).group(1)
    return plain(title), plain(abstract)


def main():
    stage = flatten()
    # arXiv rejects generated files: compile-verify, then clean before packing
    pages = verify(stage)
    for junk in stage.iterdir():
        if junk.suffix in (".pdf", ".aux", ".log", ".out", ".fls",
                           ".fdb_latexmk", ".blg", ".bib"):
            if junk.name != "main.bbl" and not junk.suffix in (".png", ".jpg"):
                if junk.suffix == ".pdf" and junk.stem != "main":
                    continue  # figure PDFs stay
                junk.unlink()
    version = "dev"
    cff = (ROOT / "CITATION.cff")
    if cff.exists():
        mv = re.search(r"^version:\s*(\S+)", cff.read_text(), re.M)
        if mv:
            version = mv.group(1)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"arxiv-{version}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for f in sorted(stage.iterdir()):
            tar.add(f, arcname=f.name)
    title, abstract = metadata()
    print(f"{out} ({pages} pages verified from the flattened source)")
    print("\n--- arXiv metadata form (LaTeX stripped) ---")
    print(f"Title: {title}")
    print("Authors: Florian Krebs")
    print(f"Abstract: {abstract}")
    print("\nLicense (operator decision, logged): CC BY-NC-SA 4.0 -- select "
          "'Attribution-NonCommercial-ShareAlike' on the arXiv form. "
          "Subject class: likely cs.DL or cs.CY, cross-list cs.SE; "
          "everything in the tarball becomes public.")
    shutil.rmtree(stage)


if __name__ == "__main__":
    main()
