// Utility functions
const $ = (id) => document.getElementById(id);
const $$ = (selector) => document.querySelectorAll(selector);

// State management
const state = {
  workspace: '',
  currentFile: null,
  selectedTreeItem: null,
  treeData: null,
  chatHistory: [],
  isStreaming: false,
  monacoLoaded: false,
  editor: null,
  gitStatus: null,
  viewMode: 'code', // 'code' or 'diff'
  currentDiff: null,
  isWelcomeScreen: true
};

// Configuration
const config = {
  debounceDelay: 300,
  maxPromptHeight: 120,
  monacoTheme: {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '64748b' },
      { token: 'string', foreground: '10b981' },
      { token: 'keyword', foreground: '5e9eff' },
      { token: 'number', foreground: 'f59e0b' },
      { token: 'type', foreground: '5e9eff' },
      { token: 'function', foreground: 'e8eaed' }
    ],
    colors: {
      'editor.background': '#0a0e1a',
      'editor.foreground': '#e8eaed',
      'editor.lineHighlightBackground': '#111930',
      'editor.selectionBackground': '#1f2a4a',
      'editorLineNumber.foreground': '#64748b',
      'editorCursor.foreground': '#5e9eff',
      'editor.inactiveSelectionBackground': '#1a2340'
    }
  }
};

// API helpers
function base() {
  return $("baseUrl").value.replace(/\/$/, "");
}

async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`${base()}${endpoint}`, options);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    return response;
  } catch (error) {
    showToast(`Network error: ${error.message}`, 'error');
    throw error;
  }
}

// Toast notifications
function showToast(message, type = 'info') {
  const toast = $('toast');
  toast.textContent = message;
  toast.className = `toast show ${type}`;
  
  setTimeout(() => {
    toast.classList.remove('show');
  }, 5000);
}

