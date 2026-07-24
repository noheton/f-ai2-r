# Changelog — ai-provenance skill

## v0.6 (2026-07-24)

- **source-vendored reframed as access gate.** Vendoring has no
  evidential value of its own — an unread copy proves nothing beyond
  `reference-resolved`. Its role is to make human verification feasible
  and durable: `promote --to source-vendored --file <path>` now records
  the vendored copy (path + sha256), promotion of a source to the
  human-only rungs is refused unless a vendored copy or clear access
  link (DOI/URL) exists — and the review material is printed with every
  request — and the validator warns on human-verified sources whose
  audit target is link-only. Schema, attribute catalogue, and paper
  ladder table updated to the gate semantics.

## v0.5 (2026-07-24)

- **Live paper preview ("show paper").** New
  `scripts/build_paper_preview.py` compiles the paper and renders a
  self-contained HTML preview: typeset pages as embedded images plus a
  status strip (commit, build time, pages, provenance-graph statistics).
  Workflow step 10 has the agent publish it as a Claude Artifact and
  re-publish the same file after every editing round, keeping a
  stable-URL sidebar preview current with the draft.

## v0.4 (2026-07-24)

- **Paper scaffolding in init.** `init --paper` scaffolds a compilable
  chapter-per-file LaTeX skeleton from `assets/paper/` (IEEEtran;
  `main.tex` as thin shell over `sections/*.tex`), author block filled
  from the ORCID-resolved identity, `references.bib` pre-seeded with the
  EU AI Act entry, and the acknowledgement section wired to the generated
  `disclosure.tex` (placeholder shipped so the skeleton compiles before
  the first activity is logged). CI disclosure step no longer fails on a
  graph without AI agents.

## v0.3 (2026-07-24)

- **EU AI Act transparency integration.** New `provlog.py disclosure`
  command derives an AI-transparency statement from the graph itself
  (which AI systems assisted, recorded activities/artefacts/claims, the
  graph as machine-readable marking), aligned with the disclosure and
  marking rules for AI-generated content in Regulation (EU) 2024/1689.
  Outputs LaTeX or Markdown; the CI template regenerates
  `paper/disclosure.tex` from the graph before every PDF build, so the
  published statement never lags the record. Workflow step 7 makes the
  disclosure part of publishing any artefact.

## v0.2 (2026-07-24)

The repository becomes the canonical skill source (`SKILL.md` at root,
packaged via `scripts/package_skill.sh`); the initial uploaded bundle is
preserved verbatim at `archive/aiprovenance-v0.skill`.

- **ORCID-first setup.** The workflow now opens by asking the user for
  their ORCID iD. `provlog.py init --orcid <iD>` registers the owner as
  `aiprov:HumanAgent` with name and current affiliation resolved from the
  public ORCID registry (pub.orcid.org, no key); nothing is fabricated when
  resolution fails. `agent --resolve` does the same for additional humans.
- **Streamlined scaffolding.** `init` derives the instance base IRI from
  the git remote when `--base` is omitted, and every later command
  auto-detects the base from the existing graph — `--base` never needs to
  be repeated. `init` prints a next-steps cheat sheet.
- **CI/CD scaffolding.** `init --ci` writes
  `.github/workflows/aiprov-build.yml` (template in `assets/ci/`): every
  push validates the provenance graph, renders the HTML dashboard, and
  compiles `paper/main.tex` to PDF via latexmk, uploading both as workflow
  artifacts so the current version of the paper is always available.

## v0 (initial upload)

Skill bundle as received: aiprov schema, provlog CLI
(init/agent/log/claim/validate/report/search/source/promote/extract),
dashboard builder, attribute catalogue.
