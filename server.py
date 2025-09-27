from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import os
import io
import uuid
import zipfile
import subprocess
import json
import tempfile
import requests
import re
from datetime import datetime
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

# Enable CORS for browser-based UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the simple web UI from the same origin to avoid CORS entirely
try:
    app.mount("/ui", StaticFiles(directory="web", html=True), name="ui")
except Exception:
    # If the directory is missing locally, skip mounting; in container it exists
    pass

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
    if not candidate.startswith(base_real):
        raise HTTPException(400, "Invalid workspace path")
    if not os.path.isdir(candidate):
        raise HTTPException(404, "Workspace not found; upload or clone first")
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

@app.get("/v1/workspaces/{ws_id}/git/status")
def git_status(ws_id: str):
    """Get git status for modified/added/deleted files"""
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    base_real = os.path.realpath(ws_root)
    if not os.path.isdir(base_real):
        raise HTTPException(404, "Workspace not found")
    
    # Check if it's a git repo
    if not os.path.isdir(os.path.join(base_real, ".git")):
        return {"is_git": False, "files": {}}
    
    try:
        # Get git status in porcelain format
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=base_real,
            capture_output=True,
            text=True,
            check=True
        )
        
        files = {}
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            # Format: XY filename
            # X = index status, Y = working tree status
            status_code = line[:2]
            filename = line[3:].strip()  # Remove any trailing whitespace
            
            # Map git status codes to simple status
            if status_code == "??":
                status = "untracked"
            elif status_code.startswith("A"):
                status = "added"
            elif status_code.startswith("M") or " M" in status_code:
                status = "modified"
            elif status_code.startswith("D"):
                status = "deleted"
            elif status_code.startswith("R"):
                status = "renamed"
            else:
                status = "unknown"
            
            files[filename] = status
        
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=base_real,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get remote URL
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=base_real,
            capture_output=True,
            text=True
        )
        
        return {
            "is_git": True,
            "branch": branch_result.stdout.strip(),
            "remote": remote_result.stdout.strip() if remote_result.returncode == 0 else None,
            "files": files
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Git command failed: {e.stderr}")

@app.get("/v1/workspaces/{ws_id}/git/diff")
def git_diff(ws_id: str, path: Optional[str] = None):
    """Get git diff for a specific file or all files"""
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    base_real = os.path.realpath(ws_root)
    if not os.path.isdir(base_real):
        raise HTTPException(404, "Workspace not found")
    
    if not os.path.isdir(os.path.join(base_real, ".git")):
        raise HTTPException(400, "Not a git repository")
    
    try:
        if path:
            # Validate path
            abs_path = os.path.realpath(os.path.join(base_real, path))
            if not abs_path.startswith(base_real + os.sep):
                raise HTTPException(400, "Invalid path")
            
            # Handle directory paths - directories cannot have individual diffs
            if os.path.isdir(abs_path):
                return {
                    "diff": f"# Directory: {path}\n# Use git diff without path parameter to see all changes in this directory",
                    "path": path,
                    "is_directory": True
                }
            
            # Check if file is untracked
            status_result = subprocess.run(
                ["git", "status", "--porcelain", path],
                cwd=base_real,
                capture_output=True,
                text=True,
                check=True
            )
            
            if status_result.stdout.startswith("??"):
                # Untracked file - show entire content as added
                try:
                    with open(abs_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    lines = content.split('\n')
                    diff_lines = [f"diff --git a/{path} b/{path}",
                                "new file mode 100644",
                                "index 0000000..0000000",
                                "--- /dev/null",
                                f"+++ b/{path}",
                                "@@ -0,0 +1," + str(len(lines)) + " @@"]
                    diff_lines.extend([f"+{line}" for line in lines])
                    return {
                        "diff": "\n".join(diff_lines),
                        "path": path
                    }
                except UnicodeDecodeError:
                    return {
                        "diff": f"diff --git a/{path} b/{path}\nnew file mode 100644\nBinary file (not shown)",
                        "path": path
                    }
        
        cmd = ["git", "diff", "--no-color"]
        if path:
            cmd.append(path)
        
        result = subprocess.run(
            cmd,
            cwd=base_real,
            capture_output=True,
            text=True,
            check=True
        )
        
        return {
            "diff": result.stdout,
            "path": path
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Git diff failed: {e.stderr}")

@app.post("/v1/workspaces/{ws_id}/download")
def download_workspace(ws_id: str, format: str = Query("zip", regex="^(zip|diff)$")):
    """Download workspace as ZIP or git diff"""
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    base_real = os.path.realpath(ws_root)
    if not os.path.isdir(base_real):
        raise HTTPException(404, "Workspace not found")
    
    if format == "diff":
        # Generate git diff
        if not os.path.isdir(os.path.join(base_real, ".git")):
            raise HTTPException(400, "Not a git repository")
        
        try:
            result = subprocess.run(
                ["git", "diff", "--no-color"],
                cwd=base_real,
                capture_output=True,
                text=True,
                check=True
            )
            
            return StreamingResponse(
                io.BytesIO(result.stdout.encode()),
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename=workspace_{ws_id}.diff"
                }
            )
            
        except subprocess.CalledProcessError as e:
            raise HTTPException(500, f"Git diff failed: {e.stderr}")
    
    else:  # format == "zip"
        # Create ZIP file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(base_real):
                # Skip ignored directories
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, base_real)
                    zipf.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=workspace_{ws_id}.zip"
            }
        )

