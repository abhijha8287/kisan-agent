#!/usr/bin/env bash
# Publishes the current commit to a Hugging Face Space that uses the Docker SDK.
#
# Spaces read their configuration from YAML front matter in README.md. To keep the
# repository README clean, the front matter is added only to the copy pushed to the Space.
#
# Usage: deploy/huggingface/deploy.sh <hf-username>/<space-name>
set -euo pipefail

SPACE="${1:?usage: $0 <hf-username>/<space-name>}"
ROOT="$(git rev-parse --show-toplevel)"
HEADER="$ROOT/deploy/huggingface/space-header.md"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
cat "$HEADER" "$ROOT/README.md" > "$WORK/README.md"

cd "$WORK"
git init -q -b main
git add -A
git commit -q -m "Deploy $(git -C "$ROOT" rev-parse --short HEAD)"
git push --force "https://huggingface.co/spaces/$SPACE" main
