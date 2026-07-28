#!/usr/bin/env python3
"""Single source of numbers for the paper (skill v0.15).

Computes every quantity the paper cites from the primary records
(provenance.ttl, the agent session record, the transcript, git) and
writes them to doc/metrics.json (the citable snapshot artifact) and
paper/metrics.tex (LaTeX macros the manuscript uses instead of
hard-coded numbers). Rerunning this script is the whole consistency
pass for quantities: no number in the paper is typed by hand.

Derivation rule: every metric's methodology is stated here, in code,
and summarized in doc/metrics.json under "_methodology". Counterfactuals
are not computed. Cost is computed, not provider-reported, at the price
basis recorded below (per 1M tokens, all cache writes 1h-TTL).
"""
import json
import pathlib
import re
import subprocess
import sys
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Published price basis (USD per 1M tokens) recorded at first computation
# (activity s36): input 10, output 50, cache read 1 (0.1x), cache write
# 20 (1h-TTL, 2x). Change only with a logged operator direction.
PRICE = {"input": 10.0, "output": 50.0, "cache_read": 1.0, "cache_write_1h": 20.0}

# Repricing bases for the model-cost comparison (published list prices,
# USD per 1M tokens, fetched 2026-07-28 from the provider's pricing
# docs). Same recorded token volume, different price list: a price-basis
# comparison, NOT a prediction of what another model would have
# consumed (tokenizers and behaviour differ per model).
PRICE_ALT = {
    "opus": {"input": 5.0, "output": 25.0, "cache_read": 0.5, "cache_write_1h": 10.0},
    # Sonnet 5 introductory pricing in effect through 2026-08-31
    "sonnet": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write_1h": 4.0},
}

ACTIVE_GAP_MIN = 30          # active-time clustering threshold
PASTE_WORDS = 500            # direction messages above this = pasted document
MACHINERY = ("<command-name>", "Base directory for this skill", "<system-reminder>")

BOOK = re.compile(r"provlog\.py (log|claim|validate|report|init|agent|disclosure|extract)\b")
AUD = re.compile(r"provlog\.py (promote|source)\b")
GC = re.compile(r"git add provenance\.ttl|commit (-q )?-m [\"']Log s|Refresh session transcript")
TR = re.compile(r"export_transcript\.py|build_metrics\.py")


