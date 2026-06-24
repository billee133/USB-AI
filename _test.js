
// LOCAL_TOKEN_PLACEHOLDER
let LOCAL_TOKEN = 'c3c59f2265aa7adbefd3b5187abc2987';

// ============ ERROR CATCHER ============
window.addEventListener('error', e => {
  auditLog('js_error', `${e.filename}:${e.lineno} — ${e.message}`, 'error');
});
window.addEventListener('unhandledrejection', e => {
  auditLog('promise_error', e.reason?.message || String(e.reason), 'error');
});

// ============ THEME ============
let theme = localStorage.getItem('portable_theme') || 'light';
function applyTheme() {
  document.body.className = theme;
  document.getElementById('theme-btn').textContent = theme === 'light' ? '☀' : '⚡';
}
function toggleTheme() {
  theme = theme === 'light' ? 'cyber' : 'light';
  localStorage.setItem('portable_theme', theme);
  applyTheme();
}
applyTheme();

// ============ SIDEBAR ============
let sidebarOpen = window.innerWidth > 768;
window.addEventListener('resize', () => {
  if (window.innerWidth > 768) { sidebarOpen = true; document.getElementById('sidebar').classList.add('open'); document.getElementById('side-overlay').classList.remove('show'); }
});
function toggleSidebar() {
  sidebarOpen = !sidebarOpen;
  document.getElementById('sidebar').classList.toggle('open', sidebarOpen);
  document.getElementById('side-overlay').classList.toggle('show', sidebarOpen && window.innerWidth <= 768);
}
function switchSideTab(tab) {
  document.querySelectorAll('#side-tabs .stab').forEach(s => s.classList.toggle('on', s.dataset.tab === tab));
  document.querySelectorAll('.side-panel').forEach(p => p.classList.toggle('on', p.id === 'panel-' + tab));
  // Auto-open sidebar on mobile when switching tabs
  if (window.innerWidth <= 768 && !sidebarOpen) toggleSidebar();
}

// ============ MODAL ============
function openSettings() { document.getElementById('modal-overlay').classList.add('show'); }
function closeSettings() { document.getElementById('modal-overlay').classList.remove('show'); }
async function saveAndClose() { await saveConfig(); closeSettings(); setStatus('配置已保存', 'success'); }

// ============ DOMAIN EXPERT PROMPTS ============
const DOMAIN_PROMPTS = {
  programming: '你是资深全栈工程师。精通 C/C#/C++/VB/Python/Java/HTML/CSS/JS。写代码优先考虑可读性、安全性、性能。代码块标注语言。解释概念用通俗比喻。',
  finance: '你是金融分析师。精通股票、期货、加密货币、外汇、基金。用数据说话，标注风险等级。涉及预测时必须声明"仅供参考，不构成投资建议"。引用最新行情时标注时间。',
  security: '你是网络安全专家。精通渗透测试、防御策略、漏洞分析、安全审计。只提供合法的安全建议。涉及攻击技术时必须加上防御方案。引用 CVE/漏洞编号。',
  server: '你是服务器运维专家。精通 Linux/Windows Server、Docker/K8s、Nginx/Apache、数据库调优、Shell/PowerShell。给命令时标注参数含义。优先推荐稳定版方案。',
  network: '你是网络工程师。精通路由交换、防火墙、VPN、SDN、网络诊断。涉及网络配置时标注厂商（Cisco/Huawei/Juniper）。命令标注权限级别。',
  ai: '你是 AI 研究员。精通机器学习、深度学习、NLP、CV、LLM 原理。解释论文时给出通俗类比。讨论模型时注明参数规模、训练数据、发布时间。',
  computer: '你是计算机维修工程师。精通硬件诊断、系统修复、数据恢复、驱动安装。优先给出排查步骤（从简到繁）。涉及拆机时加安全警告。推荐工具时优先免费开源。',
};
let currentDomain = '';
function setDomain(d) {
  currentDomain = d;
  document.getElementById('domain-select').value = d;
  const label = d ? `🧠 ${document.getElementById('domain-select').selectedOptions[0].text} 模式` : '🧠 通用模式';
  setStatus(label, 'success');
  localStorage.setItem('portable_domain', d);
}
try { const sd = localStorage.getItem('portable_domain'); if (sd) { currentDomain = sd; setDomain(sd); } } catch(e) {}

// ============ TOGGLES ============
let deepThinkOn = false, webSearchOn = false, isProcessing = false, chatHistory = [];
// Keywords that auto-trigger web search
const TIME_SENSITIVE = /\b(今天|现在|实时|最新|近期|最近|新闻|价格|天气|开奖|开赛|比分|结果|直播|刚刚|刚才|目前|当前)\b/;

function toggleDeepThink() {
  deepThinkOn = !deepThinkOn;
  const c = document.getElementById('chip-think');
  const ms = document.getElementById('model-select');
  if (deepThinkOn) {
    c.classList.add('on-think');
    ms.setAttribute('data-prev-model', ms.value);
    ms.value = 'deepseek-v4-pro';
  } else {
    c.classList.remove('on-think', 'run-think');
    const prev = ms.getAttribute('data-prev-model');
    if (prev) ms.value = prev;
  }
  updateChips(); saveConfig();
}
function toggleWebSearch() {
  webSearchOn = !webSearchOn;
  const c = document.getElementById('chip-search');
  if (webSearchOn) c.classList.add('on-search'); else c.classList.remove('on-search', 'run-search');
  updateChips(); saveConfig();
}
function setToggleRunning(r) {
  if (deepThinkOn) document.getElementById('chip-think').classList.toggle('run-think', r);
  if (webSearchOn) document.getElementById('chip-search').classList.toggle('run-search', r);
}
function updateChips() {
  const bar = document.getElementById('status-bar');
  bar.querySelectorAll('.mode-chip').forEach(c => c.remove());
  // Mode indicator with health check
  const mc = document.createElement('span');
  mc.className = 'mode-chip';
  if (isServerMode()) {
    mc.textContent = serverAvailable ? '🖥 服务器 ✓' : '🖥 服务器 ✗';
    mc.style.color = serverAvailable ? 'var(--success)' : 'var(--danger)';
  } else {
    mc.textContent = '🌍 直连';
    mc.style.color = 'var(--warn)';
  }
  bar.appendChild(mc);
  if (deepThinkOn) { const c = document.createElement('span'); c.className = 'mode-chip on'; c.textContent = '🧠 V4 Pro'; bar.appendChild(c); }
  if (webSearchOn) { const c = document.createElement('span'); c.className = 'mode-chip on'; c.textContent = '🌐 联网'; bar.appendChild(c); }
}

// ============ TASKS ============
let tasks = [];
function loadTasks() { try { tasks = JSON.parse(localStorage.getItem('portable_tasks') || '[]'); } catch { tasks = []; } renderTasks(); }
function saveTasks() { try { localStorage.setItem('portable_tasks', JSON.stringify(tasks)); } catch(e) {} }
function addTask() { const inp = document.getElementById('task-input'); const t = inp.value.trim(); if (!t) return; tasks.push({id:Date.now(),text:t,done:false}); inp.value=''; saveTasks(); renderTasks(); }
function toggleTask(id) { const t = tasks.find(t => t.id===id); if (t) { t.done=!t.done; saveTasks(); renderTasks(); } }
function deleteTask(id) { if (!confirm('确定删除此任务？')) return; tasks = tasks.filter(t => String(t.id)!==String(id)); saveTasks(); renderTasks(); }
function renderTasks() {
  const el = document.getElementById('task-list');
  if (!tasks.length) { el.innerHTML = '<div class="side-empty">暂无任务<br>在上方输入框添加</div>'; return; }
  el.innerHTML = tasks.map(t => `<div class="task-item ${t.done?'done':''}"><div class="check" onclick="toggleTask(${safeAttr(t.id)})">${t.done?'✓':''}</div><span class="tt" onclick="toggleTask(${safeAttr(t.id)})">${escapeHtml(t.text)}</span><span class="del" onclick="event.stopPropagation();deleteTask(${safeAttr(t.id)})">×</span></div>`).join('');
}
try { loadTasks(); } catch(e) { console.warn('tasks:', e); }

