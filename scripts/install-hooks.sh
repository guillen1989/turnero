#!/bin/bash
# Instala los git hooks del proyecto en .git/hooks/
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/../.git/hooks"

ln -sf "$SCRIPT_DIR/pre-push" "$HOOKS_DIR/pre-push"
chmod +x "$SCRIPT_DIR/pre-push"

echo "✓ Hooks instalados."