// Debounce utility
function debounce(func, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

// UI Screen Management
function showWelcomeScreen() {
  state.isWelcomeScreen = true;
  $('welcomeScreen').classList.remove('hidden');
  $('mainApp').classList.add('hidden');
}

function showMainApp() {
  state.isWelcomeScreen = false;
  $('welcomeScreen').classList.add('hidden');
  $('mainApp').classList.remove('hidden');
  
  // Update workspace info in header
  if (state.workspace) {
    $('workspaceInfo').textContent = `Workspace: ${state.workspace}`;
  }
}

// Dropdown functionality
function toggleDropdown(dropdownId) {
  const dropdown = $(dropdownId);
  const isVisible = !dropdown.classList.contains('hidden');
  
  // Hide all dropdowns first
  $$('.dropdown-menu').forEach(menu => menu.classList.add('hidden'));
  
  // Toggle the requested dropdown
  if (!isVisible) {
    dropdown.classList.remove('hidden');
  }
}

function hideAllDropdowns() {
  $$('.dropdown-menu').forEach(menu => menu.classList.add('hidden'));
}

// Enhanced workspace loading
async function loadWorkspace(workspaceId) {
  if (!workspaceId) return;
  
  state.workspace = workspaceId;
  localStorage.setItem('workspace', workspaceId);
  
  showMainApp();
  await refreshTree();
  showToast('Workspace loaded successfully', 'success');
}

// Git operations
async function fetchGitStatus() {
  if (!state.workspace) return;
  
  try {
    console.log('Fetching git status for workspace:', state.workspace);
    const response = await fetch(`${base()}/v1/workspaces/${state.workspace}/git/status`);
    
    if (!response.ok) {
      if (response.status === 404) {
        console.log('Git status endpoint not found - feature not deployed yet');
        return null;
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('Git status response:', data);
    state.gitStatus = data;
    
    if (data.is_git) {
      $('gitToolbar').classList.remove('hidden');
      $('gitBranch').textContent = data.branch || 'main';
      $('downloadDiffBtn').classList.remove('hidden');
      
      // Update file status markers in tree
      updateFileStatusMarkers(data.files);
      console.log('Updated file status markers for', Object.keys(data.files || {}).length, 'files');
    } else {
      $('gitToolbar').classList.add('hidden');
      $('downloadDiffBtn').classList.add('hidden');
      console.log('Workspace is not a git repository');
    }
    
    return data;
  } catch (error) {
    console.error('Git status error:', error);
    // Hide git features if endpoint is not available
    $('gitToolbar').classList.add('hidden');
    $('downloadDiffBtn').classList.add('hidden');
    return null;
  }
}

function updateFileStatusMarkers(fileStatuses) {
  // Clear existing markers
  $$('.file-status, .dir-status').forEach(el => el.remove());
  $$('.file, .dir').forEach(el => {
    el.classList.remove('modified', 'added', 'deleted', 'untracked');
  });
  
  if (!fileStatuses || Object.keys(fileStatuses).length === 0) {
    // Hide changes tab if no changes
    $('changesTab').classList.add('hidden');
    return;
  }
  
  // Show changes tab if there are changes
  $('changesTab').classList.remove('hidden');
  
  console.log('Updating file status markers for:', fileStatuses);
  
  // Add status markers to files
  Object.entries(fileStatuses).forEach(([path, status]) => {
    // Find the file element by data-path attribute
    let fileEl = document.querySelector(`[data-path="${path}"]`);
    
    // If not found, try to find by filename (fallback for path issues)
    if (!fileEl) {
      const filename = path.split('/').pop();
      const allFiles = Array.from($$('.file'));
      fileEl = allFiles.find(el => el.textContent.trim() === filename);
      if (fileEl) {
        console.log(`Found file by filename fallback: ${filename}`);
        // Update the data-path to correct value
        fileEl.dataset.path = path;
      }
    }
    
    console.log(`Looking for file with path "${path}":`, fileEl);
    
    if (fileEl) {
      // Add status class
      fileEl.classList.add(status);
      
      // Add status marker
      const existingMarker = fileEl.querySelector('.file-status');
      if (!existingMarker) {
        const marker = document.createElement('span');
        marker.className = 'file-status';
        marker.textContent = getStatusMarker(status);
        marker.title = `${status.charAt(0).toUpperCase() + status.slice(1)}: ${path}`;
        marker.style.marginRight = '4px';
        marker.style.fontWeight = 'bold';
        fileEl.insertBefore(marker, fileEl.firstChild);
        console.log(`Added ${status} marker to ${path}`);
      }
    } else {
      console.warn(`Could not find file element for path: ${path}. Available files:`, 
        Array.from($$('.file')).map(el => ({ path: el.dataset.path, text: el.textContent.trim() })));
    }
    
    // Mark parent directories as having changes
    const parts = path.split('/');
    for (let i = parts.length - 1; i > 0; i--) {
      const dirName = parts[i - 1];
      // Find directory elements that match this part of the path
      const dirEls = Array.from($$('.dir')).filter(el => {
        const span = el.querySelector('span');
        return span && span.textContent.includes(dirName);
      });
      
      dirEls.forEach(dirEl => {
        if (!dirEl.classList.contains('has-changes')) {
          dirEl.classList.add('has-changes');
          const existingMarker = dirEl.querySelector('.dir-status');
          if (!existingMarker) {
            const marker = document.createElement('span');
            marker.className = 'dir-status';
            marker.textContent = '•';
            marker.title = 'Contains modified files';
            dirEl.insertBefore(marker, dirEl.firstChild);
          }
        }
      });
    }
  });
  
  // Render changes tree
  renderChangesTree(fileStatuses);
}

function getStatusMarker(status) {
  switch (status) {
    case 'modified': return 'M';
    case 'added': return 'A';
    case 'deleted': return 'D';
    case 'untracked': return 'U';
    case 'renamed': return 'R';
    default: return '?';
  }
}

function renderChangesTree(fileStatuses) {
  const changesTreeEl = $('changesTree');
  changesTreeEl.innerHTML = '';
  
  if (!fileStatuses || Object.keys(fileStatuses).length === 0) {
    changesTreeEl.innerHTML = '<div style="padding: 8px; color: var(--text-tertiary);">No changes</div>';
    return;
  }
  
  const ul = document.createElement('ul');
  ul.setAttribute('role', 'group');
  ul.style.listStyle = 'none';
  ul.style.margin = '0';
  ul.style.padding = '0';
  
  Object.entries(fileStatuses).forEach(([path, status]) => {
    const li = document.createElement('li');
    li.className = `file ${status}`;
    li.dataset.path = path;
    li.tabIndex = 0;
    li.setAttribute('role', 'treeitem');
    
    // Create status marker
    const marker = document.createElement('span');
    marker.className = 'file-status';
    marker.textContent = getStatusMarker(status);
    marker.title = `${status.charAt(0).toUpperCase() + status.slice(1)}`;
    
    // Create filename
    const filename = path.split('/').pop();
    const textNode = document.createTextNode(` ${filename}`);
    
    // Create path info
    const pathInfo = document.createElement('div');
    pathInfo.style.fontSize = '11px';
    pathInfo.style.color = 'var(--text-tertiary)';
    pathInfo.style.marginLeft = '20px';
    pathInfo.textContent = path;
    
    li.appendChild(marker);
    li.appendChild(textNode);
    li.appendChild(pathInfo);
    
    // Add click handler
    li.addEventListener('click', () => openFile(path));
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openFile(path);
      }
    });
    
    ul.appendChild(li);
  });
  
  changesTreeEl.appendChild(ul);
}

