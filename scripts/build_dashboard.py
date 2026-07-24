#!/usr/bin/env python3
"""build_dashboard.py — render provenance.ttl as a self-contained HTML dashboard.

Usage: python3 build_dashboard.py [provenance.ttl] [-o dashboard.html]

No external assets, no CDN: data is embedded as JSON, charts are inline SVG.
AI note: drafted with AI assistance and verified by test-run against an
example graph; review before production use.
"""
from __future__ import annotations
import argparse, datetime, json, pathlib
from rdflib import Graph, Namespace, RDF, RDFS

AIPROV = Namespace("https://w3id.org/aiprov/ns#")
FAIR2R = Namespace("https://noheton.org/f-ai-r/ns#")  # F(AI)2R graphs render too
NSS = (AIPROV, FAIR2R)
PROV = Namespace("http://www.w3.org/ns/prov#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
RUNG_ALIASES = {"retrieved": "reference-resolved",
                "lit-retrieved": "reference-resolved",
                "ai-checked": "ai-confirmed",
                "lit-read": "human-read"}

INT_PROPS = ["inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens",
             "reasoningTokens", "totalTokens", "toolCalls", "turnCount", "maxTokens"]
STR_PROPS = ["sessionId", "requestId", "stopReason", "costCurrency", "model",
             "provider", "gitCommit"]
DEC_PROPS = ["cost", "temperature", "topP", "energyWh"]


def local(iri) -> str:
    return str(iri).rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def extract(path: pathlib.Path) -> dict:
    g = Graph(); g.parse(path, format="turtle")

    def subjects_of(*terms):
        out = []
        for t in terms:
            for n in NSS:
                out += list(g.subjects(RDF.type, n[t]))
        return list(dict.fromkeys(out))

    def val(s, term):
        for n in NSS:
            v = g.value(s, n[term])
            if v is not None:
                return v
        return None

    agents = {}
    for terms, kind in [(("AIAgent",), "ai"),
                        (("HumanAgent", "HumanResearcher"), "human"),
                        (("ToolAgent",), "tool")]:
        for s in subjects_of(*terms):
            a = {"id": local(s), "kind": kind,
                 "name": str(g.value(s, FOAF.name) or g.value(s, RDFS.label) or local(s))}
            for p in ["model", "provider", "orcid", "affiliation"]:
                v = val(s, p)
                if v: a[p] = str(v)
            agents[str(s)] = a

    acts = []
    pass_of = {}
    for n in NSS:
        pass_of.update({n.AuthoringPass: "authoring", n.AuditPass: "audit",
                        n.Build: "build", n.Repair: "repair"})
    subjects = (set(g.subjects(PROV.endedAtTime, None))
                | set(g.subjects(PROV.startedAtTime, None))
                | set(g.subjects(RDF.type, PROV.Activity))
                | set(o for o in g.objects(None, PROV.wasGeneratedBy))
                | set(k for k in pass_of if False))
    for cls in pass_of:
        subjects |= set(g.subjects(RDF.type, cls))
    claim_set = set(subjects_of("Claim"))
    subjects -= claim_set
    for s in subjects:
        a = {"id": local(s), "label": str(g.value(s, RDFS.label) or local(s)),
             "pass": "activity"}
        for t in g.objects(s, RDF.type):
            if t in pass_of: a["pass"] = pass_of[t]
        for key, v in [("started", g.value(s, PROV.startedAtTime)),
                       ("ended", g.value(s, PROV.endedAtTime))]:
            if v: a[key] = str(v)
        ag = g.value(s, PROV.wasAssociatedWith)
        if ag: a["agent"] = local(ag)
        for p in INT_PROPS:
            v = val(s, p)
            if v is not None: a[p] = int(v)
        for p in DEC_PROPS:
            v = val(s, p)
            if v is not None: a[p] = float(v)
        for p in STR_PROPS:
            v = val(s, p)
            if v is not None: a[p] = str(v)
        a["tools"] = sorted({str(t) for n in NSS for t in g.objects(s, n.usedTool)})
        a["generated"] = sorted(local(e) for e in g.subjects(PROV.wasGeneratedBy, s)
                                if e not in claim_set)[:6]
        acts.append(a)
    acts.sort(key=lambda x: x.get("started") or x.get("ended") or "")

    claims = []
    for s in claim_set:
        claims.append({
            "id": local(s), "text": str(g.value(s, RDFS.label) or local(s)),
            "parent": local(g.value(s, PROV.wasGeneratedBy) or ""),
            "agent": local(g.value(s, PROV.wasAttributedTo) or ""),
            "state": RUNG_ALIASES.get(
                (lambda x: x)(local(val(s, "verificationState") or "unverified")),
                local(val(s, "verificationState") or "unverified"))})
    claims.sort(key=lambda c: c["id"])
    # --- graph view: typed nodes + labelled edges over the instance data ---
    nodes, edges = {}, []
    def add_node(iri, kind, label=None):
        k = local(iri)
        if k not in nodes:
            nodes[k] = {"id": k, "kind": kind, "label": label or k}
        return k
    for iri, a in agents.items():
        add_node(iri, "agent-" + a["kind"], a["name"])
    act_ids = {local(s) for s in subjects}
    for s in subjects:
        add_node(s, "activity", local(s))
    kind_terms = {"prompt": ["Prompt"], "transcript": ["Transcript"],
                  "source": ["Source"],
                  "artefact": ["Artefact", "Manuscript", "Section", "Figure",
                                "Slidedeck", "Poster"],
                  "contribution": ["HumanContribution", "AIContribution",
                                    "MetaContribution", "Contribution"]}
    for kind, terms in kind_terms.items():
        for s in subjects_of(*terms):
            add_node(s, kind)
    for s in claim_set:
        add_node(s, "claim")
    def add_edge(s, o, rel):
        a, b = local(s), local(o)
        if a in nodes and b in nodes:
            edges.append({"s": a, "t": b, "r": rel})
    for s, o in g.subject_objects(PROV.wasAssociatedWith):
        add_edge(s, o, "wasAssociatedWith")
    for s, o in g.subject_objects(PROV.wasGeneratedBy):
        add_edge(s, o, "wasGeneratedBy")
    for s, o in g.subject_objects(PROV.wasAttributedTo):
        add_edge(s, o, "wasAttributedTo")
    for s, o in g.subject_objects(PROV.used):
        if local(s) in act_ids:
            add_edge(s, o, "used")
    for n in NSS:
        for s, o in g.subject_objects(n.transcript):
            add_edge(s, o, "transcript")
        for s, o in g.subject_objects(n.repairs):
            add_edge(s, o, "repairs")
        for s, o in g.subject_objects(n.contradicts):
            add_edge(s, o, "repairs")
    return {"generatedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": str(path), "triples": len(g),
            "agents": sorted(agents.values(), key=lambda a: a["kind"]),
            "activities": acts, "claims": claims,
            "nodes": sorted(nodes.values(), key=lambda n: n["id"]), "edges": edges}


HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>aiprov — provenance ledger</title>
<style>
:root{--ink:#1a2530;--dim:#5c6b78;--line:#d7dce0;--paper:#f7f8f9;--card:#ffffff;
--blue:#00658b;--blue-tint:#e3eef3;--green:#4c7a3d;--amber:#b98a21;--red:#a8453a;
--mono:ui-monospace,"JetBrains Mono","Cascadia Code",Consolas,monospace;
--sans:Arial,"Helvetica Neue",sans-serif}
*{box-sizing:border-box;margin:0}
body{background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans);padding:0 16px 64px}
.wrap{max-width:1060px;margin:0 auto}
header{border-bottom:2px solid var(--ink);padding:28px 0 14px;margin-bottom:22px;
display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 18px}
header h1{font-size:21px;letter-spacing:.04em}
header h1 b{color:var(--blue)}
header .meta{font:12px var(--mono);color:var(--dim);margin-left:auto}
h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);
margin:30px 0 10px;display:flex;align-items:center;gap:10px}
h2::after{content:"";flex:1;border-top:1px solid var(--line)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
background:var(--line);border:1px solid var(--line)}
.card{background:var(--card);padding:12px 14px}
.card .k{font:11px var(--mono);color:var(--dim);text-transform:uppercase;letter-spacing:.08em}
.card .v{font:600 24px/1.2 var(--mono);margin-top:4px}
.card .v small{font-size:12px;font-weight:400;color:var(--dim)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);font-size:13.5px}
th{font:11px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--dim);
text-align:left;padding:8px 10px;border-bottom:1px solid var(--ink)}
td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
.mono{font-family:var(--mono);font-size:12.5px}
.tag{display:inline-block;font:11px var(--mono);padding:1px 7px;border:1px solid currentColor}
.tag.authoring{color:var(--blue)}.tag.audit{color:var(--green)}
.tag.build{color:var(--dim)}.tag.repair{color:var(--amber)}
.tag.ai{color:var(--blue)}.tag.human{color:var(--green)}.tag.tool{color:var(--dim)}
.bar{display:flex;height:12px;min-width:120px;background:var(--blue-tint);border:1px solid var(--line)}
.bar i{display:block;height:100%}
.bar .in{background:var(--blue)}.bar .out{background:var(--green)}.bar .cache{background:#9dbfd0}
.legend{font:11px var(--mono);color:var(--dim);display:flex;gap:16px;margin:8px 2px}
.legend b{display:inline-block;width:10px;height:10px;margin-right:5px;vertical-align:-1px}
.rungs{display:grid;grid-template-columns:170px 1fr 34px;gap:6px 12px;align-items:center;
background:var(--card);border:1px solid var(--line);padding:14px 16px;font:12.5px var(--mono)}
.rbar{height:14px;background:var(--blue-tint)}
.rbar i{display:block;height:100%;background:var(--blue)}
.rungs .hu i{background:var(--green)}.rungs .warn i{background:var(--amber)}
.st{font:11px var(--mono);padding:1px 7px;border:1px solid currentColor;white-space:nowrap}
.st-human-confirmed,.st-human-read{color:var(--green)}
.st-ai-confirmed,.st-reference-resolved,.st-source-vendored{color:var(--blue)}
.st-needs-research{color:var(--amber)}.st-unverified{color:var(--red)}
.gwrap{background:var(--card);border:1px solid var(--line);position:relative}
#graph{display:block;width:100%;height:520px;cursor:grab}
#graph text{font:10.5px var(--mono);fill:var(--ink);pointer-events:none}
#graph text.dimmed,#graph .dimmed{opacity:.12}
#graph line{stroke:#b9c3cb;stroke-width:1.1}
#graph line.wasGeneratedBy{stroke:var(--blue)}
#graph line.wasAttributedTo{stroke:var(--green);stroke-dasharray:4 3}
#graph line.wasAssociatedWith{stroke:#8a97a1;stroke-dasharray:1.5 3}
#graph line.used{stroke:var(--amber)}
#graph line.transcript,#graph line.repairs{stroke:var(--red);stroke-dasharray:6 3}
#graph .node{cursor:pointer;stroke:var(--card);stroke-width:1.5}
.glegend{position:absolute;top:10px;right:10px;background:var(--card);
border:1px solid var(--line);padding:8px 12px;font:11px var(--mono);color:var(--dim);
display:grid;gap:4px}
.glegend .sw{display:inline-block;width:9px;height:9px;margin-right:6px;vertical-align:-1px}
.glegend .ln{display:inline-block;width:18px;height:0;border-top:2px solid;margin-right:6px;vertical-align:3px}
.ghint{border-top:1px solid var(--line);padding:6px 12px;font:11px var(--mono);color:var(--dim)}
@media(max-width:640px){.glegend{display:none}}
footer{margin-top:44px;border-top:1px solid var(--line);padding-top:12px;
font:11.5px var(--mono);color:var(--dim)}
@media(max-width:640px){td:nth-child(5),th:nth-child(5){display:none}}
</style></head><body><div class="wrap">
<header><h1>ai<b>prov</b> · provenance ledger</h1><div class="meta" id="meta"></div></header>
<section><h2>Graph totals</h2><div class="cards" id="cards"></div>
<div class="legend"><span><b style="background:var(--blue)"></b>input</span>
<span><b style="background:var(--green)"></b>output</span>
<span><b style="background:#9dbfd0"></b>cache read</span></div></section>
<section><h2>Agents</h2><table id="agents"><thead><tr>
<th>Agent</th><th>Kind</th><th>Model / identity</th><th>Activities</th><th>Tokens</th><th>Cost</th>
</tr></thead><tbody></tbody></table></section>
<section><h2>Activity ledger</h2><table id="acts"><thead><tr>
<th>When</th><th>Activity</th><th>Pass</th><th>Agent</th><th>Telemetry</th><th>Tokens</th>
</tr></thead><tbody></tbody></table></section>
<section><h2>Provenance graph</h2>
<div class="gwrap"><svg id="graph" role="img" aria-label="Provenance graph"></svg>
<div class="glegend" id="glegend"></div>
<div class="ghint">drag nodes · click to highlight neighbourhood · click background to reset</div>
</div></section>
<section><h2>Verification ladder</h2><div class="rungs" id="rungs"></div></section>
<section><h2>Claims</h2><table id="claims"><thead><tr>
<th>ID</th><th>Claim</th><th>Parent activity</th><th>Attributed to</th><th>State</th>
</tr></thead><tbody></tbody></table></section>
<footer id="foot"></footer></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("data").textContent);
const $=(s)=>document.querySelector(s), esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const sum=(a,k)=>a.reduce((t,x)=>t+(x[k]||0),0);
const A=D.activities, inT=sum(A,"inputTokens"), outT=sum(A,"outputTokens"),
 cache=sum(A,"cacheReadTokens"), cost=A.reduce((t,x)=>t+(x.cost||0),0),
 cur=[...new Set(A.map(x=>x.costCurrency).filter(Boolean))].join("/")||"";