// ============ FILE UPLOAD ============
let pendingUploads = [];
function makeId() { return 'd_'+Date.now()+'_'+Math.random().toString(36).slice(2,10); }
function quickUpload(input) {
  if (isProcessing) { setStatus('请等待当前请求完成', 'error'); input.value = ''; return; }
  const files = input.files; if (!files || !files.length) { input.value = ''; return; }
  const total = Math.min(files.length, 10); let loaded = 0, skipped = 0, attempted = 0;
  for (let i = 0; i < total; i++) {
    const file = files[i]; if (!file || file.size > 5*1024*1024) { skipped++; continue; }
    attempted++;
    const reader = new FileReader();
    reader.onload = (function(f){ return function(e){
      pendingUploads.push({ id: makeId(), name: f.name, content: e.target.result || '' });
      loaded++; if (loaded >= attempted) renderPendingChips();
    };})(file);
    reader.onerror = (function(){ return function(){ skipped++; loaded++; if (loaded >= attempted) renderPendingChips(); } })();
    reader.readAsText(file, 'UTF-8');
  }
  input.value = '';
}
function removePending(id) { pendingUploads = pendingUploads.filter(p => p.id !== id); renderPendingChips(); }
function renderPendingChips() {
  const el = document.getElementById('upload-preview');
  if (!pendingUploads.length) { el.innerHTML = ''; return; }
  el.innerHTML = pendingUploads.map(p => `<span class="up-chip"><span class="up-name">📄 ${escapeHtml(p.name)}</span><span class="up-rm" onclick="removePending('${safeAttr(p.id)}')">×</span></span>`).join('');
}

// ============ CONVERSATION MEMORY ============
const AUTO_CHAT_ID = '__current__';
let savedChats = [];
function loadChats() { try { savedChats = JSON.parse(localStorage.getItem('portable_chats') || '[]'); if (!Array.isArray(savedChats)) savedChats = []; } catch { savedChats = []; } renderChats(); }
function saveChats() { try { localStorage.setItem('portable_chats', JSON.stringify(savedChats)); } catch(e) {} }

function autoSaveCurrentChat() {
  if (!chatHistory.length) return;
  const title = (chatHistory.find(m => m.role === 'user')?.content || '新对话').slice(0, 40);
  const entry = { id: AUTO_CHAT_ID, title, date: new Date().toLocaleString(), messages: JSON.parse(JSON.stringify(chatHistory)), isAuto: true };
  const idx = savedChats.findIndex(c => c.id === AUTO_CHAT_ID);
  if (idx >= 0) savedChats[idx] = entry; else savedChats.push(entry);
  saveChats();
  try { localStorage.setItem('portable_autosave', JSON.stringify(entry)); } catch(e) {}
  renderChats();
}

function autoRestoreChat() {
  let last = null;
  try { last = JSON.parse(localStorage.getItem('portable_autosave')); } catch(e) {}
  if (!last || !last.messages) last = savedChats.find(c => c.isAuto);
  if (!last || !last.messages || !last.messages.length) return;
  chatHistory = JSON.parse(JSON.stringify(last.messages));
  showChat();
  document.getElementById('chat').innerHTML = '';
  last.messages.forEach(m => addMessage(m.role, m.content));
  setStatus(`已恢复上次对话: ${last.title}`, 'success');
}