function switchTreeTab(tabName) {
  // Update tab buttons
  $('filesTab').classList.toggle('active', tabName === 'files');
  $('changesTab').classList.toggle('active', tabName === 'changes');
  
  // Update tree visibility
  $('tree').classList.toggle('hidden', tabName !== 'files');
  $('changesTree').classList.toggle('hidden', tabName !== 'changes');
}

async function fetchDiff(path = null) {
  if (!state.workspace) return null;
  
  try {
    const url = path 
      ? `/v1/workspaces/${state.workspace}/git/diff?path=${encodeURIComponent(path)}`
      : `/v1/workspaces/${state.workspace}/git/diff`;
    
    const response = await apiCall(url);
    const data = await response.json();
    
    // Handle directory responses
    if (data.is_directory) {
      return {
        diff: data.diff,
        isDirectory: true
      };
    }
    
    return data.diff;
  } catch (error) {
    console.error('Diff error:', error);
    return null;
  }
}

function parseDiff(diffText) {
  const lines = diffText.split('\n');
  const parsed = [];
  let currentFile = null;
  let lineNumOld = 0;
  let lineNumNew = 0;
  
  lines.forEach(line => {
    if (line.startsWith('diff --git')) {
      // File header - show clean filename
      const match = line.match(/b\/(.+)$/);
      if (match) {
        currentFile = match[1];
        parsed.push({ 
          type: 'file-header', 
          content: `📄 ${currentFile}`, 
          file: currentFile 
        });
      }
    } else if (line.startsWith('@@')) {
      // Hunk header - extract line numbers but show cleaner separator
      const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/);
      if (match) {
        lineNumOld = parseInt(match[1]);
        lineNumNew = parseInt(match[2]);
      }
      // Add visual separator instead of cryptic @@ line
      if (parsed.length > 1) { // Only add separator if not the first hunk
        parsed.push({ 
          type: 'separator', 
          content: '⋯', 
          lineNum: null 
        });
      }
    } else if (line.startsWith('+') && !line.startsWith('+++')) {
      // Added line - clean display
      parsed.push({ 
        type: 'add', 
        content: line.substring(1), 
        lineNum: lineNumNew++,
        prefix: '+'
      });
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      // Removed line - clean display
      parsed.push({ 
        type: 'remove', 
        content: line.substring(1), 
        lineNum: lineNumOld++,
        prefix: '-'
      });
    } else if (line.startsWith(' ')) {
      // Context line - only show for actual changes
      parsed.push({ 
        type: 'context', 
        content: line.substring(1), 
        lineNumOld: lineNumOld++,
        lineNumNew: lineNumNew++,
        prefix: ' '
      });
    }
    // Skip other headers like '+++', '---', 'index', 'new file mode', etc.
  });
  
  return parsed;
}

function renderDiff(diffText) {
  const diffViewer = $('diffViewer');
  const parsedDiff = parseDiff(diffText);
  
  diffViewer.innerHTML = parsedDiff.map(line => {
    const classes = ['diff-line', line.type].join(' ');
    const lineNum = line.lineNum || line.lineNumNew || '';
    
    // Special handling for different line types
    if (line.type === 'file-header') {
      return `<div class="${classes}">${escapeHtml(line.content)}</div>`;
    } else if (line.type === 'separator') {
      return `<div class="${classes}">${line.content}</div>`;
    } else {
      // For add/remove/context lines, show line numbers and content
      const lineNumDisplay = lineNum ? `${lineNum}`.padStart(4, ' ') : '';
      return `<div class="${classes}" data-line-number="${lineNum}">
        <span class="line-number">${lineNumDisplay}</span>
        <span class="line-content">${escapeHtml(line.content)}</span>
      </div>`;
    }
  }).join('');
}

