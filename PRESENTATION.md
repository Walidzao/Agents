## Title: Agentic Code Assistant - From Local Loop to Web Deployment

### Slide 1 — Problem & Goal
- **Problem**: Run a code assistant that can safely explore/read/write/run files and expose it on the web.
- **Goal**: Turn a local Gemini tool-calling loop into a secure web service with workspaces (upload/clone), file browsing, and prompt execution.

### Slide 2 — Solution Overview
- **API**: FastAPI endpoints for upload/clone/tree/file/run
- **Agent**: Gemini function-calling loop + tool dispatcher
- **Tools**: get files, read file, write file, run python (workspace confined)
- **Deploy**: Docker; share via Cloudflare Tunnel; stable prod on Render

### Slide 3 — Project Structure (key files)
- `server.py`: API (`/v1/workspaces/*`, `/v1/run`, `/healthz`)
- `call_funtion.py`: tool registry/dispatcher (`workspace_root` aware)
- `functions/`: file ops + run python (realpath checks)
- `config.py`: system prompt, max iterations, LOCAL_MODE
- `Dockerfile`: slim image, uv + git
- `render.yaml`: Render blueprint (free tier: `/tmp/workspaces`)

### Slide 4 — Technical Architecture
- Client → FastAPI → Gemini loop → Tools → Workspace
- Workspace base: `/workspaces` (local/disk) or `/tmp/workspaces` (serverless)
- Security: realpath confinement, zip-slip guard, size/time limits, ignores

### Slide 5 — Endpoints
- `POST /v1/workspaces/upload` (zip → `workspace_id`)
- `POST /v1/workspaces/clone` (git → `workspace_id`)
- `GET /v1/workspaces/{id}/tree` (with ignores, cap)
- `GET /v1/workspaces/{id}/file?path=...` (UTF-8, size cap)
- `POST /v1/run` (prompt + workspace → tool loop)
- `GET /healthz`

### Slide 6 — Implementation Highlights
- Tool schema passed to Gemini; model requests tool invocations
- Dispatcher injects `working_directory` per call
- `run_python_file`: timeout=30, captures stdout/stderr, cwd=workspace
- All paths normalized via `realpath` then prefix-checked

### Slide 7 — Testing Results (Local & Tunnel)
- Health, Upload, Tree, File: OK
- Run (read/write): OK; created/verified files
- Clone: OK after adding git to image
- Security: `../` traversal blocked

### Slide 8 — Render Deployment (Free Tier)
- URL: example `https://agents-assistant-<id>.onrender.com`
- Works: health, upload, tree, file, run
- Free tier: `/tmp/workspaces` (ephemeral). For persistence: paid disk or object storage

### Slide 9 — Calculator Demo
- `3 + 5 = 8`, `10 * 2 = 20`, `3 + 5 * 2 = 13`, `7 / 2 = 3.5`
- Invalid token error surfaced; missing operand edge-case (prompt policy)

### Slide 10 — Performance & Ops
- Non-streaming responses; token usage returned
- Render free tier suitable for MVP; scale via paid plan or Cloud Run
- Logs/metrics via platform; add tracing later if needed

### Slide 11 — Next Steps
- SSE/WebSockets for streaming
- Diff preview + PR-based writes
- Auth, rate limits, audit logs
- Persistence via disk or object storage rehydration
- Optional: Cloud Run + Secret Manager + GCS

### Slide 12 — Takeaways
- Local agent → secure web service with minimal changes
- Workspace isolation is the core safety primitive
- Multiple deployment paths: tunnel for demo, Render for stable URL
