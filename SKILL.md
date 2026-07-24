---
name: ai-provenance
description: >-
  Domain-agnostic AI provenance tracking over PROV-O with the full aiprov:
  attribute set: model, provider, session/request IDs, input/output/cache/
  reasoning tokens, temperature, top-p, seed, cost, energy, tool calls,
  prompt hashes, content hashes, git commits, transcripts, and a verification
  ladder with human-only rungs. Generalized from F(AI)²R
  (github.com/noheton/f-ai-r) — decoupled from paper writing; works for code,
  documents, data pipelines, CAD models, AAS submodels, any AI-in-the-loop
  artefact. Use this skill whenever the user wants to track who (human or AI)
  did what, record token usage or cost per activity, maintain a provenance.ttl,
  audit AI contributions, enforce no-parentless-claim, set up traceable AI
  workflows, verify literature sources/DOIs, track the source verification
  ladder, or ingest citations from literature databases — even if they only say "log this AI session", "track token usage",
  or "make this auditable".
---

# AI Provenance Tracking (aiprov)

Records every AI-in-the-loop activity as a PROV-O graph so a later human or
AI can verify, replay, or contest each output. The two core invariants from
F(AI)²R carry over unchanged:

- **No parentless claim.** Every `aiprov:Claim` needs `prov:wasGeneratedBy`
  (a named activity), `prov:wasAttributedTo` (agent), and an
  `aiprov:verificationState`.
- **Human-only rungs.** `verif:human-confirmed` and `verif:human-read` may
  never be granted by an AI agent. The validator flags violations.

## Workflow

1. **Setup — ask for the ORCID first.** Before anything else, ask the user
   one question: their ORCID iD. Then seed the graph, register them, and
   scaffold CI in a single step:
   `python3 scripts/provlog.py init --orcid 0000-0000-0000-0000 --ci`
   - The instance base is derived from the git remote when `--base` is
     omitted (e.g. `https://github.com/owner/repo/prov/`); later commands
     auto-detect it from the graph, so `--base` never needs repeating.
   - The owner is registered as `aiprov:HumanAgent` with name and current
     affiliation resolved from the public ORCID registry — never guessed. If
     resolution fails, only the bare iD is recorded.
   - `--ci` writes `.github/workflows/aiprov-build.yml` from
     `assets/ci/aiprov-build.yml`: every push validates the graph, renders
     the dashboard, and compiles `paper/*.tex` to PDF via latexmk, uploading
     both as workflow artifacts so the current version of the paper is
     always available.
2. **Register the remaining agents** — AI models (model, version, provider,
   endpoint, context window, knowledge cutoff) and deterministic tools:
   `provlog.py agent --id <model-id> --type ai --model <model-id> --provider <provider>`
   Additional humans register with
   `agent --id <slug> --type human --orcid <iD> --resolve` (fills
   name/affiliation from the registry).
3. **Log each working session or inference call** with full telemetry:
   `provlog.py log --activity <slug> --pass authoring|audit|build|repair
   --agent <id> --label "..." --input-tokens N --output-tokens N
   --cache-read-tokens N --temperature 0.7 --cost 0.42 --currency EUR
   --session-id <uuid> --tool web_search --tool bash
   --prompt-file prompts/writer.md --transcript doc/transcripts/s01.md
   --generated path/to/output --used path/to/source --commit <hash>`
   Generated artefacts automatically get sha256 content hashes; prompt files
   get `aiprov:promptHash` (prompts are source code).
4. **Record claims** made in the artefacts:
   `provlog.py claim --id c1 --text "..." --parent <activity> --agent <id> --state ai-confirmed` (legacy names retrieved / lit-retrieved / lit-read are accepted and normalized)
5. **Validate before committing**: `provlog.py validate` — exits non-zero on
   parentless or unattributed claims or AI-granted human-only rungs; the
   scaffolded CI runs it on every push, so it is also enforced server-side.
