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
license: Apache-2.0
compatibility: >-
  Any Agent Skills client (open SKILL.md format): Claude Code, Claude
  apps, OpenCode, OpenWork, and compatible agents. Core tooling is plain
  Python + git and model/provider-agnostic; see the Portability section.
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
   scaffold CI and the paper skeleton in a single step:
   `python3 scripts/provlog.py init --orcid 0000-0000-0000-0000 --ci --paper`
   - The instance base is derived from the git remote when `--base` is
     omitted (e.g. `https://github.com/owner/repo/prov/`); later commands
     auto-detect it from the graph, so `--base` never needs repeating.
   - The owner is registered as `aiprov:HumanAgent` with name and current
     affiliation resolved from the public ORCID registry — never guessed. If
     resolution fails, only the bare iD is recorded.
   - `--ci` writes `.github/workflows/aiprov-build.yml` from
     `assets/ci/aiprov-build.yml`: every push validates the graph, renders
     the dashboard, regenerates the AI-transparency disclosure, and compiles
     `paper/main.tex` to PDF via latexmk, uploading dashboard and PDF as
     workflow artifacts so the current version of the paper is always
     available. It also writes `aiprov-release.yml`: pushing a `v*` tag
     publishes a conformance-gated GitHub Release carrying the PDF, the
     provenance graph it was built from, the dashboard, `metrics.json`,
     the packaged skill, and sha256 checksums — a release is the artefact
     plus its record.
   - `--paper` scaffolds `paper/` from `assets/paper/`: a compilable
     chapter-per-file LaTeX skeleton (IEEEtran; `main.tex` is a thin shell
     over `sections/*.tex` — write prose only there), author block filled
     from the resolved ORCID identity, `references.bib` seeded with the EU
     AI Act entry, and an acknowledgement section wired to the generated
     `disclosure.tex`.
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
   Periodically run `provlog.py hashes`: it re-hashes every vendored file
   against the recorded digests — literature evidence under
   `doc/sources/` must match exactly (a mismatch is an audit failure),
   while repository-internal artefacts may differ, their hash pinning
   the promotion-time version with git history reconciling the
   evolution. Every registered source with a file should carry a hash.
