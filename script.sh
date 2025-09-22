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

# ADDITIONAL CODE ASSISTANT CAPABILITY TESTS

# Test: Code analysis and bug detection
step "Agent: analyze code for potential bugs"
RBUG=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Read calculator/main.py and analyze it for potential bugs, edge cases, or improvements. Provide specific recommendations.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RBUG"

# Test: Code refactoring suggestions
step "Agent: suggest code refactoring"
RREFACTOR=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Analyze calculator/main.py and suggest refactoring improvements for better code structure, readability, and maintainability.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RREFACTOR"

# Test: Add unit tests
step "Agent: create unit tests"
RTEST_CREATE=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create a comprehensive unit test file called calculator/test_main.py that tests all functions in calculator/main.py including edge cases and error conditions.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RTEST_CREATE"

# Test: Run the unit tests
step "Agent: run unit tests"
RTEST_RUN=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Run the unit tests in calculator/test_main.py using python3 -m pytest or python3 -m unittest","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RTEST_RUN"

# Test: Code documentation generation
step "Agent: add documentation"
RDOC=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Add comprehensive docstrings to all functions in calculator/main.py following Python PEP 257 conventions. Include parameter types, return types, and examples.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RDOC"

# Test: Performance optimization
step "Agent: optimize performance"
RPERF=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Analyze calculator/main.py for performance bottlenecks and suggest optimizations. If possible, implement the optimizations.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RPERF"

# Test: Add logging and error handling
step "Agent: enhance error handling and logging"
RLOG=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Add proper logging and enhanced error handling to calculator/main.py. Use Python logging module and handle various exception types gracefully.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RLOG"

# Test: Create configuration file
step "Agent: create configuration system"
RCONFIG=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create a configuration file calculator/config.py or calculator/config.json for the calculator application with settings like precision, logging level, etc. Update main.py to use this configuration.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RCONFIG"

# Test: Code style and formatting
step "Agent: check code style"
RSTYLE=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Analyze calculator/main.py for PEP 8 compliance and code style issues. Suggest improvements for better Python coding standards.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RSTYLE"

# Test: Create requirements file
step "Agent: generate requirements.txt"
RREQ=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Analyze all Python files in the calculator directory and create a requirements.txt file with all necessary dependencies and their versions.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RREQ"

# Test: Security analysis
step "Agent: security analysis"
RSEC=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Perform a security analysis of calculator/main.py. Look for potential security vulnerabilities like input validation issues, code injection risks, etc.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RSEC"

# Test: Create API wrapper
step "Agent: create API wrapper"
RAPI=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create a REST API wrapper for the calculator using Flask or FastAPI. Create calculator/api.py that exposes the calculator functions as HTTP endpoints.","workspace":"'"$WS"'"}' | jq -r .final_text)
echo "$RAPI"

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

# Test: Code architecture analysis
step "Agent: analyze project architecture"
RARCH=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Analyze the overall architecture of the requests library. Explain the main modules, their responsibilities, and how they interact with each other.","workspace":"'"$WS2"'"}' | jq -r .final_text)
echo "$RARCH" | head -c 2000; echo

# Test: Find and explain design patterns
step "Agent: identify design patterns"
RPATTERN=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Identify and explain any design patterns used in the requests library. Look at src/requests/ files and provide specific examples.","workspace":"'"$WS2"'"}' | jq -r .final_text)
echo "$RPATTERN" | head -c 2000; echo

# Test: Code complexity analysis
step "Agent: analyze code complexity"
RCOMPLEX=$(curl -sS -X POST "$BASE/v1/run" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Analyze the complexity of key functions in src/requests/api.py. Identify functions that might benefit from refactoring due to high complexity.","workspace":"'"$WS2"'"}' | jq -r .final_text)
echo "$RCOMPLEX" | head -c 1500; echo


echo
echo "All steps executed. Review any 'Note:' lines above for non-fatal observations."