6. **Find and verify sources**: `provlog.py search --query "..."` sweeps
   Crossref, OpenAlex, arXiv, and DataCite (open APIs, no key); register
   picks with `provlog.py source --id <slug> --doi <doi> --verify --agent
   <id>` which resolves the DOI and promotes to `reference-resolved`.
7. **Generate the AI-transparency disclosure** whenever an artefact is
   published or shared: `provlog.py disclosure [--format tex|md] [-o file]`
   derives a statement from the graph itself — which AI systems assisted,
   how many activities/artefacts/claims are recorded, and that the graph is
   the machine-readable marking — aligned with the transparency rules for
   AI-generated content in Regulation (EU) 2024/1689 (AI Act). For papers,
   `--format tex -o paper/disclosure.tex` and `\input` it from an
   acknowledgement section; the scaffolded CI regenerates it before every
   PDF build so the statement never lags the graph. Never hand-edit the
   generated statement — fix the graph instead.
8. **Report**: `provlog.py report` — token and cost totals, per-agent
   breakdown, verification-rung distribution.
9. **Extract contribution subgraphs**: `provlog.py extract --graph provenance.ttl
   --seed-types Manuscript Section Figure Claim [--exclude-kinds Slidedeck Poster]
   -o subset.ttl --dashboard subset.html` — backward provenance closure: seeds
   are the entities that ARE the content of interest; the closure follows
   wasGeneratedBy, used, hadPlan, wasAssociatedWith, wasAttributedTo,
   wasDerivedFrom, wasInformedBy, transcript, and repairs to keep only what
   contributed to them. Works on aiprov: and fair2r: graphs alike. Use
   Artefact/Claim as seeds for aiprov graphs.
10. **Dashboard**: `python3 scripts/build_dashboard.py provenance.ttl -o dashboard.html`
   renders a self-contained, offline HTML ledger (no CDN): graph totals,
   per-agent table, activity ledger with token bars, verification-ladder
   chart, claims table, and an interactive force-directed provenance graph
   (agents/activities/claims/artefacts/prompts as typed nodes; PROV edges
   wasGeneratedBy, wasAttributedTo, wasAssociatedWith, used, transcript;
   drag + neighbourhood highlight, pure SVG/vanilla JS).

When operating in a repository that uses this skill, log YOUR OWN activities:
after producing or editing artefacts, run `provlog.py log` for the session
(estimate tokens as unavailable/omit if unknown — never fabricate telemetry)
and add claims for non-trivial assertions you introduced, at state
`unverified` or `ai-confirmed` at most.

## Attribute catalogue

Read `references/attributes.md` for the complete list of properties, their
XSD types, which PROV-O node they attach to, and mapping guidance from
provider APIs (Anthropic usage block, OpenAI usage, local llama.cpp) and
gateways. Read `assets/aiprov-schema.ttl` when editing the graph by hand or
extending the vocabulary (extend, don't fork: subclass `prov:` and `aiprov:`
terms).

## Bundled resources

| Path | What | When to read |
|---|---|---|
| `assets/aiprov-schema.ttl` | Full vocabulary: agent/activity/entity classes + all attributes + verification ladder | Seeding, hand-editing, extending |
| `assets/ci/aiprov-build.yml` | GitHub Actions template: validate graph, build dashboard, compile LaTeX paper to PDF, upload artifacts | Scaffolded by `init --ci` |
| `scripts/provlog.py` | CLI: init / agent / log / claim / validate / report / search / source / promote / disclosure / extract | Always — prefer it over hand-writing Turtle |
| `references/attributes.md` | Attribute catalogue with provider-API field mappings | Filling telemetry correctly |
| `scripts/build_dashboard.py` | Self-contained HTML dashboard from provenance.ttl | Presenting results |
| `scripts/package_skill.sh` | Zip this tree into a distributable `dist/ai-provenance.skill` | Releasing the skill |

Requires Python 3.10+ with `rdflib` (`pip install rdflib`). The graph file is
append-friendly Turtle; keep it in git next to the artefacts it describes.
Never fabricate values: omit attributes the provider did not report, and never
invent token counts, costs, or verification promotions.
