#!/bin/sh
# Package this repository tree as a distributable .skill archive (a zip).
# The repo is the canonical skill source; archive/ holds released snapshots.
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
mkdir -p "$staging/ai-provenance/scripts" "$staging/ai-provenance/assets/ci" \
         "$staging/ai-provenance/references"
cp SKILL.md "$staging/ai-provenance/"
cp scripts/provlog.py scripts/build_dashboard.py scripts/requirements.txt \
   scripts/export_transcript.py scripts/build_paper_preview.py scripts/build_metrics.py scripts/build_arxiv.py scripts/build_review_list.py \
   "$staging/ai-provenance/scripts/"
cp assets/aiprov-schema.ttl "$staging/ai-provenance/assets/"
cp assets/ci/aiprov-build.yml assets/ci/aiprov-release.yml "$staging/ai-provenance/assets/ci/"
cp -r assets/paper "$staging/ai-provenance/assets/paper"
cp references/attributes.md "$staging/ai-provenance/references/"
# Build in staging, replace dist/ only on success; python fallback for
# environments without zip (some CI runner images dropped it).
if command -v zip >/dev/null 2>&1; then
  (cd "$staging" && zip -X -q -r ai-provenance.skill ai-provenance)
else
  (cd "$staging" && python3 -m zipfile -c ai-provenance.skill ai-provenance)
fi
mv "$staging/ai-provenance.skill" dist/ai-provenance.skill
echo "dist/ai-provenance.skill"
echo "install: unzip into .claude/skills/, .opencode/skills/, or .agents/skills/"
echo "         (any Agent Skills client), or import via OpenWork's Skills manager"
