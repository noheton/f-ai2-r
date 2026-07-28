#!/usr/bin/env python3
"""Generate doc/sources/VERIFICATION.md — the human-rung review worksheet.

Derived entirely from provenance.ttl and the paper sources: for every
source on the ladder it lists the current rung, where the paper cites
it, the recorded check evidence (latest audit note), the access
material the rung-4 gate would hand over (vendored copy + sha256, or
DOI/URL), and the exact provlog commands to grant or refuse a human
rung. Regenerate after any promotion; do not edit by hand.
"""
import pathlib
import re

from rdflib import Graph, Namespace, RDF, RDFS

ROOT = pathlib.Path(__file__).resolve().parent.parent
AIPROV = Namespace("https://w3id.org/aiprov/ns#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCT = Namespace("http://purl.org/dc/terms/")

RUNG_ORDER = ["unverified", "needs-research", "reference-resolved",
              "ai-confirmed", "source-vendored", "human-confirmed",
              "human-read"]


def cite_locations(sid: str) -> tuple[list[str], int]:
    """Where and how often the paper cites the source.

    The occurrence count doubles as the relevance score for worksheet
    ordering: a source the argument leans on repeatedly is checked
    before one cited once in passing. Computed, not judged — the
    methodology is disclosed in the worksheet header.
    """
    cite_groups = re.compile(r"\\cite\{([^}]*)\}")

    def hits_in(text: str) -> int:
        return sum(1 for grp in cite_groups.findall(text)
                   if sid in (k.strip() for k in grp.split(",")))

    locs, count = [], 0
    for f in sorted((ROOT / "paper" / "sections").glob("*.tex")):
        hits = hits_in(f.read_text())
        if hits:
            locs.append(f.stem)
            count += hits
    hits = hits_in((ROOT / "paper" / "main.tex").read_text())
    if hits:
        locs.append("main (acknowledgment)")
        count += hits
    return locs, count


def _detex(s: str) -> str:
    """Light LaTeX-to-text cleanup for displaying a citing sentence."""
    s = re.sub(r"\\cite\{([^}]*)\}", r"[\1]", s)
    s = re.sub(r"\\(?:texttt|emph|textbf|textsuperscript)\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\ref\{[^}]*\}", "[ref]", s)
    s = re.sub(r"~", " ", s)
    s = re.sub(r"\\[a-zA-Z]+\{?", "", s).replace("}", "")
    s = re.sub(r"``|''", '"', s)
    return re.sub(r"\s+", " ", s).strip()


def citing_sentences(sid: str, limit: int = 3) -> list[tuple[str, str]]:
    """The exact sentence(s) in which the paper cites the source — the
    claim the human check is about. Extracted mechanically: the sentence
    containing each \\cite occurrence, lightly de-TeXed."""
    out = []
    for f in sorted((ROOT / "paper" / "sections").glob("*.tex")):
        text = " ".join(l for l in f.read_text().splitlines()
                        if not l.lstrip().startswith("%"))
        for m in re.finditer(r"\\cite\{([^}]*)\}", text):
            if sid not in (k.strip() for k in m.group(1).split(",")):
                continue
            start = max(text.rfind(". ", 0, m.start()) + 2, 0)
            end = text.find(". ", m.end())
            end = len(text) if end == -1 else end + 1
            sent = _detex(text[start:end])
            if len(sent) > 320:
                sent = sent[:317] + "..."
            out.append((f.stem, sent))
            if len(out) >= limit:
                return out
    return out


def main():
    g = Graph()
    g.parse(ROOT / "provenance.ttl", format="turtle")
    rows = []
    for s in g.subjects(RDF.type, AIPROV.Source):
        sid = str(s).rsplit("/", 1)[-1]
        title = str(g.value(s, DCT.title) or g.value(s, RDFS.label) or sid)
        rung = "unverified"
        for st in g.objects(s, AIPROV.verificationState):
            r = str(st).rsplit("/", 1)[-1]
            if RUNG_ORDER.index(r) > RUNG_ORDER.index(rung):
                rung = r
        self_cited = (s, AIPROV.selfCitation, None) in g
        files = [str(v) for v in g.objects(s, AIPROV.filePath)]
        hashes = [str(h) for h in g.objects(s, AIPROV.contentHash)]
        links = [str(d) for d in g.objects(s, AIPROV.doi)] + \
                [str(u) for u in g.objects(s, DCT.source)]
        # latest audit note: labels of activities that used this source
        notes = []
        for act in g.subjects(PROV.used, s):
            lbl = g.value(act, RDFS.label)
            if lbl and ("Promotion" in str(lbl) or "REFUSED" in str(lbl)):
                notes.append(str(lbl))
        note = max(notes, key=len) if notes else ""
        locs, cites = cite_locations(sid)
        rows.append((sid, title, rung, self_cited, files, hashes, links,
                     note, locs, cites))

    HUMAN = ("human-confirmed", "human-read")
    READY = ("ai-confirmed", "source-vendored")

    def bucket(row):
        rung, files = row[2], row[4]
        if rung in HUMAN:
            return "done"
        if rung in READY:
            # Vendored literature lives in doc/sources/ (except the generated
            # worksheet itself); everything else vendored is an in-repo
            # artefact with no literature check to perform.
            lit = [f for f in files if f.startswith("doc/sources/")
                   and not f.endswith("VERIFICATION.md")]
            if files and not lit:
                return "internal"
            return "ready-vendored" if files else "ready-link"
        return "pending"

    order = {"ready-vendored": 0, "ready-link": 1, "pending": 2,
             "internal": 3, "done": 4}
    # Within each bucket: most-cited first (relevance to the paper's
    # argument), spread across sections as tie-break, then id.
    rows.sort(key=lambda r: (order[bucket(r)], -r[9], -len(r[8]), r[0]))
    n = {k: sum(1 for r in rows if bucket(r) == k) for k in order}

    L = ["# Source verification worksheet",
         "",
         "Generated by `scripts/build_review_list.py` from `provenance.ttl` — "
         "do not edit by hand; regenerated automatically on every ladder "
         "change.",
         "",
         "**Where your intervention is required, at a glance:**",
         "",
         f"| Bucket | Sources | Your action |",
         f"|---|---|---|",
         f"| ⚠ Ready for your check, evidence vendored | {n['ready-vendored']} | Open the vendored copy, check the citing sentence, grant or refuse |",
         f"| ⚠ Ready for your check, via DOI/URL | {n['ready-link']} | Follow the access link, check, grant or refuse |",
         f"| ⏳ Not yet ready | {n['pending']} | None yet — ask the agent to content-check or vendor first |",
         f"| 🗂 Internal artefacts | {n['internal']} | None required — in-repo files, inspectable in git history |",
         f"| ✓ Human-verified | {n['done']} | Done (optionally deepen to `human-read`) |",
         "",
         "The human rungs are yours alone: `human-confirmed` means you "
         "spot-checked that the source supports the citing sentence; "
         "`human-read` means you read it in full **and** confirm (it subsumes "
         "rung 5). Refusing is first-class: a refusal is logged, changes no "
         "state, and beats silence.",
         "",
         "Within each bucket, sources are ordered by expected relevance to "
         "the paper's argument. Relevance is computed, not judged: the number "
         "of `\\cite` occurrences across the paper sources (shown per entry), "
         "with the spread across sections as tie-break — a source the "
         "argument leans on repeatedly comes before one cited once in "
         "passing. Check from the top.",
         ""]

    GROUPS = [
        ("ready-vendored", "# ⚠ Awaiting your check — evidence in hand"),
        ("ready-link", "# ⚠ Awaiting your check — obtain via link"),
        ("pending", "# ⏳ Not yet ready — AI-side work pending, no human action yet"),
        ("internal", "# 🗂 Internal artefacts — in-repo evidence, no literature check"),
        ("done", "# ✓ Human-verified — no action required"),
    ]
    ICON = {"ready-vendored": "⚠", "ready-link": "⚠", "pending": "⏳",
            "internal": "🗂", "done": "✓"}
    ACTION = {
        "ready-vendored": "**Your action:** open the vendored copy, check it "
                          "against the citing sentence(s), then grant or refuse:",
        "ready-link": "**Your action:** follow the access link, check the "
                      "citing sentence(s), then grant or refuse:",
        "pending": "**No human action yet.** The AI has not content-checked "
                   "this source; ask for a content check (and vendoring where "
                   "the license allows) before spending your time on it.",
        "internal": "**None required.** The vendored evidence is the in-repo "
                    "file itself (path + sha256 recorded); inspect via git "
                    "history. Optionally grant a human rung after review:",
        "done": "**Done.** Optionally deepen to `human-read` after a full read:",
    }
    for key, heading in GROUPS:
        group = [r for r in rows if bucket(r) == key]
        if not group:
            continue
        L.append(f"{heading} ({len(group)})")
        L.append("")
        for sid, title, rung, selfc, files, hashes, links, note, locs, cites in group:
            flag = " *(self-citation)*" if selfc else ""
            L.append(f"## {ICON[key]} `{sid}` — {rung}{flag}")
            L.append("")
            L.append(f"**{title}**")
            L.append("")
            L.append(f"- {ACTION[key]}")
            if locs:
                L.append(f"- Cited: {cites}× in {', '.join(locs)}")
                for where, sent in citing_sentences(sid):
                    L.append(f"- Claim to check ({where}): “{sent}”")
            else:
                L.append("- Cited: not currently cited in the paper")
            if files:
                for f_, h in zip(files, hashes or [""] * len(files)):
                    L.append(f"- Vendored copy: `{f_}` ({h or 'hash in graph'})")
            for link in links:
                L.append(f"- Access: {link}")
            if note:
                L.append(f"- Recorded check: {note}")
            L.append("")
            if key != "pending":
                target = "human-read" if key == "done" else "human-confirmed"
                L.append("```sh")
                L.append(f"python3 scripts/provlog.py promote --id {sid} "
                         f"--to {target} --agent florian-krebs --note \"...\"")
                L.append(f"python3 scripts/provlog.py promote --id {sid} "
                         f"--to {target} --agent florian-krebs --refuse --note \"...\"")
                L.append("```")
                L.append("")
    out = ROOT / "doc" / "sources" / "VERIFICATION.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{out}: {len(rows)} sources | awaiting human check: "
          f"{n['ready-vendored'] + n['ready-link']} "
          f"({n['ready-vendored']} with vendored evidence) | internal: "
          f"{n['internal']} | done: {n['done']} "
          f"| not yet ready: {n['pending']}")


if __name__ == "__main__":
    main()