$("#meta").textContent=D.source+" · "+D.triples+" triples · built "+D.generatedAt;
const cards=[["activities",A.length],["claims",D.claims.length],
 ["input tok",inT.toLocaleString()],["output tok",outT.toLocaleString()],
 ["cache read",cache.toLocaleString()],["cost",cost.toFixed(2)+" <small>"+esc(cur)+"</small>"]];
$("#cards").innerHTML=cards.map(([k,v])=>`<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
const perAgent={};
A.forEach(a=>{const p=perAgent[a.agent||"?"] ||= {n:0,tok:0,cost:0};
 p.n++;p.tok+=(a.totalTokens||0);p.cost+=(a.cost||0)});
$("#agents tbody").innerHTML=D.agents.map(a=>{const p=perAgent[a.id]||{n:0,tok:0,cost:0};
 const id=a.model?esc(a.model)+(a.provider?" · "+esc(a.provider):""):esc(a.affiliation||a.orcid||"—");
 return `<tr><td><b>${esc(a.name)}</b><div class="mono" style="color:var(--dim)">${esc(a.id)}</div></td>
 <td><span class="tag ${a.kind}">${a.kind}</span></td><td class="mono">${id}</td>
 <td class="mono">${p.n}</td><td class="mono">${p.tok.toLocaleString()}</td>
 <td class="mono">${p.cost?p.cost.toFixed(2)+" "+esc(cur):"—"}</td></tr>`}).join("");
const maxTok=Math.max(1,...A.map(a=>(a.inputTokens||0)+(a.outputTokens||0)+(a.cacheReadTokens||0)));
$("#acts tbody").innerHTML=A.map(a=>{
 const w=k=>((a[k]||0)/maxTok*100).toFixed(1)+"%";
 const tel=[a.sessionId&&"sess "+a.sessionId, a.temperature!=null&&"T="+a.temperature,
  a.toolCalls&&a.toolCalls+"× tools ("+a.tools.join(", ")+")",
  a.cost!=null&&a.cost.toFixed(2)+" "+(a.costCurrency||""),
  a.gitCommit&&"@"+a.gitCommit, a.generated.length&&"→ "+a.generated.join(", ")]
  .filter(Boolean).join(" · ");
 const when=(a.started||a.ended||"").slice(0,16).replace("T"," ");
 const tok=(a.inputTokens||a.outputTokens)?
  `<div class="bar"><i class="in" style="width:${w("inputTokens")}"></i><i class="out" style="width:${w("outputTokens")}"></i><i class="cache" style="width:${w("cacheReadTokens")}"></i></div>
   <div class="mono" style="color:var(--dim)">${((a.totalTokens)||0).toLocaleString()}</div>`:'<span class="mono" style="color:var(--dim)">—</span>';
 return `<tr><td class="mono">${esc(when)}</td>
 <td><b>${esc(a.label)}</b><div class="mono" style="color:var(--dim)">${esc(a.id)}</div></td>
 <td><span class="tag ${a.pass}">${a.pass}</span></td><td class="mono">${esc(a.agent||"—")}</td>
 <td class="mono" style="color:var(--dim)">${esc(tel)||"—"}</td><td>${tok}</td></tr>`}).join("");
const LADDER=["unverified","needs-research","reference-resolved","ai-confirmed","source-vendored","human-confirmed","human-read"];
const rc={};D.claims.forEach(c=>rc[c.state]=(rc[c.state]||0)+1);
const maxR=Math.max(1,...Object.values(rc));
$("#rungs").innerHTML=LADDER.map(r=>{const n=rc[r]||0;
 const cls=r.startsWith("human")?"hu":(r==="unverified"||r==="needs-research")?"warn":"";
 return `<div>${r}</div><div class="rbar ${cls}"><i style="width:${n/maxR*100}%"></i></div><div style="text-align:right">${n}</div>`}).join("");
$("#claims tbody").innerHTML=D.claims.map(c=>`<tr><td class="mono">${esc(c.id)}</td>
 <td>${esc(c.text)}</td><td class="mono">${esc(c.parent)}</td><td class="mono">${esc(c.agent)}</td>
 <td><span class="st st-${esc(c.state)}">${esc(c.state)}</span></td></tr>`).join("");
/* ---- provenance graph: dependency-free force layout over SVG ---- */
(function(){
const svg=$("#graph"),NS="http://www.w3.org/2000/svg";
const W=svg.clientWidth||1000,H=D.nodes.length>120?760:520;svg.style.height=H+"px";svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
const KIND={ "agent-ai":{c:"#00658b",r:13,shape:"rect",l:"AI agent"},
 "agent-human":{c:"#4c7a3d",r:13,shape:"rect",l:"human"},
 "agent-tool":{c:"#8a97a1",r:11,shape:"rect",l:"tool"},
 activity:{c:"#1a2530",r:9,shape:"circle",l:"activity"},
 claim:{c:"#a8453a",r:7,shape:"diamond",l:"claim"},
 artefact:{c:"#b98a21",r:7,shape:"circle",l:"artefact"},
 prompt:{c:"#7a5ea8",r:6,shape:"circle",l:"prompt"},
 source:{c:"#5c8a8a",r:6,shape:"circle",l:"source"},
 transcript:{c:"#c07a4a",r:6,shape:"circle",l:"transcript"},
 contribution:{c:"#6d8a9c",r:5,shape:"circle",l:"contribution"}};
const nodes=D.nodes.map((n,i)=>({...n,x:W/2+Math.cos(i*2.4)*(120+8*i%140),
 y:H/2+Math.sin(i*2.4)*(90+7*i%110),vx:0,vy:0}));
const byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
const links=D.edges.filter(e=>byId[e.s]&&byId[e.t]).map(e=>({...e,s:byId[e.s],t:byId[e.t]}));
const deg={};links.forEach(l=>{deg[l.s.id]=(deg[l.s.id]||0)+1;deg[l.t.id]=(deg[l.t.id]||0)+1});
/* simulate */
for(let it=0;it<340;it++){const k=it<300?1:.3;
 for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
  const a=nodes[i],b=nodes[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy||1;
  if(d2<40000){const f=1400/d2*k;dx*=f;dy*=f;a.vx+=dx;a.vy+=dy;b.vx-=dx;b.vy-=dy}}
 links.forEach(l=>{const dx=l.t.x-l.s.x,dy=l.t.y-l.s.y,d=Math.hypot(dx,dy)||1,
  f=(d-95)/d*.028*k;l.s.vx+=dx*f;l.s.vy+=dy*f;l.t.vx-=dx*f;l.t.vy-=dy*f});
 nodes.forEach(n=>{n.vx+=(W/2-n.x)*.0016*k;n.vy+=(H/2-n.y)*.0016*k;
  n.x+=n.vx*=.82;n.y+=n.vy*=.82;
  n.x=Math.max(30,Math.min(W-30,n.x));n.y=Math.max(22,Math.min(H-22,n.y))});}
/* draw */
const gE=document.createElementNS(NS,"g"),gN=document.createElementNS(NS,"g"),
 gT=document.createElementNS(NS,"g");svg.append(gE,gN,gT);
const eEls=links.map(l=>{const ln=document.createElementNS(NS,"line");
 ln.setAttribute("class",l.r);gE.append(ln);return ln});
const nEls=nodes.map(n=>{const k=KIND[n.kind]||KIND.activity;let el;
 if(k.shape==="rect"){el=document.createElementNS(NS,"rect");
  el.setAttribute("width",k.r*2);el.setAttribute("height",k.r*1.5)}
 else if(k.shape==="diamond"){el=document.createElementNS(NS,"rect");
  el.setAttribute("width",k.r*1.7);el.setAttribute("height",k.r*1.7);
  el.setAttribute("transform-origin","center")}
 else{el=document.createElementNS(NS,"circle");el.setAttribute("r",k.r)}
 el.setAttribute("class","node");el.setAttribute("fill",k.c);
 const ti=document.createElementNS(NS,"title");
 ti.textContent=n.kind+": "+n.label+(deg[n.id]?" · "+deg[n.id]+" edges":"");el.append(ti);
 gN.append(el);return el});
const big=nodes.length>120;
const tEls=nodes.map(n=>{const t=document.createElementNS(NS,"text");
 const show=!big||n.kind.startsWith("agent")||(deg[n.id]||0)>=6;
 t.textContent=show?(n.label.length>22?n.label.slice(0,21)+"…":n.label):"";
 t.setAttribute("text-anchor","middle");gT.append(t);return t});
function pos(){links.forEach((l,i)=>{const e=eEls[i];
 e.setAttribute("x1",l.s.x);e.setAttribute("y1",l.s.y);
 e.setAttribute("x2",l.t.x);e.setAttribute("y2",l.t.y)});
 nodes.forEach((n,i)=>{const k=KIND[n.kind]||KIND.activity,el=nEls[i];
 if(el.tagName==="circle"){el.setAttribute("cx",n.x);el.setAttribute("cy",n.y)}
 else{const w=+el.getAttribute("width"),h=+el.getAttribute("height");
  el.setAttribute("x",n.x-w/2);el.setAttribute("y",n.y-h/2);
  if(n.kind==="claim")el.setAttribute("transform",`rotate(45 ${n.x} ${n.y})`)}
 tEls[i].setAttribute("x",n.x);tEls[i].setAttribute("y",n.y+k.r+11)})}
pos();
/* highlight neighbourhood */
function focus(id){nodes.forEach((n,i)=>{const on=!id||n.id===id||
  links.some(l=>l.r&&(l.s.id===id&&l.t.id===n.id||l.t.id===id&&l.s.id===n.id));
 nEls[i].classList.toggle("dimmed",!on);tEls[i].classList.toggle("dimmed",!on)});
 links.forEach((l,i)=>eEls[i].classList.toggle("dimmed",id&&l.s.id!==id&&l.t.id!==id))}
let sel=null;
nEls.forEach((el,i)=>el.addEventListener("click",ev=>{ev.stopPropagation();
 sel=sel===nodes[i].id?null:nodes[i].id;focus(sel)}));
svg.addEventListener("click",()=>{sel=null;focus(null)});
/* drag */
let drag=null;
function pt(ev){const r=svg.getBoundingClientRect(),
 e=ev.touches?ev.touches[0]:ev;
 return {x:(e.clientX-r.left)*W/r.width,y:(e.clientY-r.top)*H/r.height}}
nEls.forEach((el,i)=>{const st=ev=>{drag=nodes[i];ev.preventDefault()};
 el.addEventListener("mousedown",st);el.addEventListener("touchstart",st,{passive:false})});
const mv=ev=>{if(!drag)return;const p=pt(ev);drag.x=p.x;drag.y=p.y;pos()};
addEventListener("mousemove",mv);addEventListener("touchmove",mv,{passive:false});
addEventListener("mouseup",()=>drag=null);addEventListener("touchend",()=>drag=null);
/* legend */
const usedKinds=[...new Set(nodes.map(n=>n.kind))];
const EDGE=[["wasGeneratedBy","#00658b","solid"],["wasAttributedTo","#4c7a3d","dashed"],
 ["used","#b98a21","solid"],["wasAssociatedWith","#8a97a1","dotted"],
 ["transcript / repairs","#a8453a","dashed"]];
$("#glegend").innerHTML=usedKinds.map(k=>{const d=KIND[k]||KIND.activity;
 return `<span><i class="sw" style="background:${d.c}"></i>${d.l||k}</span>`}).join("")+
 EDGE.map(([n,c,s])=>`<span><i class="ln" style="border-color:${c};border-top-style:${s}"></i>${n}</span>`).join("");
})();
$("#foot").textContent="Static export of "+D.source+". Human-only rungs (human-confirmed, human-read) can never be granted by an AI agent. AI note: dashboard generated with AI assistance from the graph; verify against provenance.ttl before relying on it.";
</script></body></html>"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("graph", nargs="?", default="provenance.ttl")
    p.add_argument("-o", "--out", default="dashboard.html")
    a = p.parse_args()
    data = extract(pathlib.Path(a.graph))
    html = HTML.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    pathlib.Path(a.out).write_text(html, encoding="utf-8")
    print(f"Wrote {a.out}: {len(data['activities'])} activities, "
          f"{len(data['claims'])} claims, {len(data['agents'])} agents")


if __name__ == "__main__":
    main()
