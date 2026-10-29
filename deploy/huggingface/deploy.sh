#!/usr/bin/env bash
# Publishes the current commit to a Hugging Face Space.
#
# Free Spaces use the Gradio SDK, which installs requirements.txt and runs app.py on
# port 7860. The Space configuration lives in YAML front matter in README.md. To keep the
# repository clean, the entry point, requirements and front matter are added only to the
# copy pushed to the Space.
#
# Requires a prior `hf auth login`.
#
# Usage: deploy/huggingface/deploy.sh <hf-username>/<space-name>
set -euo pipefail

SPACE="${1:?usage: $0 <hf-username>/<space-name>}"
ROOT="$(git rev-parse --show-toplevel)"
HERE="$ROOT/deploy/huggingface"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
cat "$HERE/space-header.md" "$ROOT/README.md" > "$WORK/README.md"
cp "$HERE/app.py" "$WORK/app.py"
# Direct dependencies with their version ranges, not exact pins: the Space installs Gradio
# alongside them, and pip must be free to pick versions compatible with both.
python3 -c 'import sys, tomllib; print("\n".join(tomllib.load(sys.stdin.buffer)["project"]["dependencies"]))' \
  < "$ROOT/pyproject.toml" > "$WORK/requirements.txt"

hf upload "$SPACE" "$WORK" . \
  --repo-type space \
  --delete "*" \
  --commit-message "Deploy $(git -C "$ROOT" rev-parse --short HEAD)"
