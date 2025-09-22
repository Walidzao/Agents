const $ = (id) => document.getElementById(id);

function base() {
  return $("baseUrl").value.replace(/\/$/, "");
}

// Health
$("healthBtn").onclick = async () => {
  try {
    const r = await fetch(`${base()}/healthz`);
    $("healthOut").textContent = `${r.status} ${await r.text()}`;
  } catch (e) {
    $("healthOut").textContent = String(e);
  }
};

// Upload
$("uploadBtn").onclick = async () => {
  const f = $("zipFile").files[0];
  if (!f) return ($("uploadOut").textContent = "Choose a .zip first");
  const fd = new FormData();
  fd.append("zip_file", f);
  try {
    const r = await fetch(`${base()}/v1/workspaces/upload`, { method: "POST", body: fd });
    const j = await r.json();
    $("uploadOut").textContent = JSON.stringify(j, null, 2);
    if (j.workspace_id) $("ws").value = j.workspace_id;
  } catch (e) {
    $("uploadOut").textContent = String(e);
  }
};

// Clone
$("cloneBtn").onclick = async () => {
  const repo = $("repoUrl").value.trim();
  const branch = $("branch").value.trim() || "main";
  if (!repo) return ($("cloneOut").textContent = "Enter repo URL");
  try {
    const r = await fetch(`${base()}/v1/workspaces/clone`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ repo_url: repo, branch }),
    });
    const j = await r.json();
    $("cloneOut").textContent = JSON.stringify(j, null, 2);
    if (j.workspace_id) $("ws").value = j.workspace_id;
  } catch (e) {
    $("cloneOut").textContent = String(e);
  }
};

// Tree
$("treeBtn").onclick = async () => {
  const ws = $("ws").value.trim();
  if (!ws) return ($("treeOut").textContent = "Set workspace_id first");
  try {
    const r = await fetch(`${base()}/v1/workspaces/${ws}/tree`);
    const j = await r.json();
    $("treeOut").textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    $("treeOut").textContent = String(e);
  }
};

// Read file
$("fileBtn").onclick = async () => {
  const ws = $("ws").value.trim();
  const path = $("filePath").value.trim();
  if (!ws || !path) return ($("fileOut").textContent = "Set workspace_id and path");
  try {
    const r = await fetch(`${base()}/v1/workspaces/${ws}/file?path=${encodeURIComponent(path)}`);
    const j = await r.json();
    // Show raw content area when available, preserving indentation
    if (j && typeof j.content === 'string') {
      $("fileOut").textContent = j.content;
    } else {
      $("fileOut").textContent = JSON.stringify(j, null, 2);
    }
  } catch (e) {
    $("fileOut").textContent = String(e);
  }
};

// Run prompt
$("runBtn").onclick = async () => {
  const ws = $("ws").value.trim();
  const prompt = $("prompt").value;
  if (!ws || !prompt) return ($("runOut").textContent = "Set workspace_id and prompt");
  try {
    const r = await fetch(`${base()}/v1/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt, workspace: ws }),
    });
    const j = await r.json();
    $("runOut").textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    $("runOut").textContent = String(e);
  }
};


