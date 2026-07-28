#!/usr/bin/env python3
"""build_paper_preview.py — render the compiled paper as a self-contained
HTML preview (typeset pages as embedded images + build status strip),
suitable for publishing as a live artifact/preview page.

Usage: python3 scripts/build_paper_preview.py [-o paper-preview.html]
                                              [--dpi 140] [--no-build]

Requires: latexmk (unless --no-build and paper/main.pdf exists) and
pdftoppm (poppler-utils). Graph stats are read from provenance.ttl when
present. AI note: drafted with AI assistance and verified by test-run.
"""
from __future__ import annotations
import argparse
import base64
import datetime
import html
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path.cwd()
PAPER = ROOT / "paper"


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    # errors="replace": LaTeX tool output may carry non-UTF-8 bytes
    # (e.g. Latin-1 umlauts echoed from the log by BibTeX entries).
    return subprocess.run(cmd, capture_output=True, text=True,
                          errors="replace", **kw)


def build_pdf() -> None:
    r = sh(["latexmk", "-pdf", "-interaction=nonstopmode", "main.tex"], cwd=PAPER)
    if r.returncode != 0:
        sys.exit("latexmk failed:\n" + r.stdout[-2000:] + r.stderr[-500:])


def pages_as_png(dpi: int) -> list[bytes]:
    with tempfile.TemporaryDirectory() as td:
        r = sh(["pdftoppm", "-png", "-r", str(dpi), str(PAPER / "main.pdf"),
                str(pathlib.Path(td) / "page")])
        if r.returncode != 0:
            sys.exit("pdftoppm failed: " + r.stderr[-500:])
        return [p.read_bytes() for p in sorted(pathlib.Path(td).glob("page-*.png"))]


def structure_notes() -> list[tuple[str, str]]:
    """Per-section planning skeletons: the %-comment blocks in
    sections/*.tex are the structure pass and never reach the PDF, so the
    preview shows them alongside the typeset pages."""
    out = []
    for f in sorted((PAPER / "sections").glob("*.tex")):
        t = f.read_text(encoding="utf-8")
        m = re.search(r"\\section\{([^}]*)\}", t)
        title = re.sub(r"\\[a-zA-Z]+\s*|[{}~$]", "", m.group(1)).strip() if m else f.stem
        notes = [line.lstrip()[1:] for line in t.splitlines()
                 if line.lstrip().startswith("%")]
        if notes:
            out.append((f.name + " — " + title, "\n".join(notes)))
    return out



# Copy-to-clipboard buttons for the grant/refuse commands: the page is
# static, so a click cannot (and must not) write the graph — the
# human-only rung is granted in the repository. The button stages the
# exact command instead.
COPY_SCRIPT_TEMPLATE = """
<script>
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.verif details pre').forEach(function (pre) {
    var code = pre.querySelector('code'); if (!code) return;
    var lines = code.textContent.split('\\n').filter(function (l) {
      return l.indexOf('provlog.py promote') !== -1; });
    if (!lines.length) return;
    var bar = document.createElement('div');
    bar.style.cssText = 'padding:6px 12px 10px;display:flex;gap:8px;flex-wrap:wrap';
    lines.forEach(function (cmd) {
      var b = document.createElement('button');
      var refuse = cmd.indexOf('--refuse') !== -1;
      b.textContent = refuse ? 'Copy refuse command' : 'Copy confirm command';
      b.style.cssText = 'font:inherit;font-size:.74rem;padding:3px 10px;' +
        'border:1px solid ' + (refuse ? '#a33' : '#2e8540') + ';border-radius:3px;' +
        'background:transparent;color:inherit;cursor:pointer';
      b.addEventListener('click', function () {
        var done = function () { b.textContent = 'Copied — run it in the repo'; };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(cmd).then(done, function () { fallback(); });
        } else { fallback(); }
        function fallback() {
          var ta = document.createElement('textarea'); ta.value = cmd;
          document.body.appendChild(ta); ta.select();
          try { document.execCommand('copy'); done(); } catch (e) {}
          document.body.removeChild(ta);
        }
      });
      bar.appendChild(b);
      var pm = cmd.match(/--id (\\S+) --to (\\S+)/);
      if (pm) {
        var a = document.createElement('a');
        a.textContent = refuse ? 'Refuse via git issue' : 'Confirm via git issue';
        a.style.cssText = b.style.cssText + ';text-decoration:none;display:inline-block';
        var body = 'Action: ' + (refuse ? 'refuse' : 'grant') +
          '\\nNote: <replace with your reasoning - required>\\n\\n' +
          'Opened from the paper preview; the aiprov-promote workflow executes ' +
          'this after verifying the issue author is a registered operator.';
        a.href = '__ISSUE_NEW__'
          .replace('{title}', encodeURIComponent('aiprov-promote: ' + pm[1] + ' -> ' + pm[2]))
          .replace('{body}', encodeURIComponent(body));
        a.rel = 'noopener';
        var label = a.textContent;
        a.addEventListener('click', function () {
          // Repeat-safe: some viewer shells honor only the first external
          // navigation, so every click also stages the link on the
          // clipboard, then the button resets itself for the next use.
          var url = a.href;
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(function () {
              a.textContent = 'Link copied - paste in browser if no tab opened';
            }, function () {});
          }
          setTimeout(function () { a.textContent = label; }, 3000);
        });
        bar.appendChild(a);
      }
    });
    pre.after(bar);
  });
});
</script>"""


