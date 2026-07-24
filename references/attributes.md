# aiprov attribute catalogue

All properties live in `https://w3id.org/aiprov/ns#`. Attach each to the
node listed. Omit anything the provider does not report — never estimate
silently.

## On agents (aiprov:AIAgent / HumanAgent / ToolAgent)

| Property | Type | Notes / API mapping |
|---|---|---|
| foaf:name | string | display name |
| aiprov:model | string | Anthropic `model`; OpenAI `model` |
| aiprov:modelVersion | string | dated snapshot, e.g. `-20251001` |
| aiprov:provider | string | `Anthropic`, `local/llama.cpp`, gateway name |
| aiprov:endpoint | anyURI | API base URL or gateway URL |
| aiprov:contextWindow | integer | tokens |
| aiprov:knowledgeCutoff | date | from model card |
| aiprov:orcid | anyURI | humans |
| aiprov:affiliation | string | humans |

## On activities (prov:Activity subclasses)

Pass classes: `aiprov:AuthoringPass`, `aiprov:AuditPass`, `aiprov:Build`,
`aiprov:Repair`.

Timing: `prov:startedAtTime`, `prov:endedAtTime` (xsd:dateTime, with zone).

| Property | Type | Anthropic API | OpenAI API | llama.cpp |
|---|---|---|---|---|
| aiprov:sessionId | string | Claude Code session UUID | — | — |
| aiprov:requestId | string | response `id` | response `id` | — |
| aiprov:turnCount | integer | count of turns | idem | idem |
| aiprov:inputTokens | integer | `usage.input_tokens` | `usage.prompt_tokens` | `prompt_n` |
| aiprov:outputTokens | integer | `usage.output_tokens` | `usage.completion_tokens` | `predicted_n` |
| aiprov:cacheReadTokens | integer | `usage.cache_read_input_tokens` | `prompt_tokens_details.cached_tokens` | — |
| aiprov:cacheWriteTokens | integer | `usage.cache_creation_input_tokens` | — | — |
| aiprov:reasoningTokens | integer | thinking tokens if reported | `completion_tokens_details.reasoning_tokens` | — |
| aiprov:totalTokens | integer | sum | `usage.total_tokens` | sum |
| aiprov:temperature | decimal | request param | request param | request param |
| aiprov:topP | decimal | request param | request param | request param |
| aiprov:maxTokens | integer | `max_tokens` | `max_completion_tokens` | `n_predict` |
| aiprov:seed | integer | — | `seed` | `seed` |
| aiprov:stopReason | string | `stop_reason` | `finish_reason` | `stop_type` |
| aiprov:cost | decimal | compute from price sheet | idem | 0 or energy-based |
| aiprov:costCurrency | string | ISO 4217 | | |
| aiprov:energyWh | decimal | optional estimate | | |
| aiprov:toolCalls | integer | count of tool_use blocks | tool_calls length | — |
| aiprov:usedTool | string, repeatable | tool names invoked | | |
| aiprov:transcript | → aiprov:Transcript | link session record | | |
| prov:used | → aiprov:Prompt / aiprov:Source | prompt files, source material | | |
| prov:wasAssociatedWith | → agent | | | |

Gateway deployments: set `aiprov:provider` to the gateway name and
`aiprov:endpoint` to the gateway URL; keep `aiprov:model` as the upstream
model ID so accounting stays comparable.

## On entities

| Property | Type | Notes |
|---|---|---|
| aiprov:contentHash | string | `sha256:<hex>` of bytes at generation |
| aiprov:promptHash | string | `sha256:<hex>` of exact prompt text |
| aiprov:gitCommit | string | commit binding entity to repo state |
| aiprov:filePath | string | repo-relative path |
| aiprov:doi | anyURI | sources |
| prov:wasGeneratedBy | → activity | mandatory for claims |
| prov:wasAttributedTo | → agent | mandatory for claims |
| aiprov:verificationState | → rung | mandatory for claims |

## Verification ladder

Rung names answer "who checked what". Position is machine-readable via
`aiprov:ladderPosition`; promotions must strictly increase it. Legacy names
(right column) are `skos:altLabel`s — all tooling normalizes them on read
and write, so fair2r graphs consolidate onto this ladder automatically.

| Pos | Rung | Meaning | Legacy aliases |
|---|---|---|---|
| 0 | unverified | Recorded; nothing checked yet by anyone | — |
| 1 | needs-research | A check was attempted/demanded and did not succeed (e.g. DOI unresolvable). Do not cite. | — |
| 2 | reference-resolved | The reference EXISTS: DOI/URL resolved in a registry, metadata captured. Says nothing about content. | retrieved, lit-retrieved |
| 3 | ai-confirmed | An AI checked the source CONTENT supports the claim. Highest rung an AI may grant. | ai-checked |
| 4 | source-vendored | A copy of the source is preserved in the repo, immune to link rot. No evidential value alone — it is the access gate for human rungs: `promote` refuses 5–6 unless the source is vendored or carries a clear DOI/URL, and prints the review material | — |
| 5 | human-confirmed | A HUMAN spot-checked that the source supports the claim. Human-only. | — |
| 6 | human-read | A HUMAN read the source in full. Top of the ladder. Human-only. | lit-read |

The offence the validator hunts is who GRANTED a rung, not who authored the
claim: an AI-authored claim may legitimately sit at human-read if a human
promoted it. Promotion activities by AI agents to rungs 5-6 are hard
failures; human-only rungs without any recorded human promotion activity
are warnings (legitimate in legacy or hand-curated graphs).

---
*AI note: drafted with AI assistance, verified against the Anthropic and
OpenAI usage-object documentation and by test-run of provlog.py; review
provider field names against current API docs before automating ingestion.*
