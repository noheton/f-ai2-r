# Zenodo deposit runbook (operator)

**Status: completed 2026-07-29.** The operator deposited release
v0.17.0 via Path A: <https://zenodo.org/records/21667684>, version
DOI `10.5281/zenodo.21667684`, concept DOI `10.5281/zenodo.21667683`,
CC BY 4.0, all seven files (source tarball, skill bundle, paper PDF,
provenance graph, metrics, dashboard, checksums). The DOI is wired
into `paper/references.bib` (`fair2r-data2026`), `CITATION.cff`,
`codemeta.json`, the cover letter, and both manuscript variants.
The steps below are kept for future versions.

QSS requires all data essential for reproducing the findings to be
shared in a public repository that mints a persistent identifier, and
names Zenodo as an example ("Making data available on request is not
acceptable", submission guidelines, checked 2026-07-29 via the
2026-02-21 Web Archive snapshot). GitHub alone does not satisfy this:
it has no DOI. This runbook turns release v0.17.0 into a Zenodo
deposit with a DOI. Zenodo account actions are outside the AI
session's scope, so these steps are the operator's.

## What gets deposited

The pinned submission snapshot, release v0.17.0
(<https://github.com/noheton/f-ai2-r/releases/tag/v0.17.0>). Its six
assets already contain everything the paper's data availability
statement promises: provenance graph, metrics, dashboard, skill
bundle, paper PDF, and checksums; the source tarball adds telemetry
(`doc/telemetry/`), the verification worksheet, transcripts, and all
scripts. Deposit metadata lives in `/.zenodo.json` (title, creator
with ORCID, license, keywords); keep it in sync with `CITATION.cff`.

## Path A (recommended): manual deposit of the pinned release

The paper's numbers pin to v0.17.0, and the GitHub–Zenodo webhook
only archives releases published *after* the integration is enabled,
so a manual deposit is the only way to get exactly v0.17.0 under the
DOI.

1. Sign in at <https://zenodo.org> (GitHub or ORCID login works).
2. New upload → upload the v0.17.0 source tarball
   (`Source code (tar.gz)` from the release page) plus the six
   release assets and `sha256sums.txt`.
3. Fill the form from `/.zenodo.json` (title, description, creator
   Florian Krebs with ORCID 0000-0001-6033-801X and DLR affiliation,
   upload type software, license Apache-2.0, version 0.17.0,
   keywords). Add the related identifier "is supplement to" pointing
   at the release URL.
4. Reserve the DOI before publishing if you want to bake it into the
   deposited files; otherwise publish and note the minted
   `10.5281/zenodo.XXXXXXX` (Zenodo also mints a concept DOI that
   resolves to the latest version; cite the version DOI in the
   paper).
5. Publish.

## Path C (automated, preferred from v0.18.0 on): release workflow archives to Zenodo

Since v0.18.0-prep the release workflow ends with an "Archive release
on Zenodo" step driven by `scripts/zenodo_archive.py`: it creates a
new version of the deposit behind concept DOI
`10.5281/zenodo.21667683`, replaces the files with the just-built
release assets (both paper variants, arXiv source bundle, graph,
dashboard, metrics, skill bundle, checksums), refreshes the metadata
from `/.zenodo.json`, and publishes. One operator action enables it:

1. Create a Zenodo personal access token at
   <https://zenodo.org/account/settings/applications/> with scopes
   `deposit:write` and `deposit:actions`.
2. Add it as the repository secret `ZENODO_TOKEN`
   (Settings → Secrets and variables → Actions).
3. To archive the already-published v0.18.0, re-run the "aiprov
   release" workflow with tag `v0.18.0` (or ask the session to
   re-trigger it): the release assets are rebuilt and the Zenodo step
   publishes them as version 0.18.0 under the concept DOI.

Without the secret the step logs "skipping" and the release stays
green. The script is implemented against the documented Zenodo REST
API and dry-run tested (`--dry-run`); its first live run happens once
the token exists, so watch that first run's log.

## Path B: GitHub–Zenodo integration for future releases

Optional but recommended for everything after v0.17.0: at
<https://zenodo.org/account/settings/github/> flip the switch for
`noheton/f-ai2-r`. Every release published from then on is archived
automatically with metadata from `/.zenodo.json`, under one concept
DOI with per-version DOIs. This does not retroactively cover
v0.17.0; that is what Path A is for.

## After the DOI exists

1. Replace the placeholder in `paper/references.bib` entry
   `fair2r-data2026`: add `doi={10.5281/zenodo.XXXXXXX}` and delete
   the "DOI to be inserted" sentence from the note.
2. Rebuild `paper-qss/` and check the data availability statement
   renders the citation.
3. Update `CITATION.cff` with a `doi` identifier and mirror it in
   `codemeta.json`.
4. Tell the session the DOI so it can log the deposit as a provenance
   activity and update the cover letter.