def _issue_new_url() -> str:
    """Prefilled new-issue URL pattern for the repo's forge. GitHub and
    GitLab use different paths and parameter names; default to GitHub
    when the remote does not identify the forge (e.g. a local proxy)."""
    slug, remote = "noheton/f-ai2-r", ""
    try:
        remote = sh(["git", "remote", "get-url", "origin"]).stdout.strip()
        m = re.search(r"([\w.-]+/[\w.-]+?)(?:\.git)?/?$", remote)
        if m:
            slug = m.group(1)
    except Exception:
        pass
    if "gitlab" in remote:
        host = re.search(r"https?://([^/]+)/", remote)
        return (f"https://{host.group(1) if host else 'gitlab.com'}/{slug}"
                "/-/issues/new?issue[title]={title}&issue[description]={body}")
    return f"https://github.com/{slug}/issues/new?title={{title}}&body={{body}}"


COPY_SCRIPT = None  # resolved lazily in verification_html


def verification_html() -> str:
    """Collapsible rendering of doc/sources/VERIFICATION.md (the human-rung
    review queue) for the bottom of the preview, grouped by whether human
    intervention is required."""
    src = ROOT / "doc" / "sources" / "VERIFICATION.md"
    if not src.exists():
        return ""
    import html as _h
    parts, cur, buf, incode = [], None, [], False
    counts = {"\u26a0": 0, "\u2713": 0, "\u23f3": 0, "\U0001f5c2": 0}

    def flush():
        nonlocal cur, buf
        if cur is not None:
            klass = ("act" if cur.startswith("\u26a0")
                     else "done" if cur.startswith("\u2713")
                     else "int" if cur.startswith("\U0001f5c2") else "wait")
            parts.append(
                f'<details class="v-{klass}"><summary>'
                f'{_h.escape(re.sub(r"[`*]", "", cur))}</summary>'
                f'<pre>{"".join(buf)}</pre></details>')
        cur, buf = None, []

    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            flush()
            cur, incode = line[3:].strip(), False
            for icon in counts:
                if cur.startswith(icon):
                    counts[icon] += 1
            continue
        if line.startswith("# ") and parts is not None and (cur or parts):
            flush()
            parts.append(f'<h3 class="v-group">{_h.escape(line[2:].strip())}</h3>')
            continue
        if cur is None:
            continue
        if line.startswith("```"):
            buf.append("</code>" if incode else "<code>")
            incode = not incode
            continue
        esc = _h.escape(line)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"`([^`]+)`", r"<i>\1</i>", esc)
        esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', esc)
        buf.append(esc + ("\n" if incode else "<br>"))
    flush()
    total = sum(counts.values())
    warn, done, wait = counts["\u26a0"], counts["\u2713"], counts["\u23f3"]
    internal = counts["\U0001f5c2"]
    return (
        '<details class="notes verif"><summary><span class="pages-head">'
        f'Source verification queue \u2014 {warn} awaiting the '
        f'operator, {done} human-verified, {internal} internal, '
        f'{wait} not yet ready ({total} total)</span></summary>'
        '<p>Grouped by required action. \u26a0 needs the human operator now '
        '(evidence handed over by the rung-4 gate); \u23f3 needs AI-side '
        'work first; \U0001f5c2 is an in-repo artefact needing no literature '
        'check; \u2713 is done. Generated from provenance.ttl; the '
        'human rungs are the operator\'s alone.</p>'
        + "\n".join(parts)
        + COPY_SCRIPT_TEMPLATE.replace('__ISSUE_NEW__', _issue_new_url())
        + '</details>')


