#!/usr/bin/env python3
"""provlog — append-only AI provenance logger over PROV-O (aiprov: profile).

Commands:
  init                       Seed provenance.ttl from the aiprov schema.
                             --orcid registers the owner as HumanAgent with
                             metadata resolved from the public ORCID registry;
                             --ci scaffolds the GitHub Actions build (graph
                             validation + LaTeX paper -> PDF artifact). The
                             base IRI derives from the git remote if omitted,
                             and later commands auto-detect it from the graph.
  agent   --id --type ...    Register a human/AI/tool agent with attributes.
  log     --activity ...     Record an activity with full inference telemetry
                             (tokens, cost, model, session, tools, prompt hash)
                             and optionally the entities it generated/used.
  claim   --id ...           Add a claim bound to a parent activity + agent.
  validate                   Conformance: parentless claims, AI-granted
                             human-only verification rungs, missing attribution.
  report                     Totals: tokens, cost, activities per agent, rungs.
  search                     Self-contained literature search over open APIs
                             (Crossref, OpenAlex, arXiv, DataCite) — no MCP
                             server, no key, no paid service required.
  source                     Register a literature source; --verify checks the
                             DOI against Crossref/OpenAlex (open APIs, no key)
                             and promotes unverified -> retrieved with metadata.
  promote                    Move a source or claim up the verification ladder.
                             Ladder order is enforced; human-only rungs
                             (human-confirmed, human-read) require --agent of a
                             registered HumanAgent. Every promotion is logged as
                             an AuditPass activity.
  disclosure                 Generate an AI-transparency statement (tex/md)
                             from the graph, aligned with the EU AI Act
                             (Regulation (EU) 2024/1689) marking/disclosure
                             rules for AI-generated content.
  extract                    Backward-closure subgraph of everything that
                             contributed to chosen seed entity types; can
                             also render a dashboard of the extract.

All writes are appends; the graph is the audit substrate. AI note: this tool
was drafted with AI assistance and verified by test-run; review before
production use.
"""
from __future__ import annotations
import argparse, datetime, hashlib, pathlib, sys
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, XSD

