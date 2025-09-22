#!/usr/bin/env bash
set -euo pipefail

BASE="https://agents-assistant-qwcl.onrender.com"

need() { command -v "$1" >/dev/null || { echo "Missing $1"; exit 1; }; }
need curl; need jq; need zip

retry() { # retry cmd with backoff; usage: retry <max> <cmd...>
  local max=$1; shift; local i=1
  until "$@"; do
    [[ $i -ge $max ]] && return 1
    sleep $((i*2)); i=$((i+1))
  done
}

step() { echo; echo "== $* =="; }

# 0) Health (handles free-tier cold starts)
step "Health check"
retry 5 curl -sS -m 20 "$BASE/healthz" | jq -c . || { echo "Health failed"; exit 1; }

# 1) Upload a workspace (zip your calculator dir)
step "Upload ZIP to create workspace"
cd /Users/walidzaouch/Documents/Agents
zip -r -q project.zip calculator -x "**/__pycache__/*" "**/.git/*" "**/.venv/*" "**/node_modules/*"
WS=$(curl -sS -X POST "$BASE/v1/workspaces/upload" -F zip_file=@project.zip | jq -r .workspace_id)
[[ -n "$WS" && "$WS" != "null" ]] || { echo "Upload failed"; exit 1; }
echo "WS=$WS"

# 2) Tree should show calculator files
step "List tree"
TREE=$(curl -sS "$BASE/v1/workspaces/$WS/tree" | jq -c .)
echo "$TREE" | jq '.entries[0:12]'
echo "$TREE" | jq -r '.entries[]' | grep -q '^calculator/main.py$' || { echo "calculator/main.py not found"; exit 1; }

# 3) File read sanity check
step "Read README.md"
curl -sS "$BASE/v1/workspaces/$WS/file?path=calculator/README.md" | jq -c '{len:(.content|length),head:(.content|.[:80])}'

# 4) Run: list files via agent
step "Agent: list files"
L1=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"List top-level items and tell me if calculator/ exists","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$L1"

# 5) Run: write a file and verify via browse endpoints
TARGET="calculator/hello_run_check.txt"
CONTENT="hello-from-run"
step "Agent: write a file (generic instruction)"
RWRITE=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create file '"$TARGET"' with content: '"$CONTENT"'","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RWRITE"

# Verify; if not present, try a more explicit instruction
if ! curl -sS "$BASE/v1/workspaces/$WS/file?path=$TARGET" | jq -e -r .content >/dev/null 2>&1; then
  step "Agent: write again (explicit tool intent)"
  RWRITE2=$(curl -sS -X POST "$BASE/v1/run" \
    -H 'content-type: application/json' \
    -d '{"prompt":"Use write_file_content to create '"$TARGET"' with content exactly: '"$CONTENT"'", "workspace":"'"$WS"'"}' | jq -r .final_text)
  echo "$RWRITE2"
fi

# Final verification of created file
step "Verify created file"
curl -sS "$BASE/v1/workspaces/$WS/file?path=$TARGET" | jq -c '{len:(.content|length),content:.content}' || { echo "Write verification failed"; exit 1; }

# 6) Run: execute a Python file with args and verify result mentioned
step "Agent: run calculator/main.py with args"
RRUN=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Run calculator/main.py with args: 3 + 5","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RRUN"
echo "$RRUN" | grep -Eiq '8|\"result\":\s*8' || echo "Note: response does not explicitly show 8; review output above"

# NEW FEATURE: Add advanced calculator functionality
step "Agent: add advanced calculator features"
FEATURE_PROMPT="Add a new function to calculator/main.py that can handle square root operations. Create a function called sqrt_operation that takes a number and returns its square root. Also add error handling for negative numbers."
RFEATURE=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"'"$FEATURE_PROMPT"'","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RFEATURE"

# Test the new feature
step "Test: run calculator with square root operation"
RTEST=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Run calculator/main.py to test the square root function with input 16","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RTEST"
echo "$RTEST" | grep -Eiq '4|\"result\":\s*4' || echo "Note: square root test may need verification; review output above"

# Test error handling for negative square root
step "Test: square root error handling"
RERROR=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Run calculator/main.py to test square root function with negative input -9 to verify error handling","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RERROR"
echo "$RERROR" | grep -Eiq 'error|invalid|negative' || echo "Note: error handling test may need verification; review output above"

# 7) Clone a real Python repo and verify tree
step "Clone psf/requests"
BASE="https://agents-assistant-qwcl.onrender.com"

WS2=$(curl -sS -X POST "$BASE/v1/workspaces/clone" \
  -H 'content-type: application/json' \
  -d '{"repo_url":"https://github.com/psf/requests.git","branch":"main"}' | jq -r .workspace_id)
[[ -n "$WS2" && "$WS2" != "null" ]] || { echo "Clone failed"; exit 1; }
echo "WS2=$WS2"

step "Tree for cloned repo (first 12)"
curl -sS "$BASE/v1/workspaces/$WS2/tree" | jq '.entries[0:12]'

# 8) Run: have the agent read and explain a specific file
step "Agent: explain src/requests/api.py:get()"
REXP=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Read src/requests/api.py and explain what get() does; include first ~15 lines of the function.","workspace":"'"$WS2"'"}' | jq -r .final_text)
echo "$REXP" | head -c 1500; echo

prompt="check is there a file called hello.txt in the workspace"
REXP=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"'"$prompt"'","workspace":"'"$WS2"'"}' | jq -r .final_text)
echo "$REXP" | head -c 1500; echo

echo
echo "All steps executed. Review any 'Note:' lines above for non-fatal observations."