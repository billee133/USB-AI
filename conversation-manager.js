// ====== ConversationManager v3 ======
// Single source of truth for all conversation state.
// Storage: portable_chats (history) + portable_autosave (crash recovery only)
class ConversationManager {
  constructor() {
    this._chats = [];
    this._currentId = null;
    this._load();
  }

  // ====== Persistence ======
  _checkStorage(){
    try{const k='__test__';localStorage.setItem(k,k);localStorage.removeItem(k);return true}catch(e){return false}
  }
  _load() {
    if(!this._checkStorage()){console.warn('[CM] localStorage blocked — history disabled');this._chats=[];return}
    try { this._chats = JSON.parse(localStorage.getItem('portable_chats') || '[]'); }
    catch(e) { this._chats = []; }
    if (!Array.isArray(this._chats)) this._chats = [];
  }
  _save() {
    if(!this._checkStorage())return;
    const seen = new Set();
    this._chats = this._chats.filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true; });
    try { localStorage.setItem('portable_chats', JSON.stringify(this._chats)); } catch(e) {}
  }
  _recoverySave() {
    if(!this._checkStorage())return;
    const c = this._getById(this._currentId);
    if (c) try { localStorage.setItem('portable_autosave', JSON.stringify(c)); } catch(e) {}
  }

  // ====== Helpers ======
  _now() { return Date.now(); }
  _id() { return 'chat_' + this._now() + '_' + Math.random().toString(36).slice(2,8); }
  _getById(id) { return this._chats.find(c => c.id === id); }
  _dbg(action) { console.log('[CM]', action, 'currentId=' + this._currentId, 'chats=' + this._chats.length); }

  // ====== API ======

  /** Create new conversation. Returns chatId. */
  createConversation(title) {
    const id = this._id();
    const entry = { id, title: title || '新对话', createdAt: this._now(), updatedAt: this._now(), messages: [] };
    this._chats.push(entry);
    this._currentId = id;
    this._save();
    this._dbg('create');
    return id;
  }

  /** Append a message to current conversation. Auto-creates if needed. */
  appendMessage(role, content) {
    if (!this._currentId) this.createConversation(content.slice(0, 40));
    const c = this._getById(this._currentId);
    if (!c) return;
    c.messages.push({ role, content });
    c.updatedAt = this._now();
    if (role === 'user' && c.messages.length <= 2) c.title = content.slice(0, 40);
    this._save();
    this._recoverySave();
  }

  /** Update conversation title */
  updateTitle(chatId, title) {
    const c = this._getById(chatId);
    if (c) { c.title = title; c.updatedAt = this._now(); this._save(); }
  }

  /** Delete conversation by ID */
  deleteConversation(chatId) {
    this._chats = this._chats.filter(c => c.id !== chatId);
    if (this._currentId === chatId) this._currentId = null;
    this._save();
    this._dbg('delete');
  }

  /** Load conversation messages. Returns messages array or null. */
  loadConversation(chatId) {
    const c = this._getById(chatId);
    if (!c) return null;
    // Save current before switching
    if (this._currentId && this._currentId !== chatId) {
      const cur = this._getById(this._currentId);
      if (cur && cur.messages.length >= 2) { cur.updatedAt = this._now(); this._save(); }
    }
    this._currentId = chatId;
    this._dbg('load');
    return JSON.parse(JSON.stringify(c.messages));
  }

  /** Get current conversation state */
  getCurrentConversation() {
    if (!this._currentId) return null;
    const c = this._getById(this._currentId);
    return c ? { id: c.id, title: c.title, messages: c.messages } : null;
  }

  /** Set current conversation by ID */
  setCurrentConversation(chatId) {
    if (this._getById(chatId)) this._currentId = chatId;
  }

  /** Get all conversations sorted by updatedAt desc */
  getAllConversations() {
    return [...this._chats].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  }

  /** Start a new conversation (appears in sidebar immediately, survives refresh) */
  newConversation() {
    const id = this._id();
    const entry = { id, title: '新对话', createdAt: this._now(), updatedAt: this._now(), messages: [] };
    this._chats.push(entry);
    this._currentId = id;
    this._save();
    this._recoverySave();  // Overwrite autosave so refresh doesn't restore old chat
    this._dbg('new');
    return id;
  }

  /** Auto-restore last session after page refresh */
  autoRestore() {
    if(!this._checkStorage())return null;
    try {
      const saved = JSON.parse(localStorage.getItem('portable_autosave'));
      if (saved && saved.id && saved.messages) {
        // Ensure restored chat is in history
        const existing = this._getById(saved.id);
        if (!existing) this._chats.push(saved);
        else { existing.messages = saved.messages; existing.updatedAt = this._now(); }
        this._currentId = saved.id;
        this._save();
        this._dbg('restore');
        return saved;
      }
    } catch(e) {}
    return null;
  }

  /** Clear current conversation (trash button) */
  clearCurrent() {
    if (this._currentId) {
      this._chats = this._chats.filter(c => c.id !== this._currentId);
      this._currentId = null;
      this._save();
      try { localStorage.removeItem('portable_autosave'); } catch(e) {}
    }
  }

  // ====== Sidebar Rendering ======

  /** Render sidebar chat list into container element */
  renderSidebar(container, onSelect, onDelete) {
    const chats = this.getAllConversations();
    if (!chats.length) {
      container.innerHTML = '<div style="padding:24px;text-align:center;font-size:12px;color:var(--txd)">暂无历史对话</div>';
      return;
    }
    container.innerHTML = chats.map(c => {
      const title = (c.title || '新对话').slice(0, 40);
      // Escape for HTML attribute safety
      const esc = (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
      return '<div class="ci" onclick="' + (onSelect || 'CM_select') + "('" + c.id + '\')"><span style="font-size:14px">💬</span><span class="t">' + esc(title) + '</span><span class="x" onclick="event.stopPropagation();' + (onDelete || 'CM_delete') + "('" + c.id + '\')">×</span></div>';
    }).join('');
  }
}

// Global instance
const CM = new ConversationManager();
