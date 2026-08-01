# Venue analysis for the F(AI)²R paper — checked 2026-07-28

Preprint: arXiv (uploaded 2026-07-28, CC BY-NC-SA 4.0, cs.DL).
Most venues accept preprinted work; check each policy at submission.

## Tier 1 — rolling journals, submit any time

| Venue | Fit | Notes |
|---|---|---|
| Quantitative Science Studies (MIT Press, OA) | High: research integrity, scholarly communication, measurement; the dilution argument, cost/overhead accounting, and division-of-work metrics speak its language | Already cited in the paper (publishing-strain2024); diamond OA |
| PeerJ Computer Science (OA) | High for the method-as-CS: provenance model, validator, skill; preprint-friendly, open review | Fast turnaround |
| Data Science (IOS Press, OA) | Good: FAIR/semantics community; RO-Crate paper appeared here | Already cited (rocrate2022) |
| Learned Publishing (Wiley) | Medium-high: the scholarly-publishing/AI-transparency angle | Shorter, practitioner-flavored rewrite advisable |
| International Journal of Digital Curation | Good: curation/stewardship framing | Journal path independent of IDCC deadlines |
| JOSS | Companion software paper for the aiprov tooling, not the meta-paper | Complements any of the above |

## Tier 2 — upcoming conference calls (2027 cycle)

| Venue | Expected deadline | Fit |
|---|---|---|
| ESWC 2027, Resources track | ~Nov–Dec 2026 (2026 cycle: abstract Nov 27, paper Dec 4) | Textbook Resources paper: vocabulary + validator + graph + skill; the semantic-web community feedback the operator wants before freezing the w3id namespace |
| deRSE27 (RSE Germany) | CfC ~Oct 2026 (deRSE26: Oct 31) for ~March 2027 | Talk/demo, German RSE community feedback, home turf (Helmholtz/DLR) |
| IPAW / ProvenanceWeek 2027 | Early 2027 (biennial, 2025/2026 with SIGMOD) | THE provenance research community; strongest technical audience for the ladder |
| TPDL 2027 | ~May 2027 (2026: May 3) | Digital-libraries core, European |
| JCDL 2027 | ~June 2027 (2026: Jun 30) | Digital-libraries core, ACM/IEEE |
| IEEE e-Science 2027 | ~May 2027 | Research-infrastructure framing |
| ISWC 2027 | ~May 2027 | Semantic web flagship; Resources track alternative to ESWC |

## Just missed (calibration; verify late tracks directly)

- JCDL 2026: papers closed Jun 30, 2026.
- IDCC27 (Lisbon, Feb 2027): papers closed Jul 24, 2026 (extended) —
  posters/demos may still be open; worth checking dcc.ac.uk directly.
- ISWC 2026 (Bari): posters/demos closed Jul 24; industry Jul 7.
- IEEE e-Science 2026 (Naples): papers closed ~Jun 8; the poster call
  may still be open (one source lists a Sep 23 date) — verify at
  escience-conference.org if a 2026 community touchpoint is wanted.

## Recommended strategy (operator's call)

Dual track. (1) Submit the meta-paper to Quantitative Science Studies
now (rolling; fit spans the dilution argument and the measured
demonstration; PeerJ CS as the more CS-flavored alternative). (2) Aim
the vocabulary-and-tooling story at ESWC 2027 Resources (deadline
around early December 2026) and a deRSE27 talk — both deliver exactly
the community feedback the operator wants before the w3id namespace
freezes, and neither collides with a journal submission of the
meta-paper since the resource paper is a different article.

## Status

**Submitted to QSS on 2026-07-29** (operator-reported in session):
manuscript = paper-qss build at the state of this commit (author-year
references, CRediT, data availability with Zenodo DOI
10.5281/zenodo.21667684, arXiv:2607.25637 disclosed), cover letter
276 words. QSS targets first review within ~5 weeks; on acceptance
review reports, author responses, and decision letters are published
openly in Web of Science.