function renderDirectoryDiff(diffText) {
  const diffViewer = $('diffViewer');
  diffViewer.innerHTML = `
    <div class="directory-diff">
      <div class="directory-info">
        <h3>📁 Directory Diff</h3>
        <p style="color: var(--text-secondary); margin: var(--space-md) 0;">
          ${escapeHtml(diffText).replace(/\n/g, '<br>')}
        </p>
        <button onclick="setViewMode('diff'); openFile('')" class="view-all-changes" 
                style="background: var(--button-primary); color: white; border: none; padding: var(--space-sm) var(--space-md); border-radius: 4px; cursor: pointer;">
          View All Changes
        </button>
      </div>
    </div>
  `;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Download operations
async function downloadWorkspace(format = 'zip') {
  if (!state.workspace) {
    showToast('No workspace selected', 'warning');
    return;
  }
  
  try {
    console.log(`Attempting to download workspace as ${format}`);
    const response = await fetch(`${base()}/v1/workspaces/${state.workspace}/download?format=${format}`, {
      method: 'POST'
    });
    
    if (!response.ok) {
      if (response.status === 404) {
        showToast('Download feature not available yet - deployment in progress', 'warning');
        return;
      }
      throw new Error(`Download failed: ${response.statusText}`);
    }
    
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workspace_${state.workspace}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast(`Downloaded workspace as ${format}`, 'success');
  } catch (error) {
    console.error('Download error:', error);
    showToast(`Download failed: ${error.message}`, 'error');
  }
}

// Commit & Push
function showCommitModal() {
  const modal = $('commitModal');
  modal.classList.remove('hidden');
  $('commitMessage').focus();
}

function hideCommitModal() {
  const modal = $('commitModal');
  modal.classList.add('hidden');
  $('commitMessage').value = '';
  $('targetBranch').value = '';
  $('prTitle').value = '';
  $('createPrCheckbox').checked = true;
}

async function commitAndPush() {
  const message = $('commitMessage').value.trim();
  const branch = $('targetBranch').value.trim();
  const prTitle = $('prTitle').value.trim();
  const createPr = $('createPrCheckbox').checked;
  
  if (!message) {
    showToast('Please enter a commit message', 'warning');
    return;
  }
  
  // Disable button to prevent double-submission
  $('confirmCommitBtn').disabled = true;
  $('confirmCommitBtn').textContent = 'Processing...';
  
  try {
    const requestBody = {
      message,
      create_pr: createPr
    };
    
    if (branch) requestBody.branch = branch;
    if (prTitle) requestBody.pr_title = prTitle;
    
    const response = await apiCall(`/v1/workspaces/${state.workspace}/git/push`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    
    const data = await response.json();
    console.log('Commit/push response:', data);
    
    hideCommitModal();
    
    if (data.status === 'no_changes') {
      showToast('No changes to commit', 'info');
    } else if (data.status === 'pushed_to_branch') {
      showToast(`Successfully pushed to branch '${data.branch}'`, 'success');
      
      if (data.pr_created === true) {
        // PR was successfully created
        setTimeout(() => {
          showToast(`✅ PR #${data.pr_number} created successfully!`, 'success');
          addChatBubble('system', `Pull Request created: ${data.pr_url}`);
        }, 1000);
      } else if (data.pr_created === 'existing') {
        // PR already existed
        setTimeout(() => {
          showToast(`📋 PR #${data.pr_number} already exists`, 'info');
          addChatBubble('system', `Existing Pull Request: ${data.pr_url}`);
        }, 1000);
      } else if (data.pr_url && !data.pr_created) {
        // Manual PR URL (no GitHub token)
        setTimeout(() => {
          showToast('📝 Click to create PR manually', 'info');
          addChatBubble('system', `Create PR manually: ${data.pr_url}`);
        }, 1000);
      }
      
      // Refresh git status
      await fetchGitStatus();
      await refreshTree();
    } else if (data.status === 'commit_failed') {
      showToast(`Commit failed: ${data.message}`, 'error');
      console.error('Commit details:', data);
    } else if (data.status === 'push_failed') {
      showToast(`Push failed: ${data.message}`, 'error');
      console.error('Push details:', data);
    } else if (data.status === 'error') {
      showToast(`Error: ${data.message}`, 'error');
      console.error('Git error details:', data);
    }
  } catch (error) {
    console.error('Commit/push error:', error);
    showToast(`Operation failed: ${error.message}`, 'error');
  } finally {
    // Re-enable button
    $('confirmCommitBtn').disabled = false;
    $('confirmCommitBtn').textContent = 'Commit & Push';
  }
}

// Monaco Editor initialization
function initMonaco() {
  if (state.monacoLoaded || !window.require) return;
  
  const monacoEl = $("monaco");
  const fallbackEl = $("fallback");
  
  try {
    require(["vs/editor/editor.main"], function () {
      // Define custom theme
      monaco.editor.defineTheme('agentic-dark', config.monacoTheme);
      
      state.editor = monaco.editor.create(monacoEl, {
        value: "",
        language: "plaintext",
        theme: "agentic-dark",
        readOnly: true,
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 13,
        lineHeight: 20,
        padding: { top: 8, bottom: 8 },
        scrollBeyondLastLine: false,
        renderWhitespace: 'selection',
        fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", monospace'
      });
      
      state.monacoLoaded = true;
      monacoEl.hidden = false;
      fallbackEl.style.display = "none";
      
      // If there's a pending file to open, open it now
      if (state.currentFile) {
        openFile(state.currentFile);
      }
    });
  } catch (error) {
    console.error('Monaco initialization failed:', error);
    // Keep fallback visible
  }
}

// Language detection
function guessLanguage(path) {
  const ext = (path.split('.').pop() || '').toLowerCase();
  const langMap = {
    js: 'javascript', mjs: 'javascript', cjs: 'javascript',
    ts: 'typescript', tsx: 'typescript',
    jsx: 'javascript',
    py: 'python', pyw: 'python',
    rb: 'ruby',
    go: 'go',
    rs: 'rust',
    java: 'java',
    c: 'c', h: 'c',
    cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp',
    cs: 'csharp',
    php: 'php',
    swift: 'swift',
    kt: 'kotlin',
    r: 'r',
    m: 'objective-c',
    scala: 'scala',
    sh: 'shell', bash: 'shell', zsh: 'shell',
    ps1: 'powershell',
    sql: 'sql',
    md: 'markdown', markdown: 'markdown',
    json: 'json',
    xml: 'xml', svg: 'xml',
    html: 'html', htm: 'html',
    css: 'css', scss: 'scss', sass: 'sass', less: 'less',
    yml: 'yaml', yaml: 'yaml',
    toml: 'toml',
    ini: 'ini', cfg: 'ini',
    dockerfile: 'dockerfile',
    makefile: 'makefile',
    cmake: 'cmake',
    gradle: 'groovy',
    vue: 'vue',
    lua: 'lua',
    dart: 'dart',
    elm: 'elm',
    clj: 'clojure',
    ex: 'elixir', exs: 'elixir'
  };
  
  // Check full filename for special cases
  const filename = path.split('/').pop().toLowerCase();
  if (filename === 'dockerfile') return 'dockerfile';
  if (filename === 'makefile' || filename === 'gnumakefile') return 'makefile';
  if (filename === 'cmakelists.txt') return 'cmake';
  
  return langMap[ext] || 'plaintext';
}

// File operations
async function openFile(path) {
  if (!state.workspace || path === undefined || path === null) return;
  
  state.currentFile = path;
  updateBreadcrumbs(path);
  showViewerLoading(true);
  
  // Show editor toolbar for files
  $('editorToolbar').classList.remove('hidden');
  
  try {
    if (state.viewMode === 'diff') {
      // Load diff view
      const diffResult = await fetchDiff(path);
      if (diffResult) {
        if (typeof diffResult === 'object' && diffResult.isDirectory) {
          // Handle directory diff
          renderDirectoryDiff(diffResult.diff);
        } else {
          // Handle file diff
          renderDiff(diffResult);
        }
        showDiffView();
      } else {
        showToast('No changes in this file', 'info');
        setViewMode('code');
      }
    } else {
      // Load code view
      const response = await apiCall(`/v1/workspaces/${state.workspace}/file?path=${encodeURIComponent(path)}`);
      const data = await response.json();
      
      if (data && typeof data.content === 'string') {
        renderCode(data.content, path);
        $("activePath").textContent = path.split('/').pop() || path;
        selectTreeItem(path);
      } else if (data && data.is_directory) {
        renderCode(data.message, path);
        $("activePath").textContent = path.split('/').pop() || path;
      }
    }
  } catch (error) {
    console.error('File open error:', error);
    renderCode(`Error loading file: ${error.message}`, path);
  } finally {
    showViewerLoading(false);
  }
}

function renderCode(content, path) {
  if (state.monacoLoaded && state.editor) {
    const language = guessLanguage(path);
    const model = monaco.editor.createModel(content, language);
    state.editor.setModel(model);
    showCodeView();
  } else {
    // Fallback rendering
    const lines = content.split('\n');
    const gutter = $('gutter');
    const code = $('fileOut');
    
    // Generate line numbers
    gutter.innerHTML = lines.map((_, i) => `<div>${i + 1}</div>`).join('');
    code.textContent = content;
    showCodeView();
    
    // Lazy load Monaco on first file open
    if (!state.monacoLoaded) {
      initMonaco();
    }
  }
}

function setViewMode(mode) {
  state.viewMode = mode;
  
  if (mode === 'code') {
    $('viewCodeBtn').classList.add('active');
    $('viewDiffBtn').classList.remove('active');
  } else {
    $('viewCodeBtn').classList.remove('active');
    $('viewDiffBtn').classList.add('active');
  }
  
  // Reload current file in new mode
  if (state.currentFile) {
    openFile(state.currentFile);
  }
}

function showCodeView() {
  if (state.monacoLoaded) {
    $('monaco').hidden = false;
    $('fallback').style.display = 'none';
  } else {
    $('monaco').hidden = true;
    $('fallback').style.display = 'flex';
  }
  $('diffViewer').classList.add('hidden');
}

function showDiffView() {
  $('monaco').hidden = true;
  $('fallback').style.display = 'none';
  $('diffViewer').classList.remove('hidden');
}

function showViewerLoading(show) {
  const loading = $('viewerLoading');
  const viewer = $('viewer');
  
  if (show) {
    loading.classList.remove('hidden');
    viewer.classList.add('hidden');
  } else {
    loading.classList.add('hidden');
    viewer.classList.remove('hidden');
  }
}

// Breadcrumbs
function updateBreadcrumbs(path) {
  const breadcrumbs = $('breadcrumbs');
  if (!path) {
    breadcrumbs.innerHTML = '<span>No file selected</span>';
    return;
  }
  
  const parts = path.split('/').filter(Boolean);
  const elements = [];
  
  parts.forEach((part, index) => {
    const isLast = index === parts.length - 1;
    const currentPath = parts.slice(0, index + 1).join('/');
    
    if (isLast) {
      elements.push(`<span>${part}</span>`);
    } else {
      elements.push(`<a href="#" data-path="${currentPath}">${part}</a>`);
      elements.push('<span class="separator">/</span>');
    }
  });
  
  breadcrumbs.innerHTML = `<span>${elements.join('')}</span>`;
  
  // Add click handlers
  breadcrumbs.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      // Could implement folder navigation here
    });
  });
}

