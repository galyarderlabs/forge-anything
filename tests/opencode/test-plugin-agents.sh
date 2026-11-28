#!/usr/bin/env bash
# Test: OpenCode agent injection
# Verifies the plugin's config hook injects all 54 rendered agents as native
# OpenCode subagents (config.agents), from .opencode/agents/*.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Test: OpenCode agent injection ==="

if ! command -v node >/dev/null 2>&1; then
    echo "  [SKIP] node not on PATH"
    exit 0
fi

if node --test "$SCRIPT_DIR/test-plugin-agents.mjs" 2>&1; then
    echo "  [PASS] All 54 agents injected as native OpenCode subagents"
else
    echo "  [FAIL] Agent injection test failed"
    exit 1
fi

echo ""
echo "=== Agent injection tests passed ==="
