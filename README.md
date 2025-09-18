## Project Overview

### Problem statement
Building a safe, agentic code assistant that can explore, read, write, and run code in a constrained workspace is easy locally, but hard to expose on the web with proper isolation, persistence, and a clean user flow (upload or clone a repo, browse files, and run prompts).

### Solution approach
- Wrap the existing Gemini tool-calling loop in a web API (FastAPI).
- Add workspace management endpoints: upload a ZIP, clone a Git repo, list a file tree, fetch a file.
- Constrain tools to a per-workspace root via realpath checks and safe ZIP extraction.
- Containerize and deploy with two options: quick sharing via Cloudflare Tunnel and a stable deployment on Render (free tier using ephemeral storage).

---

## Technical Architecture

### High-level design
```
Client (curl / UI)
   |
   v
FastAPI service (server.py)
  - /v1/workspaces/upload (ZIP -> workspace)
  - /v1/workspaces/clone (repo -> workspace)
  - /v1/workspaces/{id}/tree
  - /v1/workspaces/{id}/file
  - /v1/run (Gemini loop with tool-calls)
   |
   v
Agent loop (Gemini SDK)
  -> Tool dispatcher (call_funtion.py)
     -> Tools (functions/*):
        - get_files_info
        - get_file_content
        - write_file_content
        - run_python_file
           (all path-confined to workspace_root)
   |
   v
Workspace Store
  - Local: /workspaces (mounted) or /tmp/workspaces (ephemeral)
  - Render free tier: /tmp/workspaces
```

### Technology stack
- Runtime: Python 3.13, Docker
- API: FastAPI + Uvicorn
- LLM: Google Gemini (google-genai SDK)
- Packaging: uv (pip), pyproject.toml
- Deployment:
  - Local dev: Docker + Cloudflare Tunnel
  - Production (stable URL): Render (free tier, ephemeral), optional paid disk
- VCS: GitHub

---

## Implementation Details

### Key files
- `server.py`: FastAPI app exposing endpoints
  - `POST /v1/workspaces/upload`: accepts a ZIP and extracts safely into a new `workspace_id`
    - Zip slip guard via `realpath` comparisons
  - `POST /v1/workspaces/clone`: shallow `git clone` into a new `workspace_id`
  - `GET /v1/workspaces/{id}/tree`: lists files with ignore patterns and max entries
  - `GET /v1/workspaces/{id}/file?path=...`: returns UTF‑8 text content with size cap
  - `POST /v1/run`: executes the agent loop against a specified workspace
  - `GET /healthz`: health check

- `call_funtion.py`: tool registry and dispatcher
  - Accepts `workspace_root` from the server (or `LOCAL_MODE` fallback)
  - Injects `working_directory` into every tool call

- Tools in `functions/`
  - `get_files_info(working_directory, directory=".")`: lists items with sizes
  - `get_file_content(working_directory, file_path)`: reads with max chars and truncation marker
  - `write_file_content(working_directory, file_path, content)`: creates dirs, writes file
  - `run_python_file(working_directory, file_path, args=None)`: runs with timeout=30s, captures stdout/stderr
  - All tools: normalize with `os.path.realpath` and enforce `path.startswith(workspace_root + os.sep)`

- `config.py`: system prompt, `max_iterations`, local defaults; `LOCAL_MODE` supported

- `Dockerfile`: builds a slim Python image, installs uv and git, copies code, runs Uvicorn

- `render.yaml`: Render Blueprint
  - Free tier: sets `WORKSPACES_BASE=/tmp/workspaces` (ephemeral, no disk)
  - Paid tier path: switch to `/workspaces` and add a persistent disk in the blueprint

### Agent loop
- Iterative loop using Gemini function calling:
  1) Send user prompt and system instruction with tool schemas
  2) If the model requests tools, dispatch securely and append results to messages
  3) Continue until a final answer is produced or `max_iterations` reached

### Security controls
- Path confinement using `realpath` checks for all reads/writes/exec
- Safe ZIP extraction (prevents "zip slip")
- File size and output caps
- Ignore heavy directories in listings (`.git`, `node_modules`, `.venv`, `__pycache__`)

---

## Results & Evaluation

### Local container tests (http://localhost:8090)
- Health: OK
- Upload ZIP -> `workspace_id` issued: OK
- Tree, File: OK
- Run (read): OK
- Run (write): created `calculator/new_via_api.txt`: OK
- Clone: required `git` in image; added and retested: OK
- Bad path attempts (`../etc/passwd`): blocked

### Cloudflare Tunnel tests (public temporary URL)
- Health, Upload, Tree, File, Run (read/write): all succeeded over the tunnel

### Render deployment tests (https://agents-assistant-qwcl.onrender.com)
- Health: OK
- Upload -> Tree -> File: OK
- Run (read): summarized project structure: OK
- Note: free tier uses `/tmp/workspaces` (ephemeral across restarts)

### Example calculator runs (via prompts)
- `3 + 5` -> `8`
- `10 * 2` -> `20`
- `3 + 5 * 2` -> `13` (operator precedence respected)
- `7 / 2` -> `3.5`
- `3 + a` -> error surfaced (invalid token)
- `3 +` -> model hallucinated a missing operand; configurable via prompt/policy for stricter behavior

### Performance
- Qualitative: endpoints responded promptly under light load (Render free tier)
- Streaming not enabled; responses delivered on completion
- Token usage returned by Gemini in `/v1/run` responses for transparency

---

## Presentation Quality

### Visual aids
- Architecture block diagram (above)
- Endpoint list grouped by concerns

### Time management during development (high-level timeline)
- Day 0: Extracted loop to API; added endpoints; local Dockerized run
- Day 1: Hardening (realpath, zip-slip guard), Cloudflare Tunnel tests
- Day 2: Render deployment (free tier), blueprint added and validated

---

## How to Run

### Local (Docker)
```
docker build -t agents-assistant:latest .
docker run --rm -it -p 8081:8080 \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e WORKSPACES_BASE=/workspaces \
  -v $(pwd)/workspaces:/workspaces:rw \
  agents-assistant:latest

# health
curl -sS http://localhost:8081/healthz
# upload
curl -sS -X POST http://localhost:8081/v1/workspaces/upload -F zip_file=@project.zip
```

### Render (free tier)
- Set `GEMINI_API_KEY` in service env vars
- `WORKSPACES_BASE=/tmp/workspaces` is configured in `render.yaml`
- Use the public URL for the same endpoints

---

## Next Steps
- Add SSE/WebSocket streaming for responses
- Diff preview and PR-based writes for team workflows
- Persistence layer (paid disk on Render, or object storage rehydration)
- Auth, rate limits, and audit logs for multi-user scenarios
- Optional: Cloud Run deployment with Secret Manager and GCS persistence