// Tree operations
async function refreshTree() {
  if (!state.workspace) return;
  
  showTreeLoading(true);
  
  try {
    const response = await apiCall(`/v1/workspaces/${state.workspace}/tree`);
    const data = await response.json();
    state.treeData = data.entries || [];
    renderTree(state.treeData);
    
    // Fetch git status after tree refresh and wait for it
    await fetchGitStatus();
  } catch (error) {
    $("tree").innerHTML = `<div class="error">Error loading tree: ${error.message}</div>`;
  } finally {
    showTreeLoading(false);
  }
}

const debouncedRefreshTree = debounce(refreshTree, config.debounceDelay);

function showTreeLoading(show) {
  const loading = $('treeLoading');
  const tree = $('tree');
  
  if (show) {
    loading.classList.remove('hidden');
    tree.classList.add('hidden');
  } else {
    loading.classList.add('hidden');
    tree.classList.remove('hidden');
  }
}

function renderTree(entries) {
  const root = buildTreeStructure(entries);
  const treeEl = $("tree");
  treeEl.innerHTML = "";
  
  if (!entries.length) {
    treeEl.innerHTML = '<div style="padding: 8px; color: var(--text-tertiary);">No files</div>';
    return;
  }
  
  const ul = document.createElement("ul");
  ul.setAttribute('role', 'group');
  treeEl.appendChild(ul);
  renderTreeNode(root, ul, "");
}

