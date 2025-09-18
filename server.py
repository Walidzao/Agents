from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

import config as cfg
from call_funtion import call_function, available_functions

# Parameterize the base path
WORKSPACES_BASE = "/workspaces"
os.makedirs(WORKSPACES_BASE, exist_ok=True)

class RunRequest(BaseModel):
    prompt: str
    workspace: Optional[str] = None
    verbose: bool = False
    max_iterations: Optional[int] = None

app = FastAPI()

@app.post("/v1/run")
def run(req: RunRequest):
    # Set up workspace directory
    workspace_root = WORKSPACES_BASE
    if not req.workspace:
        raise HTTPException(400, "workspace is required")  # or create a default per-session workspace

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

        candidate = resp.candidates[0]
        messages.append(candidate.content)

        if resp.function_calls:
            tool_parts = []
            for fc in resp.function_calls:
                tool_result = call_function(fc, req.verbose, workspace_root)
                tool_parts.extend(tool_result.parts)
            messages.append(types.Content(role="tool", parts=tool_parts))
            continue

        return {"final_text": resp.text, "usage": {
            "prompt_tokens": resp.usage_metadata.prompt_token_count,
            "response_tokens": resp.usage_metadata.candidates_token_count,
        }}

    raise HTTPException(408, "Max iterations reached without final answer")