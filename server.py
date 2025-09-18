from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional
import os
import io
import uuid
import zipfile
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types

import config as cfg
from call_funtion import call_function, available_functions

WORKSPACES_BASE = os.getenv("WORKSPACES_BASE", "/workspaces")
os.makedirs(WORKSPACES_BASE, exist_ok=True)

IGNORE_DIRS = {".git", "node_modules", ".venv", "__pycache__"}
MAX_ENTRIES = 2000

class RunRequest(BaseModel):
    prompt: str
    workspace: Optional[str] = None
    verbose: bool = False
    max_iterations: Optional[int] = None

class CloneRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = "main"

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/v1/workspaces/upload")
async def upload_ws(zip_file: UploadFile = File(...)):
    if not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Must be a .zip")
    ws_id = str(uuid.uuid4())
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    os.makedirs(ws_root, exist_ok=True)

    data = await zip_file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            base_real = os.path.realpath(ws_root)
            for member in z.infolist():
                target = os.path.realpath(os.path.join(ws_root, member.filename))
                if not target.startswith(base_real + os.sep):
                    raise HTTPException(400, "Invalid entry in ZIP")
                if member.is_dir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
    except zipfile.BadZipFile:
        raise HTTPException(400, "Corrupt or invalid ZIP")

    return {"workspace_id": ws_id}

@app.post("/v1/workspaces/clone")
def clone_ws(body: CloneRequest):
    ws_id = str(uuid.uuid4())
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    os.makedirs(ws_root, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", body.branch, body.repo_url, ws_root],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(400, f"Git clone failed: {e.stderr.strip() or e.stdout.strip()}")
    except Exception as e:
        raise HTTPException(500, f"Clone error: {e}")
    return {"workspace_id": ws_id}

@app.get("/v1/workspaces/{ws_id}/tree")
def tree(ws_id: str, max_entries: int = MAX_ENTRIES):
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    base_real = os.path.realpath(ws_root)
    if not os.path.isdir(base_real):
        raise HTTPException(404, "Workspace not found")
    entries = []
    for root, dirs, files in os.walk(base_real):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_root = os.path.relpath(root, base_real)
        for name in sorted(files):
            rel = os.path.normpath(os.path.join(rel_root, name)) if rel_root != "." else name
            if rel.startswith(".."):
                continue
            entries.append(rel)
            if len(entries) >= max_entries:
                return {"entries": entries, "truncated": True}
    return {"entries": entries, "truncated": False}

@app.get("/v1/workspaces/{ws_id}/file")
def read_file(ws_id: str, path: str = Query(...)):
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    base_real = os.path.realpath(ws_root)
    if not os.path.isdir(base_real):
        raise HTTPException(404, "Workspace not found")
    abs_path = os.path.realpath(os.path.join(base_real, path))
    if not abs_path.startswith(base_real + os.sep):
        raise HTTPException(400, "Bad path")
    if not os.path.isfile(abs_path):
        raise HTTPException(404, "Not found")
    with open(abs_path, "rb") as f:
        data = f.read(2_000_000)
    try:
        return {"path": path, "content": data.decode("utf-8")}
    except UnicodeDecodeError:
        raise HTTPException(415, "Binary file not supported")

@app.post("/v1/run")
def run(req: RunRequest):
    if not req.workspace:
        raise HTTPException(400, "workspace is required")

    base_real = os.path.realpath(WORKSPACES_BASE)
    candidate = os.path.realpath(os.path.join(WORKSPACES_BASE, req.workspace))
    if not candidate.startswith(base_real + os.sep):
        raise HTTPException(400, "Invalid workspace path")
    os.makedirs(candidate, exist_ok=True)
    workspace_root = candidate

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(500, "GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=cfg.system_prompt,
        tools=[available_functions],
        candidate_count=1,
    )
    messages = [types.Content(role="user", parts=[types.Part(text=req.prompt)])]
    iters = req.max_iterations or cfg.max_iterations

    for _ in range(iters):
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=messages,
            config=config,
        )
        if not resp or not resp.candidates:
            raise HTTPException(500, "Empty response")

        candidate_msg = resp.candidates[0]
        messages.append(candidate_msg.content)

        if resp.function_calls:
            tool_parts = []
            for fc in resp.function_calls:
                tool_result = call_function(fc, req.verbose, workspace_root)
                tool_parts.extend(tool_result.parts)
            messages.append(types.Content(role="tool", parts=tool_parts))
            continue

        usage = resp.usage_metadata
        return {
            "final_text": resp.text,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "response_tokens": getattr(usage, "candidates_token_count", None),
            },
        }

    raise HTTPException(408, "Max iterations reached without final answer")