6. **Find and verify sources**: `provlog.py search --query "..."` sweeps
   Crossref, OpenAlex, arXiv, and DataCite (open APIs, no key); register
   picks with `provlog.py source --id <slug> --doi <doi> --verify --agent
   <id>` which resolves the DOI and promotes to `reference-resolved`.
   DOIs outside Crossref/OpenAlex (e.g. arXiv's DataCite namespace)
   resolve through the doi.org content-negotiation fallback; sanitize
   registry BibTeX before committing it (publisher titles can leak HTML
   tags like `<i>` into LaTeX). Before requesting human confirmation of
   a source, hand over the
   evidence: `promote --to source-vendored --file <path>` records the
   vendored copy (path + sha256), or make sure a clear DOI/URL is on the
   node — vendoring has no evidential value of its own; it is the access
   gate, and `promote` refuses the human-only rungs without it, printing
   the review material (vendored path or obtain-via link) with every
   request. Mark sources authored by a contributor of the present work
   with `--self` — provenance-driven self-citation is legitimate but must
   stay machine-visible (`report` prints the ratio). Rung semantics:
   `human-read` subsumes `human-confirmed` (full read AND confirmation);
   reading without confirming is not a rung.
   The human-rung review queue lives at `doc/sources/VERIFICATION.md`,
   generated by `scripts/build_review_list.py` and regenerated
   automatically by every `promote`, `--refuse`, and `source` call —
   never edit it by hand; hand it to the operator when they walk rungs
   5–6. The paper preview renders it as a collapsible section at the
   bottom, so the operator's queue travels with the draft. Within each
   bucket the queue is ordered by computed relevance — the number of
   `\cite` occurrences across the paper, shown per entry — so the
   operator checks the most load-bearing sources first; the ordering
   methodology is disclosed in the worksheet header. Operators who
   never touch the repository can grant or refuse via prefilled
   GitHub issues: the preview's buttons open them, and the
   `aiprov-promote` workflow (scaffolded by `init --ci`) verifies the
   author against `doc/operators.json`, executes with the mapped
   human agent id, and replies on the issue — the authenticated click
   and required note are the judgement; the workflow transcribes.
   When incorporating issue-driven promotions (merging the workflow's
   commits), always read the issue threads too: fetch the issues AND
   their comments — operator remarks beyond the executed note are
   direction, not noise. Sweep for promotion issues left open with no
   reply (parallel grants race on the push and some runs lose):
   execute the recorded judgement from the issue body identically,
   note the failed run in the promotion note, then reply and close.
   An operator's granted judgement must never be silently dropped by
   an infrastructure race.
   Guide the deepest rungs to where the argument leans hardest: suggest
   `human-read` first for the sources the text's core claims ride on
   (the relevance ordering names them). If the operator deliberately
   leaves rungs ungranted for demonstration, record their blanket
   statement and disclose the reported-vs-formalized distinction where
   the ladder is shown; the graph records grants, statements stay
   statements. When screenshots or figures are regenerated, re-check
   the prose that describes them — captions and setup paragraphs drift
   silently when the image changes underneath them. Two practices
   that pay off early: ask the operator to confirm **self-cited
   sources** first (for works they authored, their judgement is
   uniquely authoritative and costs them least effort), and when a
   source's canonical page refuses automated access (script-rendered,
   bot-walled), record in the promotion note both the failed canonical
   fetch and the access path actually used — refusing
   `source-vendored` with that reason is the honest outcome when no
   redistributable canonical text can be obtained.
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
10. **Show the paper** on request ("show paper", "current draft"):
   `python3 scripts/build_paper_preview.py -o paper-preview.html` compiles
   the paper and renders a self-contained HTML preview — the typeset pages
   as embedded images plus a status strip (commit, build time, page count,
   graph statistics). Publish it as a Claude Artifact and RE-PUBLISH THE
   SAME FILE PATH after every round of paper edits so the sidebar preview
   stays current at a stable URL. Requires latexmk + pdftoppm.
11. **Dashboard**: `python3 scripts/build_dashboard.py provenance.ttl -o dashboard.html`
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

**Transcript-as-artifact.** `scripts/export_transcript.py` exports the
current agent session to `doc/transcripts/<session>.md` (images and
oversized tool payloads omitted); a repository Stop hook
(`.claude/settings.json`) regenerates it after every turn, so the
conversation is logged to the repository automatically and rides into
history with each commit. Link activities to it via
`provlog.py log --transcript doc/transcripts/<session>.md`.

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
| `assets/ci/aiprov-release.yml` | GitHub Actions template: on `v*` tags, conformance-gated GitHub Release with PDF + graph + dashboard + metrics + skill bundle + sha256 checksums | Scaffolded by `init --ci` |
| `scripts/provlog.py` | CLI: init / agent / log / claim / validate / hashes / report / search / source / promote / disclosure / extract | Always — prefer it over hand-writing Turtle |
| `references/attributes.md` | Attribute catalogue with provider-API field mappings | Filling telemetry correctly |
| `scripts/build_dashboard.py` | Self-contained HTML dashboard from provenance.ttl | Presenting results |
| `scripts/export_transcript.py` | Session → `doc/transcripts/<session>.md` + `--usage` token aggregation (Claude Code session format; see Portability) | Transcript-as-artifact, token backfill |
| `scripts/build_metrics.py` | Single source of numbers: every quantity the paper cites → `doc/metrics.json` + `paper/metrics.tex` macros | Before every build; rerun = consistency pass |
| `scripts/build_arxiv.py` | arXiv-ready flattened source tarball (comments stripped, `.bbl` shipped, compile-verified) + plain-text metadata | Preparing a submission |
| `scripts/build_review_list.py` | `doc/sources/VERIFICATION.md`: per-source human-rung worksheet (rung, cite count + citing sections, check evidence, access material, grant/refuse commands), relevance-ordered | Before the operator walks rungs 5–6 |
| `scripts/build_paper_preview.py` | Compile paper + render self-contained HTML preview (pages + structure notes) | Live preview / "show paper" |
| `scripts/package_skill.sh` | Zip this tree into a distributable `dist/ai-provenance.skill` | Releasing the skill |