class GitPushRequest(BaseModel):
    message: str
    branch: Optional[str] = None
    create_pr: bool = True  # Default to creating PR
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None

def create_github_pr(repo_owner, repo_name, head_branch, base_branch, title, body, github_token):
    """Create a GitHub Pull Request using the GitHub API"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    data = {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "body": body,
        "maintainer_can_modify": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 201:
            pr_data = response.json()
            return {
                "success": True,
                "pr_url": pr_data["html_url"],
                "pr_number": pr_data["number"]
            }
        elif response.status_code == 422:
            # PR might already exist
            error_data = response.json()
            if "pull request already exists" in error_data.get("message", "").lower():
                # Try to find existing PR
                existing_prs_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls?head={repo_owner}:{head_branch}&base={base_branch}"
                existing_response = requests.get(existing_prs_url, headers=headers, timeout=30)
                if existing_response.status_code == 200:
                    prs = existing_response.json()
                    if prs:
                        return {
                            "success": True,
                            "pr_url": prs[0]["html_url"],
                            "pr_number": prs[0]["number"],
                            "existing": True
                        }
            return {
                "success": False,
                "error": f"GitHub API error: {error_data.get('message', 'Unknown error')}"
            }
        else:
            return {
                "success": False,
                "error": f"GitHub API error: {response.status_code} {response.text}"
            }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Network error: {str(e)}"
        }

def parse_github_url(remote_url):
    """Parse GitHub remote URL to extract owner and repo name"""
    # Handle both HTTPS and SSH formats
    patterns = [
        r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$"
    ]
    
    for pattern in patterns:
        match = re.match(pattern, remote_url.strip())
        if match:
            return match.group(1), match.group(2)
    
    return None, None

@app.post("/v1/workspaces/{ws_id}/git/push")
def git_push(ws_id: str, body: GitPushRequest):
    """Commit and push changes, optionally create PR"""
    ws_root = os.path.join(WORKSPACES_BASE, ws_id)
    base_real = os.path.realpath(ws_root)
    if not os.path.isdir(base_real):
        raise HTTPException(404, "Workspace not found")
    
    if not os.path.isdir(os.path.join(base_real, ".git")):
        raise HTTPException(400, "Not a git repository")
    
    try:
        # Configure git user (required for commits)
        subprocess.run(["git", "config", "user.email", "agent@example.com"], cwd=base_real, check=True)
        subprocess.run(["git", "config", "user.name", "AI Agent"], cwd=base_real, check=True)
        
        # Configure authentication for GitHub if token is available
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            # Get remote URL to modify it with token
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=base_real,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = remote_result.stdout.strip()
            
            # Convert HTTPS URL to include token
            if remote_url.startswith("https://github.com/"):
                auth_url = remote_url.replace("https://github.com/", f"https://token:{github_token}@github.com/")
                subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=base_real, check=True)
            elif remote_url.startswith("git@github.com:"):
                # Convert SSH to HTTPS with token
                repo_path = remote_url.replace("git@github.com:", "")
                auth_url = f"https://token:{github_token}@github.com/{repo_path}"
                subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=base_real, check=True)
        
        # Add all changes
        add_result = subprocess.run(["git", "add", "-A"], cwd=base_real, capture_output=True, text=True)
        if add_result.returncode != 0:
            raise HTTPException(500, f"Git add failed: {add_result.stderr}")
        
        # Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=base_real,
            capture_output=True,
            text=True,
            check=True
        )
        
        if not status_result.stdout.strip():
            return {"status": "no_changes", "message": "No changes to commit"}
        
        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", body.message],
            cwd=base_real,
            capture_output=True,
            text=True
        )
        
        if commit_result.returncode != 0:
            return {
                "status": "commit_failed", 
                "message": f"Commit failed: {commit_result.stderr}",
                "stdout": commit_result.stdout
            }
        
        # Get current branch
        current_branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=base_real,
            capture_output=True,
            text=True,
            check=True
        )
        current_branch = current_branch_result.stdout.strip()
        
        # Always create a new branch for changes to avoid conflicts
        new_branch = body.branch or f"agent-changes-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create and switch to new branch
        checkout_result = subprocess.run(
            ["git", "checkout", "-b", new_branch],
            cwd=base_real,
            capture_output=True,
            text=True
        )
        
        if checkout_result.returncode != 0:
            # If branch already exists, switch to it
            subprocess.run(
                ["git", "checkout", new_branch],
                cwd=base_real,
                capture_output=True,
                text=True,
                check=True
            )
        
        # Push to new branch
        push_result = subprocess.run(
            ["git", "push", "origin", new_branch],
            cwd=base_real,
            capture_output=True,
            text=True
        )
        
        if push_result.returncode != 0:
            return {
                "status": "push_failed",
                "message": f"Push failed: {push_result.stderr}",
                "branch": new_branch,
                "stdout": push_result.stdout
            }
        
        # Restore original remote URL if we modified it
        if github_token and 'remote_url' in locals():
            try:
                subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=base_real, check=True)
            except subprocess.CalledProcessError:
                pass  # Don't fail the whole operation if we can't restore the URL
        
        # Get remote URL and create PR if requested
        final_remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=base_real,
            capture_output=True,
            text=True
        )
        
        pr_url = None
        pr_number = None
        pr_created = False
        
        if final_remote_result.returncode == 0:
            final_remote_url = final_remote_result.stdout.strip()
            repo_owner, repo_name = parse_github_url(final_remote_url)
            
            if repo_owner and repo_name and body.create_pr:
                # Try to create PR using GitHub API
                github_token = os.getenv("GITHUB_TOKEN")
                if github_token:
                    pr_title = body.pr_title or f"AI Agent Changes: {body.message}"
                    pr_body_text = body.pr_body or f"""
