#!/usr/bin/env python3
"""Archive a release on Zenodo as a new version of the existing deposit.

Used by the aiprov release workflow (and runnable by the operator
locally). Creates a new version of the deposit behind the concept DOI,
replaces its files with the given release assets, refreshes the
metadata from /.zenodo.json (version and related release tag taken
from --tag), and publishes. Standard library only; authenticates via
the ZENODO_TOKEN environment variable (personal access token with
deposit:write and deposit:actions scopes).

Flow (Zenodo REST API, developers.zenodo.org):
  1. GET  /api/records/<CONCEPT_RECID>          -> latest published id
  2. POST /api/deposit/depositions/<id>/actions/newversion
  3. PUT  /api/deposit/depositions/<draft>      <- metadata
  4. DELETE inherited draft files, PUT new files to the draft bucket
  5. POST /api/deposit/depositions/<draft>/actions/publish

--dry-run prints every step without calling the API (no token needed).
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://zenodo.org/api"
# Concept record of the F(AI)²R data deposit (concept DOI
# 10.5281/zenodo.21667683; first version 10.5281/zenodo.21667684).
CONCEPT_RECID = "21667683"


def _req(method, url, token, payload=None, data=None, ctype="application/json"):
    headers = {"Authorization": f"Bearer {token}"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = ctype
    elif data is not None:
        body = data
        headers["Content-Type"] = "application/octet-stream"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:2000]
        sys.exit(f"Zenodo API {method} {url} -> HTTP {e.code}: {detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="release tag, e.g. v0.18.0")
    ap.add_argument("--concept", default=CONCEPT_RECID)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    version = a.tag.lstrip("v")
    files = [pathlib.Path(f) for f in a.files
             if pathlib.Path(f).is_file() and not f.endswith("notes.md")]
    if not files:
        sys.exit("no files to archive")

    meta = json.loads((ROOT / ".zenodo.json").read_text())
    meta["version"] = version
    for rel in meta.get("related_identifiers", []):
        if "releases/tag/" in rel.get("identifier", ""):
            rel["identifier"] = (
                f"https://github.com/noheton/f-ai2-r/releases/tag/{a.tag}")
    # publication_date: let Zenodo default to today on publish.
    meta.pop("publication_date", None)

    if a.dry_run:
        print(f"[dry-run] new version of concept {a.concept} as {version}")
        for f in files:
            print(f"[dry-run] upload {f.name} ({f.stat().st_size} bytes)")
        print("[dry-run] metadata:", json.dumps(meta, indent=2)[:800])
        return

    token = os.environ.get("ZENODO_TOKEN") or sys.exit("ZENODO_TOKEN not set")

    latest = _req("GET", f"{BASE}/records/{a.concept}", token)
    latest_id = latest["id"]
    print(f"latest published version: record {latest_id}")

    nv = _req("POST",
              f"{BASE}/deposit/depositions/{latest_id}/actions/newversion",
              token)
    draft_url = nv["links"]["latest_draft"]
    draft = _req("GET", draft_url, token)
    draft_id = draft["id"]
    print(f"new draft: deposition {draft_id}")

    _req("PUT", f"{BASE}/deposit/depositions/{draft_id}", token,
         payload={"metadata": meta})

    for old in _req("GET", f"{BASE}/deposit/depositions/{draft_id}/files",
                    token):
        _req("DELETE",
             f"{BASE}/deposit/depositions/{draft_id}/files/{old['id']}",
             token)

    bucket = _req("GET", f"{BASE}/deposit/depositions/{draft_id}",
                  token)["links"]["bucket"]
    for f in files:
        print(f"uploading {f.name} ({f.stat().st_size} bytes)")
        _req("PUT", f"{bucket}/{f.name}", token, data=f.read_bytes())

    pub = _req("POST",
               f"{BASE}/deposit/depositions/{draft_id}/actions/publish",
               token)
    print(f"published: {pub.get('doi_url') or pub.get('doi')}")


if __name__ == "__main__":
    main()