def graph_stats() -> dict | None:
    if not (ROOT / "provenance.ttl").exists():
        return None
    try:
        from rdflib import Graph, Namespace, RDF
        AIPROV = Namespace("https://w3id.org/aiprov/ns#")
        PROV = Namespace("http://www.w3.org/ns/prov#")
        g = Graph()
        g.parse(ROOT / "provenance.ttl", format="turtle")
        return {
            "triples": len(g),
            "activities": len(set(g.subjects(PROV.endedAtTime, None))),
            "claims": len(set(g.subjects(RDF.type, AIPROV.Claim))),
            "sources": len(set(g.subjects(RDF.type, AIPROV.Source))),
        }
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="paper-preview.html")
    ap.add_argument("--dpi", type=int, default=140)
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()

    if not a.no_build or not (PAPER / "main.pdf").exists():
        build_pdf()
    main_tex = (PAPER / "main.tex").read_text(encoding="utf-8")
    m = re.search(r"\\title\{(.+?)\}\s*$", main_tex, re.S | re.M)
    raw = m.group(1) if m else "Paper preview"
    raw = raw.replace("\\\\", " \u2014 ")
    raw = raw.replace("\\textsuperscript{2}", "\u00b2")
    title = " ".join(re.sub(r"\\[a-zA-Z]+|[{}~]", " ", raw).split())
    commit = sh(["git", "rev-parse", "--short", "HEAD"]).stdout.strip() or "uncommitted"
    dirty = bool(sh(["git", "status", "--porcelain"]).stdout.strip())
    stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    pngs = pages_as_png(a.dpi)
    stats = graph_stats()

    chips = [f"commit {commit}" + (" +dirty" if dirty else ""),
             f"{len(pngs)} pages", f"built {stamp}"]
    if stats:
        chips += [f"{stats['activities']} activities", f"{stats['claims']} claims",
                  f"{stats['sources']} sources", f"{stats['triples']} triples"]
    chip_html = "".join(f'<span class="chip">{html.escape(c)}</span>' for c in chips)
    pages_html = "\n".join(
        f'<figure class="page"><img alt="Page {i + 1}" '
        f'src="data:image/png;base64,{base64.b64encode(b).decode()}">'
        f'<figcaption>Page {i + 1} / {len(pngs)}</figcaption></figure>'
        for i, b in enumerate(pngs))
    verif_html = verification_html()
    notes = structure_notes()
    notes_html = ""
    if notes:
        blocks = "\n".join(
            f'<details open><summary>{html.escape(name)}</summary>'
            f'<pre>{html.escape(body)}</pre></details>'
            for name, body in notes)
        notes_html = (
            '<details class="notes" open><summary><span class="pages-head">'
            f'Planned structure — not yet prose ({len(notes)} sections)</span>'
            '</summary>'
            '<p>These skeletons live as LaTeX comments in '
            '<code>paper/sections/*.tex</code>; they steer the prose pass and '
            'never appear in the typeset PDF.</p>' + blocks + '</details>')

    page = f"""<title>{html.escape(title)}</title>
<style>
:root {{
  --ground: #eceff2; --ink: #20262d; --muted: #5c6672; --accent: #00658b;
  --chip-bg: #ffffff; --chip-line: #d3dae0; --page-shadow: 0 1px 4px rgba(20,30,40,.18);
}}
@media (prefers-color-scheme: dark) {{ :root {{
  --ground: #14181d; --ink: #e6eaee; --muted: #97a1ac; --accent: #56a8c8;
  --chip-bg: #1d2329; --chip-line: #313a43; --page-shadow: 0 1px 6px rgba(0,0,0,.5);
}} }}
:root[data-theme="dark"] {{
  --ground: #14181d; --ink: #e6eaee; --muted: #97a1ac; --accent: #56a8c8;
  --chip-bg: #1d2329; --chip-line: #313a43; --page-shadow: 0 1px 6px rgba(0,0,0,.5);
}}
:root[data-theme="light"] {{
  --ground: #eceff2; --ink: #20262d; --muted: #5c6672; --accent: #00658b;
  --chip-bg: #ffffff; --chip-line: #d3dae0; --page-shadow: 0 1px 4px rgba(20,30,40,.18);
}}
body {{ background: var(--ground); color: var(--ink);
  font: 15px/1.5 Arial, Helvetica, sans-serif; margin: 0; }}
main {{ max-width: 900px; margin: 0 auto; padding: 24px 16px 48px; }}
header h1 {{ font-size: 1.25rem; line-height: 1.35; margin: 0 0 4px;
  text-wrap: balance; }}
header .sub {{ color: var(--muted); font-size: .82rem; margin: 0 0 12px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }}
.chip {{ background: var(--chip-bg); border: 1px solid var(--chip-line);
  border-radius: 3px; padding: 2px 8px; font-size: .78rem; color: var(--muted);
  font-variant-numeric: tabular-nums; }}
.chip:first-child {{ color: var(--accent); border-color: var(--accent); }}
.pages {{ display: flex; flex-direction: column; gap: 22px; }}
.page {{ margin: 0; }}
.page img {{ display: block; width: 100%; height: auto; background: #fff;
  box-shadow: var(--page-shadow); }}
.page figcaption {{ color: var(--muted); font-size: .75rem; text-align: right;
  padding-top: 4px; font-variant-numeric: tabular-nums; }}
.notes {{ margin: 4px 0 18px; }}
.pages-head {{ font-size: 1rem; font-weight: bold; }}
.pdfblock > summary, .notes > summary {{ cursor: pointer; padding: 8px 0;
  border-top: 1px solid var(--chip-line); }}
.pdfblock .pages {{ margin-top: 8px; }}
.notes h2 {{ font-size: 1rem; margin: 0 0 4px; }}
.notes > p {{ color: var(--muted); font-size: .82rem; margin: 0 0 12px; }}
.notes details {{ background: var(--chip-bg); border: 1px solid var(--chip-line);
  border-radius: 3px; margin-bottom: 8px; }}
.notes summary {{ cursor: pointer; padding: 6px 10px; font-weight: bold;
  font-size: .85rem; }}
.v-group {{ font-size: .9rem; margin: 14px 0 6px; color: var(--muted); }}
.notes .v-act summary {{ border-left: 3px solid #c77700; }}
.notes .v-done summary {{ border-left: 3px solid #2e8540; }}
.notes .v-wait summary {{ border-left: 3px solid var(--chip-line); color: var(--muted); }}
.notes .v-int summary {{ border-left: 3px solid #6b7f94; color: var(--muted); }}
.notes pre {{ margin: 0; padding: 8px 12px 12px; overflow-x: auto;
  font-size: .74rem; line-height: 1.45; color: var(--ink);
  border-top: 1px solid var(--chip-line); white-space: pre; }}
footer {{ color: var(--muted); font-size: .78rem; margin-top: 28px;
  border-top: 1px solid var(--chip-line); padding-top: 10px; }}
</style>
<main>
<header>
  <h1>{html.escape(title)}</h1>
  <p class="sub">Continuously built draft — regenerated from the repository
  on every update; provenance-tracked under the aiprov method.</p>
  <div class="chips">{chip_html}</div>
</header>
{notes_html}
<details class="pdfblock" open>
<summary><span class="pages-head">Typeset build ({len(pngs)} pages)</span></summary>
<div class="pages">
{pages_html}
</div>
</details>
{verif_html}
<footer>Preview generated by build_paper_preview.py from paper/main.pdf.
Structure lives in paper/sections/ (chapter-per-file); the acknowledgement's
AI-transparency statement is derived from provenance.ttl.</footer>
</main>
"""
    pathlib.Path(a.out).write_text(page, encoding="utf-8")
    print(f"{a.out}: {len(pngs)} pages, {len(page) // 1024} KiB")


if __name__ == "__main__":
    main()