AIPROV = Namespace("https://w3id.org/aiprov/ns#")
FAIR2R = Namespace("https://noheton.org/f-ai-r/ns#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCT = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

DEFAULT_BASE = "https://example.org/prov/"
GRAPH = pathlib.Path("provenance.ttl")
SCHEMA = pathlib.Path(__file__).resolve().parent.parent / "assets" / "aiprov-schema.ttl"


def ns(base: str, kind: str) -> Namespace:
    return Namespace(f"{base}{kind}/")


def load() -> Graph:
    g = Graph()
    if GRAPH.exists():
        g.parse(GRAPH, format="turtle")
    for p, u in [("aiprov", AIPROV), ("prov", PROV), ("dcterms", DCT), ("foaf", FOAF),
             ("rdfs", RDFS)]:
        g.bind(p, u)
    return g


def save(g: Graph) -> None:
    g.serialize(GRAPH, format="turtle")


def now() -> Literal:
    return Literal(datetime.datetime.now().astimezone().isoformat(), datatype=XSD.dateTime)


CI_TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "ci" / "aiprov-build.yml"
RELEASE_TEMPLATE = CI_TEMPLATE.parent / "aiprov-release.yml"
PAPER_TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "paper"


def _scaffold_paper(subs: dict[str, str], force: bool) -> None:
    dst = pathlib.Path("paper")
    if dst.exists() and not force:
        print("paper/ exists; skipped (use --force to overwrite)")
        return
    n = 0
    for p in sorted(PAPER_TEMPLATE.rglob("*")):
        if p.is_dir():
            continue
        text = p.read_text(encoding="utf-8")
        for k, v in subs.items():
            text = text.replace(k, v)
        q = dst / p.relative_to(PAPER_TEMPLATE)
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(text, encoding="utf-8")
        n += 1
    print(f"paper/ scaffolded ({n} files: chapter-per-file LaTeX skeleton, "
          f"references.bib seeded with the EU AI Act entry, acknowledgement "
          f"wired to the generated disclosure)")


def cmd_init(a) -> None:
    if GRAPH.exists() and not a.force:
        sys.exit("provenance.ttl exists; use --force to reseed")
    base = a.base
    if base == DEFAULT_BASE:
        derived = _git_base()
        if derived:
            base = derived
            print(f"base derived from git remote: {base}")
        else:
            print(f"no --base given and none derivable from a git remote; "
                  f"using {base} — replace with your own IRI base")
    text = SCHEMA.read_text(encoding="utf-8").replace("https://example.org/prov/", base)
    GRAPH.write_text(text, encoding="utf-8")
    g = load()  # parse check
    print(f"Seeded {GRAPH} ({len(g)} triples, base {base})")
    meta = {}
    if a.orcid:
        meta = _fetch_orcid(a.orcid) or {}
        if not meta:
            print(f"ORCID {a.orcid} not resolvable (offline or bad iD); "
                  f"registering the bare iD — no metadata fabricated")
        name = meta.get("name")
        ident = a.human_id or (_slug(name) if name else "owner")
        _register_human(g, base, ident, a.orcid, name, meta.get("affiliation"))
        save(g)
        got = ", ".join(v for v in (name, meta.get("affiliation")) if v)
        print(f"agent:{ident} registered (human"
              + (f": {got} [resolved via pub.orcid.org]" if got else "") + ")")
    if a.paper:
        _scaffold_paper({
            "{{TITLE}}": "TODO: Working Title",
            "{{AUTHOR}}": meta.get("name") or "TODO Author",
            "{{AFFILIATION}}": meta.get("affiliation") or "TODO Affiliation",
            "{{ORCID}}": (a.orcid.strip().removeprefix("https://orcid.org/")
                          if a.orcid else "0000-0000-0000-0000"),
        }, a.force)
    if a.ci:
        for tmpl, name, what in (
            (CI_TEMPLATE, "aiprov-build.yml",
             "validates the graph, builds paper/ LaTeX to PDF, uploads artifacts"),
            (RELEASE_TEMPLATE, "aiprov-release.yml",
             "on v* tags: conformance-gated GitHub Release with PDF, graph, "
             "dashboard, skill bundle, and checksums"),
        ):
            dst = pathlib.Path(".github/workflows") / name
            if dst.exists() and not a.force:
                print(f"{dst} exists; skipped (use --force to overwrite)")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(tmpl.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"CI workflow scaffolded -> {dst} ({what})")
    print("next steps:")
    print("  provlog.py agent --id <model-id> --type ai --model <model-id> --provider <provider>")
    print("  provlog.py log --activity s01-<slug> --agent <id> --label \"...\" --generated <path>")
    print("  provlog.py validate   # before every commit (--base is now auto-detected)")


def cmd_agent(a) -> None:
    if getattr(a, "resolve", False):
        if a.type != "human" or not a.orcid:
            sys.exit("--resolve requires --type human and --orcid")
        meta = _fetch_orcid(a.orcid)
        if meta is None:
            print("ORCID not resolvable; registering provided values only")
        else:
            a.name = a.name or meta.get("name")
            a.affiliation = a.affiliation or meta.get("affiliation")
            got = ", ".join(v for v in (a.name, a.affiliation) if v)
            print(f"resolved via pub.orcid.org: {got or '(no public name/affiliation)'}")
    g = load()
    s = ns(a.base, "agent")[a.id]
    cls = {"ai": AIPROV.AIAgent, "human": AIPROV.HumanAgent, "tool": AIPROV.ToolAgent}[a.type]
    g.add((s, RDF.type, cls))
    if a.name:
        g.add((s, FOAF.name, Literal(a.name)))
    for key, prop, dt in [
        ("model", AIPROV.model, XSD.string), ("model_version", AIPROV.modelVersion, XSD.string),
        ("provider", AIPROV.provider, XSD.string), ("endpoint", AIPROV.endpoint, XSD.anyURI),
        ("context_window", AIPROV.contextWindow, XSD.integer),
        ("knowledge_cutoff", AIPROV.knowledgeCutoff, XSD.date),
        ("orcid", AIPROV.orcid, XSD.anyURI), ("affiliation", AIPROV.affiliation, XSD.string),
    ]:
        v = getattr(a, key, None)
        if v is not None:
            g.add((s, prop, Literal(v, datatype=dt)))
    save(g)
    print(f"agent:{a.id} registered ({a.type})")


ACT_ATTRS = [  # (cli key, property, xsd type)
    ("session_id", AIPROV.sessionId, XSD.string), ("request_id", AIPROV.requestId, XSD.string),
    ("turns", AIPROV.turnCount, XSD.integer),
    ("input_tokens", AIPROV.inputTokens, XSD.integer), ("output_tokens", AIPROV.outputTokens, XSD.integer),
    ("cache_read_tokens", AIPROV.cacheReadTokens, XSD.integer),
    ("cache_write_tokens", AIPROV.cacheWriteTokens, XSD.integer),
    ("reasoning_tokens", AIPROV.reasoningTokens, XSD.integer),
    ("temperature", AIPROV.temperature, XSD.decimal), ("top_p", AIPROV.topP, XSD.decimal),
    ("max_tokens", AIPROV.maxTokens, XSD.integer), ("seed", AIPROV.seed, XSD.integer),
    ("stop_reason", AIPROV.stopReason, XSD.string),
    ("cost", AIPROV.cost, XSD.decimal), ("currency", AIPROV.costCurrency, XSD.string),
    ("energy_wh", AIPROV.energyWh, XSD.decimal), ("tool_calls", AIPROV.toolCalls, XSD.integer),
]


def cmd_log(a) -> None:
    g = load()
    act = ns(a.base, "activity")[a.activity]
    cls = {"authoring": AIPROV.AuthoringPass, "audit": AIPROV.AuditPass,
           "build": AIPROV.Build, "repair": AIPROV.Repair}.get(a.pass_, PROV.Activity)
    g.add((act, RDF.type, cls))
    if a.label:
        g.add((act, RDFS.label, Literal(a.label, lang="en")))
    g.add((act, PROV.endedAtTime, now()))
    if a.started:
        g.add((act, PROV.startedAtTime, Literal(a.started, datatype=XSD.dateTime)))
    if a.agent:
        g.add((act, PROV.wasAssociatedWith, ns(a.base, "agent")[a.agent]))
    for key, prop, dt in ACT_ATTRS:
        v = getattr(a, key, None)
        if v is not None:
            g.add((act, prop, Literal(v, datatype=dt)))
    it = int(a.input_tokens or 0) + int(a.output_tokens or 0)
    if a.total_tokens is not None:
        g.add((act, AIPROV.totalTokens, Literal(a.total_tokens, datatype=XSD.integer)))
    elif it:
        g.add((act, AIPROV.totalTokens, Literal(it, datatype=XSD.integer)))
    for t in a.tool or []:
        g.add((act, AIPROV.usedTool, Literal(t)))
    if a.prompt_file:
        p = pathlib.Path(a.prompt_file)
        pe = ns(a.base, "entity")["prompt-" + p.stem]
        g.add((pe, RDF.type, AIPROV.Prompt))
        g.add((pe, DCT.source, URIRef(p.as_posix())))
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            g.add((pe, AIPROV.promptHash, Literal("sha256:" + h)))
        g.add((act, PROV.used, pe))
    if a.transcript:
        te = ns(a.base, "entity")["transcript-" + pathlib.Path(a.transcript).stem]
        g.add((te, RDF.type, AIPROV.Transcript))
        g.add((te, DCT.source, URIRef(a.transcript)))
        g.add((act, AIPROV.transcript, te))
    for path in a.generated or []:
        e = ns(a.base, "entity")[pathlib.Path(path).name.replace(".", "-")]
        g.add((e, RDF.type, AIPROV.Artefact))
        g.add((e, AIPROV.filePath, Literal(path)))
        fp = pathlib.Path(path)
        if fp.exists():
            g.add((e, AIPROV.contentHash,
                   Literal("sha256:" + hashlib.sha256(fp.read_bytes()).hexdigest())))
        g.add((e, PROV.wasGeneratedBy, act))
        if a.agent:
            g.add((e, PROV.wasAttributedTo, ns(a.base, "agent")[a.agent]))
        if a.commit:
            g.add((e, AIPROV.gitCommit, Literal(a.commit)))
    for path in a.used or []:
        e = ns(a.base, "source")[pathlib.Path(path).name.replace(".", "-")]
        g.add((e, RDF.type, AIPROV.Source))
        g.add((e, AIPROV.filePath, Literal(path)))
        g.add((act, PROV.used, e))
    save(g)
    print(f"act:{a.activity} logged ({len(g)} triples total)")


def cmd_claim(a) -> None:
    g = load()
    c = ns(a.base, "claim")[a.id]
    g.add((c, RDF.type, AIPROV.Claim))
    g.add((c, RDFS.label, Literal(a.text, lang="en")))
    g.add((c, PROV.wasGeneratedBy, ns(a.base, "activity")[a.parent]))
    g.add((c, PROV.wasAttributedTo, ns(a.base, "agent")[a.agent]))
    g.add((c, AIPROV.verificationState, ns(a.base, "verification")[a.state]))
    save(g)
    print(f"claim:{a.id} added (state {a.state})")


def cmd_validate(a) -> None:
    g = load()
    fail = 0
    q1 = """SELECT ?c WHERE { ?c a aiprov:Claim .
            FILTER NOT EXISTS { ?c prov:wasGeneratedBy ?x } }"""
    orphans = list(g.query(q1))
    print(f"[{'FAIL' if orphans else ' OK '}] parentless claims: {len(orphans)}")
    fail += len(orphans)
    q2 = """SELECT ?c WHERE { ?c a aiprov:Claim .
            FILTER NOT EXISTS { ?c prov:wasAttributedTo ?x } }"""
    unattr = list(g.query(q2))
    print(f"[{'FAIL' if unattr else ' OK '}] unattributed claims: {len(unattr)}")
    fail += len(unattr)
    # Human-only rungs: the offence is WHO GRANTED the rung, not who authored
    # the claim. Promotions are AuditPass activities labelled "... -> <rung>";
    # an AI agent associated with such a promotion is a hard failure.
    q3 = """SELECT ?act ?ag WHERE {
              ?act a aiprov:AuditPass ; rdfs:label ?l ;
                   prov:wasAssociatedWith ?ag .
              ?ag a aiprov:AIAgent .
              FILTER(REGEX(STR(?l), "-> (human-confirmed|human-read|lit-read)")) }"""
    bad = list(g.query(q3))
    print(f"[{'FAIL' if bad else ' OK '}] human-only rungs granted by AI agents: {len(bad)}")
    fail += len(bad)
    # Softer check: node sits at a human-only rung but the graph records no
    # human-associated promotion activity for it. Legitimate for legacy or
    # hand-curated graphs, so WARN, not FAIL.
    q3w = """SELECT ?n WHERE {
              ?n aiprov:verificationState ?s .
              FILTER(REGEX(STR(?s), "(human-confirmed|human-read|lit-read)$"))
              FILTER NOT EXISTS {
                ?act prov:used ?n ; prov:wasAssociatedWith ?h .
                ?h a aiprov:HumanAgent . } }"""
    unwit = list(g.query(q3w))
    print(f"[{'WARN' if unwit else ' OK '}] human-only rungs without a recorded "
          f"human promotion activity: {len(unwit)}")
    q3b = """SELECT ?s ?st WHERE { ?s a aiprov:Source ;
              aiprov:verificationState ?st .
            FILTER(REGEX(STR(?st), "(retrieved|reference-resolved|ai-confirmed|source-vendored|human-confirmed|human-read|lit-read)$"))
            FILTER NOT EXISTS { ?s aiprov:doi ?d }
            FILTER NOT EXISTS { ?s <http://purl.org/dc/terms/source> ?u }
            FILTER NOT EXISTS { ?s aiprov:filePath ?f } }"""
    noref = list(g.query(q3b))
    print(f"[{'FAIL' if noref else ' OK '}] sources above needs-research without DOI/URL/vendored copy: {len(noref)}")
    fail += len(noref)
    # Vendoring is an access gate, not evidence: a human-verified source
    # should ideally have been checked against vendored bytes; link-only is
    # legitimate but the audit target is then mutable, so WARN.
    q3v = """SELECT ?s WHERE { ?s a aiprov:Source ;
              aiprov:verificationState ?st .
            FILTER(REGEX(STR(?st), "(human-confirmed|human-read|lit-read)$"))
            FILTER NOT EXISTS { ?s aiprov:filePath ?f } }"""
    unvend = list(g.query(q3v))
    print(f"[{'WARN' if unvend else ' OK '}] human-verified sources not vendored "
          f"(link-only audit target): {len(unvend)}")
    q4 = """SELECT ?act WHERE { ?e prov:wasGeneratedBy ?act .
            FILTER NOT EXISTS { ?act prov:wasAssociatedWith ?ag } }"""
    anon = set(r[0] for r in g.query(q4))
    print(f"[{'WARN' if anon else ' OK '}] activities without agent: {len(anon)}")
    for row in list(orphans) + list(unattr):
        print("   ↳", row[0])
    sys.exit(1 if fail else 0)


def cmd_report(a) -> None:
    g = load()
    def total(prop):
        return sum(int(o) for _, _, o in g.triples((None, prop, None)))
    print("== aiprov report ==")
    print(f"triples:            {len(g)}")
    print(f"activities:         {len(set(g.subjects(PROV.endedAtTime, None)))}")
    print(f"claims:             {len(set(g.subjects(RDF.type, AIPROV.Claim)))}")
    n_src = len(set(g.subjects(RDF.type, AIPROV.Source)))
    n_self = len(set(g.subjects(AIPROV.selfCitation, Literal(True, datatype=XSD.boolean))))
    print(f"sources:            {n_src} ({n_self} marked self-citation)")
    print(f"input tokens:       {total(AIPROV.inputTokens)}")
    print(f"output tokens:      {total(AIPROV.outputTokens)}")
    print(f"cache read tokens:  {total(AIPROV.cacheReadTokens)}")
    print(f"total tokens:       {total(AIPROV.totalTokens)}")
    cost = sum(float(o) for _, _, o in g.triples((None, AIPROV.cost, None)))
    cur = {str(o) for _, _, o in g.triples((None, AIPROV.costCurrency, None))} or {"?"}
    print(f"cost:               {cost:.4f} {'/'.join(sorted(cur))}")
    print("-- tokens per agent --")
    q = """SELECT ?ag (SUM(?t) AS ?tok) (COUNT(DISTINCT ?act) AS ?n) WHERE {
            ?act prov:wasAssociatedWith ?ag ; aiprov:totalTokens ?t }
           GROUP BY ?ag ORDER BY DESC(?tok)"""
    for ag, tok, n in g.query(q):
        print(f"   {str(ag).rsplit('/',1)[-1]:24s} {int(tok):>10} tok  {int(n)} activities")
    print("-- verification rungs --")
    q = """SELECT ?s (COUNT(?c) AS ?n) WHERE {
            ?c a aiprov:Claim ; aiprov:verificationState ?s } GROUP BY ?s"""
    agg = {}
    for st, n in g.query(q):
        r = canon_rung(str(st).rsplit("/", 1)[-1])
        agg[r] = agg.get(r, 0) + int(n)
    order = lambda r: LADDER.index(r) if r in LADDER else 99
    for r in sorted(agg, key=order):
        print(f"   {r:24s} {agg[r]}")


LADDER = ["unverified", "needs-research", "reference-resolved", "ai-confirmed",
          "source-vendored", "human-confirmed", "human-read"]
HUMAN_ONLY = {"human-confirmed", "human-read"}
# Legacy rung names normalize to canonical ones (fair2r lit-*; early aiprov)
RUNG_ALIASES = {"retrieved": "reference-resolved",
                "lit-retrieved": "reference-resolved",
                "ai-checked": "ai-confirmed",
                "lit-read": "human-read"}


def canon_rung(name: str) -> str:
    return RUNG_ALIASES.get(name, name)


def _fetch_doi(doi: str) -> dict | None:
    """Resolve a DOI via Crossref, falling back to OpenAlex. Open APIs, no key."""
    import json as _json
    import urllib.request
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:")
    for url, pick in [
        (f"https://api.crossref.org/works/{doi}",
         lambda d: {"title": " ".join(d["message"].get("title") or []) or None,
                    "year": (d["message"].get("issued", {}).get("date-parts") or [[None]])[0][0],
                    "container": " ".join(d["message"].get("container-title") or []) or None,
                    "source_api": "crossref"}),
        (f"https://api.openalex.org/works/doi:{doi}",
         lambda d: {"title": d.get("display_name"),
                    "year": d.get("publication_year"),
                    "container": (d.get("primary_location") or {}).get("source", {}).get("display_name"),
                    "source_api": "openalex"}),
    ]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "aiprov-provlog/0.1 (mailto:ops@example.org)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                meta = pick(_json.loads(r.read()))
                meta["doi"] = doi
                return meta
        except Exception:
            continue
    return None


def _set_state(g: Graph, base: str, node, state: str) -> None:
    state = canon_rung(state)
    for old in list(g.objects(node, AIPROV.verificationState)):
        g.remove((node, AIPROV.verificationState, old))
    g.add((node, AIPROV.verificationState, ns(base, "verification")[state]))


def _http_json(url: str, accept: str | None = None):
    import json as _json
    import urllib.request
    headers = {"User-Agent": "aiprov-provlog/0.1 (mailto:ops@example.org)"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return _json.loads(r.read())


def _fetch_orcid(orcid: str) -> dict | None:
    """Resolve an ORCID iD via the public ORCID API (no key): name and
    current affiliation. Returns None when the record cannot be fetched;
    fields the registry does not carry stay None — nothing is fabricated."""
    oid = orcid.strip().removeprefix("https://orcid.org/").removeprefix("orcid:")
    try:
        d = _http_json(f"https://pub.orcid.org/v3.0/{oid}/record",
                       accept="application/json")
    except Exception:
        return None
    name = (d.get("person") or {}).get("name") or {}
    given = (name.get("given-names") or {}).get("value")
    family = (name.get("family-name") or {}).get("value")
    affiliation = None
    emp = (d.get("activities-summary") or {}).get("employments") or {}
    for grp in emp.get("affiliation-group", []):
        for s in grp.get("summaries", []):
            e = s.get("employment-summary") or {}
            if e.get("end-date") is None:
                affiliation = (e.get("organization") or {}).get("name")
                break
        if affiliation:
            break
    return {"orcid": oid,
            "name": " ".join(x for x in (given, family) if x) or None,
            "affiliation": affiliation}


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _git_base() -> str | None:
    """Derive an instance-IRI base from the git remote, e.g.
    https://github.com/owner/repo/prov/. None if no usable remote."""
    import re
    import subprocess
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    m = re.search(r"([\w-]+(?:\.[\w-]+)*\.[a-z]{2,})[:/]{1,2}([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url)
    if not m:
        return None
    host, owner, repo = m.groups()
    return f"https://{host}/{owner}/{repo}/prov/"


def _detect_base() -> str | None:
    """Read the instance base back out of an existing graph so follow-up
    commands do not need --base repeated."""
    import re
    if not GRAPH.exists():
        return None
    txt = GRAPH.read_text(encoding="utf-8")
    for tag in ("agent/", "activity/", "verification/"):
        m = re.search(r"<(https?://[^>\s]+/)" + tag + ">", txt)
        if m:
            return m.group(1)
    return None


def _register_human(g: Graph, base: str, ident: str, orcid: str | None,
                    name: str | None, affiliation: str | None) -> None:
    s = ns(base, "agent")[ident]
    g.add((s, RDF.type, AIPROV.HumanAgent))
    if name:
        g.add((s, FOAF.name, Literal(name)))
    if orcid:
        oid = orcid.strip().removeprefix("https://orcid.org/").removeprefix("orcid:")
        g.add((s, AIPROV.orcid,
               Literal("https://orcid.org/" + oid, datatype=XSD.anyURI)))
    if affiliation:
        g.add((s, AIPROV.affiliation, Literal(affiliation, datatype=XSD.string)))


def cmd_search(a) -> None:
    import urllib.parse
    q = urllib.parse.quote(a.query)
    rows = a.rows
    results, errors = [], []
    backends = a.backend or ["crossref", "openalex"]
    if "crossref" in backends:
        try:
            d = _http_json(f"https://api.crossref.org/works?query={q}&rows={rows}"
                           f"&select=DOI,title,issued,container-title,author,is-referenced-by-count")
            for it in d["message"]["items"]:
                results.append({
                    "doi": it.get("DOI"),
                    "title": " ".join(it.get("title") or ["?"]),
                    "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
                    "venue": " ".join(it.get("container-title") or []) or "—",
                    "cites": it.get("is-referenced-by-count"),
                    "api": "crossref"})
        except Exception as e:
            errors.append(f"crossref: {e}")
    if "openalex" in backends:
        try:
            d = _http_json(f"https://api.openalex.org/works?search={q}&per-page={rows}")
            for it in d.get("results", []):
                doi = (it.get("doi") or "").removeprefix("https://doi.org/") or None
                results.append({
                    "doi": doi, "title": it.get("display_name") or "?",
                    "year": it.get("publication_year"),
                    "venue": ((it.get("primary_location") or {}).get("source") or {}).get("display_name") or "—",
                    "cites": it.get("cited_by_count"), "api": "openalex"})
        except Exception as e:
            errors.append(f"openalex: {e}")
    if "arxiv" in backends:
        try:
            import re
            import urllib.request
            req = urllib.request.Request(
                f"http://export.arxiv.org/api/query?search_query=all:{q}&max_results={rows}",
                headers={"User-Agent": "aiprov-provlog/0.1"})
            xml = urllib.request.urlopen(req, timeout=15).read().decode()
            for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
                e = m.group(1)
                t = re.search(r"<title>(.*?)</title>", e, re.S)
                i = re.search(r"<id>http://arxiv.org/abs/(.*?)</id>", e)
                y = re.search(r"<published>(\d{4})", e)
                doim = re.search(r"<arxiv:doi[^>]*>(.*?)</arxiv:doi>", e)
                results.append({
                    "doi": doim.group(1) if doim else None,
                    "title": " ".join((t.group(1) if t else "?").split()),
                    "year": int(y.group(1)) if y else None,
                    "venue": "arXiv:" + (i.group(1) if i else "?"),
                    "cites": None, "api": "arxiv"})
        except Exception as e:
            errors.append(f"arxiv: {e}")
    if "datacite" in backends:
        try:
            d = _http_json(f"https://api.datacite.org/dois?query={q}&page[size]={rows}")
            for it in d.get("data", []):
                at = it.get("attributes", {})
                results.append({
                    "doi": at.get("doi"),
                    "title": (at.get("titles") or [{}])[0].get("title", "?"),
                    "year": at.get("publicationYear"),
                    "venue": at.get("publisher") or "—",
                    "cites": at.get("citationCount"), "api": "datacite"})
        except Exception as e:
            errors.append(f"datacite: {e}")
    seen, out = set(), []
    for r in results:
        key = r["doi"] or r["title"].lower()
        if key not in seen:
            seen.add(key); out.append(r)
    if not out:
        print("no results" + (f" ({'; '.join(errors)})" if errors else ""))
        return
    print(f"== {len(out)} candidates for: {a.query} ==")
    for r in out:
        c = f" · {r['cites']} cites" if r.get("cites") else ""
        print(f"  [{r['api']:8s}] {r['title'][:78]}")
        print(f"             {r['year'] or '?'} · {r['venue'][:60]}{c}")
        print(f"             doi: {r['doi'] or '— (no DOI; verify manually before use)'}")
    for e in errors:
        print("  (backend unavailable:", e + ")")
    print("Next: provlog.py source --id <slug> --doi <doi> --verify --agent <id>")


def cmd_source(a) -> None:
    g = load()
    s = ns(a.base, "source")[a.id]
    g.add((s, RDF.type, AIPROV.Source))
    state = canon_rung(a.state) if a.state else "unverified"
    meta = None
    if a.verify:
        if not a.doi:
            sys.exit("--verify requires --doi")
        meta = _fetch_doi(a.doi)
        if meta is None:
            state = "needs-research"
            print(f"DOI {a.doi} NOT resolvable via Crossref/OpenAlex -> "
                  f"state needs-research (do not cite until resolved)")
        else:
            state = ("reference-resolved"
                     if LADDER.index(state) < LADDER.index("reference-resolved")
                     else state)
            print(f"DOI verified via {meta['source_api']}: "
                  f"{(meta['title'] or '?')[:70]} ({meta.get('year')})")
    title = a.title or (meta or {}).get("title")
    if title:
        g.add((s, RDFS.label, Literal(title, lang="en")))
    if a.doi:
        g.add((s, AIPROV.doi, Literal("https://doi.org/" +
              a.doi.removeprefix("https://doi.org/").removeprefix("doi:"),
              datatype=XSD.anyURI)))
    if a.url:
        g.add((s, DCT.source, URIRef(a.url)))
    if a.self_citation:
        g.add((s, AIPROV.selfCitation, Literal(True, datatype=XSD.boolean)))
    if meta:
        if meta.get("year"):
            g.add((s, DCT.date, Literal(str(meta["year"]))))
        if meta.get("container"):
            g.add((s, DCT.isPartOf, Literal(meta["container"])))
    _set_state(g, a.base, s, state)
    if a.verify:
        act = ns(a.base, "activity")[f"verify-src-{a.id}"]
        g.add((act, RDF.type, AIPROV.AuditPass))
        g.add((act, RDFS.label, Literal(
            f"DOI verification of src:{a.id} via "
            f"{(meta or {}).get('source_api', 'crossref/openalex')} -> {state}", lang="en")))
        g.add((act, PROV.endedAtTime, now()))
        g.add((act, PROV.used, s))
        if a.agent:
            g.add((act, PROV.wasAssociatedWith, ns(a.base, "agent")[a.agent]))
    save(g)
    print(f"src:{a.id} registered at rung '{state}'")
    _regen_worksheet()


def _regen_worksheet() -> None:
    """Keep doc/sources/VERIFICATION.md current: best-effort regeneration
    whenever a command changes the ladder. Never fails the command."""
    import subprocess
    script = pathlib.Path(__file__).resolve().parent / "build_review_list.py"
    if script.exists():
        r = subprocess.run([sys.executable, str(script)],
                           capture_output=True, text=True)
        try:
            if r.returncode == 0:
                print(r.stdout.strip())
            else:
                print("worksheet regeneration skipped:", r.stderr.strip()[:200])
        except BrokenPipeError:
            pass  # caller closed stdout (e.g. piped through head) — harmless


def cmd_promote(a) -> None:
    g = load()
    node = None
    for kind in ("source", "claim"):
        cand = ns(a.base, kind)[a.id]
        if (cand, None, None) in g:
            node = cand
            break
    if node is None:
        sys.exit(f"no source or claim with id '{a.id}' in graph")
    cur = "unverified"
    for st in g.objects(node, AIPROV.verificationState):
        cur = canon_rung(str(st).rsplit("/", 1)[-1])
    a.to = canon_rung(a.to)
    if a.to not in LADDER:
        sys.exit(f"unknown rung '{a.to}'; ladder: {' -> '.join(LADDER)}")
    if a.refuse:
        # Disagreement is first-class: a refused promotion changes no
        # state, but the refusal itself is a logged audit activity
        # carrying the refused rung, so "checked and NOT convinced" is
        # distinguishable from "never checked".
        if not a.note:
            sys.exit("--refuse requires --note: record WHY the rung was refused")
        agent = ns(a.base, "agent")[a.agent]
        act = ns(a.base, "activity")[f"refuse-{a.id}-{a.to}"]
        g.add((act, RDF.type, AIPROV.AuditPass))
        g.add((act, RDFS.label, Literal(
            f"REFUSED promotion of {a.id} to {a.to} (current rung stays "
            f"{cur}): {a.note}", lang="en")))
        g.add((act, AIPROV.refusedRung,
               ns(a.base, "verification")[a.to]))
        g.add((act, PROV.endedAtTime, now()))
        g.add((act, PROV.used, node))
        g.add((act, PROV.wasAssociatedWith, agent))
        save(g)
        print(f"{a.id}: promotion to {a.to} REFUSED by agent:{a.agent} "
              f"(rung stays {cur}; refusal logged as AuditPass)")
        _regen_worksheet()
        return
    if LADDER.index(a.to) <= LADDER.index(cur):
        sys.exit(f"'{a.to}' is not above current rung '{cur}' — "
                 f"demotions/no-ops are graph repairs, not promotions")
    agent = ns(a.base, "agent")[a.agent]
    is_human = (agent, RDF.type, AIPROV.HumanAgent) in g
    if a.to in HUMAN_ONLY and not is_human:
        sys.exit(f"REFUSED: rung '{a.to}' is human-only; agent:{a.agent} is not "
                 f"a registered HumanAgent. An AI must never grant this rung.")
    is_source = (node, RDF.type, AIPROV.Source) in g
    if a.to == "source-vendored" and is_source:
        # Vendoring is an act of provision, not an assertion: record what
        # was provided, where, and its hash.
        if not a.file:
            sys.exit("promotion to source-vendored requires --file "
                     "<repo path of the vendored copy>")
        fp = pathlib.Path(a.file)
        if not fp.exists():
            sys.exit(f"vendored file {a.file} does not exist")
        g.add((node, AIPROV.filePath, Literal(a.file)))
        g.add((node, AIPROV.contentHash,
               Literal("sha256:" + hashlib.sha256(fp.read_bytes()).hexdigest())))
    if a.to in HUMAN_ONLY and is_source:
        # Human verification needs the evidence in hand: a vendored copy or
        # a clear access link. Vendoring has no evidential value of its own
        # — it exists to make this step possible.
        vendored = [str(v) for v in g.objects(node, AIPROV.filePath)]
        links = [str(d) for d in g.objects(node, AIPROV.doi)] + \
                [str(u) for u in g.objects(node, DCT.source)]
        if not (vendored or links):
            sys.exit(f"REFUSED: '{a.to}' requires the source in hand — vendor "
                     f"a copy first (promote --id {a.id} --to source-vendored "
                     f"--file <path>) or record a DOI/URL for it")
        print("review material: " +
              "; ".join([f"vendored copy at {v}" for v in vendored] +
                        [f"obtain via {x}" for x in links]))
    _set_state(g, a.base, node, a.to)
    act = ns(a.base, "activity")[f"promote-{a.id}-{a.to}"]
    g.add((act, RDF.type, AIPROV.AuditPass))
    g.add((act, RDFS.label, Literal(
        f"Promotion of {a.id}: {cur} -> {a.to}" +
        (f" ({a.note})" if a.note else ""), lang="en")))
    g.add((act, PROV.endedAtTime, now()))
    g.add((act, PROV.used, node))
    g.add((act, PROV.wasAssociatedWith, agent))
    save(g)
    print(f"{a.id}: {cur} -> {a.to} (logged as AuditPass, agent:{a.agent})")
    _regen_worksheet()


def cmd_disclosure(a) -> None:
    """Generate an AI-transparency statement from the graph itself, aligned
    with the disclosure/marking obligations for AI-generated content in
    Regulation (EU) 2024/1689 (AI Act). Everything stated is derived from
    recorded triples — nothing is asserted that the graph does not carry."""
    g = load()
    ais = []
    for s in sorted(set(g.subjects(RDF.type, AIPROV.AIAgent))):
        name = str(g.value(s, FOAF.name) or str(s).rsplit("/", 1)[-1])
        model = g.value(s, AIPROV.model)
        provider = g.value(s, AIPROV.provider)
        n = len(set(g.subjects(PROV.wasAssociatedWith, s)))
        desc = name
        bits = [str(x) for x in (model, provider) if x]
        if bits:
            desc += " (" + ", ".join(bits) + ")"
        ais.append((desc, n))
    if not ais:
        sys.exit("no AIAgent in the graph — nothing to disclose")
    n_art = len(set(g.subjects(RDF.type, AIPROV.Artefact)))
    n_claims = len(set(g.subjects(RDF.type, AIPROV.Claim)))
    n_acts = len(set(g.subjects(PROV.endedAtTime, None)))
    agents = "; ".join(f"{d}, associated with {n} recorded activities"
                       for d, n in ais)
    text = (
        f"Parts of this work were generated or edited with the assistance of "
        f"artificial-intelligence systems: {agents}. In line with the "
        f"transparency obligations for AI-generated content under Regulation "
        f"(EU) 2024/1689 (AI Act), this assistance is disclosed here and is "
        f"additionally marked in machine-readable form: the version-controlled "
        f"provenance graph (provenance.ttl, W3C PROV-O) records the "
        f"{n_acts} activities behind this work, the {n_art} generated "
        f"artefacts with content hashes, and the {n_claims} recorded claims "
        f"with their verification states. Human oversight is structural: "
        f"verification rungs above ai-confirmed are reserved to human agents, "
        f"and the conformance validator rejects AI-granted promotions.")
    if a.format == "tex":
        out = "% Generated by provlog.py disclosure — do not edit by hand.\n" + text + "\n"
    else:
        out = ("<!-- Generated by provlog.py disclosure — do not edit by hand. -->\n"
               + text + "\n")
    if a.out:
        pathlib.Path(a.out).write_text(out, encoding="utf-8")
        print(f"disclosure -> {a.out}")
    else:
        print(out, end="")


def cmd_extract(a) -> None:
    import collections
    from rdflib import URIRef
    src = pathlib.Path(a.graph) if a.graph else GRAPH
    g = Graph(); g.parse(src, format="turtle")
    both = (AIPROV, FAIR2R)
    seeds = set()
    for t in a.seed_types:
        for n in both:
            seeds |= set(g.subjects(RDF.type, n[t]))
    if not seeds:
        sys.exit(f"no seed entities of types {a.seed_types} found in {src}")
    excl = set()
    for t in a.exclude_kinds or []:
        for n in both:
            excl |= set(g.subjects(RDF.type, n[t]))
    follow = [PROV.wasGeneratedBy, PROV.wasDerivedFrom, PROV.wasAttributedTo,
              PROV.specializationOf, PROV.wasAssociatedWith, PROV.used,
              PROV.wasInformedBy, PROV.hadPlan]
    for n in both:
        follow += [n.transcript, n.repairs]
    keep, q = set(seeds), collections.deque(seeds)
    while q:
        node = q.popleft()
        nbrs = {o for pr in follow for o in g.objects(node, pr)
                if isinstance(o, URIRef)}
        for n in both:
            nbrs |= set(g.subjects(n.repairs, node))
        for m in nbrs - excl:
            if m not in keep:
                keep.add(m); q.append(m)
    out = Graph()
    for pfx, u in g.namespaces():
        out.bind(pfx, u)
    for s_, p_, o_ in g:
        if s_ in keep and (isinstance(o_, Literal) or o_ in keep or p_ == RDF.type
                           or "verification" in str(o_).lower()
                           or str(p_).endswith("source")):
            out.add((s_, p_, o_))
    out.serialize(a.out, format="turtle")
    print(f"extract: {len(seeds)} seeds -> {len(keep)} nodes, "
          f"{len(out)}/{len(g)} triples -> {a.out}")
    if a.dashboard:
        import json
        import build_dashboard as bd
        data = bd.extract(pathlib.Path(a.out))
        html = bd.HTML.replace("__DATA__",
                               json.dumps(data).replace("</", "<\\/"))
        pathlib.Path(a.dashboard).write_text(html, encoding="utf-8")
        print(f"dashboard -> {a.dashboard} "
              f"({len(data['nodes'])} nodes, {len(data['edges'])} edges)")


def main() -> None:
    p = argparse.ArgumentParser(prog="provlog", description=__doc__)
    p.add_argument("--base", default=DEFAULT_BASE, help="instance-IRI base")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--force", action="store_true")
    s.add_argument("--orcid", help="owner's ORCID iD; registers them as HumanAgent "
                   "with name/affiliation resolved from the public registry")
    s.add_argument("--human-id", dest="human_id", help="agent id for the owner (default: name slug)")
    s.add_argument("--ci", action="store_true",
                   help="scaffold .github/workflows/aiprov-build.yml (validate "
                   "graph, build LaTeX paper to PDF on every push) and "
                   "aiprov-release.yml (conformance-gated GitHub Release with "
                   "PDF, graph, dashboard, skill bundle + checksums on v* tags)")
    s.add_argument("--paper", action="store_true",
                   help="scaffold paper/ (chapter-per-file LaTeX skeleton with "
                        "AI-transparency acknowledgement wired to provlog disclosure)")

    s = sub.add_parser("agent")
    s.add_argument("--id", required=True); s.add_argument("--type", choices=["ai", "human", "tool"], required=True)
    for f in ["name", "model", "model_version", "provider", "endpoint", "context_window",
              "knowledge_cutoff", "orcid", "affiliation"]:
        s.add_argument("--" + f.replace("_", "-"), dest=f)
    s.add_argument("--resolve", action="store_true",
                   help="fill missing name/affiliation from the public ORCID registry")

    s = sub.add_parser("log")
    s.add_argument("--activity", required=True); s.add_argument("--label")
    s.add_argument("--pass", dest="pass_", choices=["authoring", "audit", "build", "repair"], default="authoring")
    s.add_argument("--agent"); s.add_argument("--started"); s.add_argument("--commit")
    s.add_argument("--total-tokens", dest="total_tokens")
    for key, _, _ in ACT_ATTRS:
        s.add_argument("--" + key.replace("_", "-"), dest=key)
    s.add_argument("--tool", action="append"); s.add_argument("--prompt-file", dest="prompt_file")
    s.add_argument("--transcript"); s.add_argument("--generated", action="append")
    s.add_argument("--used", action="append")

    s = sub.add_parser("claim")
    s.add_argument("--id", required=True); s.add_argument("--text", required=True)
    s.add_argument("--parent", required=True); s.add_argument("--agent", required=True)
    s.add_argument("--state", default="unverified")

    sub.add_parser("validate"); sub.add_parser("report")

    s = sub.add_parser("disclosure")
    s.add_argument("--format", choices=["tex", "md"], default="md")
    s.add_argument("-o", "--out", help="write to file instead of stdout")

    s = sub.add_parser("search")
    s.add_argument("--query", required=True)
    s.add_argument("--rows", type=int, default=5)
    s.add_argument("--backend", action="append",
                   choices=["crossref", "openalex", "arxiv", "datacite"],
                   help="repeatable; default crossref + openalex")

    s = sub.add_parser("source")
    s.add_argument("--id", required=True)
    s.add_argument("--doi"); s.add_argument("--url"); s.add_argument("--title")
    s.add_argument("--state", choices=LADDER + sorted(RUNG_ALIASES))
    s.add_argument("--verify", action="store_true",
                   help="resolve the DOI via Crossref/OpenAlex and promote to retrieved")
    s.add_argument("--agent", help="agent performing the verification")
    s.add_argument("--self", dest="self_citation", action="store_true",
                   help="mark as self-citation (authored by a contributor of this work); "
                        "keeps the self-citation ratio machine-visible")

    s = sub.add_parser("promote")
    s.add_argument("--id", required=True, help="source or claim id")
    s.add_argument("--to", required=True, help="target rung")
    s.add_argument("--agent", required=True)
    s.add_argument("--note")
    s.add_argument("--file", help="vendored copy of the source (required for "
                   "--to source-vendored); path + sha256 are recorded")
    s.add_argument("--refuse", action="store_true",
                   help="refuse the promotion instead of granting it: no "
                   "state change, but the refusal is logged as an AuditPass "
                   "carrying aiprov:refusedRung (requires --note)")

    s = sub.add_parser("extract")
    s.add_argument("--graph", help="input TTL (default provenance.ttl)")
    s.add_argument("--seed-types", nargs="+", required=True,
                   help="entity classes to seed from, e.g. Manuscript Section Figure Claim")
    s.add_argument("--exclude-kinds", nargs="+",
                   help="classes never pulled into the closure, e.g. Slidedeck Poster")
    s.add_argument("-o", "--out", default="provenance-extract.ttl")
    s.add_argument("--dashboard", help="also render an HTML dashboard of the extract")

    a = p.parse_args()
    if a.cmd != "init" and a.base == DEFAULT_BASE:
        a.base = _detect_base() or a.base  # reuse the base the graph was seeded with
    {"init": cmd_init, "agent": cmd_agent, "log": cmd_log,
     "claim": cmd_claim, "validate": cmd_validate, "report": cmd_report,
     "extract": cmd_extract, "source": cmd_source, "promote": cmd_promote,
     "search": cmd_search, "disclosure": cmd_disclosure}[a.cmd](a)


if __name__ == "__main__":
    main()