function loadConversation(id) {
  const chat = savedChats.find(c => String(c.id) === String(id));
  if (!chat || !chat.messages || !chat.messages.length) return;
  // Save current as permanent entry before switching
  if (chatHistory.length >= 2) {
    const title = (chatHistory.find(m => m.role === 'user')?.content || '新对话').slice(0, 40);
    const entry = { id: 'c_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6), title, date: new Date().toLocaleString(), messages: JSON.parse(JSON.stringify(chatHistory)), isAuto: false };
    savedChats.push(entry);
    saveChats();
  }
  chatHistory = JSON.parse(JSON.stringify(chat.messages));
  showChat();
  document.getElementById('chat').innerHTML = '';
  chat.messages.forEach(m => addMessage(m.role, m.content));
  setStatus(`已加载: ${chat.title}`, 'success');
  if (window.innerWidth <= 768 && sidebarOpen) toggleSidebar();
}

function deleteConversation(id) {
  if (!confirm('确定删除此对话？此操作不可恢复。')) return;
  const chat = savedChats.find(c => String(c.id) === String(id));
  savedChats = savedChats.filter(c => String(c.id) !== String(id));
  saveChats(); renderChats();
  const sameFirst = chat.messages[0] && chatHistory[0] && chat.messages[0].content === chatHistory[0].content;
  if (sameFirst) clearChat();
}

function renderChats() {
  const el = document.getElementById('chat-list');
  if (!savedChats.length) { el.innerHTML = '<div class="side-empty">暂无对话<br>发送消息后自动保存</div>'; return; }
  el.innerHTML = savedChats.slice().reverse().map(c => `
    <div class="task-item" style="flex-direction:column;align-items:stretch;gap:2px;" onclick="loadConversation('${safeAttr(c.id)}')">
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:12px;flex:1;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${c.isAuto ? '🔄' : '💬'} ${escapeHtml(c.title)}</span>
        <span class="del" onclick="event.stopPropagation();deleteConversation('${safeAttr(c.id)}')" title="删除">×</span>
      </div>
      <div style="display:flex;gap:6px;font-size:10px;color:var(--text-dim);">
        <span>${c.date}</span><span>${c.messages.length} 条</span>
        <span style="color:var(--accent);margin-left:auto;">📥 加载</span>
      </div>
    </div>`).join('');
}
try { loadChats(); } catch(e) { console.warn('chats:', e); }
try { autoRestoreChat(); } catch(e) { console.warn('restore:', e); }

// ============ PROJECT MEMORY ============
let memories = [];
let activeMemIds = new Set();
function loadMemories() { try { memories = JSON.parse(localStorage.getItem('portable_memories') || '[]'); if (!Array.isArray(memories)) memories = []; } catch { memories = []; } renderMemories(); }
function saveMemories() { try { localStorage.setItem('portable_memories', JSON.stringify(memories)); } catch(e) {} }

function addMemory() {
  const titleEl = document.getElementById('memory-input'), contentEl = document.getElementById('memory-content');
  const title = titleEl.value.trim(), content = contentEl.value.trim();
  if (!title) return;
  memories.push({ id: Date.now(), title, content, date: new Date().toLocaleString() });
  if (memories.length > 100) memories.shift();
  titleEl.value = ''; contentEl.value = '';
  saveMemories(); renderMemories();
}

function toggleMemory(id) {
  id = Number(id);
  if (activeMemIds.has(id)) activeMemIds.delete(id); else activeMemIds.add(id);
  renderMemories();
  setStatus(activeMemIds.size > 0 ? `已激活 ${activeMemIds.size} 条项目记忆` : '已停用所有项目记忆', '');
  // Close sidebar on mobile
  if (window.innerWidth <= 768 && sidebarOpen) toggleSidebar();
}

function deleteMemory(id) {
  if (!confirm('确定删除此记忆？')) return;
  id = Number(id);
  memories = memories.filter(m => m.id !== id);
  activeMemIds.delete(id);
  saveMemories(); renderMemories();
}

function renderMemories() {
  const el = document.getElementById('memory-list');
  if (!memories.length) { el.innerHTML = '<div class="side-empty">暂无项目记忆<br>添加标题和内容后激活</div>'; return; }
  el.innerHTML = memories.map(m => {
    const active = activeMemIds.has(m.id);
    return `<div class="task-item" style="flex-direction:column;align-items:stretch;gap:2px;" onclick="toggleMemory(${safeAttr(m.id)})">
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:12px;font-weight:600;color:var(--text);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">🧠 ${escapeHtml(m.title)}</span>
        <span style="font-size:10px;cursor:pointer;padding:2px 8px;border-radius:4px;background:${active?'var(--success)':'var(--accent-soft)'};color:${active?'#fff':'var(--accent)'};">${active?'✓ 已激活':'激活'}</span>
        <span class="del" onclick="event.stopPropagation();deleteMemory(${safeAttr(m.id)})">×</span>
      </div>
      <div style="font-size:10px;color:var(--text-dim);max-height:32px;overflow:hidden;">${escapeHtml(m.content || '(无内容)')}</div>
    </div>`;
  }).join('');
}
try { loadMemories(); } catch(e) { console.warn('memories:', e); }

// ============ CONFIG ============
function getConfig() { try { return JSON.parse(localStorage.getItem('portable_ai_config')||'{}'); } catch { return {}; } }
function isServerMode() { let m = document.getElementById('api-mode').value; if (m==='auto') m=detectMode(); return m==='proxy'; }
async function saveConfig() {
  const cfg = { apiKey: document.getElementById('api-key').value, model: document.getElementById('model-select').value, apiMode: document.getElementById('api-mode').value, deepThink: deepThinkOn, webSearch: webSearchOn };
  localStorage.setItem('portable_ai_config', JSON.stringify(cfg));
  updateChips();
  // Sync to server DB (strip API Key for security)
  if (isServerMode()) {
    try {
      const safeCfg = Object.assign({}, cfg);
      delete safeCfg.apiKey;
      await fetch('/api/db/settings', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Local-Token': LOCAL_TOKEN }, body: JSON.stringify(safeCfg) });
    } catch(e) {}
  }
  }
async function loadConfig() {
  const cfg = getConfig();
  // If no local API Key and in server mode, try to fetch from server DB
  if (!cfg.apiKey && isServerMode()) {
    try {
      const r = await fetch('/api/db/settings', { headers: { 'X-Local-Token': LOCAL_TOKEN } });
      if (r.ok) {
        const srv = await r.json();
        if (srv.apiKey) { cfg.apiKey = srv.apiKey; localStorage.setItem('portable_ai_config', JSON.stringify(Object.assign(cfg, srv))); }
        if (srv.model) cfg.model = srv.model;
        if (srv.apiMode) cfg.apiMode = srv.apiMode;
        if (srv.deepThink && !cfg.deepThink) { cfg.deepThink = true; }
        if (srv.webSearch && !cfg.webSearch) { cfg.webSearch = true; }
      }
    } catch(e) {}
  }
  // Auto-correct apiMode: if on http:// server, force proxy mode
  const onServer = window.location.protocol !== 'file:';
  if (onServer && cfg.apiMode === 'direct') {
    cfg.apiMode = 'auto';  // auto on http -> proxy
    localStorage.setItem('portable_ai_config', JSON.stringify(Object.assign(cfg, {})));
  }
  if (cfg.apiKey) document.getElementById('api-key').value = cfg.apiKey;
  if (cfg.model) document.getElementById('model-select').value = cfg.model;
  if (cfg.apiMode) document.getElementById('api-mode').value = cfg.apiMode;
  if (cfg.deepThink) { deepThinkOn = true; document.getElementById('chip-think').classList.add('on-think'); }
  if (cfg.webSearch) { webSearchOn = true; document.getElementById('chip-search').classList.add('on-search'); }
}
// ============ SERVER HEALTH CHECK ============
let serverAvailable = false;
async function checkServer(retries = 3) {
  if (!isServerMode()) { serverAvailable = false; updateChips(); return; }
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch('/api/ping');
      if (r.ok) { serverAvailable = true; const d = await r.json(); auditLog('server_check', `v${d.version}`); break; }
    } catch(e) { serverAvailable = false; }
    if (i < retries - 1) await new Promise(r => setTimeout(r, 800));
  }
  updateChips();
}
(async function(){ try { await loadConfig(); await checkServer(); updateChips(); } catch(e) { console.warn('config:', e); } })();

// ============ API HELPERS ============
function detectMode() { return window.location.protocol === 'file:' ? 'direct' : 'proxy'; }
function getApiUrl() { let m = document.getElementById('api-mode').value; if (m==='auto') m=detectMode(); return m==='proxy'?'/api/deepseek':'https://api.deepseek.com/v1/chat/completions'; }
function getSearchUrl() { let m = document.getElementById('api-mode').value; if (m==='auto') m=detectMode(); return m==='proxy'?'/api/search':null; }
function getApiHeaders(key) { let m = document.getElementById('api-mode').value; if (m==='auto') m=detectMode(); return m==='proxy'?{'Content-Type':'application/json','X-API-Key':key}:{'Content-Type':'application/json','Authorization':`Bearer ${key}`}; }
function onModeChange() { saveConfig(); }

// ============ RENDER ============
// Shared storage: processAIResponse fills this, renderMarkdown uses it
let _fixedCodeBlocks = [];

