# F(AI)²R — domain-agnostic AI provenance tracking (`aiprov`)

Records every AI-in-the-loop activity as a [PROV-O](https://www.w3.org/TR/prov-o/)
graph so a later human or AI can **verify, replay, or contest** each output.
Generalized from [F(AI)²R](https://github.com/noheton/f-ai-r) and decoupled
from paper writing: the same vocabulary and tooling work for code, documents,
data pipelines, CAD models, AAS submodels — any artefact with AI in the loop.

Two invariants carry over from F(AI)²R unchanged:

- **No parentless claim.** Every `aiprov:Claim` needs `prov:wasGeneratedBy`
  (a named activity), `prov:wasAttributedTo` (an agent), and an
  `aiprov:verificationState`.
- **Human-only rungs.** `verif:human-confirmed` and `verif:human-read` may
  never be granted by an AI agent. The validator flags violations; `promote`
  refuses them outright.

## Quickstart

Requires Python 3.10+ and `rdflib`:

```sh
pip install -r scripts/requirements.txt
```

Seed a graph (once per project), register agents, log work, validate:

```sh
python3 scripts/provlog.py init --base https://your-domain.example/prov/

python3 scripts/provlog.py agent --id ada --type human \
    --name "Ada L." --orcid https://orcid.org/0000-0000-0000-0000

python3 scripts/provlog.py agent --id my-model --type ai \
    --model my-model-id --provider SomeProvider

python3 scripts/provlog.py log --activity s01-draft --pass authoring \
    --agent my-model --label "Draft module X" \
    --input-tokens 12000 --output-tokens 3400 --cost 0.42 --currency EUR \
    --session-id <uuid> --tool bash --tool web_search \
    --prompt-file prompts/writer.md --generated src/module_x.py \
    --used doc/spec.md --commit <hash>

python3 scripts/provlog.py claim --id c1 --text "Module X is O(n log n)" \
    --parent s01-draft --agent my-model --state unverified

python3 scripts/provlog.py validate   # non-zero exit on invariant violations
python3 scripts/provlog.py report     # token/cost totals, agents, rungs
```

Generated artefacts automatically get `sha256` content hashes; prompt files
get `aiprov:promptHash` — prompts are source code.

## The verification ladder

Rung names answer *who checked what*. Promotions must strictly climb and are
themselves logged as `aiprov:AuditPass` activities, so the history stays in
the graph. Legacy names (`retrieved`, `lit-retrieved`, `lit-read`,
`ai-checked`) are normalized on read and write.

| Pos | Rung | Meaning |
|---|---|---|
| 0 | `unverified` | Recorded; nothing checked yet |
| 1 | `needs-research` | A check was attempted and failed (e.g. DOI unresolvable). Do not cite. |
| 2 | `reference-resolved` | The reference *exists*: DOI/URL resolved in a registry |
| 3 | `ai-confirmed` | An AI checked the source content supports the claim — highest rung an AI may grant |
| 4 | `source-vendored` | A copy of the source is preserved in the repo |
| 5 | `human-confirmed` | A **human** spot-checked the claim against the source. Human-only. |
| 6 | `human-read` | A **human** read the source in full. Human-only. |

The offence the validator hunts is who *granted* a rung, not who authored the
claim: an AI-authored claim may legitimately sit at `human-read` if a human
promoted it.

## Further commands

| Command | What |
|---|---|
| `provlog.py search --query "..."` | Literature search over open APIs (Crossref, OpenAlex, arXiv, DataCite) — no key needed |
| `provlog.py source --id s --doi d --verify --agent a` | Register a source; `--verify` resolves the DOI and promotes to `reference-resolved` |
| `provlog.py promote --id x --to rung --agent a` | Climb the ladder; enforces order and human-only rungs |
| `provlog.py extract --seed-types Artefact Claim -o subset.ttl` | Backward provenance closure of everything that contributed to the seeds |
| `build_dashboard.py provenance.ttl -o dashboard.html` | Self-contained offline HTML ledger: totals, per-agent table, activity ledger, ladder chart, interactive provenance graph — no CDN |

## Repository layout

| Path | What |
|---|---|
| `assets/aiprov-schema.ttl` | Full vocabulary: agent/activity/entity classes, all attributes, verification ladder |
| `scripts/provlog.py` | CLI: init / agent / log / claim / validate / report / search / source / promote / extract |
| `scripts/build_dashboard.py` | Renders `provenance.ttl` as a self-contained HTML dashboard |
| `references/attributes.md` | Attribute catalogue with provider-API field mappings (Anthropic, OpenAI, llama.cpp) |
| `provenance.ttl` | This repository's own provenance graph — the toolkit tracks its own construction |

The graph file is append-friendly Turtle; keep it in git next to the
artefacts it describes. Extend the vocabulary by subclassing `prov:` and
`aiprov:` terms — extend, don't fork. Never fabricate values: omit attributes
the provider did not report, and never invent token counts, costs, or
verification promotions.

`provlog.py validate` is suitable as a pre-commit hook or CI step.

---
*AI note: this repository was bootstrapped with AI assistance; its own
construction is recorded in `provenance.ttl`. Review before production use.*
