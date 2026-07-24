# Meta-paper outline — target: 10 pages incl. references and figures (IEEE two-column)

Working title: *F(AI)²R — FAIR Research with AI in the Loop, Twice:
Verifiable AI Provenance as an Executable Skill*
(F(AI)²R is not an established term — deliberately: the title intrigues,
the abstract's first sentence and §1 P0 unpack it immediately.)

Building on the F(AI)²R method (github.com/noheton/f-ai-r): FAIR research
with AI in the loop, twice — an authoring pass (LLM drafts under human
direction) and an audit pass (machine-readable PROV-O graph of who did
what, when, from which sources), under the no-parentless-claim invariant,
with the stance that "the repository is the paper and is the process."
This paper is the meta-experiment: it generalizes the method beyond
scholarly writing, packages it as an executable agent skill, and applies
the method to its own production.

## Page budget (10 pp incl. references + figures)

| § | Section | Pages | Figures/Tables |
|---|---------|-------|----------------|
| 1 | Introduction | 1.0 | — |
| 2 | Background and related work | 1.25 | — |
| 3 | The dilution crisis | 1.0 | — |
| 4 | The aiprov method (generalized F(AI)²R) | 1.75 | F1 verification ladder, F2 core vocabulary |
| 5 | The executable skill | 1.25 | F3 workflow incl. ORCID-first setup + CI/CD |
| 6 | Meta-experiment: this paper as case study | 1.5 | F4 provenance graph of this paper, T1 telemetry report |
| 7 | Discussion and limitations | 0.75 | — |
| 8 | Conclusion | 0.5 | — |
| — | References | 1.0 | — |

## Section notes

1. **Introduction** — AI participation in knowledge work is routine but
   unaccounted; contributions vanish at commit boundaries. Contributions:
   (a) domain-agnostic generalization of F(AI)²R into the aiprov
   vocabulary; (b) the method as an *executable skill* an AI agent
   operates itself; (c) self-application with full telemetry.
2. **Background** — FAIR principles; W3C PROV-O; F(AI)²R two-pass model;
   contributor taxonomies (CRediT); AI transparency artefacts (model
   cards, datasheets); packaging (RO-Crate); publisher/venue AI-disclosure
   policies. Lineage: Obscurity-Is-Dead (transcript-as-artifact, the
   verification labels the ladder canonicalizes) → F(AI)²R → this work;
   neighbors: DLR uncertainty-aware provenance (Valente et al., with
   Frank Dressel); HMC-context discussions. All citations enter via the
   ladder: search → DOI-verified `reference-resolved` → `ai-confirmed`
   → human rungs.
3. **Dilution crisis** — output outgrows review capacity; paper mills +
   LLMs collapse the cost of plausible papers; fabricated papers and
   citations are indexed and propagate; model collapse compounds the
   pollution. Finding good sources becomes the bottleneck. Originality
   of ideas is the scarce good, and it must be checkable: a novelty
   claim carries its recorded search horizon, and every claim is
   explicitly supported — or refuted (`aiprov:contradicts`) — by facts
   on the ladder. Provenance is the supply-side answer: pedigree that
   fabrication cannot cheaply forge.
4. **Method** — agents (human/AI/tool), passes (authoring/audit/build/
   repair), claims, telemetry attributes, two invariants
   (no-parentless-claim; human-only rungs), verification ladder.
5. **Skill** — SKILL.md as the operable procedure; ORCID-first setup;
   base-IRI derivation; CI/CD so the current PDF and dashboard are always
   available; the skill logs its own operator.
6. **Meta-experiment** — this repo's graph: activities, claims, sources,
   token/cost report, dashboard; what the auditor can and cannot verify.
7. **Discussion** — fabrication risk and the omit-don't-estimate rule;
   why human-only rungs stay human; limits of self-report; skill drift
   and version pinning (archive/ + CHANGELOG).

## Figure plan

- F1: verification ladder with rung semantics + who may grant (TikZ).
- F2: aiprov core classes/properties over PROV-O (TikZ).
- F3: skill workflow loop from ORCID question to CI artifact (TikZ).
- F4: rendered provenance subgraph of this paper (extract → dashboard →
  vector export), generated near submission.