// Lightweight syntax tokenizer — wraps code in colored spans
function tokenizeCode(code, lang) {
  if (!lang || lang === 'text' || lang === 'plain') return escapeHtml(code);
  // Tokenize raw code, escape as final step
  let h = code;
  // Strings
  h = h.replace(/(["'`])(?:(?!\1|\\).|\\.)*\1/g, '<span class=\"hl-str\">$&</span>');
  // Comments
  if (['js','javascript','ts','typescript','css','c','cpp','java','go','rust','py','python'].includes(lang)) {
    h = h.replace(/(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g, '<span class=\"hl-cmt\">$&</span>');
  }
  if (['py','python','rb','sh','bash','yaml','yml'].includes(lang)) {
    h = h.replace(/(#[^\n]*)/g, '<span class=\"hl-cmt\">$&</span>');
  }
  // Numbers
  h = h.replace(/\b(\d+\.?\d*)\b/g, '<span class=\"hl-num\">$1</span>');
  // Keywords (subset)
  const kw = 'function|const|let|var|if|else|for|while|return|class|import|export|from|async|await|try|catch|throw|new|this|def|print|lambda|yield|raise|except|finally|with|and|or|not|in|is|None|True|False'.split('|');
  if (lang !== 'json' && lang !== 'css') {
    for (const k of kw) {
      h = h.replace(new RegExp('\\b('+k+')\\b', 'g'), '<span class=\"hl-kw\">$1</span>');
    }
  }
  // Functions: word followed by (
  h = h.replace(/\b([a-zA-Z_$][\w$]*)\s*\(/g, '<span class=\"hl-fn\">$1</span>(');
  return h;
}

function renderMarkdown(text) {
  let h = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // If code blocks were pre-processed by processAIResponse, use fixed versions
  if (h.indexOf('\x01FIX') >= 0) {
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Links: [text](url) — only http/https allowed
  h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    h = h.replace(/^### (.+)$/gm,'<h3>$1</h3>'); h = h.replace(/^## (.+)$/gm,'<h2>$1</h2>'); h = h.replace(/^# (.+)$/gm,'<h1>$1</h1>');
    h = h.replace(/\*\*\*(.+?)\*\*\*/g,'<b><i>$1</i></b>'); h = h.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>'); h = h.replace(/\*(.+?)\*/g,'<i>$1</i>');
    h = h.replace(/\n\n/g,'<br><br>'); h = h.replace(/\n/g,'<br>');
    // Restore fixed code blocks
    h = h.replace(/\x01FIX(\d+)\x01/g, (_, i) => {
      const b = _fixedCodeBlocks[+i];
      if (!b) return '';
      const warn = b.warnings.length ? ' ⚠' : '';
      const langLabel = b.lang && b.lang !== 'text' ? `<span class="code-lang">${b.lang}</span>` : '';
      const highlighted = tokenizeCode(b.code, b.lang);
      return `<div class="code-block"><div class="code-bar">${langLabel}<button class="copy-btn" onclick="copyCode(this)">复制</button>${warn}</div><pre><code>${highlighted}</code></pre></div>`;
    });
    return h;
  }
  // Fallback: standard rendering with code block protection
  const blocks = [];
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    blocks.push({ lang, code: code.trim() });
    return '\x01BLK' + (blocks.length - 1) + '\x01';
  });
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Links: [text](url) — only http/https allowed
  h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  h = h.replace(/^### (.+)$/gm,'<h3>$1</h3>'); h = h.replace(/^## (.+)$/gm,'<h2>$1</h2>'); h = h.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  h = h.replace(/\*\*\*(.+?)\*\*\*/g,'<b><i>$1</i></b>'); h = h.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>'); h = h.replace(/\*(.+?)\*/g,'<i>$1</i>');
  h = h.replace(/\n\n/g,'<br><br>'); h = h.replace(/\n/g,'<br>');
  h = h.replace(/\x01BLK(\d+)\x01/g, (_, i) => {
    const b = blocks[+i];
    const langLabel = b.lang ? `<span class="code-lang">${b.lang}</span>` : '';
    const highlighted = tokenizeCode(b.code, b.lang);
    return `<div class="code-block"><div class="code-bar">${langLabel}<button class="copy-btn" onclick="copyCode(this)">复制</button></div><pre><code>${highlighted}</code></pre></div>`;
  });
  return h;
}
// ============ SECURITY CORE ============
// Principle 1-7 enforcement: audit, detect, confirm, log.
const AUDIT_LOG = [];
const RISK_PATTERNS = [
  // Shell commands
  [/\b(rm\s+-rf|sudo\s+|chmod\s+777|mkfs\.|dd\s+if=|:\(\)\s*\{)/gi, '危险Shell命令'],
  [/\b(curl|wget)\s+.*\|\s*(bash|sh|python)/gi, '管道执行下载脚本'],
  [/\b(eval|exec|system|subprocess|os\.system|popen)\s*\(/gi, '代码执行调用'],
  // File destruction
  [/>\s*\/dev\/sd[a-z]|format\s+[c-z]:/gi, '磁盘/分区写入'],
  // Network attacks
  [/\b(nc\s+-[lne]|ncat\s+-[lne]|socat)\b/gi, '网络监听/反弹Shell'],
  [/\b(sqlmap|hydra|nmap|metasploit|msfconsole)\b/gi, '渗透测试工具'],
  // Sensitive paths
  [/(\/etc\/shadow|\/etc\/passwd|C:\\Windows\\System32|\\\\\.\\pipe\\)/gi, '敏感系统路径'],
  // Crypto miners
  [/\b(cryptonight|stratum\+tcp|minerd|cpuminer|xmrig)\b/gi, '挖矿程序'],
];

function auditLog(action, detail, risk) {
  const entry = {
    time: new Date().toISOString(),
    action,
    detail: detail.slice(0, 200),
    risk: risk || 'info'
  };
  AUDIT_LOG.push(entry);
  if (AUDIT_LOG.length > 200) AUDIT_LOG.shift();
  // Principle 6: log to console for debugging
  console.log(`[AUDIT ${entry.risk.toUpperCase()}] ${action}: ${entry.detail}`);
  return entry;
}

function detectRisks(content) {
  const found = [];
  for (const [pattern, label] of RISK_PATTERNS) {
    const matches = content.match(pattern);
    if (matches) {
      found.push({ label, count: matches.length, sample: matches[0].slice(0, 60) });
    }
  }
  return found;
}

// ============ JSON REPAIR ============
// Auto-fix broken JSON without JSON.parse() as primary tool.
// Handles: unquoted keys, single quotes, trailing commas, missing commas, missing brackets.
function repairJSON(raw) {
  let s = raw.trim();
  const fixes = [];
  if (!s) return { json: null, error: '空输入', fixes: [] };

  // 1. Detect + extract JSON structure if embedded in text
  if (s[0] !== '{' && s[0] !== '[') {
    const objStart = s.indexOf('{'), arrStart = s.indexOf('[');
    const start = objStart >= 0 && (arrStart < 0 || objStart < arrStart) ? objStart : arrStart;
    if (start >= 0) { s = s.slice(start); fixes.push('提取JSON结构'); }
  }
  if (s[s.length-1] !== '}' && s[s.length-1] !== ']') {
    const objEnd = s.lastIndexOf('}'), arrEnd = s.lastIndexOf(']');
    const end = Math.max(objEnd, arrEnd);
    if (end > 0) { s = s.slice(0, end + 1); if (!fixes.length) fixes.push('截断尾部'); }
  }

  // 2. Single quotes -> double (state-machine, skip escaped)
  let inDq = false, inSq = false, esc = false, r2 = '';
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (esc) { r2 += ch; esc = false; continue; }
    if (ch === '\\') { r2 += ch; esc = true; continue; }
    if (ch === '"' && !inSq) { inDq = !inDq; r2 += ch; continue; }
    if (ch === "'" && !inDq) { inSq = !inSq; r2 += '"'; continue; }
    r2 += ch;
  }
  if (r2 !== s) { s = r2; fixes.push('单引号→双引号'); }

  // 3. Unquoted keys: {key: -> {"key":
  s = s.replace(/([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:/g, '$1"$2":');
  if (s !== r2) fixes.push('补全键名引号');

  // 4. Trailing commas: ,] -> ]  ,} -> }
  const before = s;
  s = s.replace(/,(\s*[}\]])/g, '$1');
  if (s !== before) fixes.push('移除尾随逗号');

  // 5. Missing commas: "val"\s*"key" -> "val",\n"key"
  s = s.replace(/("\s*\n\s*"{)/g, '",\n$1');
  s = s.replace(/([}\]"'\d])\s*\n\s*([\[{"])(?!")/g, '$1,\n$2');
  if (s !== before) fixes.push('补全缺失逗号');

  // 6. Missing closing brackets
  for (const [o, c] of [['{','}'], ['[',']']]) {
    const open = s.split(o).length - 1, close = s.split(c).length - 1;
    if (open > close) { s += c.repeat(open - close); fixes.push(`补全${c}x${open-close}`); }
    if (close > open) { s = o.repeat(close - open) + s; fixes.push(`补全${o}x${close-open}`); }
  }

  // 7. Strip invisible/BOM
  s = s.replace(/[﻿​]/g, '');

  // 8. Final verify with JSON.parse
  try { JSON.parse(s); return { json: s, error: null, fixes }; }
  catch (e) {
    const pm = (e.message||'').match(/position\s*(\d+)/);
    const pos = pm ? parseInt(pm[1]) : -1;
    let ctx = '';
    if (pos >= 0 && pos < s.length) {
      ctx = s.slice(Math.max(0,pos-30), Math.min(s.length, pos+30));
    }
    return { json: s, error: e.message.split('\n')[0], errorPos: pos, context: ctx, fixes };
  }
}

// ============ AI RESPONSE PROCESSING PIPELINE ============
// 10-step pipeline + JSON repair. Auto-fix on failure.
function processAIResponse(content) {
  _fixedCodeBlocks = [];
  let text = content;
  const allWarnings = [];

  // Skip processing if no code blocks
  if (!text.includes('```')) {
    const risks = detectRisks(content);
    if (risks.length) { auditLog('risk_detect', risks.map(r => r.label).join(','), 'high'); }
    return { content: text, warnings: [], risks };
  }

  // Step 1-2: Extract code blocks with lang
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = _fixedCodeBlocks.length;
    _fixedCodeBlocks.push({ lang: lang || '', code: code.trim(), warnings: [] });
    return '\x01FIX' + idx + '\x01';
  });

  // Step 3: Fix markdown nesting — merge orphan ```
  const strayFences = text.match(/```/g);
  if (strayFences && strayFences.length % 2 !== 0) {
    text = text.replace(/```/g, '`\x60`');
    allWarnings.push('修复未闭合的代码围栏');
  }

  // Step 4: JSON repair for json/jsonc blocks
  _fixedCodeBlocks.forEach((b, i) => {
    let code = b.code;
    if (b.lang === 'json' || b.lang === 'jsonc') {
      const repaired = repairJSON(code);
      if (repaired.error) {
        allWarnings.push(`JSON#${i}: ${repaired.error}`);
        if (repaired.context) allWarnings.push(`  …${repaired.context}…`);
      }
      if (repaired.fixes.length) {
        code = repaired.json || code;
        allWarnings.push(`JSON#${i} 修复: ${repaired.fixes.join(', ')}`);
      }
    }

    // Step 5: Quote pairing check
    const dqOpen = (code.match(/(?<!\\)"/g) || []).length;
    const sqOpen = (code.match(/(?<!\\)'/g) || []).length;
    const btOpen = (code.match(/`/g) || []).length;
    if (btOpen % 2 !== 0) { code += '`'; b.warnings.push('补全反引号'); }
    if (['js','javascript','ts','typescript','json'].includes(b.lang)) {
      if (dqOpen % 2 !== 0) { code += '"'; b.warnings.push('补全双引号'); }
      if (sqOpen % 2 !== 0) { code += "'"; b.warnings.push('补全单引号'); }
    }

    // Step 6: Bracket pairing
    for (const [o, c] of [['(',')'], ['[',']'], ['{','}']]) {
      const open = code.split(o).length - 1;
      const close = code.split(c).length - 1;
      if (open !== close) {
        const diff = open - close;
        if (diff > 0) code += c.repeat(diff);
        else code = o.repeat(-diff) + code;
        if (Math.abs(diff) <= 3) b.warnings.push(`${o}${c}补全x${Math.abs(diff)}`);
      }
    }

    // Step 7: HTML tag closure check
    const htmlTags = code.match(/<\/?(\w+)[^>]*>/g) || [];
    const tagStack = [];
    for (const tag of htmlTags) {
      const closeM = tag.match(/<\/(\w+)>/);
      const openM = tag.match(/<(\w+)[^>]*>/);
      if (closeM) {
        if (tagStack.length && tagStack[tagStack.length-1] === closeM[1]) tagStack.pop();
      } else if (openM && !/^(br|hr|img|input|meta|link)$/i.test(openM[1])) {
        tagStack.push(openM[1]);
      }
    }
    if (tagStack.length) {
      b.warnings.push(`HTML标签未闭合: ${tagStack.join(', ')}`);
    }

    // Step 8: JS syntax check (static — no code execution)
    if (['js','javascript'].includes(b.lang.toLowerCase())) {
      const jsIssues = [];
      // Check for obvious problems without executing
      const lines = code.split('\n');
      let openBraces = 0, openParens = 0, openBrackets = 0;
      for (let li = 0; li < lines.length; li++) {
        const l = lines[li];
        openBraces += (l.match(/{/g) || []).length - (l.match(/}/g) || []).length;
        openParens += (l.match(/\(/g) || []).length - (l.match(/\)/g) || []).length;
        openBrackets += (l.match(/\[/g) || []).length - (l.match(/\]/g) || []).length;
        // Check for infinite loop pattern
        if (/while\s*\(\s*true\s*\)/.test(l) || /for\s*\(\s*;\s*;\s*\)/.test(l)) {
          jsIssues.push(`L${li+1}: 疑似无限循环`);
        }
      }
      if (openBraces !== 0) jsIssues.push(`花括号未闭合 (差${openBraces})`);
      if (openParens !== 0) jsIssues.push(`圆括号未闭合 (差${openParens})`);
      if (openBrackets !== 0) jsIssues.push(`方括号未闭合 (差${openBrackets})`);
      if (jsIssues.length) b.warnings.push(...jsIssues);
    }

    // Step 9: CSS syntax check
    if (b.lang.toLowerCase() === 'css') {
      try {
        const sheet = new CSSStyleSheet();
        sheet.replaceSync(code);
      } catch(e) {
        b.warnings.push(`CSS: ${e.message.split('\n')[0].slice(0,60)}`);
      }
    }

    // Collect warnings
    if (b.warnings.length) {
      allWarnings.push(`代码块#${i}: ${b.warnings.join('; ')}`);
    }
    _fixedCodeBlocks[i].code = code;
    _fixedCodeBlocks[i].warnings = b.warnings;
  });

  // Step 10: Risk detection on full content (Principle 4)
  const risks = detectRisks(content);
  if (risks.length) {
    allWarnings.push(`⚠ 风险检测: ${risks.map(r => `${r.label}(${r.count})`).join(', ')}`);
    auditLog('risk_detect', risks.map(r => r.label).join(','), 'high');
  }

  // Principle 6: audit all processing
  auditLog('pipeline', `${_fixedCodeBlocks.length} blocks, ${allWarnings.length} warnings`);

  return { content: text, warnings: allWarnings, risks };
}

function copyCode(btn) {
  const pre = btn.closest('.code-block')?.querySelector('pre code');
  if (!pre) return;
  const code = pre.textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = '已复制!'; setTimeout(() => { btn.textContent = '复制'; }, 1500);
  }).catch(() => {
    const ta = document.createElement('textarea'); ta.value = code; ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
    btn.textContent = '已复制!'; setTimeout(() => { btn.textContent = '复制'; }, 1500);
  });
}
const _ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function escapeHtml(s) { return s.replace(/[&<>"']/g, c => _ESC[c]); }
function safeAttr(v) { return String(v).replace(/['"<>&]/g, c => c === "'" ? "\\'" : _ESC[c]); }
function setStatus(txt, type) { const el = document.getElementById('status-text'); el.textContent = txt; el.className = type||''; }

function showChat() {
  document.getElementById('welcome').classList.add('hidden');
  document.getElementById('chat').classList.add('active');
}
function hideChat() {
  document.getElementById('welcome').classList.remove('hidden');
  document.getElementById('chat').classList.remove('active');
  document.getElementById('chat').innerHTML = '';
}

function scrollChat() { const c = document.getElementById('chat'); c.scrollTop = c.scrollHeight; }

function addMessage(role, content, opts={}) {
  showChat();
  const { rawResponse, thinking, searchResults } = opts;
  const d = document.createElement('div'); d.className = `msg ${role}`;
  // Role tag
  const roleLabels = { user: '👤 用户', assistant: '🤖 AI', tool: '🔧 工具执行' };
  const label = roleLabels[role] || '';
  let ex = '';
  if (label) ex += `<div class="role-tag">${label}${role==='assistant'?' <span style=\"cursor:pointer;font-size:12px;\" onclick=\"readAloud(this.parentElement.parentElement)\" title=\"朗读\">🔊</span>':''}</div>`;
  if (searchResults && searchResults.length) {
    const engines = [...new Set(searchResults.map(r => r.engine || '').filter(Boolean))];
    ex += `<div class="search-block"><div class="search-header" onclick="togBlock(this)"><span class="arrow">▶</span> 搜索结果 · ${searchResults.length}条 ${engines.length ? `(${engines.join(' + ')})` : ''}</div><div class="search-content">${searchResults.map(r => `<div class="search-item"><div class="t">${escapeHtml(r.title)} ${r.engine ? `<span style="font-size:9px;padding:1px 5px;border-radius:4px;background:var(--chip-bg);color:var(--text-dim);">${escapeHtml(r.engine)}</span>` : ''}</div>${r.url?`<span class="u">${escapeHtml(r.url)}</span>`:''}<div class="s">${escapeHtml(r.snippet||'')}</div></div>`).join('')}</div></div>`;
  }
  if (thinking) ex += `<div class="think-block"><div class="think-header" onclick="togBlock(this)"><span class="arrow">▶</span> 思考过程 <span class="think-badge">V4 Pro</span></div><div class="think-content">${escapeHtml(thinking)}</div></div>`;
  // All assistant content goes through processing pipeline (Principle 2-3-4)
  let processedWarnings = [], processedRisks = [];
  if (role === 'assistant' && content) {
    const processed = processAIResponse(content);
    content = processed.content;
    processedWarnings = processed.warnings || [];
    processedRisks = processed.risks || [];
  }
  let riskHTML = '';
  if (processedRisks.length) {
    riskHTML = `<div style="margin-top:6px;padding:6px 10px;border-radius:6px;background:#ff000018;border:1px solid var(--danger);font-size:10px;color:var(--danger);">🚫 安全警告: ${processedRisks.map(r=>`${r.label}`).join(' | ')}<br><small>原则5: 高风险操作已在管线中拦截，代码未执行</small></div>`;
  }
  d.innerHTML = `<div class="avatar">${role==='user'?'👤':'AI'}</div><div class="msg-body">${ex}<div class="bubble">${role==='assistant'?renderMarkdown(content):escapeHtml(content)}</div>${rawResponse?`<div class="msg-extra"><span class="raw-toggle" onclick="this.nextElementSibling.classList.toggle('show')">查看原始返回 ▾</span><div class="raw-output">${escapeHtml(JSON.stringify(rawResponse,null,2))}</div></div>`:''}${riskHTML}${processedWarnings.length?`<div style="margin-top:6px;font-size:10px;color:var(--warn);">⚠ 管线: ${processedWarnings.join(' | ')}</div>`:''}</div>`;
  document.getElementById('chat').appendChild(d); scrollChat();
}
function togBlock(h) { const c = h.nextElementSibling, a = h.querySelector('.arrow'); c.classList.toggle('show'); a.classList.toggle('open'); }
function addTypingIndicator(text) { showChat(); const d = document.createElement('div'); d.className='msg assistant'; d.id='typing-indicator'; d.innerHTML=`<div class="avatar">AI</div><div class="msg-body"><div class="bubble">${text||'<div class="typing"><span></span><span></span><span></span></div>'}</div></div>`; document.getElementById('chat').appendChild(d); scrollChat(); }
function removeTypingIndicator() { const el = document.getElementById('typing-indicator'); if (el) el.remove(); }
function clearChat() {
  document.getElementById('chat').innerHTML = '';
  document.getElementById('chat').classList.remove('active');
  document.getElementById('welcome').classList.remove('hidden');
  chatHistory = []; pendingUploads = []; renderPendingChips();
  try { localStorage.removeItem('portable_autosave'); } catch(e) {}
  savedChats = savedChats.filter(c => c.id !== AUTO_CHAT_ID);
  saveChats(); renderChats();
}
function newConversation() {
  // Save current auto-save as permanent entry
  let last = null;
  try { last = JSON.parse(localStorage.getItem('portable_autosave')); } catch(e) {}
  if (!last || !last.messages) last = savedChats.find(c => c.isAuto);
  if (last && last.messages && last.messages.length >= 2) {
    const savedId = 'c_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    last.id = savedId; last.isAuto = false;
    savedChats.push(JSON.parse(JSON.stringify(last)));
    saveChats();
  }
  // Clear for fresh start
  document.getElementById('chat').innerHTML = '';
  document.getElementById('chat').classList.remove('active');
  document.getElementById('welcome').classList.remove('hidden');
  chatHistory = []; pendingUploads = []; renderPendingChips();
  try { localStorage.removeItem('portable_autosave'); } catch(e) {}
  saveChats(); renderChats();
  if (window.innerWidth <= 768 && sidebarOpen) toggleSidebar();
  setStatus('已新建对话', 'success');
  document.getElementById(window.innerWidth <= 768 ? 'welcome-input' : 'user-input').focus();
}

// ============ WEB SEARCH ============
async function performWebSearch(query) {
  const sUrl = getSearchUrl();
  // Server mode: multi-engine search (DDG + Bing + Baidu)
  if (sUrl) {
    try {
      const r = await fetch(sUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, num: 10 }) });
      if (r.ok) { const d = await r.json(); return d.results || []; }
    } catch (e) {}
  }
  // Direct mode: DDG Instant Answer API only (CORS limitation)
  try {
    const r = await fetch(`https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1&skip_disambig=1`);
    if (r.ok) {
      const d = await r.json(); const res = [];
      if (d.AbstractText) res.push({ title: d.Heading || query, url: d.AbstractURL || '', snippet: d.AbstractText, engine: 'DuckDuckGo' });
      if (d.RelatedTopics) { for (const t of d.RelatedTopics) { if (t.Text && res.length < 5) res.push({ title: t.FirstURL ? t.FirstURL.split('/').pop().replace(/_/g, ' ') : query, url: t.FirstURL || '', snippet: t.Text, engine: 'DuckDuckGo' }); } }
      if (!res.length) return await scrapeDDG(query); return res;
    }
  } catch (e) { return await scrapeDDG(query); }
  return [];
}
async function scrapeDDG(query) {
  try {
    const r = await fetch(`https://lite.duckduckgo.com/lite/?q=${encodeURIComponent(query)}`); if (!r.ok) return [];
    const h = await r.text(); const rows = h.split(/<tr[^>]*>/i); const res = []; let idx = 0;
    for (const row of rows) {
      if (idx >= 5) break;
      const lm = /<a\s[^>]*href="(https?:\/\/[^"]+)"[^>]*>\s*([^<]{5,200}?)\s*<\/a>/i.exec(row);
      if (lm) {
        if (/(duckduckgo\.com|twitter\.com\/intent|facebook\.com\/sharer)/i.test(lm[1])) continue;
        const t = lm[2].replace(/<[^>]+>/g, '').trim(); if (t.length < 5) continue;
        const sm = /<td[^>]*class="[^"]*result-snippet[^"]*"[^>]*>([\s\S]*?)<\/td>/i.exec(row);
        res.push({ title: t, url: lm[1], snippet: sm ? sm[1].replace(/<[^>]+>/g, '').trim().substring(0, 400) : '', engine: 'DuckDuckGo' });
        idx++;
      }
    }
    return res;
  } catch (e) { return []; }
}

// ============ SEND ============
async function doSend(content) {

  if (isProcessing) return;
  // Safety net: force reset after 60s no matter what
  const safetyTimer = setTimeout(() => {
    isProcessing = false;
    document.getElementById('send-btn').disabled = false;
    setToggleRunning(false); updateChips();
    setStatus('超时恢复', 'error');
  }, 60000);
  const apiKey = document.getElementById('api-key').value.trim();
  if (!apiKey) { setStatus('请先点击 ⚙ 设置 API Key','error'); openSettings(); return; }

  let model = document.getElementById('model-select').value;
  if (deepThinkOn) { model = 'deepseek-v4-pro'; document.getElementById('model-select').value = model; }

  // Auto-trigger handled by input debounce; Enter bypasses it
  if (!webSearchOn && TIME_SENSITIVE.test(content)) {
    webSearchOn = true;
    toggleWebSearch();
    setStatus('检测到实时关键词，自动开启联网搜索','');
  }

  isProcessing = true;
  document.getElementById('send-btn').disabled = true;
  setToggleRunning(true); setStatus('处理中…',''); updateChips();

  addMessage('user', content);
  chatHistory.push({ role:'user', content });

  // Agent status indicator — tool execution card
  let toolCard = null, toolSteps = [];
  function showToolCard() {
    if (toolCard) return toolCard;
    showChat();
    toolCard = document.createElement('div'); toolCard.className = 'msg tool';
    toolCard.innerHTML = '<div class="tool-card"><div class="tool-icon">🔧</div><div class="tool-body"></div></div>';
    document.getElementById('chat').appendChild(toolCard);
    toolSteps = [];
    return toolCard;
  }
  function addToolStep(icon, text, cls) {
    const card = showToolCard();
    const body = card.querySelector('.tool-body');
    const step = document.createElement('div'); step.className = `step ${cls||''}`;
    step.innerHTML = `<span class="step-icon">${icon}</span>${text}`;
    body.appendChild(step);
    toolSteps.push({ icon, text, cls });
    scrollChat();
  }
  function finishToolCard(status) {
    if (toolCard) {
      const icon = toolCard.querySelector('.tool-icon');
      icon.textContent = status === 'ok' ? '✅' : '⚠️';
      if (status !== 'ok') toolCard.querySelector('.tool-card').style.borderColor = 'var(--danger)';
    }
  }
  function closeToolCard() {
    if (toolCard) { toolCard.remove(); toolCard = null; }
    toolSteps = [];
  }

  let searchResults = null, ragContext = '';
  if (webSearchOn) {
    if (!serverAvailable && isServerMode()) {
      setStatus('⚠ 服务器无响应，搜索不可用','error');
      addMessage('assistant', '⚠️ 搜索服务不可用\n\n请双击运行 **启动服务器模式.bat** 启动本地服务器。\n\n服务器提供：Sogou + Bing + DDG 多引擎搜索 + 页面全文抓取。');
      isProcessing = false; document.getElementById('send-btn').disabled = false;
      setToggleRunning(false); updateChips(); return;
    }
    if (!isServerMode()) {
      setStatus('⚠ 直连模式搜索受限（仅DDG），建议启动服务器模式','error');
    }
    // RAG pipeline: single /api/rag call (search → fetch → compress)
    if (isServerMode() && serverAvailable) {
      addToolStep('🔍', 'RAG检索中…');
      try {
        const rr = await fetch('/api/rag', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:content, num:8, fetch:3, maxChars:4000}) });
        if (rr.ok) { const rd = await rr.json(); ragContext = rd.context || ''; searchResults = rd.searchResults || []; }
      } catch(e) {}
      addToolStep(searchResults && (searchResults && searchResults.length) ? '✅' : '⚠️', searchResults && (searchResults && searchResults.length) ? `搜索完成 · ${searchResults.length}条` : '搜索无结果', (searchResults && searchResults.length ? "done" : "err"));
finishToolCard((searchResults && searchResults.length) ? 'ok' : 'warn');
    } else {
      addToolStep('🔍', '直连搜索中…');
      try { searchResults = await performWebSearch(content); } catch(e) { searchResults = []; }
      addToolStep(searchResults && (searchResults && searchResults.length) ? '✅' : '⚠️', searchResults && (searchResults && searchResults.length) ? `搜索完成 · ${searchResults.length}条` : '搜索无结果', (searchResults && searchResults.length ? "done" : "err"));
      finishToolCard((searchResults && searchResults.length) ? 'ok' : 'warn');
    }
    // No results: skip AI call, show clear message
    if (webSearchOn && (!searchResults || !searchResults.length) && !ragContext) {
      addToolStep('❌', '搜索无结果', 'err'); finishToolCard('err');
    }
    // If web search was on but returned nothing at all, skip AI call

  addTypingIndicator();
  try {
    const apiUrl = getApiUrl(), apiHeaders = getApiHeaders(apiKey);
    const today = new Date();
    const todayStr = `${today.getFullYear()}年${today.getMonth()+1}月${today.getDate()}日（周${'日一二三四五六'[today.getDay()]}）`;
    let sysP = `今天是${todayStr}。`;
    if (currentDomain && DOMAIN_PROMPTS[currentDomain]) {
      sysP += '\n\n' + DOMAIN_PROMPTS[currentDomain];
    if (ragContext || (searchResults && searchResults.length)) {
      sysP += '

以下是最新搜索到的信息，直接基于这些内容回答。引用时标注[来源X]。';
    } else {
      sysP += '

请用你的知识回答。如果涉及实时数据（开奖/比分/天气/股价等），建议稍后开启联网搜索重试。今天是' + todayStr + '。';
    }
    } else {
      sysP += '

请用你的知识回答。如果涉及实时数据（开奖/比分/天气/股价等），建议稍后开启联网搜索重试。今天是' + todayStr + '。';
    }
    if (ragContext) {
      sysP += '\n\n===== RAG检索上下文 =====\n' + ragContext + '===== 上下文结束 =====';
    } else if (searchResults && searchResults.length) {
      sysP += '\n\n--- 搜索摘要 ---\n'+searchResults.map((r,i)=>`[${i+1}] ${r.title}\n${r.snippet}`).join('\n');
    }
    if (pendingUploads.length > 0) { sysP += '\n\n===== 用户上传的文件 ====='; pendingUploads.forEach(p => { sysP += `\n--- ${p.name} ---\n${p.content.substring(0, 8000)}\n`; }); sysP += '===== 文件结束 ====='; }
    if (activeMemIds.size > 0) {
      const activeMems = memories.filter(m => activeMemIds.has(m.id));
      if (activeMems.length) { sysP += '\n\n===== 项目记忆（优先参考）====='; activeMems.forEach(m => { sysP += `\n--- ${m.title} ---\n${m.content.substring(0, 4000)}\n`; }); sysP += '===== 记忆结束 ====='; }
    }

    // Streaming: create message bubble early, append chunks as they arrive
    removeTypingIndicator();
    showChat();
    const msgDiv = document.createElement('div'); msgDiv.className = 'msg assistant';
    const bubble = document.createElement('div'); bubble.className = 'bubble';
    bubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
    msgDiv.innerHTML = '<div class="avatar">AI</div><div class="msg-body"></div>';
    msgDiv.querySelector('.msg-body').appendChild(bubble);
    document.getElementById('chat').appendChild(msgDiv); scrollChat();

    let fullReply = '', fullThinking = '';
    const isStreamCapable = isServerMode() && serverAvailable;
    const endpoint = isStreamCapable ? getApiUrl().replace('/api/deepseek','/api/deepseek/stream') : getApiUrl();
    const body = JSON.stringify({model,messages:[{role:'system',content:sysP},...chatHistory],temperature:0.7,max_tokens:4096,stream:isStreamCapable});

    if (isStreamCapable) {
      try {
        const resp = await fetch(endpoint, { method:'POST', headers:apiHeaders, body });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let streamDone = false, displayed = 0;
        addToolStep('🤖', 'AI生成中…');
        // Simple reliable typewriter: show new chars every ~30ms
        window._twInterval = setInterval(() => {
          if (displayed >= fullReply.length) {
            if (streamDone) {
              clearInterval(window._twInterval);
              bubble.innerHTML = (fullThinking ? `<div class="think-block"><div class="think-header" onclick="togBlock(this)"><span class="arrow open">▶</span> 思考过程</div><div class="think-content show">${escapeHtml(fullThinking)}</div></div>`:'') + renderMarkdown(fullReply);
              setStatus('完成 · 流式','success'); finishToolCard('ok'); closeToolCard();
            }
            return;
          }
          displayed = Math.min(displayed + 3, fullReply.length);
          const visible = fullReply.slice(0, displayed);
          bubble.innerHTML = (fullThinking ? `<div class="think-block"><div class="think-header" onclick="togBlock(this)"><span class="arrow">▶</span> 思考中…</div><div class="think-content show">${escapeHtml(fullThinking)}</div></div>`:'') + renderMarkdown(visible) + '<span class="typing"><span></span><span></span><span></span></span>';
          scrollChat();
        }, 30);
        // Stream reader: accumulate into fullReply
        let sseBuf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) { streamDone = true; break; }
          sseBuf += decoder.decode(value, {stream: true});
          const lines = sseBuf.split('\n'); sseBuf = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const d = line.slice(6).trim();
            if (d === '[DONE]') { streamDone = true; break; }
            try { const ch = JSON.parse(d); const delta = ch.choices?.[0]?.delta||{};
              if (delta.content) fullReply += delta.content;
              if (delta.reasoning_content) fullThinking += delta.reasoning_content;
            } catch(e) {}
          }
        }
        // Wait max 10s for tick to finish rendering
        let waited = 0;
        while (displayed < fullReply.length && waited < 10000) {
          await new Promise(r => setTimeout(r, 100)); waited += 100;
        }
        clearInterval(window._twInterval);
        if (fullReply) { bubble.innerHTML = (fullThinking ? `<div class="think-block"><div class="think-header" onclick="togBlock(this)"><span class="arrow open">▶</span> 思考过程</div><div class="think-content show">${escapeHtml(fullThinking)}</div></div>`:'') + renderMarkdown(fullReply); }
      } catch(err) { bubble.innerHTML = `❌ ${err.message}`; setStatus('流式失败','error'); closeToolCard(); }
    } else {
      try {
        const resp = await fetch(endpoint, { method:'POST', headers:apiHeaders, body });
        const data = await resp.json();
        if (!resp.ok) { bubble.innerHTML = `❌ API错误: ${data.error?.message||resp.status}`; }
        else {
          const msg = data.choices?.[0]?.message||{};
          fullReply = msg.content||'(无内容)'; fullThinking = msg.reasoning_content||'';
          bubble.innerHTML = renderMarkdown(fullReply);
          setStatus('完成','success');
        }
      } catch(err) { bubble.innerHTML = `❌ ${err.message}`; setStatus('网络错误','error'); }
      closeToolCard();
    }
    if (fullReply) { chatHistory.push({role:'assistant',content:fullReply}); autoSaveCurrentChat(); }
  } catch(err) {
    setStatus(`网络错误: ${err.message}`,'error');
    addMessage('assistant',`❌ 请求失败\n\n**${err.message}**`,{searchResults});
  }



  // Guaranteed cleanup — every exit path reaches here
  closeToolCard();
  clearInterval(window._twInterval);  // safety: kill typewriter interval
  pendingUploads = []; renderPendingChips();
  clearTimeout(safetyTimer);
  isProcessing = false;
  document.getElementById('send-btn').disabled = false;
  document.getElementById('user-input').focus();
  setToggleRunning(false); updateChips();
}

function sendMessage() {
  const input = document.getElementById('user-input');
  const content = input.value.trim();
  if (!content) return;
  input.value = '';
  doSend(content);
}

// ============ VOICE INPUT ============
let voiceListening = false, recognition = null;
function toggleVoice() {
  const btn = document.getElementById('voice-btn');
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    setStatus('浏览器不支持语音输入','error'); return;
  }
  if (voiceListening) { recognition && recognition.stop(); return; }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR(); recognition.lang = 'zh-CN'; recognition.interimResults = false; recognition.continuous = false;
  recognition.onstart = () => { voiceListening = true; btn.style.background = 'var(--danger)'; btn.style.color = '#fff'; setStatus('🎤 正在聆听…',''); };
  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    document.getElementById('user-input').value += text;
  };
  recognition.onend = () => { voiceListening = false; btn.style.background = ''; btn.style.color = ''; };
  recognition.onerror = (e) => { voiceListening = false; btn.style.background = ''; btn.style.color = ''; setStatus('语音错误: '+e.error,'error'); };
  recognition.start();
}

// ============ READ ALOUD ============
function readAloud(msgDiv) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const text = msgDiv.querySelector('.bubble')?.textContent || '';
  if (!text) return;
  const u = new SpeechSynthesisUtterance(text.slice(0, 2000));
  u.lang = 'zh-CN'; u.rate = 1.1; u.pitch = 1.0;
  speechSynthesis.speak(u);
}

// ============ EXPORT CHAT ============
function exportChat() {
  if (!chatHistory.length) { setStatus('无对话可导出','error'); return; }
  let md = `# USB-AI 对话记录\n\n> ${new Date().toLocaleString()}\n\n`;
  for (const m of chatHistory) {
    md += `### ${m.role === 'user' ? '👤 用户' : '🤖 AI'}\n\n${m.content}\n\n---\n\n`;
  }
  const blob = new Blob([md], {type:'text/markdown'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `chat_${new Date().toISOString().slice(0,10)}.md`;
  a.click(); URL.revokeObjectURL(a.href);
  setStatus('对话已导出','success');
}

// ============ KEYBOARD SHORTCUTS ============
document.addEventListener('keydown', e => {
  if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); sendMessage(); }
  if (e.ctrlKey && e.key === 'k') { e.preventDefault(); clearChat(); }
  if (e.ctrlKey && e.key === 's') { e.preventDefault(); webSearchOn = !webSearchOn; toggleWebSearch(); }
  if (e.ctrlKey && e.key === 'e') { e.preventDefault(); exportChat(); }
});

function sendWelcome() {
  const input = document.getElementById('welcome-input');
  const content = input.value.trim();
  if (!content) return;
  input.value = '';
  doSend(content);
}

// ============ SEARCH DEBOUNCE ============
let _debounceTimer = null;
function setupDebounce(inputEl) {
  inputEl.addEventListener('input', () => {
    clearTimeout(_debounceTimer);
    if (webSearchOn || isProcessing) return;
    const val = inputEl.value.trim();
    if (TIME_SENSITIVE.test(val)) {
      _debounceTimer = setTimeout(() => {
        if (!webSearchOn && !isProcessing) {
          webSearchOn = true; document.getElementById('chip-search').classList.add('on-search'); updateChips();
          setStatus('检测到实时关键词，自动开启联网搜索','');
        }
      }, 1000);
    }
  });
  // Enter clears debounce and sends immediately
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      clearTimeout(_debounceTimer);
    }
  });
}