function buildTreeStructure(entries) {
  const root = { children: {} };
  
  for (const path of entries) {
    const parts = path.split("/").filter(Boolean);
    let node = root;
    
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1 && !path.endsWith("/");
      
      if (!node.children[part]) {
        node.children[part] = {
          name: part,
          children: {},
          file: isFile
        };
      }
      
      node = node.children[part];
    }
  }
  
  return root;
}

function renderTreeNode(node, parentEl, prefix) {
  if (!node.children) return;
  
  const entries = Object.entries(node.children).sort(([nameA, nodeA], [nameB, nodeB]) => {
    // Directories first, then alphabetical
    if (nodeA.file === nodeB.file) return nameA.localeCompare(nameB);
    return nodeA.file ? 1 : -1;
  });
  
  for (const [name, child] of entries) {
    const li = document.createElement("li");
    li.setAttribute('role', 'treeitem');
    
    if (child.file) {
      li.className = "file";
      li.textContent = name;
      li.dataset.path = `${prefix}${name}`;
      li.tabIndex = 0;
      
      li.addEventListener('click', () => openFile(`${prefix}${name}`));
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openFile(`${prefix}${name}`);
        }
      });
      
      parentEl.appendChild(li);
    } else {
      li.className = "dir";
      li.setAttribute('aria-expanded', 'false');
      li.tabIndex = 0;
      
      const span = document.createElement('span');
      span.textContent = `▸ ${name}`;
      li.appendChild(span);
      
      const subUl = document.createElement("ul");
      subUl.setAttribute('role', 'group');
      subUl.style.display = 'none';
      subUl.style.paddingLeft = '14px';
      
      const toggle = () => {
        const isOpen = li.getAttribute('aria-expanded') === 'true';
        li.setAttribute('aria-expanded', !isOpen);
        subUl.style.display = isOpen ? 'none' : 'block';
        span.textContent = `${isOpen ? '▸' : '▾'} ${name}`;
      };
      
      li.addEventListener('click', (e) => {
        if (e.target === li || e.target === span) {
          toggle();
        }
      });
      
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggle();
        } else if (e.key === 'ArrowRight' && li.getAttribute('aria-expanded') === 'false') {
          toggle();
        } else if (e.key === 'ArrowLeft' && li.getAttribute('aria-expanded') === 'true') {
          toggle();
        }
      });
      
      parentEl.appendChild(li);
      parentEl.appendChild(subUl);
      renderTreeNode(child, subUl, `${prefix}${name}/`);
    }
  }
}

