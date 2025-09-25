const $ = (id) => document.getElementById(id);

function base() {
  return $("baseUrl").value.replace(/\/$/, "");
}

// Health
$("healthBtn").onclick = async () => {
  try {
    const r = await fetch(`${base()}/healthz`);
    const text = await r.text();
    $("healthBadge").textContent = r.ok ? "ok" : `err ${r.status}`;
    $("healthBadge").style.color = r.ok ? "#8fff8f" : "#ff8f8f";
  } catch (e) {
    $("healthBadge").textContent = "err";
    $("healthBadge").style.color = "#ff8f8f";
  }
};

// Upload
$("uploadBtn").onclick = async () => {
  const f = $("zipFile").files[0];
  if (!f) return alert("Choose a .zip first");
  const fd = new FormData();
  fd.append("zip_file", f);
  try {
    const r = await fetch(`${base()}/v1/workspaces/upload`, { method: "POST", body: fd });
    const j = await r.json();
    if (j.workspace_id) {
      $("ws").value = j.workspace_id;
      await refreshTree();
    }
  } catch (e) {
    console.error(e);
    alert("Upload failed: " + e);
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
    if (j.workspace_id) {
      $("ws").value = j.workspace_id;
      await refreshTree();
    }
  } catch (e) {
    console.error(e);
    alert("Clone failed: " + e);
  }
};

// Tree
async function refreshTree() {
  const ws = $("ws").value.trim();
  if (!ws) return;
  try {
    const r = await fetch(`${base()}/v1/workspaces/${ws}/tree`);
    const j = await r.json();
    renderTree(j.entries || []);
  } catch (e) {
    $("tree").textContent = String(e);
  }
}

$("treeBtn").onclick = refreshTree;

// Open file helper
async function openFile(path) {
  const ws = $("ws").value.trim();
  if (!ws || !path) return;
  try {
    const r = await fetch(`${base()}/v1/workspaces/${ws}/file?path=${encodeURIComponent(path)}`);
    const j = await r.json();
    if (j && typeof j.content === 'string') {
      renderCode(j.content);
      $("activePath").textContent = path;
    } else {
      $("fileOut").textContent = JSON.stringify(j, null, 2);
    }
  } catch (e) {
    console.error(e);
    $("fileOut").textContent = String(e);
  }
}

// Run prompt
$("runBtn").onclick = async () => {
  const ws = $("ws").value.trim();
  const prompt = $("prompt").value;
  if (!ws || !prompt) return ($("runOut").textContent = "Set workspace_id and prompt");
  addChatBubble("user", prompt);
  try {
    const r = await fetch(`${base()}/v1/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt, workspace: ws }),
    });
    const j = await r.json();
    $("runOut").textContent = JSON.stringify(j, null, 2);
    // Refresh tree in case run wrote files
    await refreshTree();
    if (j && j.final_text) addChatBubble("assistant", j.final_text);
  } catch (e) {
    $("runOut").textContent = String(e);
  }
};

// send on Ctrl/Cmd+Enter
$("prompt").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { $("runBtn").click(); }
});

// update tree when workspace id changes (blur)
$("ws").addEventListener("change", refreshTree);
$("ws").addEventListener("blur", refreshTree);

// --- Tree rendering ---
function renderTree(entries) {
  // Build a nested structure from flat paths like a/b/c.txt
  const root = {};
  for (const p of entries) {
    const parts = p.split("/");
    let node = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1 && !p.endsWith("/");
      node.children = node.children || {};
      node.children[part] = node.children[part] || { name: part, children: {} };
      if (isFile) node.children[part].file = true;
      node = node.children[part];
    }
  }
  const treeEl = $("tree");
  treeEl.innerHTML = "";
  if (!entries.length) { treeEl.textContent = "No files"; return; }
  const ul = document.createElement("ul");
  ul.style.listStyle = "none";
  ul.style.margin = 0; ul.style.paddingLeft = "6px";
  ul.style.maxHeight = "calc(100vh - 200px)";
  ul.style.overflow = "auto";
  treeEl.appendChild(ul);
  renderNode(root, ul, "");
}

function renderNode(node, parentEl, prefix) {
  if (!node.children) return;
  const names = Object.keys(node.children).sort((a,b) => {
    const A = node.children[a], B = node.children[b];
    if (!!A.file === !!B.file) return a.localeCompare(b);
    return A.file ? 1 : -1; // dirs first
  });
  for (const name of names) {
    const child = node.children[name];
    const li = document.createElement("li");
    if (child.file) {
      li.className = "file";
      li.textContent = name;
      li.onclick = () => openFile(`${prefix}${name}`);
      parentEl.appendChild(li);
    } else {
      li.className = "dir";
      li.textContent = `▸ ${name}`;
      const sub = document.createElement("ul");
      sub.style.listStyle = "none"; sub.style.margin = 0; sub.style.paddingLeft = "14px";
      let open = false;
      const toggle = () => {
        open = !open; sub.style.display = open ? "block" : "none";
        li.textContent = `${open ? "▾" : "▸"} ${name}`;
      };
      li.onclick = toggle; toggle(); // start collapsed
      parentEl.appendChild(li);
      parentEl.appendChild(sub);
      renderNode(child, sub, `${prefix}${name}/`);
    }
  }
}

function addChatBubble(role, text) {
  const c = $("chatMessages");
  const div = document.createElement("div");
  div.style.margin = "6px 0";
  div.style.whiteSpace = "pre-wrap";
  div.textContent = (role === "user" ? "You: " : "Assistant: ") + text;
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
}

// --- Code viewer helpers ---
function renderCode(text) {
  const lines = text.split(/\r?\n/);
  const gutter = $("gutter");
  const out = $("fileOut");
  gutter.innerHTML = "";
  out.textContent = text; // preserve indentation
  // line numbers
  const frag = document.createDocumentFragment();
  for (let i = 0; i < lines.length; i++) {
    const d = document.createElement("div");
    d.textContent = String(i + 1);
    frag.appendChild(d);
  }
  gutter.appendChild(frag);
}