## QSS detail check (2026-07-28)

- Publisher/owner: MIT Press with ISSI; diamond-era OA since 2020,
  now APC up to USD 1,200 on acceptance (waiver policy exists; no
  submission fee). License CC BY, author retains copyright — no
  conflict with the arXiv preprint (CC BY-NC-SA), and the journal
  explicitly welcomes preprinted manuscripts.
- Review: editor triage, then typically 2–3 external reviewers;
  journal targets review within ~5 weeks; DOAJ reports ~22 weeks
  average submission-to-publication. Anonymous peer review;
  reviewers of preprinted manuscripts are encouraged to publish
  their reviews openly.
- Submission: brief cover letter (<= 300 words) on significance and
  scope fit; manuscript via the QSS submission site
  (direct.mit.edu/qss).
- Scope: theoretical and empirical research on the system of
  science: scholarly communication, science indicators, science
  policy, workforce. Fit: dilution argument, measured
  overhead/cost/division-of-work, transparency infrastructure, EU AI
  Act angle. Risk: the PROV-O/ontology machinery may read as
  out-of-core-scope; reviewers may press the n=1 demonstration
  framing. Mitigation: frame as scholarly-communication
  infrastructure with a measured self-demonstration; the paper
  already cites QSS (publishing-strain2024).
- Adaptation needed: reformat from IEEE two-column to journal
  manuscript (single column); the 12.5-page cap no longer binds, so
  the review-driven compressions may partially unwind where clarity
  gains.

## QSS full guidelines (2026-07-29, via Web Archive snapshot of 2026-02-21)

direct.mit.edu blocks automated fetches; the full submission
guidelines were read from the Wayback Machine capture
`web.archive.org/web/20260221062714/https://direct.mit.edu/qss/pages/submission-guidelines`.

- Data sharing is REQUIRED: "requires authors to openly share all
  data essential for reproducing the key findings", "Data must be
  shared in a public repository that provides a persistent identifier
  such as a DOI. You may for instance use Zenodo", "Making data
  available on request is not acceptable". Code sharing strongly
  recommended. A data availability statement in the manuscript is
  mandatory. Data sets (own and third-party) must be formally cited
  in text and reference list, preferably by DOI.
  Action: Zenodo deposit of release v0.17.0 (doc/zenodo/RUNBOOK.md);
  data availability statement and dataset citation added to
  paper-qss/main.tex.
- First submission format: single Word or PDF file, everything
  integrated; no strict template. Abstract <= 200 words; up to six
  keywords; numbered pages and sections, line numbering suggested;
  author names and affiliations on page 1. References in a
  consistent AUTHOR-YEAR style; "Numbered references should not be
  used" (fixed: paper-qss now uses natbib + apalike). APA style only
  at revision stage (Word or LaTeX; methods early, statements and
  appendices at the end).
- Article types: Articles typically 5,000-8,000 words (ours: ~9,300
  prose words; "typically" is not a hard cap, but expect pressure to
  tighten); Reviews 5,000-10,000; Letters up to 1,000; book reviews
  1,000-2,000.
- Required at submission: cover letter <= 300 words; co-author
  approvals (n/a); ORCIDs strongly encouraged; CRediT author
  contributions REQUIRED for research articles (added to
  manuscript); competing-interest declarations; agreement to CC BY.
- Preprinting: strongly encouraged, including revised versions, not
  just the initial one (arXiv named first).
- Peer review: editor triage then typically 2-3 external reviewers;
  single anonymized; target ~5 weeks; on acceptance the reports,
  responses, and decision letters are published openly in Web of
  Science; reviewers of preprinted manuscripts encouraged to publish
  reviews (without revealing the journal or a recommendation).
- Supplementary materials: any suitable file type, <= 100 Mb.
- Reviewer suggestions and oppositions may be provided.