function selectTreeItem(path) {
  // Remove previous selection
  if (state.selectedTreeItem) {
    state.selectedTreeItem.classList.remove('selected');
  }
  
  // Find and select new item
  const item = document.querySelector(`[data-path="${path}"]`);
  if (item) {
    item.classList.add('selected');
    state.selectedTreeItem = item;
    item.scrollIntoView({ block: 'nearest' });
  }
}

// Chat operations
function addChatBubble(role, text, timestamp = new Date()) {
  const messages = $("chatMessages");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${role === 'user' ? 'You' : 'Assistant'} • ${timestamp.toLocaleTimeString()}`;
  
  const content = document.createElement("div");
  content.className = "content";
  content.textContent = text;
  
  bubble.appendChild(meta);
  bubble.appendChild(content);
  messages.appendChild(bubble);
  
  // Scroll to bottom
  messages.scrollTop = messages.scrollHeight;
  
  // Add to history
  state.chatHistory.push({ role, text, timestamp });
}

function addStreamingBubble() {
  const messages = $("chatMessages");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble assistant";
  bubble.id = "streamingBubble";
  
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `Assistant • ${new Date().toLocaleTimeString()}`;
  
  const content = document.createElement("div");
  content.className = "content";
  content.innerHTML = '<div class="streaming"><span></span><span></span><span></span></div> Thinking...';
  
  bubble.appendChild(meta);
  bubble.appendChild(content);
  messages.appendChild(bubble);
  
  messages.scrollTop = messages.scrollHeight;
  
  return bubble;
}

function updateStreamingBubble(text) {
  const bubble = $("streamingBubble");
  if (bubble) {
    const content = bubble.querySelector('.content');
    content.textContent = text;
  }
}

function removeStreamingBubble() {
  const bubble = $("streamingBubble");
  if (bubble) {
    bubble.remove();
  }
}

// Add function to get limited chat context
function getChatContext(limit = 10) {
  // Get recent chat history, excluding the current prompt that will be added
  const recentHistory = state.chatHistory.slice(-limit);
  return recentHistory.map(msg => ({
    role: msg.role === 'user' ? 'user' : 'assistant', 
    text: msg.text
  }));
}

async function sendPrompt() {
  const prompt = $("prompt").value.trim();
  if (!state.workspace || !prompt || state.isStreaming) return;
  
  state.isStreaming = true;
  $("runBtn").disabled = true;
  $("prompt").value = "";
  
  addChatBubble("user", prompt);
  const streamingBubble = addStreamingBubble();
  
  try {
    // Include recent chat history in the request
    const chatContext = getChatContext(10); // Last 10 messages
    
    const response = await apiCall("/v1/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ 
        prompt, 
        workspace: state.workspace,
        chatHistory: chatContext
      })
    });
    
    const data = await response.json();
    
    removeStreamingBubble();
    
    if (data && data.final_text) {
      addChatBubble("assistant", data.final_text);
    } else {
      addChatBubble("assistant", "I completed the task.");
    }
    
    // Show raw output if debug mode
    if (data && Object.keys(data).length > 1) {
      $("runOut").textContent = JSON.stringify(data, null, 2);
      $("runOut").classList.remove('hidden');
    }
    
    // Refresh tree and git status after operations
    await debouncedRefreshTree();
    
  } catch (error) {
    removeStreamingBubble();
    addChatBubble("assistant", `Error: ${error.message}`);
  } finally {
    state.isStreaming = false;
    $("runBtn").disabled = false;
    $("prompt").focus();
  }
}

// Workspace operations
async function uploadWorkspace() {
  const file = $("zipFile").files[0];
  if (!file) {
    showToast("Please select a ZIP file first", "warning");
    return;
  }
  
  const formData = new FormData();
  formData.append("zip_file", file);
  
  try {
    const response = await apiCall("/v1/workspaces/upload", {
      method: "POST",
      body: formData
    });
    
    const data = await response.json();
    if (data.workspace_id) {
      await loadWorkspace(data.workspace_id);
      showToast("Workspace uploaded successfully", "success");
    }
  } catch (error) {
    showToast(`Upload failed: ${error.message}`, "error");
  }
}

async function cloneRepository() {
  const repoUrl = $("repoUrl").value.trim();
  const branch = $("branch").value.trim() || "main";
  
  if (!repoUrl) {
    showToast("Please enter a repository URL", "warning");
    return;
  }
  
  try {
    const response = await apiCall("/v1/workspaces/clone", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, branch })
    });
    
    const data = await response.json();
    if (data.workspace_id) {
      await loadWorkspace(data.workspace_id);
      showToast("Repository cloned successfully", "success");
    }
  } catch (error) {
    showToast(`Clone failed: ${error.message}`, "error");
  }
}

async function checkHealth() {
  try {
    const response = await apiCall("/healthz");
    const text = await response.text();
    $("healthBadge").textContent = "✓ Connected";
    $("healthBadge").style.color = "var(--success)";
  } catch (error) {
    $("healthBadge").textContent = "✗ Disconnected";
    $("healthBadge").style.color = "var(--error)";
  }
}

// Auto-resize textarea
function autoResizeTextarea() {
  const textarea = $("prompt");
  textarea.style.height = 'auto';
  const newHeight = Math.min(textarea.scrollHeight, config.maxPromptHeight);
  textarea.style.height = newHeight + 'px';
}

// Event listeners
document.addEventListener("DOMContentLoaded", () => {
  // Initialize
  checkHealth();
  
  // Load saved state
  const savedUrl = localStorage.getItem('baseUrl');
  const savedWorkspace = localStorage.getItem('workspace');
  
  if (savedUrl) $("baseUrl").value = savedUrl;
  if (savedWorkspace) {
    $("ws").value = savedWorkspace;
    state.workspace = savedWorkspace;
    loadWorkspace(savedWorkspace);
  } else {
    // Show welcome screen if no saved workspace
    showWelcomeScreen();
  }
  
  // Health check
  $("healthBtn").addEventListener('click', checkHealth);
  
  // Workspace operations (welcome screen)
  $("uploadBtn").addEventListener('click', uploadWorkspace);
  $("cloneBtn").addEventListener('click', cloneRepository);
  $("loadWorkspaceBtn").addEventListener('click', () => {
    const workspaceId = $("ws").value.trim();
    if (workspaceId) {
      loadWorkspace(workspaceId);
    } else {
      showToast("Please enter a workspace ID", "warning");
    }
  });
  
  // Main app workspace operations
  $("treeBtn").addEventListener('click', refreshTree);
  $("uploadNewBtn").addEventListener('click', () => {
    showWelcomeScreen();
    // Clear previous selections
    $("zipFile").value = '';
    $("repoUrl").value = '';
    $("branch").value = 'main';
    $("ws").value = '';
  });
  $("cloneNewBtn").addEventListener('click', () => {
    showWelcomeScreen();
    // Clear previous selections
    $("zipFile").value = '';
    $("repoUrl").value = '';
    $("branch").value = 'main';
    $("ws").value = '';
  });
  
  // Dropdown functionality
  $("downloadDropdownBtn").addEventListener('click', (e) => {
    e.stopPropagation();
    toggleDropdown('downloadDropdown');
  });
  
  // Tree tab switching
  $("filesTab").addEventListener('click', () => switchTreeTab('files'));
  $("changesTab").addEventListener('click', () => switchTreeTab('changes'));
  
  // Download buttons (in dropdown)
  $("downloadZipBtn").addEventListener('click', () => {
    downloadWorkspace('zip');
    hideAllDropdowns();
  });
  $("downloadDiffBtn").addEventListener('click', () => {
    downloadWorkspace('diff');
    hideAllDropdowns();
  });
  
  // Git operations
  $("commitBtn").addEventListener('click', showCommitModal);
  $("cancelCommitBtn").addEventListener('click', hideCommitModal);
  $("confirmCommitBtn").addEventListener('click', commitAndPush);
  
  // View mode toggle
  $("viewCodeBtn").addEventListener('click', () => setViewMode('code'));
  $("viewDiffBtn").addEventListener('click', () => setViewMode('diff'));
  
  // Workspace input (for welcome screen load existing)
  $("ws").addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const workspaceId = e.target.value.trim();
      if (workspaceId) {
        loadWorkspace(workspaceId);
      }
    }
  });
  
  // Base URL
  $("baseUrl").addEventListener('change', (e) => {
    localStorage.setItem('baseUrl', e.target.value);
  });
  
  // Chat
  $("runBtn").addEventListener('click', sendPrompt);
  $("prompt").addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      sendPrompt();
    }
  });
  
  $("prompt").addEventListener('input', autoResizeTextarea);
  
  // Modal close on escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('commitModal').classList.contains('hidden')) {
      hideCommitModal();
    }
    if (e.key === 'Escape') {
      hideAllDropdowns();
    }
  });
  
  // Click outside to close dropdowns
  document.addEventListener('click', () => {
    hideAllDropdowns();
  });
  
  // Global keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Refresh tree: Ctrl/Cmd + R
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
      e.preventDefault();
      refreshTree();
    }
    
    // Focus prompt: Alt + P
    if (e.altKey && e.key === 'p') {
      e.preventDefault();
      $("prompt").focus();
    }
  });
  
  // Initialize Monaco after a short delay
  setTimeout(initMonaco, 100);
});

// Handle visibility change to refresh on return
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && state.workspace) {
    checkHealth();
  }
});

// Add event listener
$("resetBtn").addEventListener('click', () => {
    if (confirm('Reset workspace? This will clear local storage and show welcome screen.')) {
        localStorage.removeItem('workspace');
        location.reload();
    }
});