## Portability

The skill follows the open Agent Skills format (a folder with this
`SKILL.md` plus `scripts/`, `assets/`, `references/`), so it loads in any
client that supports the spec — Claude Code and Claude apps natively;
OpenCode (and OpenWork, which runs on OpenCode) discover it at
`.opencode/skills/ai-provenance/`, `.claude/skills/ai-provenance/`, or the
neutral `.agents/skills/ai-provenance/`; OpenWork's Skills manager can also
import the unpacked bundle directly. Clients without Agent Skills support
can still operate the method: point their instruction file (e.g.
`AGENTS.md`) at this document.

What is universal vs. what needs a per-client shim:

- **Universal (no changes):** `provlog.py`, the aiprov schema, the
  validator, the verification ladder, the two-commit binding discipline,
  CI templates, dashboard, paper scaffolding. All plain Python + git. The
  graph is model- and provider-agnostic: any AI system (hosted or local)
  registers as an `aiprov:AIAgent` with its model and provider recorded as
  data.
- **Per-client shims (adapt when not on Claude Code):**
  1. *Turn-end hook* — the auto-export of the transcript after each turn is
     wired via a Claude Code Stop hook (`.claude/settings.json`); other
     clients use their own hook/plugin mechanism (e.g. an OpenCode plugin).
  2. *Transcript exporter* — `scripts/export_transcript.py` parses Claude
     Code's session JSONL layout; other clients store sessions differently
     and need their own exporter (same output contract:
     `doc/transcripts/<session>.md`).
  3. *Usage aggregation* — `export_transcript.py --usage` reads
     Anthropic-shaped usage blocks (`input_tokens`,
     `cache_read_input_tokens`, …); map provider fields per
     `references/attributes.md` (e.g. OpenAI `prompt_tokens` →
     `aiprov:inputTokens`).

The invariants do not change per client: omit-don't-estimate, no
parentless claim, and human-only rungs hold everywhere.

Requires Python 3.10+ with `rdflib` (`pip install rdflib`). The graph file is
append-friendly Turtle; keep it in git next to the artefacts it describes.
Never fabricate values: omit attributes the provider did not report, and never
invent token counts, costs, or verification promotions. One sanctioned
exception: when the operator directs it, cost may be *computed* from
provider-reported token counts and a published price list — log it with the
price basis (rates, cache TTL class) in the activity label so the record shows
a computed figure, never a provider-reported one.

**Derived numbers carry their derivation.** Any computed, aggregated, or
estimated figure that enters the graph or a published artefact must state its
methodology where the figure is recorded: inputs, formula, thresholds, and
exclusions (e.g. the gap threshold behind an active-time clustering, the price
basis behind a computed cost, the filters behind a word or message count), in
the activity label or promotion note. Prefer committing the measurement script
or making the computation reproducible from the record. Counterfactuals ("what
this would have cost without AI") are not measurable from the record and are
not estimated — omit-don't-estimate applies to them in full. An unexplained
number is treated the same as a fabricated one. Repricing recorded
consumption at another provider's or model's published rates is a
legitimate computation when the basis is disclosed and the claim is
scoped honestly: it compares price bases, never runs — consumption
under a different model is a counterfactual and stays unestimated.

**Demonstrations run on copies.** The live graph records only events that
actually happened. To show the operator how the tooling behaves — a refusal,
a human-only-rung gate error, a validator failure — copy `provenance.ttl`
(and `scripts/`) to a scratch directory and run the real commands there,
presenting the captured output. A staged refusal or demo promotion written
into the live graph is a fabricated record, however illustrative; the
honesty rule covers demonstration data in full.
