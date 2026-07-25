#!/bin/sh
# Package this repository tree as a distributable .skill archive (a zip).
# The repo is the canonical skill source; archive/ holds released snapshots.
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/ai-provenance.skill
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
mkdir -p "$staging/ai-provenance/scripts" "$staging/ai-provenance/assets/ci" \
         "$staging/ai-provenance/references"
cp SKILL.md "$staging/ai-provenance/"
cp scripts/provlog.py scripts/build_dashboard.py scripts/requirements.txt \
   scripts/export_transcript.py scripts/build_paper_preview.py \
   "$staging/ai-provenance/scripts/"
cp assets/aiprov-schema.ttl "$staging/ai-provenance/assets/"
cp assets/ci/aiprov-build.yml "$staging/ai-provenance/assets/ci/"
cp -r assets/paper "$staging/ai-provenance/assets/paper"
cp references/attributes.md "$staging/ai-provenance/references/"
(cd "$staging" && zip -X -q -r "$OLDPWD/dist/ai-provenance.skill" ai-provenance)
echo "dist/ai-provenance.skill"
echo "install: unzip into .claude/skills/, .opencode/skills/, or .agents/skills/"
echo "         (any Agent Skills client), or import via OpenWork's Skills manager"