// ============ EVENT BINDINGS ============
(function init() {
  try {
    const ui = document.getElementById('user-input');
    if (ui) {
      setupDebounce(ui);
      ui.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} });
      ui.addEventListener('paste', e => {
        const pasted = (e.clipboardData || window.clipboardData).getData('text');
        if (!pasted) return;
        const lines = pasted.split('\n');
        const hasCode = (lines.length > 3 && lines.some(l => l.startsWith('    ')||l.startsWith('\t'))) || (/[{}();]/.test(pasted) && lines.length >= 3);
        if (hasCode) { e.preventDefault(); ui.value += '\`\`\`\n' + pasted + '\n\`\`\`'; }
      });
    }
    const wi = document.getElementById('welcome-input');
    if (wi) {
      setupDebounce(wi);
      wi.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendWelcome();} });
      wi.addEventListener('paste', e => {
        const pasted = (e.clipboardData || window.clipboardData).getData('text');
        if (!pasted) return;
        const lines = pasted.split('\n');
        if ((lines.length > 3 && lines.some(l => l.startsWith('    ')||l.startsWith('\t'))) || (/[{}();]/.test(pasted) && lines.length >= 3)) {
          e.preventDefault(); wi.value += '\`\`\`\n' + pasted + '\n\`\`\`';
        }
      });
    }
    const ak = document.getElementById('api-key'); if (ak) ak.addEventListener('change', saveConfig);
    const ms = document.getElementById('model-select'); if (ms) ms.addEventListener('change', saveConfig);
    setStatus('就绪 · 点击 ⚙ 配置 API Key','');
  } catch(e) {
    document.body.innerHTML = '<div style="padding:40px;text-align:center;"><h2>启动失败</h2><p style="color:red;">' + escapeHtml(e.message) + '</p></div>';
  }
})();