def find_session_file():
    base = pathlib.Path.home() / ".claude" / "projects"
    cands = sorted(base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def graph_metrics(m):
    from rdflib import Graph, Namespace, RDF
    g = Graph()
    g.parse(ROOT / "provenance.ttl", format="turtle")
    AIPROV = Namespace("https://w3id.org/aiprov/ns#")
    PROV = Namespace("http://www.w3.org/ns/prov#")
    m["triples"] = len(g)
    passes = {"AuthoringPass": 0, "AuditPass": 0, "Build": 0, "Repair": 0}
    for act in set(g.subjects(RDF.type, None)):
        types = {str(t).rsplit("#")[-1] for t in g.objects(act, RDF.type)}
        for k in passes:
            if k in types:
                passes[k] += 1
                break
    m["activities"] = sum(passes.values())
    m["pass_authoring"] = passes["AuthoringPass"]
    m["pass_audit"] = passes["AuditPass"]
    m["pass_build"] = passes["Build"]
    m["pass_repair"] = passes["Repair"]
    m["claims"] = len(set(g.subjects(RDF.type, AIPROV.Claim)))
    sources = set(g.subjects(RDF.type, AIPROV.Source))
    m["sources"] = len(sources)
    self_cited = checked = human_rungs = 0
    for s in sources:
        if (s, AIPROV.selfCitation, None) in g:
            self_cited += 1
        for st in g.objects(s, AIPROV.verificationState):
            rung = str(st).rsplit("/")[-1]
            if rung in ("ai-confirmed", "source-vendored"):
                checked += 1
            if rung in ("human-confirmed", "human-read"):
                checked += 1
                human_rungs += 1
    m["sources_self"] = self_cited
    m["sources_checked"] = checked
    m["human_rungs_granted"] = human_rungs


def session_metrics(m):
    src = find_session_file()
    if not src:
        sys.exit("no session record found; session metrics unavailable")
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    cw_1h = cw_5m = reqs = 0
    over_req = over_out = 0
    over_cost = all_cost = 0.0
    stamps, direction = [], []
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = d.get("timestamp")
        if ts:
            try:
                stamps.append(datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except ValueError:
                pass
        msg = d.get("message") or {}
        u = msg.get("usage")
        if isinstance(u, dict) and "output_tokens" in u:
            reqs += 1
            vals = {
                "input": u.get("input_tokens") or 0,
                "output": u.get("output_tokens") or 0,
                "cache_read": u.get("cache_read_input_tokens") or 0,
                "cache_write": u.get("cache_creation_input_tokens") or 0,
            }
            for k in tot:
                tot[k] += vals[k]
            cc = u.get("cache_creation")
            if isinstance(cc, dict):
                cw_5m += cc.get("ephemeral_5m_input_tokens") or 0
                cw_1h += cc.get("ephemeral_1h_input_tokens") or 0
            cost = (vals["input"] * PRICE["input"] + vals["output"] * PRICE["output"]
                    + vals["cache_read"] * PRICE["cache_read"]
                    + vals["cache_write"] * PRICE["cache_write_1h"]) / 1e6
            all_cost += cost
            content = msg.get("content")
            calls = []
            if isinstance(content, list):
                calls = [json.dumps(b.get("input", {}), ensure_ascii=False)
                         for b in content
                         if isinstance(b, dict) and b.get("type") == "tool_use"]
            if calls and all(BOOK.search(c) or AUD.search(c) or GC.search(c)
                             or TR.search(c) for c in calls):
                over_req += 1
                over_out += vals["output"]
                over_cost += cost
        if d.get("type") == "user":
            c = msg.get("content")
            texts = [c] if isinstance(c, str) else [
                b.get("text", "") for b in (c or [])
                if isinstance(b, dict) and b.get("type") == "text"]
            t = " ".join(texts).strip()
            if t and "Stop hook feedback" not in t and not any(x in t for x in MACHINERY):
                direction.append(len(t.split()))
    stamps.sort()
    active = sum(((b - a) for a, b in zip(stamps, stamps[1:])
                  if (b - a) <= datetime.timedelta(minutes=ACTIVE_GAP_MIN)),
                 datetime.timedelta())
    typed = [w for w in direction if w <= PASTE_WORDS]
    m["requests"] = reqs
    m["tok_input"] = tot["input"]
    m["tok_output"] = tot["output"]
    m["tok_cache_read"] = tot["cache_read"]
    m["tok_cache_write"] = tot["cache_write"]
    m["cache_write_5m"] = cw_5m
    m["cache_write_1h"] = cw_1h
    m["cost_usd"] = round(all_cost, 2)
    for name, pr in PRICE_ALT.items():
        m[f"cost_usd_{name}"] = round(
            (tot["input"] * pr["input"] + tot["output"] * pr["output"]
             + tot["cache_read"] * pr["cache_read"]
             + tot["cache_write"] * pr["cache_write_1h"]) / 1e6, 2)
    m["overhead_req_pct"] = round(100 * over_req / reqs, 1)
    m["overhead_out_pct"] = round(100 * over_out / tot["output"], 1)
    m["overhead_cost_pct"] = round(100 * over_cost / all_cost, 1)
    m["overhead_reqs"] = over_req
    m["dir_msgs"] = len(typed)
    m["dir_words"] = sum(typed)
    m["dir_median"] = sorted(typed)[len(typed) // 2] if typed else 0
    m["active_hours"] = round(active.total_seconds() / 3600, 1)
    m["span_hours"] = round((stamps[-1] - stamps[0]).total_seconds() / 3600) if stamps else 0
    m["session_id"] = src.stem


def repo_metrics(m):
    def sh(*cmd):
        return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout.strip()
    m["commits"] = int(sh("git", "rev-list", "--count", "HEAD"))
    log = sh("git", "log", "--oneline")
    m["commits_bookkeeping"] = len(re.findall(
        r"^[0-9a-f]+ (Log s|Refresh session transcript)", log, re.M))
    words = 0
    for p in (ROOT / "paper" / "sections").glob("*.tex"):
        for ln in p.read_text().splitlines():
            ln = ln.strip()
            if ln.startswith("%") or not ln:
                continue
            ln = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", "", ln)
            words += len(ln.split())
    m["prose_words"] = words
    m["tool_lines"] = sum(len(p.read_text().splitlines())
                          for p in (ROOT / "scripts").glob("*.py"))
    tr = ROOT / "doc" / "transcripts"
    turns = 0
    for p in tr.glob("*.md"):
        turns = max(turns, p.read_text(encoding="utf-8", errors="replace").count("\n## "))
    m["transcript_turns"] = turns


def tex_int(n):
    s = f"{n:,}"
    return s.replace(",", "\\,")


def write_outputs(m):
    m["_generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    ver = re.search(r"^## (v[\d.]+)", (ROOT / "CHANGELOG.md").read_text(), re.M)
    m["skill_version"] = ver.group(1) if ver else "v0"
    m["_methodology"] = {
        "cost": f"computed from token counts at price basis {PRICE} USD/1M; "
                "all cache writes verified 1h-TTL; not provider-reported",
        "active_hours": f"request timestamps clustered, gaps <= {ACTIVE_GAP_MIN} min joined",
        "direction": f"user messages minus tool results, hooks, machinery, and "
                     f"pastes > {PASTE_WORDS} words",
        "overhead": "requests whose tool calls all match bookkeeping patterns "
                    "(provlog log/claim/validate/report/init/agent/disclosure/"
                    "extract, promote/source, graph+transcript commits, exporters)",
        "prose_words": "sections/*.tex, comments stripped, LaTeX commands stripped",
        "cost_repriced": "same recorded token volume repriced at other "
                         "models' published list prices (Opus 5; Sonnet 5 at "
                         "introductory pricing through 2026-08-31); a "
                         "price-basis comparison, not a run prediction - "
                         "tokenizers and behaviour differ per model",
        "counterfactuals": "not computed (omit-don't-estimate)",
    }
    (ROOT / "doc" / "metrics.json").write_text(json.dumps(m, indent=2) + "\n")
    L = []
    L.append("% Generated by scripts/build_metrics.py - DO NOT EDIT BY HAND.")
    L.append("% Every number the paper cites comes from these macros; rerun the")
    L.append("% script to refresh all of them coherently (skill v0.15 rule).")
    def mac(name, val):
        L.append(f"\\newcommand{{{name}}}{{{val}}}")
    mac("\\MTriples", tex_int(m["triples"]))
    mac("\\MActivities", m["activities"])
    mac("\\MClaims", m["claims"])
    mac("\\MSources", m["sources"])
    mac("\\MSrcChecked", m["sources_checked"])
    mac("\\MSrcSelf", m["sources_self"])
    mac("\\MHumanRungs", m["human_rungs_granted"])
    mac("\\MCommits", m["commits"])
    mac("\\MBookCommits", m["commits_bookkeeping"])
    mac("\\MTurns", tex_int(m["transcript_turns"]))
    mac("\\MOutTok", tex_int(m["tok_output"]))
    mac("\\MInTok", tex_int(m["tok_input"]))
    mac("\\MCacheReadM", f"{m['tok_cache_read'] / 1e6:.1f}")
    mac("\\MCacheWriteM", f"{m['tok_cache_write'] / 1e6:.1f}")
    mac("\\MCacheReadMint", f"{round(m['tok_cache_read'] / 1e6)}")
    mac("\\MCostUSD", f"{round(m['cost_usd'])}")
    mac("\\MCostOpus", f"{round(m['cost_usd_opus'])}")
    mac("\\MCostSonnet", f"{round(m['cost_usd_sonnet'])}")
    mac("\\MOverReqPct", f"{m['overhead_req_pct']}\\%")
    mac("\\MOverOutPct", f"{m['overhead_out_pct']}\\%")
    mac("\\MOverCostPct", f"{m['overhead_cost_pct']}\\%")
    mac("\\MDirMsgs", m["dir_msgs"])
    mac("\\MDirWords", tex_int(m["dir_words"]))
    mac("\\MDirMedian", m["dir_median"])
    mac("\\MActiveH", m["active_hours"])
    mac("\\MSpanH", m["span_hours"])
    mac("\\MPassAuth", m["pass_authoring"])
    mac("\\MPassAudit", m["pass_audit"])
    mac("\\MPassRepair", m["pass_repair"])
    mac("\\MPassBuild", m["pass_build"])
    mac("\\MProseWordsK", f"{round(m['prose_words'], -2):,}".replace(",", "\\,"))
    mac("\\MToolLinesK", f"{round(m['tool_lines'], -2):,}".replace(",", "\\,"))
    mac("\\MSkillVersion", m["skill_version"])
    mac("\\MPriceBasis",
        f"input \\${PRICE['input']:.0f}, output \\${PRICE['output']:.0f}, "
        f"cache read \\${PRICE['cache_read']:.0f}, 1\\,h cache write "
        f"\\${PRICE['cache_write_1h']:.0f}")
    (ROOT / "paper" / "metrics.tex").write_text("\n".join(L) + "\n")
    print(f"doc/metrics.json + paper/metrics.tex written "
          f"({m['activities']} activities, cost {m['cost_usd']} USD)")


def main():
    m = {}
    graph_metrics(m)
    session_metrics(m)
    repo_metrics(m)
    write_outputs(m)


if __name__ == "__main__":
    main()
