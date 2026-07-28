# Registering https://w3id.org/aiprov — operator runbook

The paper's vocabulary namespace `https://w3id.org/aiprov/ns#` must
resolve (FAIR F1/A1; flagged by review). w3id.org identifiers are
registered by pull request to the community repository; the PR must
come from a maintainer's own account, so this step is yours. Budget:
about five minutes plus reviewer turnaround.

## Steps

1. Fork https://github.com/perma-id/w3id.org (the repo behind
   w3id.org).
2. Copy the directory `doc/w3id/aiprov/` from this repository into the
   fork's root as `aiprov/` (two files: `.htaccess`, `README.md` —
   both prepared and syntax-reviewed here).
3. Commit ("Add /aiprov — AI provenance vocabulary (F(AI)2R)") and
   open a PR against perma-id/w3id.org. In the PR text state that you
   are the maintainer and give a contact (the README already carries
   ORCID and GitHub handle; w3id reviewers look for exactly this).
4. w3id reviewers usually respond within days; address any requested
   tweaks by pushing to your fork branch.

## After the PR merges — verify

    curl -sIL -H "Accept: text/turtle" https://w3id.org/aiprov/ns | head
    # expect: 303 -> raw.githubusercontent.com/.../aiprov-schema.ttl -> 200
    curl -sIL https://w3id.org/aiprov/ns | head
    # expect: 303 -> github.com blob view
    curl -sIL https://w3id.org/aiprov/ | head
    # expect: 303 -> the repository

Then: grant the pending check in the verification worksheet, and drop
the "registration pending" caveat wherever it appears.

## Design notes (why the rules look like this)

- Fragments (`#model`) never reach the server; every term request
  arrives as `/aiprov/ns`, so one rule covers all terms.
- Targets use `HEAD` refs, so the redirect follows the repository's
  default branch and survives a branch rename.
- 303 See Other is the linked-data convention for "the identifier
  names a thing; here is a document about it".