## AI Agent Generated Changes

**Commit Message:** {body.message}

**Branch:** `{new_branch}`

This PR was automatically created by the AI Agent after making code changes.

### Changes Made:
- {body.message}

Please review the changes and merge if appropriate.
                    """.strip()
                    
                    pr_result = create_github_pr(
                        repo_owner, repo_name, new_branch, current_branch,
                        pr_title, pr_body_text, github_token
                    )
                    
                    if pr_result["success"]:
                        pr_url = pr_result["pr_url"]
                        pr_number = pr_result["pr_number"]
                        pr_created = True
                        if pr_result.get("existing"):
                            pr_created = "existing"
                else:
                    # No GitHub token, generate manual PR URL
                    manual_url = final_remote_url
                    if manual_url.endswith('.git'):
                        manual_url = manual_url[:-4]
                    if manual_url.startswith('git@github.com:'):
                        manual_url = manual_url.replace('git@github.com:', 'https://github.com/')
                    pr_url = f"{manual_url}/compare/{current_branch}...{new_branch}?expand=1"
        
        return {
            "status": "pushed_to_branch",
            "branch": new_branch,
            "message": f"Successfully pushed changes to new branch '{new_branch}'",
            "pr_url": pr_url,
            "pr_number": pr_number,
            "pr_created": pr_created,
            "pr_instructions": "Click the PR URL to review and merge" if pr_url else f"Create a PR from '{new_branch}' to '{current_branch}'"
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "message": f"Git operation failed: {str(e)}",
            "stderr": getattr(e, 'stderr', ''),
            "stdout": getattr(e, 'stdout', '')
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }