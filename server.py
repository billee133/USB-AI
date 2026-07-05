#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USB-AI — 本地服务器
解决浏览器直接打开HTML时的跨域(CORS)问题
启动后访问: http://localhost:8082
"""
import http.server
import json
import urllib.request
import urllib.error
import urllib.parse
import os
import sys
import re
import html as html_mod
import sqlite3
import threading
import concurrent.futures
import hashlib
import base64 as _b64
import time

# Performance flag: numpy available for IDF computation?
try:
    import numpy as np
    has_numpy = True
except ImportError:
    has_numpy = False
    import math as np  # Fallback: math.log, math.exp work as numpy equivalents for scalars

PORT = 8082

# ============ Engine Health Tracker ============
_ENGINE_FAILS = {'DDG': 0, 'Bing': 0, 'Sogou': 0, 'SearXNG': 0}
_ENGINE_FAIL_THRESHOLD = 3
_ENGINE_LOCK = threading.Lock()

# SearXNG self-hosted search config
_SEARXNG_URL = "http://127.0.0.1:8888"  # Default SearXNG for Windows port
_SEARXNG_TIMEOUT = 8

def _engine_ok(name):
    with _ENGINE_LOCK:
        return _ENGINE_FAILS.get(name, 0) < _ENGINE_FAIL_THRESHOLD

def _engine_success(name):
    with _ENGINE_LOCK:
        _ENGINE_FAILS[name] = 0

def _engine_fail(name):
    with _ENGINE_LOCK:
        _ENGINE_FAILS[name] = _ENGINE_FAILS.get(name, 0) + 1
        if _ENGINE_FAILS[name] == _ENGINE_FAIL_THRESHOLD:
            print(f"  [ENGINE] {name} disabled after {_ENGINE_FAIL_THRESHOLD} consecutive failures")

# ============ Search Constants ============
JUNK_DOMAINS = ['baike.baidu.com','baike.sogou.com','zh.wikipedia.org','hanyuguoxue.com','chagushici.com','zidian.gushici.net','shidianguji.com','zdic.net','cidian.com','jinyici.com','fangfahui.com','qjyule.com','zhihu.com/topic']
DIRECT_ENGINES = {'GoldAPI','OpenER','OpenMeteo','Wikipedia','GoogleNews','BingNews','Kitco','00038'}
# Domains blocked by anti-bot — skip fetch, use search snippet directly
SNIPPET_ONLY_DOMAINS = {'zhihu.com','zhuanlan.zhihu.com','thepaper.cn','dw.com','baijiahao.baidu.com','tieba.baidu.com','wenku.baidu.com','zhidao.baidu.com'}
# Accessible Chinese news domains for targeted search (Bing site: operator)
CHINA_NEWS_DOMAINS = ['news.sina.com.cn','news.163.com','news.sohu.com','ifeng.com','news.qq.com','huanqiu.com','guancha.cn','zaobao.com','news.cctv.com','xinhuanet.com','chinanews.com.cn','ltn.com.tw','theinitium.com']
CHINA_EDU_DOMAINS = ['gaokao.chsi.com.cn','gaokao.com','eol.cn','exam100.cn','sooxue.com','zhongkao.com','jiaoyu.cn','edu.sina.com.cn','edu.163.com','gaokao.qq.com','edushi.com']
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "data.db")
ERROR_LOG = os.path.join(SCRIPT_DIR, "docs", "ERROR_LOG.md")

# ============ Static Vendor Assets (offline-first) ============
_VENDOR_DIR = os.path.join(SCRIPT_DIR, "static", "vendor")
_VENDOR_ASSETS = {
    "marked.min.js":        "https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js",
    "katex.min.js":         "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js",
    "katex.min.css":        "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css",
    "highlight.min.js":     "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js",
    "github.min.css":       "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css",
    "github-dark.min.css":  "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css",
}

def _ensure_vendor_assets():
    """Download missing vendor assets for offline use. Runs once at startup."""
    os.makedirs(_VENDOR_DIR, exist_ok=True)
    missing = [k for k, v in _VENDOR_ASSETS.items() if not os.path.exists(os.path.join(_VENDOR_DIR, k))]
    if not missing:
        print(f"  [VENDOR] All {len(_VENDOR_ASSETS)} assets cached locally")
        return
    print(f"  [VENDOR] Downloading {len(missing)} missing assets...")
    ok = 0
    for name in missing:
        url = _VENDOR_ASSETS[name]
        dest = os.path.join(_VENDOR_DIR, name)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "USB-AI/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"    ✓ {name} ({len(data)//1024}KB)")
            ok += 1
        except Exception as e:
            print(f"    ✗ {name}: {e}")
    print(f"  [VENDOR] {ok}/{len(missing)} downloaded")


def log_error(module, error_type, description):
    try:
        from datetime import datetime
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(ERROR_LOG, 'a', encoding='utf-8') as lf:
            lf.write(f'| {ts} | ERROR | {module} | {error_type} | {description} | 待修复 |\n')
    except Exception:
        pass

# ============ Database Layer ============
class Database:
    """SQLite database for server-side persistence. Thread-safe."""
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _with_conn(self):
        """Context manager that auto-closes the connection. Usage: with self._with_conn() as conn:"""
        from contextlib import contextmanager
        @contextmanager
        def _cm():
            conn = self._connect()
            try:
                yield conn
            finally:
                conn.close()
        return _cm()

    def _init_db(self):
        with self._lock:
            conn = self._connect()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL DEFAULT '',
                    messages   TEXT NOT NULL DEFAULT '[]',
                    is_auto    INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    text       TEXT NOT NULL,
                    done       INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    title      TEXT NOT NULL,
                    content    TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)
            conn.commit()
            conn.close()

    # --- Settings ---
    def get_settings(self):
        with self._lock:
            conn = self._connect()
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            conn.close()
            return {r["key"]: json.loads(r["value"]) for r in rows}

    def save_settings(self, data):
        with self._lock:
            conn = self._connect()
            for key, value in data.items():
                conn.execute(
                    "INSERT INTO settings(key,value,updated_at) VALUES(?,?,datetime('now')) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (key, json.dumps(value, ensure_ascii=False))
                )
            conn.commit()
            conn.close()

    # --- Conversations ---
    def list_conversations(self):
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                "SELECT id,title,is_auto,created_at,updated_at,json_array_length(messages) as msg_count FROM conversations ORDER BY updated_at DESC"
            ).fetchall()
            conn.close()
            return [{"id": r["id"], "title": r["title"], "isAuto": bool(r["is_auto"]),
                     "createdAt": r["created_at"], "updatedAt": r["updated_at"],
                     "messageCount": r["msg_count"]} for r in rows]

    def get_conversation(self, cid):
        with self._lock:
            conn = self._connect()
            row = conn.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
            conn.close()
            if not row:
                return None
            return {"id": row["id"], "title": row["title"],
                    "messages": json.loads(row["messages"]),
                    "isAuto": bool(row["is_auto"]),
                    "createdAt": row["created_at"], "updatedAt": row["updated_at"]}

    def save_conversation(self, cid, title, messages, is_auto=False):
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO conversations(id,title,messages,is_auto,created_at,updated_at) "
                "VALUES(?,?,?,?,datetime('now'),datetime('now')) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, messages=excluded.messages, "
                "is_auto=excluded.is_auto, updated_at=datetime('now')",
                (cid, title, json.dumps(messages, ensure_ascii=False), int(is_auto))
            )
            conn.commit()
            conn.close()

    def delete_conversation(self, cid):
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
            conn.commit()
            conn.close()

    # --- Tasks ---
    def list_tasks(self):
        with self._lock:
            conn = self._connect()
            rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
            conn.close()
            return [{"id": r["id"], "text": r["text"], "done": bool(r["done"]),
                     "createdAt": r["created_at"]} for r in rows]

    def save_task(self, data):
        with self._lock:
            conn = self._connect()
            c = conn.execute(
                "INSERT INTO tasks(text,done) VALUES(?,?)",
                (data.get("text", ""), int(data.get("done", False)))
            )
            conn.commit()
            tid = c.lastrowid
            conn.close()
            return tid

    def update_task(self, tid, data):
        with self._lock:
            conn = self._connect()
            conn.execute(
                "UPDATE tasks SET text=COALESCE(?,text), done=COALESCE(?,done) WHERE id=?",
                (data.get("text"), None if data.get("done") is None else int(data["done"]), tid)
            )
            conn.commit()
            conn.close()

    # --- Entity Memory ---
    def _ensure_entities_table(self, conn):
        """Lazily create entities table for long-term user memory."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT,
                entity_value TEXT,
                context TEXT,
                weight REAL DEFAULT 1.0,
                created_at TEXT DEFAULT (datetime('now')),
                last_seen_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")

    def upsert_entity(self, entity_type, entity_value, context=""):
        """Insert or refresh an entity's last_seen_at (boosts recency weight)."""
        with self._lock:
            conn = self._connect()
            self._ensure_entities_table(conn)
            existing = conn.execute(
                "SELECT id FROM entities WHERE entity_type=? AND entity_value=?",
                (entity_type, entity_value)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE entities SET last_seen_at=datetime('now'), weight=weight+0.2, context=? WHERE id=?",
                    (context[:200], existing[0])
                )
            else:
                conn.execute(
                    "INSERT INTO entities (entity_type, entity_value, context) VALUES (?,?,?)",
                    (entity_type, entity_value, context[:200])
                )
            conn.commit()
            conn.close()

    def get_top_entities(self, limit=8):
        """Return entities ranked by recency-decayed weight."""
        with self._lock:
            conn = self._connect()
            self._ensure_entities_table(conn)
            rows = conn.execute("""
                SELECT entity_type, entity_value, context,
                       weight * (1.0 / (1.0 + (julianday('now') - julianday(last_seen_at)) * 0.1)) AS score
                FROM entities
                ORDER BY score DESC LIMIT ?
            """, (limit,)).fetchall()
            conn.close()
            return [{"type": r[0], "value": r[1], "context": r[2]} for r in rows]

    def delete_task(self, tid):
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
            conn.commit()
            conn.close()

    # --- Memories ---
    def list_memories(self):
        with self._lock:
            conn = self._connect()
            rows = conn.execute("SELECT * FROM memories ORDER BY id ASC").fetchall()
            conn.close()
            return [{"id": r["id"], "title": r["title"], "content": r["content"],
                     "createdAt": r["created_at"]} for r in rows]

    def save_memory(self, data):
        with self._lock:
            conn = self._connect()
            c = conn.execute(
                "INSERT INTO memories(title,content) VALUES(?,?)",
                (data.get("title", ""), data.get("content", ""))
            )
            conn.commit()
            mid = c.lastrowid
            conn.close()
            return mid

    def update_memory(self, mid, data):
        with self._lock:
            conn = self._connect()
            conn.execute(
                "UPDATE memories SET title=COALESCE(?,title), content=COALESCE(?,content) WHERE id=?",
                (data.get("title"), data.get("content"), mid)
            )
            conn.commit()
            conn.close()

    def delete_memory(self, mid):
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM memories WHERE id=?", (mid,))
            conn.commit()
            conn.close()



# Global DB instance + CSRF token
import secrets
db = None
LOCAL_TOKEN = None  # Loaded/generated on startup, persisted across restarts

def _inject_token(token):
    """Replace placeholder (empty or old) with actual token."""
    idx_path = os.path.join(SCRIPT_DIR, "index.html")
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Replace already-injected token or empty placeholder
        html = re.sub(r"let LOCAL_TOKEN = '[^']*';", "let LOCAL_TOKEN = '%s';" % token, html)
        if "let LOCAL_TOKEN = '" not in html:
            html = html.replace("</script>\n</body>", "<script>let LOCAL_TOKEN = '%s';</script>\n</body>" % token)
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print("  [CSRF] warn: token inject failed: %s" % e)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ============ Local LLM (llama-cpp-python, optional) ============
# pip install llama-cpp-python → local inference with GGUF models
# pip uninstall llama-cpp-python → clean removal, falls back to Ollama/API
_LOCAL_LLM = None          # llama_cpp.Llama instance
_LOCAL_LLM_MODEL = None    # Path to loaded GGUF
_LOCAL_LLM_LOCK = threading.Lock()

def _find_gguf_models():
    """List GGUF files in runtime/models/."""
    d = os.path.join(SCRIPT_DIR, "runtime", "models")
    if not os.path.isdir(d):
        return []
    return sorted([os.path.join(d, f) for f in os.listdir(d) if f.endswith('.gguf')])

def _load_local_model(model_path=None):
    """Load GGUF via llama-cpp-python. Returns (ok, msg)."""
    global _LOCAL_LLM, _LOCAL_LLM_MODEL
    _unload_local_model()
    if not model_path:
        cands = _find_gguf_models()
        if not cands:
            return False, "runtime/models/ 下没有 .gguf 文件"
        model_path = cands[0]
    try:
        import llama_cpp
        _LOCAL_LLM = llama_cpp.Llama(
            model_path=model_path, n_ctx=4096,
            n_threads=max(2, (os.cpu_count() or 2) - 1),
            verbose=False
        )
        _LOCAL_LLM_MODEL = model_path
        name = os.path.basename(model_path)
        print(f"  [LOCAL-LLM] Loaded: {name}")
        return True, f"已加载 {name}"
    except ImportError:
        return False, "llama-cpp-python 未安装。运行: pip install llama-cpp-python"
    except Exception as e:
        return False, f"模型加载失败: {str(e)[:200]}"

def _unload_local_model():
    """Unload model, free memory."""
    global _LOCAL_LLM, _LOCAL_LLM_MODEL
    if _LOCAL_LLM is not None:
        try:
            del _LOCAL_LLM
        except Exception:
            pass
        _LOCAL_LLM = None
        _LOCAL_LLM_MODEL = None
        print("  [LOCAL-LLM] Unloaded")


def _resolve_local_model(model_name):
    """Find GGUF by filename in runtime/models/. Returns (path or None)."""
    name_only = os.path.basename(model_name.replace('_local_', '', 1))
    cands = _find_gguf_models()
    for p in cands:
        if os.path.basename(p) == name_only:
            return p
    # Fallback: first available
    return cands[0] if cands else None

def _auto_load_local(model_name):
    """Auto-load model if not already loaded. Returns (ok, msg)."""
    if _LOCAL_LLM is not None:
        return True, "already loaded"
    p = _resolve_local_model(model_name)
    if not p:
        return False, "no .gguf found in runtime/models/"
    return _load_local_model(p)

def _check_llama_cpp():
    """Check if llama-cpp-python is importable."""
    try:
        import llama_cpp
        return True
    except ImportError:
        return False


def _fetch(url, timeout=12, extra_headers=None):
    h = {"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if extra_headers: h.update(extra_headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

def _clean(s):
    t = re.sub(r'<[^>]+>', ' ', s).strip()
    t = re.sub(r'\s+', ' ', t)
    return html_mod.unescape(t)

def _decode_bing_url(encoded):
    """Decode Bing's u= base64-encoded URL parameter."""
    # Replace HTML entities first
    clean = encoded.replace('&amp;', '&')
    m = re.search(r'[?&]u=([a-zA-Z0-9_\-/+=]+?)(?:&|$)', clean)
    if not m: return None
    b64 = m.group(1)
    try:
        padded = b64 + '=' * (-len(b64) % 4)
        return _b64.b64decode(padded, validate=False).decode('utf-8', errors='replace')
    except Exception:
        return None

def _ddg_search(query, num=5):
    """DuckDuckGo with retry + Content-Type check + engine health."""
    results = []
    if not _engine_ok("DDG"):
        print(f"  [DDG] engine disabled ({_ENGINE_FAILS.get('DDG',0)} failures), skipping")
        return results
    max_retries = 3
    last_error = ""

    for attempt in range(max_retries):
        try:
            params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
            url = f"https://api.duckduckgo.com/?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "PortableAI/3.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                ct = resp.headers.get("Content-Type", "")
                if "json" not in ct:
                    last_error = f"Non-JSON response: {ct.split(';')[0]}"
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt
                        print(f"  [DDG] attempt {attempt+1}: {last_error}, retry in {wait}s")
                        time.sleep(wait)
                        continue
                    print(f"  [DDG] all {max_retries} attempts failed: {last_error}")
                    return results
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
            if not isinstance(data, dict):
                return results
            if data.get("AbstractText"):
                results.append({"title": data.get("Heading", query), "url": data.get("AbstractURL", ""),
                                "snippet": data["AbstractText"], "engine": "DuckDuckGo"})
            topics = data.get("RelatedTopics") or []
            for topic in topics:
                if len(results) >= num: break
                if isinstance(topic, dict):
                    if "Topics" in topic and isinstance(topic["Topics"], list):
                        for sub in topic["Topics"]:
                            if len(results) >= num: break
                            if isinstance(sub, dict) and sub.get("Text"):
                                results.append({"title": (sub.get("FirstURL") or "").split("/")[-1].replace("_", " ") or query,
                                                "url": sub.get("FirstURL", ""), "snippet": sub["Text"],
                                                "engine": "DuckDuckGo"})
                    elif topic.get("Text"):
                        results.append({"title": (topic.get("FirstURL") or "").split("/")[-1].replace("_", " ") or query,
                                        "url": topic.get("FirstURL", ""), "snippet": topic["Text"],
                                        "engine": "DuckDuckGo"})
            break

        except json.JSONDecodeError as e:
            last_error = f"JSON decode failed: {e}"
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  [DDG] attempt {attempt+1}: {last_error}, retry in {wait}s")
                time.sleep(wait)
                continue
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_error = f"{type(e).__name__}: {str(e)[:100]}"
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  [DDG] attempt {attempt+1}: {last_error}, retry in {wait}s")
                time.sleep(wait)
                continue
        except Exception as e:
            last_error = str(e)[:200]
            print(f"  [DDG] {type(e).__name__}: {last_error}")
            log_error("search", "DDG", last_error)
            break

    if last_error and not results:
        print(f"  [DDG] exhausted: {last_error}")
        log_error("search", "DDG", last_error[:200])
        _engine_fail("DDG")
    else:
        if results:
            _engine_success("DDG")
    return results

def _bing_search(query, num=5):
    """Bing.com HTML scraping — extracts titles, snippets, and real URLs."""
    results = []
    try:
        html = _fetch(f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query, 'count': num, 'setlang': 'zh-Hans', 'mkt': 'zh-CN'})}")
        blocks = re.split(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>', html)[1:]
        for block in blocks:
            if len(results) >= num: break
            # Title from h2 > a
            title_m = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block, re.I)
            if not title_m: continue
            href, title_raw = title_m.group(1), title_m.group(2)
            title = _clean(title_raw)
            if len(title) < 5: continue
            # Extract URL: prefer cite tag (clean), fallback to base64 decode, last resort tracking URL
            url = None
            cm = re.search(r'<cite[^>]*>([\s\S]*?)</cite>', block, re.I)
            if cm:
                cite = _clean(cm.group(1)).replace(' ', '')  # collapse spaces
                cite = cite.replace('›', '/').replace('»', '/')  # › and » -> /
                url = cite if cite.startswith('http') else ('https://' + cite.lstrip('/'))
            if not url:
                url = _decode_bing_url(href)
            if not url or not url.startswith('http'):
                url = href
            # Snippet from <p> with b_lineclamp class
            sm = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>([\s\S]*?)</p>', block, re.I)
            if not sm:
                sm = re.search(r'<span[^>]*class="[^"]*b_caption[^"]*"[^>]*>([\s\S]*?)</span>', block, re.I)
            if not sm:
                sm = re.search(r'<p[^>]*>([\s\S]{10,400}?)</p>', block, re.I)
            snippet = _clean(sm.group(1))[:500] if sm else ""
            results.append({"title": title, "url": url, "snippet": snippet, "engine": "Bing"})
    except Exception as e:
        print(f"  [Bing] {e}", file=sys.stderr); log_error("search", "Bing", str(e)[:200])
        _engine_fail("Bing")
    else:
        if results: _engine_success("Bing")
    return results

def _sogou_search(query, num=5):
    """Sogou.com (搜狗搜索) — cookie-based anti-bot bypass."""
    results = []
    try:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        req = urllib.request.Request("https://www.sogou.com/",
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"})
        opener.open(req, timeout=8)
        req = urllib.request.Request(
            f"https://www.sogou.com/web?{urllib.parse.urlencode({'query': query})}",
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9", "Referer": "https://www.sogou.com/"})
        with opener.open(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="ignore")
        if len(html) < 10000: return results
        for lm in re.finditer(r'<h3[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', html, re.I):
            if len(results) >= num: break
            url, title_raw = lm.group(1), lm.group(2)
            title = _clean(title_raw)
            if 'sogou.com' in url.lower() and '/link?' not in url.lower(): continue
            if len(title) < 4: continue
            after = html[lm.end():lm.end()+800]
            sm = re.search(r'<p[^>]*class="[^"]*(?:str_info|star-wiki|abstract|summary)[^"]*"[^>]*>([\s\S]*?)</p>', after, re.I)
            if not sm:
                sm = re.search(r'<p[^>]*>([\s\S]{10,300}?)</p>', after, re.I)
            snippet = _clean(sm.group(1))[:500] if sm else ""
            results.append({"title": title, "url": url, "snippet": snippet, "engine": "Sogou"})
    except Exception as e:
        print(f"  [Sogou] {type(e).__name__}", file=sys.stderr); log_error("search", "Sogou", str(e)[:200])
        _engine_fail("Sogou")
    else:
        if results: _engine_success("Sogou")
    return results


def _searxng_search(query, num=5):
    """Search via local SearXNG instance (self-hosted, privacy-respecting).
    Falls back silently if SearXNG is not running.
    """
    results = []
    if not _engine_ok("SearXNG"):
        return results
    try:
        url = f"{_SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json&language=zh-CN&categories=general&pageno=1"
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_SEARXNG_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        for item in data.get("results", [])[:num]:
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("content", "")
            if title or snippet:
                results.append({"title": title, "url": url, "snippet": snippet, "engine": "SearXNG"})
        if results:
            _engine_success("SearXNG")
    except (urllib.error.HTTPError, urllib.error.URLError, ConnectionRefusedError, ConnectionError) as e:
        _engine_fail("SearXNG")
        log_error("search", "SearXNG", f"{type(e).__name__}: {str(e)[:100]}")
    except Exception as e:
        _engine_fail("SearXNG")
        log_error("search", "SearXNG", str(e)[:200])
    return results


# ============ Chinese Tokenizer ============
try:
    import jieba
    jieba.setLogLevel(20)
    _has_jieba = True
except ImportError:
    _has_jieba = False
    print('  [tokenizer] jieba not installed, using basic tokenizer. Run: pip install jieba')

def tokenize_query(text):
    if not text: return []
    if _has_jieba:
        tokens = jieba.lcut(text)
        return [t.strip() for t in tokens if len(t.strip()) >= 2 or t in '金价股汇涨跌停买卖多空']
    else:
        import re
        tokens = re.findall(r'[a-zA-Z0-9]+', text)
        chinese = re.sub(r'[a-zA-Z0-9\s]', '', text)
        i = 0
        while i < len(chinese):
            for n in [4, 3, 2]:
                if i + n <= len(chinese):
                    tokens.append(chinese[i:i+n])
                    i += n; break
            else: i += 1
        return tokens


# ============ Query Optimization ============

# Words to strip: conversational filler, pronouns, question markers
_STRIP_WORDS = {
    '帮我', '请', '麻烦', '能不能', '可不可以', '谁知道', '哪位', '大家',
    '我想', '我要', '我需要', '帮忙', '请问', '问一下', '查一下', '搜一下',
    '找一下', '看一下', '告诉我', '解释一下', '有没有人', '有谁知道',
    '这届', '本届', '这次', '这个', '那个', '那些', '这些', '一下',
    '你猜', '你说', '你看', '你觉得', '你认为', '怎么', '什么样',
    '是什么', '什么是', '什么叫', '有没有', '会不会', '能不能',
    '一下', '告诉我', '知道吗', '知道不', '继续', '继续分析', '收集', '资料', '帮我收集', '整理', '汇总', '获取', '拿到',
    '继续', '继续分析', '帮我分析', '分析一下',
    '给我', '来一个', '来一期', '帮我查', '查一下', '看一看', '帮我看看',
    '如何', '怎样', '怎么样', '为何', '为啥',
}
# NOTE: '安装','配置','设置','部署','下载','编译','运行','启动','连接','登录'
# are technical verbs — NEVER add them to strip list.

def generate_hyde_query(user_message, api_key, timeout=8):
    """Generate a hypothetical answer to use as the search query (HyDE technique).
    Falls back to the original message on any failure — never blocks the pipeline."""
    if not api_key or len(user_message) < 6:
        return user_message
    prompt = (
        f"针对这个问题，写一段50字以内的假设性回答（即使你不确定也要写出最可能的答案，"
        f"措辞要像新闻或百科文章）：{user_message}\n只返回这段假设性回答，不要任何前缀或解释。"
    )
    try:
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100, "temperature": 0.3
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        hyde_text = data["choices"][0]["message"]["content"].strip()
        return hyde_text if hyde_text else user_message
    except Exception as e:
        print(f"  [HyDE] {e}", file=sys.stderr)
        return user_message


def generate_stepback_query(user_message, api_key, timeout=6):
    """Generate a more general/abstract version of a specific question (Step-Back Prompting).
    e.g. '特朗普对华关税最新进展' -> '美中贸易关系'. Returns None if not applicable."""
    if not api_key or len(user_message) < 15:
        return None
    prompt = (
        f"如果这个问题太具体，写一个更宏观、更通用的版本（5-10字，用于辅助搜索背景信息）："
        f"{user_message}\n如果问题已经足够通用就返回\"无\"。只返回结果，不要解释。"
    )
    try:
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 30, "temperature": 0.2
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        result = data["choices"][0]["message"]["content"].strip()
        return None if (not result or "无" in result[:3]) else result
    except Exception as e:
        print(f"  [StepBack] {e}", file=sys.stderr)
        return None


def optimize_query(user_message, search_context=""):
    """
    Extract clean search keywords from Chinese conversational queries.
    Removes filler, interrogatives, pronouns — keeps nouns and core intent.
    """
    q = user_message.strip()
    # Remove question marks and punctuation
    q = re.sub(r'[？?！!。，,、\s]+', ' ', q)
    # Remove filler words (whole word match)
    for w in sorted(_STRIP_WORDS, key=len, reverse=True):
        q = q.replace(w, ' ')
    # Keep time words — they provide important temporal context
    has_time = bool(re.search(r'今天|今日|本周|本月|今年', q))
    if has_time:
        q = q + ' 最新'
    # Remove filler patterns
    q = re.sub(r'(有什么|有什么新闻|最近有什么|最近怎么样|最新消息|最近消息|什么新闻|有啥|有没啥|吗|呢|吧|啊|的)', ' ', q)
    # Remove generic words that are redundant when event keyword already present
    if any(kw in q for kw in ['世界杯','欧冠','欧洲杯','美洲杯','NBA','英超','西甲','法甲','德甲','中超']):
        q = re.sub(r'\b(球赛|比赛|赛事)\b', ' ', q)
    # Remove single-character leftovers
    q = re.sub(r'[的了是吗呢吧啊呀嘛哦哈嘿诶哎哟噢喔乎哉兮和与跟及或谁哪这那啥咋她他它]+', ' ', q)
    q = re.sub(r'\b\d{1,2}\b', ' ', q, flags=re.ASCII)  # Strip 1-2 digit standalone numbers (keep years 2025, periods 24101)
    # Clean up "X期" lottery pattern leftover
    if '期' in q and any(k in q for k in ['开奖','彩票','号码','kl8','大乐透','双色球','快乐8']):
        q = q.replace('期', ' ')
    q = re.sub(r'\s+', ' ', q).strip()
    if len(q) < 4:
        q = re.sub(r'[？?！!。，,、\s]+', ' ', user_message).strip()
    # Smart keyword expansion
    expansions = {
        '快乐8': 'kl8 开奖 号码',
        '世界杯': '最新 赛程',
        '大乐透': '最新 开奖 号码 体彩',
        '双色球': '最新 开奖 结果 福彩',
        '排列三': '最新 开奖 体彩',
        '排列五': '最新 开奖 体彩',
        '欧冠': '2026 赛程 对阵',
        'NBA': '2026 赛程 总决赛',
        '天气': '今天 预报',
    }
    # Problematic compound words that Bing splits: replace with abbreviations
    _replace_words = {'快乐8': 'kl8'}
    # Geopolitical compound name expansion: "美以伊" → "美国 以色列 伊朗"
    _geo_expand = {
        '美以伊': '美国 以色列 伊朗 ', '美以': '美国 以色列 ', '美伊': '美国 伊朗 ',
        '以伊': '以色列 伊朗 ', '中美': '中国 美国 ', '中日': '中国 日本 ',
        '中印': '中国 印度 ', '美俄': '美国 俄罗斯 ', '俄乌': '俄罗斯 乌克兰 ',
        '朝韩': '朝鲜 韩国 ', '巴以': '巴勒斯坦 以色列 ', '印巴': '印度 巴基斯坦 ',
    }
    for old_k, new_v in _geo_expand.items():
        if old_k in q:
            q = q.replace(old_k, new_v)
    for old, new in _replace_words.items():
        if old in q:
            q = q.replace(old, new)
    # Preserve timeliness keywords for news queries
    if re.search(r'最新|最近|近日|今天|当前|目前|现在|实时', q):
        if '最新' not in q: q = q + ' 最新'
        if '新闻' not in q and any(k in q for k in ['战争','冲突','局势','选举','事件','动态','进展','政策']):
            q = q + ' 新闻'
    for key, val in expansions.items():
        if key in q and val not in q:
            q = f'{q} {val}'; break
    # Strip single-character leftovers that confuse search engines
    q = re.sub(r'[的了是吗呢吧啊呀哦嘛哈嘿哎哟噢乎乎哉兮谁哪这那啥咋她他它]+', '', q)
    q = re.sub(r'\s+', ' ', q).strip()
    # Append external context
    if search_context:
        q = f"{q} {search_context}"
    return q


# ============ RAG Context Compressor ============
def compress_context(text, query, max_chars=2000):
    """
    Split text into chunks, score relevance against query using BM25-style scoring.
    Returns compressed context that fits within max_chars budget.
    """
    if not text or len(text) <= max_chars:
        return text

    # Tokenize query for scoring
    q_terms = set(query.lower().split())
    # Use jieba tokenization for Chinese word segmentation
    q_terms.update(tokenize_query(query))
    # Add Chinese bigrams for finer granularity
    for i in range(len(query) - 1):
        if '一' <= query[i] <= '鿿' and '一' <= query[i+1] <= '鿿':
            q_terms.add(query[i:i+2])

    # Filter short/trivial terms
    q_terms = {t for t in q_terms if len(t) >= 2}

    if not q_terms:
        return text[:max_chars]

    # Split into chunks: by sentence (。！？\n), with overlap
    chunks = re.split(r'(?<=[。！？\n])', text)
    merged = []
    buf = ""
    for ch in chunks:
        buf += ch
        if len(buf) >= 100 or ch.endswith('\n'):
            merged.append(buf.strip())
            buf = ""
    if buf.strip():
        merged.append(buf.strip())

    # Quality filter: if most chunks are short (<40 chars), it's an aggregation page — skip
    short_count = sum(1 for ch in merged if len(ch) < 40)
    if len(merged) > 10 and short_count > len(merged) * 0.6:
        return text[:max_chars]  # Just truncate — compression won't help

    if len(merged) <= 1:
        return text[:max_chars]

    # BM25-style scoring: TF · IDFapprox with length normalization
    num_docs = len(merged)
    avg_doc_len = sum(len(ch) for ch in merged) / max(num_docs, 1)
    k1, b = 1.5, 0.75  # BM25 tunable parameters

    # Pre-compute IDF approximation per term
    # df = how many chunks contain the term
    df = {}
    for t in q_terms:
        count = sum(1 for ch in merged if t in ch.lower())
        df[t] = count

    scored = []
    for ch in merged:
        if len(ch) < 20:
            continue
        ch_lower = ch.lower()
        doc_len = len(ch)
        bm25_score = 0
        # BM25 sum over query terms
        for t in q_terms:
            if t not in ch_lower:
                continue
            tf = ch_lower.count(t)
            idf_approx = max(0, np.log((num_docs - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))) if has_numpy else 1.0
            bm25_score += idf_approx * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))

        # Bonus: title/heading-like lines (exact match gets high boost)
        if re.search(r'(开奖|结果|号码|冠军|比分|最新|公布|发布|宣布|报道|据悉|快讯|快报)', ch):
            bm25_score += 3
        # Bonus: exact query phrase match
        if query.lower() in ch_lower:
            bm25_score += 5
        # Bonus: multiple distinct query terms co-occur
        term_hits = sum(1 for t in q_terms if t in ch_lower)
        if term_hits >= 3:
            bm25_score += 2

        scored.append((bm25_score, ch))

    # Sort by score descending, take top chunks within budget
    scored.sort(key=lambda x: -x[0])
    result = []
    used = 0
    for score, ch in scored:
        if score < 0.1:
            continue
        if used + len(ch) > max_chars:
            remaining = max_chars - used
            if remaining > 100:
                result.append(ch[:remaining] + '…')
            break
        result.append(ch)
        used += len(ch)

    if not result:
        return text[:max_chars]

    return '\n'.join(result)




def generate_summary(text, query, max_items=6):
    """
    Extractive summarization: structured fact extraction.
    Extracts: time, place, person, data, quote, header.
    No API calls — pure regex + heuristics.
    """
    items = []
    lines = text.split('\n')

    # 1. Time: 年月日/小时前/分钟前/北京时间/开赛时间
    for line in lines:
        if re.search(r'(\d{4}年|\d{1,2}月\d{1,2}日|\d+小时前|\d+分钟前|北京时间|开赛|开奖时间|发布于)', line):
            items.append(('🕐', line.strip()[:200]))

    # 2. Data: numbers with units (亿/万/元/分/球/帽/注/倍/℃)
    for line in lines:
        if re.search(r'\d+[亿万元分球帽注倍℃秒个位场次]', line) and len(line) > 10:
            items.append(('📊', line.strip()[:200]))

    # 3. Person/Team: known entities
    for line in lines:
        if re.search(r'(梅西|C罗|姆巴佩|内马尔|哈兰德|本泽马|莱万|莫德里奇|德布劳内|萨拉赫|'
                      r'阿根廷|巴西|法国|英格兰|西班牙|德国|意大利|荷兰|葡萄牙|'
                      r'皇马|巴萨|曼联|曼城|拜仁|巴黎|利物浦|切尔西|阿森纳)', line):
            if len(line) > 20 and line.strip() not in [i[1] for i in items]:
                items.append(('👤', line.strip()[:200]))

    # 4. Place: locations
    for line in lines:
        if re.search(r'(北京|上海|广州|深圳|成都|杭州|南京|武汉|重庆|西安|'
                      r'卡塔尔|美加墨|温布利|伯纳乌|诺坎普|老特拉福德)', line):
            if len(line) > 20 and line.strip() not in [i[1] for i in items]:
                items.append(('📍', line.strip()[:200]))

    # 5. Quotes/announcements
    for line in lines:
        if re.search(r'(表示|宣布|透露|承认|确认|公布|发布|回应|强调|指出)', line):
            if line.strip() not in [i[1] for i in items]:
                items.append(('💬', line.strip()[:200]))

    # 6. Headers/topics
    for line in lines:
        if re.match(r'^[^\s]{5,40}[：:]\s', line) and len(line) < 100:
            if line.strip() not in [i[1] for i in items]:
                items.append(('📌', line.strip()[:200]))

    # Deduplicate and limit
    seen = set()
    unique = []
    for icon, item in items:
        key = item[:40]
        if key not in seen:
            seen.add(key)
            unique.append(f"{icon} {item}")
            if len(unique) >= max_items:
                break

    if not unique:
        for line in lines[:max_items]:
            if len(line.strip()) > 15:
                unique.append(f"• {line.strip()[:200]}")

    return '\n'.join(unique)


# ====== Direct Data APIs (weather, news, knowledge) ======
def search_weather(query):
    results = []
    cities = {"北京":(39.9,116.4),"上海":(31.2,121.5),"广州":(23.1,113.3),"深圳":(22.5,114.1),"成都":(30.6,104.1),"杭州":(30.3,120.2),"武汉":(30.6,114.3),"南京":(32.1,118.8),"西安":(34.3,108.9),"重庆":(29.6,106.5),"天津":(39.1,117.2),"苏州":(31.3,120.6),"长沙":(28.2,113.0),"郑州":(34.8,113.7),"济南":(36.7,117.0),"青岛":(36.1,120.4),"大连":(38.9,121.6),"厦门":(24.5,118.1),"福州":(26.1,119.3),"合肥":(31.8,117.3),"沈阳":(41.8,123.4),"哈尔滨":(45.8,126.5),"昆明":(25.0,102.7),"贵阳":(26.6,106.7),"台北":(25.0,121.5),"香港":(22.3,114.2)}
    for name,(lat,lon) in cities.items():
        if name in query:
            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2,wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia/Shanghai&forecast_days=3"
                data = json.loads(_fetch(url, timeout=8))
                c = data.get("current",{})
                d = data.get("daily",{})
                wcodes = {0:"晴",1:"晴",2:"多云",3:"阴",45:"雾",51:"小雨",53:"小雨",55:"中雨",61:"小雨",63:"中雨",65:"大雨",71:"小雪",73:"中雪",75:"大雪",80:"阵雨",95:"雷暴"}
                w = wcodes.get(c.get("weather_code",0),"多云")
                info = f"{name}天气：{w}，{c.get('temperature_2m','?')}°C，湿度{c.get('relative_humidity_2','?')}%"
                for i in range(min(3, len(d.get("time",[])))):
                    info += f" | {d['time'][i]}：{d.get('temperature_2m_max',[0])[i]}°C / {d.get('temperature_2m_min',[0])[i]}°C"
                results.append({"title":info,"url":"https://open-meteo.com/","snippet":info,"engine":"OpenMeteo"})
                break
            except: pass
    return results

def search_wiki(query):
    results = []
    try:
        term = re.sub(r'[是什么是谁在哪怎样如何怎么]','',query).strip()
        if len(term) < 2: term = query.strip()
        url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(term)}"
        data = json.loads(_fetch(url, timeout=8))
        if data.get("extract"):
            results.append({"title":data.get("title",term),"url":data.get("content_urls",{}).get("desktop",{}).get("page",""),"snippet":data["extract"][:800],"engine":"Wikipedia"})
    except: pass
    return results

def search_news(query):
    results = []
    # Google News RSS (may be blocked in mainland China)
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        html = _fetch(url, timeout=6)
        items = re.findall(r'<item>([\s\S]*?)</item>', html)
        for item in items[:5]:
            title_m = re.search(r'<title>([^<]+)</title>', item)
            link_m = re.search(r'<link>([^<]+)</link>', item)
            desc_m = re.search(r'<description>([^<]+)</description>', item)
            if title_m:
                results.append({"title":html_mod.unescape(title_m.group(1).strip()),"url":link_m.group(1).strip() if link_m else "","snippet":html_mod.unescape(desc_m.group(1).strip())[:300] if desc_m else "","engine":"GoogleNews"})
    except: pass
    # Bing News fallback (accessible in China)
    if not results:
        try:
            bing_url = f"https://www.bing.com/news/search?q={urllib.parse.quote(query)}&format=rss"
            html = _fetch(bing_url, timeout=6)
            items = re.findall(r'<item>([\s\S]*?)</item>', html)
            for item in items[:5]:
                title_m = re.search(r'<title>([^<]+)</title>', item)
                link_m = re.search(r'<link>([^<]+)</link>', item)
                desc_m = re.search(r'<description>([^<]+)</description>', item)
                if title_m:
                    results.append({"title":html_mod.unescape(title_m.group(1).strip()),"url":link_m.group(1).strip() if link_m else "","snippet":html_mod.unescape(desc_m.group(1).strip())[:300] if desc_m else "","engine":"BingNews"})
        except: pass
    # Chinese news site targeted search via Sogou (best Chinese coverage)
    if not results:
        try:
            site_filter = ' OR '.join(f'site:{d}' for d in CHINA_NEWS_DOMAINS[:8])
            cn_query = f'({query}) {site_filter}'
            cn_results = _sogou_search(cn_query, num=5)
            if cn_results:
                for r in cn_results:
                    r["engine"] = "ChinaNews"
                results = cn_results
        except: pass
    return results


def search_edu(query):
    """Targeted search over Chinese education domains via Sogou site: operator."""
    results = []
    try:
        site_filter = ' OR '.join(f'site:{d}' for d in CHINA_EDU_DOMAINS[:6])
        edu_query = f'({query}) {site_filter}'
        cn_results = _sogou_search(edu_query, num=5)
        if cn_results:
            for r in cn_results:
                r["engine"] = "EduSite"
            results = cn_results
    except: pass
    return results


def search_gold_price():
    """Fetch live commodity prices from free APIs (GoldAPI + Binance)."""
    results = []
    # GoldAPI: metals
    _commodities = {
        'XAU': ('黄金','XAU/USD','每盎司'), 'XAG': ('白银','XAG/USD','每盎司'),
        'HG': ('铜','Copper','每磅'), 'XPD': ('钯金','XPD/USD','每盎司')
    }
    for sym, (name, pair, unit) in _commodities.items():
        try:
            data = json.loads(_fetch(f"https://api.gold-api.com/price/{sym}", timeout=8))
            if data.get("price"):
                results.append({"title":f"{name}实时价格: ${data['price']:,.2f}/{unit.split('每')[-1] if '每' in unit else unit}",
                    "url":"https://api.gold-api.com","engine":"GoldAPI",
                    "snippet":f"{name} {pair}: ${data['price']:,.2f} {unit} (更新: {data.get('updatedAtReadable','N/A')})"})
        except: pass
    # Binance: crypto top coins
    try:
        data = json.loads(_fetch("https://api.binance.com/api/v3/ticker/price", timeout=8))
        _top_coins = {'BTCUSDT':'比特币','ETHUSDT':'以太坊','BNBUSDT':'BNB','SOLUSDT':'Solana',
                      'XRPUSDT':'XRP','ADAUSDT':'Cardano','DOGEUSDT':'狗狗币','DOTUSDT':'Polkadot'}
        for pair in data:
            sym = pair.get('symbol','')
            if sym in _top_coins:
                name = _top_coins[sym]
                price = float(pair.get('price',0))
                results.append({"title":f"{name}实时价格: ${price:,.2f}",
                    "url":"https://www.binance.com","engine":"Binance",
                    "snippet":f"{name} ({sym}): ${price:,.2f}"})
    except: pass
    return results

def search_oil_price():
    """Scrape oil prices from free sources."""
    results = []
    try:
        # Try oilpriceapi (free tier, no key for basic endpoint)
        html = _fetch("https://markets.businessinsider.com/commodities/oil-price?type=wti", timeout=10)
        if html:
            # Extract prices: look for $XX.XX patterns near WTI/Brent labels
            import re as _re
            for label, field in [('WTI原油','WTI'),('布伦特原油','Brent')]:
                idx = html.find(field)
                if idx > 0:
                    m = _re.search(r'\$?([\d,]+\.\d{2})', html[idx:idx+300])
                    if m:
                        results.append({"title":f"{label}实时价格: ${m.group(1)}/桶",
                            "url":"https://markets.businessinsider.com/commodities/oil-price",
                            "snippet":f"{label}: ${m.group(1)}/桶","engine":"CommodityScraper"})
    except: pass
    if not results:
        # Fallback: use search engine keywords
        results.append({"title":"原油价格查询","url":"https://finance.sina.com.cn/futures/quotes/CL.shtml",
            "snippet":"WTI/布伦特原油实时价格请访问新浪财经或东方财富期货频道","engine":"Reference"})
    return results

def search_products(query):
    """Search for product prices across Chinese e-commerce/auto sites."""
    results = []
    # Car info: try autohome or dongchedi
    if any(k in query for k in ['汽车','买车','SUV','轿车','新能源','落地价','报价','配置','保养',
                                  '保险','油耗','二手','回收','置换','特斯拉','比亚迪','蔚来','理想']):
        try:
            html = _fetch(f"https://www.autohome.com.cn/grade/carhtml/{urllib.parse.quote(query[:20])}.html", timeout=8)
            if html:
                import re as _re
                prices = _re.findall(r'[\d]{1,3}\.[\d]{2}万', html)[:5]
                if prices:
                    results.append({"title":"汽车之家报价","url":"https://www.autohome.com.cn",
                        "snippet":"参考价格: "+", ".join(prices),"engine":"AutoHome"})
        except: pass
    # Phone info: try zol
    if any(k in query for k in ['手机','iPhone','华为','小米','OPPO','vivo','三星','折叠屏','旗舰','千元','回收']):
        try:
            html = _fetch(f"https://detail.zol.com.cn/cell_phone_index/subcate57_0_list_1_0_1_1_0_1.html", timeout=8)
            if html:
                import re as _re
                titles = _re.findall(r'<a[^>]*class="[^"]*pic[^"]*"[^>]*>[\s\S]{0,50}?<img[^>]*alt="([^"]+)"', html)[:5]
                prices = _re.findall(r'<b[^>]*class="[^"]*price[^"]*"[^>]*>[\s]*¥?(\d+)', html)[:5]
                if titles:
                    items = []
                    for i in range(min(len(titles), len(prices))):
                        items.append(f"{titles[i]}: ¥{prices[i]}")
                    if items:
                        results.append({"title":"中关村在线手机报价","url":"https://detail.zol.com.cn",
                            "snippet":"\n".join(items[:5]),"engine":"ZOL"})
        except: pass
    return results

def search_forex(query):
    """Fetch forex rates (free API, no key)."""
    results = []
    try:
        pairs = []
        q = query.lower()
        if '美元' in q or 'usd' in q: pairs.append('USD')
        if '人民币' in q or 'cny' in q: pairs.append('CNY')
        if '欧元' in q or 'eur' in q: pairs.append('EUR')
        if '日元' in q or 'jpy' in q: pairs.append('JPY')
        if '英镑' in q or 'gbp' in q: pairs.append('GBP')
        if len(pairs) >= 2:
            base, targets = pairs[0], pairs[1:]
        elif len(pairs) == 1:
            # Single currency: default to USD/CNY or pair with what we have
            base, targets = pairs[0], ['CNY'] if pairs[0] != 'CNY' else ['USD']
        else:
            base, targets = 'USD', ['CNY','EUR','JPY']
        for target in targets[:3]:
            url = f"https://open.er-api.com/v6/latest/{base}"
            data = json.loads(_fetch(url, timeout=8))
            if data.get("result") == "success":
                rate = data["rates"].get(target)
                if rate:
                    results.append({"title":f"{base}/{target} 汇率","url":f"https://www.xe.com/currencyconverter/convert/?From={base}&To={target}","snippet":f"1 {base} = {rate} {target}","engine":"OpenER"})
    except: pass
    return results


# ============ 新增信息源 ============

def search_hacker_news(query):
    """Hacker News via Algolia API — 技术资讯，CORS开放，免费无key。"""
    results = []
    try:
        params = urllib.parse.urlencode({
            "query": query, "tags": "story",
            "hitsPerPage": 5
        })
        url = f"https://hn.algolia.com/api/v1/search?{params}"
        data = json.loads(_fetch(url, timeout=8))
        for hit in data.get("hits", [])[:5]:
            title = hit.get("title", "")
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID','')}"
            pts = hit.get("points", 0)
            comments = hit.get("num_comments", 0)
            age = hit.get("created_at", "")[:10]
            results.append({
                "title": title,
                "url": story_url,
                "snippet": f"[HN] {pts}分 {comments}评 {age}",
                "engine": "HackerNews"
            })
    except Exception as e:
        print(f"  [HN] {e}", file=sys.stderr)
    return results


def search_arxiv(query, max_results=4):
    """arXiv API — 学术预印本，物理/数学/CS/AI，免费无key。"""
    results = []
    try:
        params = urllib.parse.urlencode({
            "search_query": f"all:{query}",
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        })
        url = f"http://export.arxiv.org/api/query?{params}"
        xml = _fetch(url, timeout=10)
        # Parse entries with regex (no xml lib needed)
        entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
        for entry in entries[:max_results]:
            title_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            summary_m = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            link_m = re.search(r'<id>(.*?)</id>', entry)
            published_m = re.search(r'<published>(.*?)</published>', entry)
            if title_m and link_m:
                title = re.sub(r'\s+', ' ', title_m.group(1)).strip()
                summary = re.sub(r'\s+', ' ', summary_m.group(1)).strip()[:200] if summary_m else ""
                link = link_m.group(1).strip()
                pub = published_m.group(1)[:10] if published_m else ""
                results.append({
                    "title": f"[arXiv] {title}",
                    "url": link.replace("http://", "https://"),
                    "snippet": f"{pub} — {summary}",
                    "engine": "arXiv"
                })
    except Exception as e:
        print(f"  [arXiv] {e}", file=sys.stderr)
    return results


def search_pubmed(query, max_results=4):
    """PubMed E-utilities — 生物医学文献，免费无key，1100万篇。"""
    results = []
    try:
        # Step 1: search for IDs
        params = urllib.parse.urlencode({
            "db": "pubmed", "term": query,
            "retmax": max_results, "retmode": "json", "sort": "relevance"
        })
        data = json.loads(_fetch(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}", timeout=8))
        ids = data.get("esearchresult", {}).get("idlist", [])[:max_results]
        if not ids:
            return results
        # Step 2: fetch summaries
        sum_params = urllib.parse.urlencode({
            "db": "pubmed", "id": ",".join(ids), "retmode": "json"
        })
        sum_data = json.loads(_fetch(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{sum_params}", timeout=8))
        for pid in ids:
            art = sum_data.get("result", {}).get(pid, {})
            title = art.get("title", "")
            pub_date = art.get("pubdate", "")[:7]
            authors = ", ".join([a.get("name","") for a in art.get("authors", [])[:2]])
            if title:
                results.append({
                    "title": f"[PubMed] {title}",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    "snippet": f"{pub_date} {authors}",
                    "engine": "PubMed"
                })
    except Exception as e:
        print(f"  [PubMed] {e}", file=sys.stderr)
    return results


def search_semantic_scholar(query, max_results=4):
    """Semantic Scholar API — AI驱动学术搜索，免费无key，引用关系。"""
    results = []
    try:
        params = urllib.parse.urlencode({
            "query": query, "limit": max_results,
            "fields": "title,year,abstract,url,citationCount,authors"
        })
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
        data = json.loads(_fetch(url, timeout=10))
        for paper in data.get("data", [])[:max_results]:
            title = paper.get("title", "")
            year = paper.get("year", "")
            citations = paper.get("citationCount", 0)
            abstract = (paper.get("abstract") or "")[:150]
            authors = ", ".join([a.get("name","") for a in paper.get("authors",[])[:2]])
            paper_url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper.get('paperId','')}"
            if title:
                results.append({
                    "title": f"[Scholar] {title}",
                    "url": paper_url,
                    "snippet": f"{year} {authors} — 被引{citations}次 — {abstract}",
                    "engine": "SemanticScholar"
                })
    except Exception as e:
        print(f"  [SemanticScholar] {e}", file=sys.stderr)
    return results


def search_github(query, max_results=5):
    """GitHub Search API — 代码/仓库搜索，无token 60次/h，有token 5000次/h。"""
    results = []
    try:
        # Search repositories
        params = urllib.parse.urlencode({
            "q": query, "sort": "stars", "order": "desc", "per_page": max_results
        })
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        req = urllib.request.Request(
            f"https://api.github.com/search/repositories?{params}", headers=headers
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        for repo in data.get("items", [])[:max_results]:
            name = repo.get("full_name", "")
            desc = repo.get("description") or ""
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language") or ""
            updated = (repo.get("updated_at") or "")[:10]
            results.append({
                "title": f"[GitHub] {name}",
                "url": repo.get("html_url", ""),
                "snippet": f"⭐{stars:,} {lang} {updated} — {desc[:100]}",
                "engine": "GitHub"
            })
    except Exception as e:
        print(f"  [GitHub] {e}", file=sys.stderr)
    return results


def search_stackoverflow(query, max_results=4):
    """Stack Overflow API — 编程问答，免费，CORS开放。"""
    results = []
    try:
        params = urllib.parse.urlencode({
            "intitle": query, "order": "desc", "sort": "votes",
            "site": "stackoverflow", "filter": "withbody",
            "pagesize": max_results
        })
        url = f"https://api.stackexchange.com/2.3/questions?{params}"
        data = json.loads(_fetch(url, timeout=8))
        for q in data.get("items", [])[:max_results]:
            title = q.get("title", "")
            link = q.get("link", "")
            score = q.get("score", 0)
            answers = q.get("answer_count", 0)
            tags = " ".join(q.get("tags", [])[:3])
            results.append({
                "title": f"[SO] {title}",
                "url": link,
                "snippet": f"↑{score} {answers}答 [{tags}]",
                "engine": "StackOverflow"
            })
    except Exception as e:
        print(f"  [SO] {e}", file=sys.stderr)
    return results


def search_npm(package_name):
    """npm Registry — 包信息/版本/下载量，免费无key，CORS开放。"""
    results = []
    try:
        # Search
        search_url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(package_name)}&size=3"
        data = json.loads(_fetch(search_url, timeout=8))
        for obj in data.get("objects", [])[:3]:
            p = obj.get("package", {})
            name = p.get("name", "")
            ver = p.get("version", "")
            desc = p.get("description", "")
            dl = obj.get("score", {}).get("detail", {}).get("popularity", 0)
            results.append({
                "title": f"[npm] {name} v{ver}",
                "url": f"https://www.npmjs.com/package/{name}",
                "snippet": desc[:150],
                "engine": "npm"
            })
    except Exception as e:
        print(f"  [npm] {e}", file=sys.stderr)
    return results


def search_pypi(package_name):
    """PyPI API — Python包信息，免费无key，CORS开放。"""
    results = []
    try:
        # Try direct package lookup first
        pkg = re.sub(r'[^\w\-]', '-', package_name.strip().split()[0])
        url = f"https://pypi.org/pypi/{pkg}/json"
        data = json.loads(_fetch(url, timeout=8))
        info = data.get("info", {})
        name = info.get("name", pkg)
        ver = info.get("version", "")
        desc = info.get("summary", "")
        author = info.get("author", "")
        license_ = info.get("license", "")
        results.append({
            "title": f"[PyPI] {name} {ver}",
            "url": f"https://pypi.org/project/{name}/",
            "snippet": f"{desc} | 作者:{author} | 协议:{license_}",
            "engine": "PyPI"
        })
    except Exception as e:
        print(f"  [PyPI] {e}", file=sys.stderr)
    return results


def search_bilibili_hot():
    """B站热门排行 — CORS部分开放，实时中文娱乐/科技趋势，无key。"""
    results = []
    try:
        url = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"
        data = json.loads(_fetch(url, timeout=8))
        for video in (data.get("data", {}).get("list") or [])[:6]:
            title = video.get("title", "")
            author = video.get("owner", {}).get("name", "")
            views = video.get("stat", {}).get("view", 0)
            bvid = video.get("bvid", "")
            desc = video.get("desc", "")[:80]
            results.append({
                "title": f"[B站] {title}",
                "url": f"https://www.bilibili.com/video/{bvid}",
                "snippet": f"UP:{author} 播放:{views:,} — {desc}",
                "engine": "Bilibili"
            })
    except Exception as e:
        print(f"  [Bilibili] {e}", file=sys.stderr)
    return results


def search_weibo_hot():
    """微博热搜 — 实时社会热点，需代理，返回Top20热搜词+热度。"""
    results = []
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        html = _fetch(url, timeout=8, extra_headers={
            "Referer": "https://weibo.com/",
            "Accept": "application/json, text/plain, */*"
        })
        data = json.loads(html)
        realtime = data.get("data", {}).get("realtime", [])[:10]
        for item in realtime:
            word = item.get("word", "")
            hot = item.get("raw_hot", 0)
            category = item.get("category", "")
            if word:
                results.append({
                    "title": f"[微博热搜] {word}",
                    "url": f"https://s.weibo.com/weibo?q=%23{urllib.parse.quote(word)}%23",
                    "snippet": f"热度:{hot:,} 分类:{category}",
                    "engine": "WeiboHot"
                })
    except Exception as e:
        print(f"  [Weibo] {e}", file=sys.stderr)
    return results


def search_zhihu_hot():
    """知乎热榜 — 话题/问题热点，代理抓取。"""
    results = []
    try:
        url = "https://www.zhihu.com/hot"
        html = _fetch(url, timeout=10, extra_headers={
            "Referer": "https://www.zhihu.com/"
        })
        # Extract hot items from JSON embedded in page
        json_match = re.search(r'"hotList":\s*(\[.*?\])\s*,\s*"', html, re.DOTALL)
        if json_match:
            items = json.loads(json_match.group(1))
            for item in items[:8]:
                target = item.get("target", {})
                title = target.get("titleArea", {}).get("text", "") or target.get("title", "")
                url_token = target.get("link", {}).get("url", "")
                heat = item.get("detailText", "")
                if title:
                    results.append({
                        "title": f"[知乎] {title}",
                        "url": url_token or "https://www.zhihu.com/hot",
                        "snippet": heat,
                        "engine": "ZhihuHot"
                    })
        else:
            # Fallback: regex scrape
            titles = re.findall(r'<h2[^>]*class="[^"]*HotList-itemTitle[^"]*"[^>]*>(.*?)</h2>', html)
            for t in titles[:8]:
                clean = re.sub(r'<[^>]+>', '', t).strip()
                if clean:
                    results.append({
                        "title": f"[知乎热榜] {clean}",
                        "url": "https://www.zhihu.com/hot",
                        "snippet": "知乎实时热点",
                        "engine": "ZhihuHot"
                    })
    except Exception as e:
        print(f"  [Zhihu] {e}", file=sys.stderr)
    return results


def search_world_bank(indicator, country="CN"):
    """世界银行 API — 全球宏观经济指标，免费CORS开放。"""
    results = []
    try:
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&mrv=3"
        data = json.loads(_fetch(url, timeout=8))
        if len(data) >= 2:
            records = data[1] or []
            for rec in records[:3]:
                if rec.get("value") is not None:
                    country_name = rec.get("country", {}).get("value", country)
                    ind_name = rec.get("indicator", {}).get("value", indicator)
                    val = rec.get("value")
                    year = rec.get("date", "")
                    results.append({
                        "title": f"[世界银行] {country_name} {ind_name}",
                        "url": f"https://data.worldbank.org/indicator/{indicator}?locations={country}",
                        "snippet": f"{year}年: {val:,.2f}" if isinstance(val, float) else f"{year}年: {val}",
                        "engine": "WorldBank"
                    })
    except Exception as e:
        print(f"  [WorldBank] {e}", file=sys.stderr)
    return results


def search_cvedb(keyword, max_results=4):
    """NVD CVE 漏洞数据库 — 安全漏洞搜索，免费CORS开放。"""
    results = []
    try:
        params = urllib.parse.urlencode({
            "keywordSearch": keyword, "resultsPerPage": max_results
        })
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?{params}"
        data = json.loads(_fetch(url, timeout=10))
        for vuln in data.get("vulnerabilities", [])[:max_results]:
            cve = vuln.get("cve", {})
            cve_id = cve.get("id", "")
            descs = cve.get("descriptions", [])
            desc = next((d["value"] for d in descs if d.get("lang") == "en"), "")[:150]
            metrics = cve.get("metrics", {})
            score = ""
            if "cvssMetricV31" in metrics:
                score = f"CVSS3.1: {metrics['cvssMetricV31'][0]['cvssData']['baseScore']}"
            elif "cvssMetricV2" in metrics:
                score = f"CVSS2: {metrics['cvssMetricV2'][0]['cvssData']['baseScore']}"
            published = cve.get("published", "")[:10]
            results.append({
                "title": f"[CVE] {cve_id} {score}",
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                "snippet": f"{published} — {desc}",
                "engine": "NVD"
            })
    except Exception as e:
        print(f"  [NVD] {e}", file=sys.stderr)
    return results


def search_pengpai_rss(query=""):
    """澎湃新闻 RSS — 深度报道，中文高质量新闻，免费。"""
    results = []
    try:
        rss_urls = [
            ("https://www.thepaper.cn/rss_cm.jsp", "澎湃新闻"),
            ("https://feedx.net/rss/pengpai.xml", "澎湃新闻(镜像)"),
        ]
        for rss_url, src_name in rss_urls:
            try:
                xml = _fetch(rss_url, timeout=6)
                items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
                for item in items[:4]:
                    title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', item)
                    link_m = re.search(r'<link>(.*?)</link>', item)
                    pub_m = re.search(r'<pubDate>(.*?)</pubDate>', item)
                    title = (title_m.group(1) or title_m.group(2) or "").strip() if title_m else ""
                    link = link_m.group(1).strip() if link_m else ""
                    pub = pub_m.group(1)[:16] if pub_m else ""
                    if title and (not query or any(w in title for w in query.split())):
                        results.append({
                            "title": f"[{src_name}] {title}",
                            "url": link,
                            "snippet": pub,
                            "engine": "PengPai"
                        })
                if results:
                    break
            except:
                continue
    except Exception as e:
        print(f"  [PengPai] {e}", file=sys.stderr)
    return results


def search_xinhua_rss(query=""):
    """新华社 RSS — 官方权威新闻，实时。"""
    results = []
    try:
        rss_urls = [
            "https://www.xinhuanet.com/politics/news_politics.xml",
            "https://www.xinhuanet.com/world/news_world.xml",
        ]
        for rss_url in rss_urls[:1]:
            try:
                xml = _fetch(rss_url, timeout=6)
                items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
                for item in items[:4]:
                    title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', item)
                    link_m = re.search(r'<link>(https?://[^<]+)</link>', item)
                    desc_m = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>', item, re.DOTALL)
                    title = (title_m.group(1) or title_m.group(2) or "").strip() if title_m else ""
                    link = link_m.group(1).strip() if link_m else ""
                    desc = re.sub(r'<[^>]+>', '', (desc_m.group(1) or desc_m.group(2) or ""))[:100].strip() if desc_m else ""
                    if title:
                        results.append({
                            "title": f"[新华社] {title}",
                            "url": link,
                            "snippet": desc,
                            "engine": "Xinhua"
                        })
            except:
                continue
    except Exception as e:
        print(f"  [Xinhua] {e}", file=sys.stderr)
    return results


def search_coingecko(query="", top_n=5):
    """CoinGecko — 10000+加密货币，市值/价格/变化，免费无key。"""
    results = []
    try:
        if query:
            # Search by name
            params = urllib.parse.urlencode({"query": query})
            data = json.loads(_fetch(f"https://api.coingecko.com/api/v3/search?{params}", timeout=8))
            coin_ids = [c["id"] for c in data.get("coins", [])[:3]]
        else:
            # Top coins by market cap
            coin_ids = ["bitcoin","ethereum","binancecoin","solana","ripple"]
        if not coin_ids:
            return results
        ids_str = ",".join(coin_ids[:5])
        url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids_str}&order=market_cap_desc"
        coins = json.loads(_fetch(url, timeout=8))
        for c in coins[:top_n]:
            name = c.get("name","")
            sym = c.get("symbol","").upper()
            price = c.get("current_price", 0)
            change24h = c.get("price_change_percentage_24h", 0)
            mcap = c.get("market_cap", 0)
            results.append({
                "title": f"[CoinGecko] {name} ({sym})",
                "url": f"https://www.coingecko.com/en/coins/{c.get('id','')}",
                "snippet": f"${price:,.4f} | 24h:{change24h:+.2f}% | 市值:${mcap/1e9:.2f}B",
                "engine": "CoinGecko"
            })
    except Exception as e:
        print(f"  [CoinGecko] {e}", file=sys.stderr)
    return results


def search_earthquake(min_mag=4.5, limit=5):
    """USGS 地震数据 — 全球实时地震信息，免费CORS开放。"""
    from datetime import datetime
    results = []
    try:
        params = urllib.parse.urlencode({
            "format": "geojson", "limit": limit,
            "minmagnitude": min_mag, "orderby": "time"
        })
        url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?{params}"
        data = json.loads(_fetch(url, timeout=8))
        for feat in data.get("features", [])[:limit]:
            props = feat.get("properties", {})
            place = props.get("place", "")
            mag = props.get("mag", 0)
            t = props.get("time", 0)
            event_url = props.get("url", "")
            ts = datetime.fromtimestamp(t/1000).strftime('%Y-%m-%d %H:%M') if t else ""
            results.append({
                "title": f"[地震] M{mag} {place}",
                "url": event_url,
                "snippet": ts,
                "engine": "USGS"
            })
    except Exception as e:
        print(f"  [USGS] {e}", file=sys.stderr)
    return results


def search_wikidata_entity(query):
    """Wikidata SPARQL — 结构化知识图谱，实体/关系查询，免费无key。"""
    results = []
    try:
        # Entity search first
        params = urllib.parse.urlencode({
            "action": "wbsearchentities", "search": query,
            "language": "zh", "limit": 3, "format": "json"
        })
        data = json.loads(_fetch(f"https://www.wikidata.org/w/api.php?{params}", timeout=8))
        for item in data.get("search", [])[:3]:
            qid = item.get("id", "")
            label = item.get("label", "")
            desc = item.get("description", "")
            results.append({
                "title": f"[Wikidata] {label} ({qid})",
                "url": f"https://www.wikidata.org/wiki/{qid}",
                "snippet": desc,
                "engine": "Wikidata"
            })
    except Exception as e:
        print(f"  [Wikidata] {e}", file=sys.stderr)
    return results


def search_frankfurter_forex(base="USD", targets=None):
    """Frankfurter 欧洲央行汇率 — 免费CORS开放，168种货币，比OpenER更稳定。"""
    results = []
    if not targets:
        targets = ["CNY", "EUR", "JPY", "GBP", "HKD"]
    try:
        symbols = ",".join(targets)
        url = f"https://api.frankfurter.app/latest?from={base}&to={symbols}"
        data = json.loads(_fetch(url, timeout=8))
        rates = data.get("rates", {})
        date = data.get("date", "")
        for target, rate in rates.items():
            results.append({
                "title": f"[ECB汇率] {base}/{target}",
                "url": f"https://www.frankfurter.app/",
                "snippet": f"{date} | 1 {base} = {rate} {target}",
                "engine": "Frankfurter"
            })
    except Exception as e:
        print(f"  [Frankfurter] {e}", file=sys.stderr)
    return results


def search_holiday(country="CN", year=None):
    """公共假日查询 — Nager.Date API，全球法定节假日，免费CORS开放。"""
    from datetime import datetime
    results = []
    try:
        if not year:
            year = datetime.now().year
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
        holidays = json.loads(_fetch(url, timeout=8))
        for h in holidays[:8]:
            date = h.get("date", "")
            name = h.get("localName") or h.get("name", "")
            is_national = h.get("global", True)
            if is_national:
                results.append({
                    "title": f"[假日] {name}",
                    "url": f"https://date.nager.at/",
                    "snippet": date,
                    "engine": "PublicHoliday"
                })
    except Exception as e:
        print(f"  [Holiday] {e}", file=sys.stderr)
    return results


def search_ipinfo(ip=""):
    """IP地理位置 — ipapi.co，免费1000次/天，CORS开放。"""
    results = []
    try:
        url = f"https://ipapi.co/{ip}/json/" if ip else "https://ipapi.co/json/"
        data = json.loads(_fetch(url, timeout=6))
        city = data.get("city","")
        region = data.get("region","")
        country = data.get("country_name","")
        org = data.get("org","")
        ip_addr = data.get("ip","")
        results.append({
            "title": f"[IP定位] {ip_addr}",
            "url": f"https://ipapi.co/{ip_addr}/",
            "snippet": f"{country} {region} {city} — {org}",
            "engine": "ipapi"
        })
    except Exception as e:
        print(f"  [ipapi] {e}", file=sys.stderr)
    return results


def web_search(query, num=10, timeout=10):
    """Multi-engine search: Sogou + Bing + DuckDuckGo.
    Runs engines in parallel, merges and deduplicates by URL.
    Uses only Python standard library.
    """
    import concurrent.futures
    _all_engines = [_ddg_search, _bing_search, _sogou_search, _searxng_search]
    _engine_names = {'_ddg_search': 'DDG', '_bing_search': 'Bing', '_sogou_search': 'Sogou', '_searxng_search': 'SearXNG'}
    engines = [fn for fn in _all_engines if _engine_ok(_engine_names.get(fn.__name__, fn.__name__))]
    if not engines:
        for k in _ENGINE_FAILS: _ENGINE_FAILS[k] = 0
        engines = _all_engines
        print("  [ENGINE] All engines disabled — resetting health counters")
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(engines)) as ex:
        futures = {ex.submit(fn, query, num): fn.__name__ for fn in engines}
        done, _ = concurrent.futures.wait(futures, timeout=timeout)
        for fut in done:
            try:
                all_results.extend(fut.result())
            except Exception:
                pass

    # Deduplicate by URL
    seen = set()
    merged = []
    for r in all_results:
        url_key = (r.get("url") or "").split("?")[0].rstrip("/") or r.get("title","")[:40]
        if url_key not in seen:
            seen.add(url_key)
            merged.append(r)

    # === Re-ranking: BM25-style relevance + date freshness ===
    query_terms = set(query.lower().split())
    # Chinese bigrams for better matching (strict CJK range)
    for i in range(len(query) - 1):
        if '\u4e00' <= query[i] <= '\u9fff' and '\u4e00' <= query[i+1] <= '\u9fff':
            query_terms.add(query[i:i+2])

    for r in merged:
        score = 0
        title_lower = r.get("title", "").lower()
        snippet_lower = r.get("snippet", "").lower()
        # Term frequency in title (weight 3x) and snippet (weight 1x)
        for t in query_terms:
            score += title_lower.count(t) * 3
            score += snippet_lower.count(t) * 1
        # Entity/place/product priority boost
        entity_patterns = [
            r'(?:公司|集团|银行|基金|证券|保险|交易所|央行|证监会)',
            r'(?:北京|上海|广州|深圳|成都|杭州|南京|武汉|重庆|西安|香港|台北|东京|纽约|伦敦|巴黎)',
            r'(?:股票|期货|外汇|黄金|白银|原油|比特币|以太坊|基金|债券|利率|汇率|指数|A股|港股|美股)',
            r'(?:苹果|华为|三星|特斯拉|比亚迪|英伟达|微软|谷歌|亚马逊|Meta|腾讯|阿里|字节)',
        ]
        for pat in entity_patterns:
            if re.search(pat, title_lower): score += 3
        # Engine bonus
        if r.get("engine") == "Sogou": score += 1
        elif r.get("engine") == "Bing": score += 0.5
        elif r.get("engine") == "SearXNG": score += 2  # Self-hosted = freshest results, no anti-bot
        # Date freshness bonus: extract recent dates from snippet
        date_matches = re.findall(r'(\d{4}).*?(\d{1,2})\D+(\d{1,2})', snippet_lower + title_lower)
        if date_matches:
            try:
                from datetime import datetime
                cy = datetime.now().year
                if int(date_matches[0][0]) >= cy - 3:
                    score += 2
            except: pass
        # "小时之前" / "分钟之前" = very recent
        if re.search(r'(\d+)\s*(小时|分钟|天)\s*之前', snippet_lower):
            score += 5
        r["_score"] = score

    # Sort by score descending
    merged.sort(key=lambda r: -(r.get("_score", 0)))

    # Trim to num
    return merged[:num]


# ============ Lottery API Fetcher (huiniao.top - primary) ============
def fetch_lottery_huiniao(lottery_type, num_draws=10):
    """
    Fetch lottery results from huiniao.top API (free, no key).
    lottery_type: 'kl8', 'dlt', 'ssq'
    Returns list of {period, date, numbers} dicts.
    Much cleaner than HTML scraping — JSON API with structured data.
    """
    type_map = {'kl8': 'klb', 'dlt': 'dlt', 'ssq': 'ssq'}
    api_type = type_map.get(lottery_type)
    if not api_type:
        return []

    url = f'http://api.huiniao.top/interface/home/lotteryHistory?type={api_type}&limit={num_draws}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'USB-AI/4.1'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get('code') != 1:
            return []

        items = data['data']['data']['list']
        results = []
        for item in items:
            period = item.get('code', '')
            day = item.get('day', '')
            # Extract numbers from 'one' through 'twenty'/'seven' fields
            nums = []
            for key in ['one','two','three','four','five','six','seven','eight','nine','ten',
                        'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen',
                        'eighteen','nineteen','twenty']:
                if key in item:
                    nums.append(item[key])
            if lottery_type == 'dlt':
                # First 5 = front (1-35), last 2 = back (1-12)
                result_nums = nums[:5] + ['+'] + nums[5:7]
            elif lottery_type == 'ssq':
                # First 6 = red (1-33), last 1 = blue (1-16)
                result_nums = nums[:6] + ['+'] + nums[6:7]
            else:
                result_nums = nums  # kl8: all 20 numbers
            results.append({'period': period, 'date': day, 'numbers': result_nums,
                          'url': f'https://www.00038.cn/kjh/{lottery_type}/{period}.htm'})
        return results
    except Exception as e:
        print(f'  [huiniao] {lottery_type} fetch failed: {e}')
        return []


# ============ Direct Lottery HTML Scraper (00038.cn - fallback) ============
def fetch_direct_lottery(lottery_type, num_draws=10):
    """
    Fetch lottery draw results directly from 00038.cn.
    lottery_type: 'kl8', 'dlt', 'ssq'
    Returns list of {period, numbers, url} dicts sorted by period desc.
    """
    import concurrent.futures

    urls = {
        'kl8': 'https://www.00038.cn/kjh/kl8/',
        'dlt': 'https://www.00038.cn/kjh/dlt/',
        'ssq': 'https://www.00038.cn/kjh/ssq/',
    }
    base = urls.get(lottery_type)
    if not base:
        return []

    results = []
    html = _fetch(base, timeout=12)
    if not html:
        return []

    # Parse main page — kjTable rows
    # kl8: <span class="text-red">02 04 06 ... (20 numbers)</span>
    # dlt: <span class="text-red">06 16 18 19 28 </span>+ <span class="text-blue">07 11</span>
    # ssq: <span class="text-red">12 14 16 17 18 32 </span>+ <span class="text-blue">08</span>
    rows = re.findall(r'<tr>\s*<td[^>]*>(\d+)期</td>\s*<td>(.*?)</td>', html, re.DOTALL)
    for period, raw_html in rows:
        # Extract red (front) numbers and blue (back) numbers
        red_span = re.search(r'<span[^>]*class="[^"]*red[^"]*"[^>]*>(.*?)</span>', raw_html, re.I)
        blue_span = re.search(r'<span[^>]*class="[^"]*blue[^"]*"[^>]*>(.*?)</span>', raw_html, re.I)
        red_nums = re.findall(r'\b(\d{1,2})\b', red_span.group(1)) if red_span else []
        blue_nums = re.findall(r'\b(\d{1,2})\b', blue_span.group(1)) if blue_span else []

        if lottery_type == 'kl8':
            # 20 numbers, all in red span, range 1-80
            valid = [n for n in red_nums if 1 <= int(n) <= 80]
            if len(valid) == 20:
                results.append({'period': period, 'numbers': valid, 'url': f'{base}{period}.htm'})
        elif lottery_type == 'dlt':
            # 5 front (1-35) + 2 back (1-12)
            front = [n for n in red_nums if 1 <= int(n) <= 35]
            back = [n for n in blue_nums if 1 <= int(n) <= 12]
            if len(front) == 5 and len(back) == 2:
                results.append({'period': period, 'numbers': front + ['+'] + back, 'front': front, 'back': back, 'url': f'{base}{period}.htm'})
        elif lottery_type == 'ssq':
            # 6 red (1-33) + 1 blue (1-16)
            reds = [n for n in red_nums if 1 <= int(n) <= 33]
            blues = [n for n in blue_nums if 1 <= int(n) <= 16]
            if len(reds) == 6 and len(blues) == 1:
                results.append({'period': period, 'numbers': reds + ['+'] + blues, 'red': reds, 'blue': blues[0] if blues else '', 'url': f'{base}{period}.htm'})

    # Fetch older detail pages if needed
    if len(results) < num_draws and results:
        last_period = int(results[-1]['period'])
        needed = num_draws - len(results)

        def _fetch_detail(period):
            try:
                url = f'{base}{period}.htm'
                html2 = _fetch(url, timeout=10)
                if not html2:
                    return None
                # Detail page: numbers in ballBox div
                m = re.search(r'class="[^"]*ballBox[^"]*"[^>]*>(.*?)</div>', html2, re.DOTALL)
                if not m:
                    return None
                ball_html = m.group(1)
                # Extract red and blue ball numbers
                reds = re.findall(r'class="[^"]*ball[^"]*red[^"]*"[^>]*>(\d+)<', ball_html, re.I)
                blues = re.findall(r'class="[^"]*ball[^"]*blue[^"]*"[^>]*>(\d+)<', ball_html, re.I)
                if not reds:
                    # Fallback: all balls without color distinction
                    reds = re.findall(r'>(\d{2})<', ball_html)
                    valid = [n for n in reds if 1 <= int(n) <= 80]
                    if lottery_type == 'kl8' and len(valid) == 20:
                        return {'period': str(period), 'numbers': valid, 'url': url}
                    return None

                if lottery_type == 'kl8':
                    valid = [n for n in reds if 1 <= int(n) <= 80]
                    if len(valid) == 20:
                        return {'period': str(period), 'numbers': valid, 'url': url}
                elif lottery_type == 'dlt':
                    front = [n for n in reds if 1 <= int(n) <= 35]
                    back = [n for n in blues if 1 <= int(n) <= 12]
                    if len(front) == 5 and len(back) == 2:
                        return {'period': str(period), 'numbers': front + ['+'] + back, 'front': front, 'back': back, 'url': url}
                elif lottery_type == 'ssq':
                    red = [n for n in reds if 1 <= int(n) <= 33]
                    blue = [n for n in blues if 1 <= int(n) <= 16]
                    if len(red) == 6 and len(blue) == 1:
                        return {'period': str(period), 'numbers': red + ['+'] + blue, 'red': red, 'blue': blue[0] if blue else '', 'url': url}
                return None
            except Exception:
                return None

        periods_to_fetch = [last_period - i for i in range(1, needed + 1)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(_fetch_detail, p): p for p in periods_to_fetch}
            for fut in concurrent.futures.as_completed(futs):
                r = fut.result()
                if r:
                    results.append(r)

        results.sort(key=lambda x: -int(x['period']))

    return results[:num_draws]


# ============ Page Content Fetcher ============
def fetch_page_content(url, max_chars=5000, timeout=10):
    """
    Fetch and extract readable text content from a web page.
    Handles gzip/deflate. Strips scripts/styles/nav and returns plain text.
    Special handling for lottery/finance sites: extracts number sequences first.
    """
    try:
        # Fix common URL issues from search results
        url = url.replace('›', '/').replace('»', '/').replace(' ', '')
        if not url.startswith('http'):
            url = 'https://' + url.lstrip('/')

        # SSRF protection: block private/internal IPs and non-HTTP schemes
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None
        hostname = (parsed.hostname or '').lower()
        if not hostname:
            return None
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return None
        except ValueError:
            pass  # Not an IP, check hostname patterns
        # Block localhost variants
        if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '[::1]', '::1'):
            return None
        if hostname.endswith('.local') or hostname.endswith('.internal'):
            return None
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            enc = r.headers.get("Content-Encoding", "")
            if "gzip" in enc:
                import gzip
                raw = gzip.decompress(raw)
            elif "deflate" in enc:
                import zlib
                raw = zlib.decompress(raw)
        html = raw.decode("utf-8", errors="ignore")

        # Anti-bot detection: Baidu/domestic platforms return security verification (~1400 bytes)
        if len(raw) < 3000 and ('百度安全验证' in html or '安全验证' in html):
            return None

        # === Try to extract lottery/finance numbers before stripping HTML ===
        num_blocks = []
        # Find sequences of 2-digit numbers wrapped in span/td/em tags
        for pattern in [
            r'(?:<span[^>]*>|<td[^>]*>|<em[^>]*>|<b[^>]*>|<strong[^>]*>)\s*(\d{2})\s*</(?:span|td|em|b|strong)>',
        ]:
            nums = re.findall(pattern, html, re.I)
            if len(nums) >= 5:  # Lottery numbers: at least 5 numbers in a row
                # Group consecutive numbers found near each other
                num_blocks.append("开奖号码: " + " ".join(nums[:10]))
                break
        # Also try to find lottery data in JSON-like script blocks
        json_matches = re.findall(
            r'(?:openCode|lottery|kjhm|kaijiang|开奖号码|中奖号码|ballNums)[\s"\':]+(\d[\d\s,，]{5,40})',
            html, re.I
        )
        for m in json_matches[:3]:
            clean_nums = re.sub(r'[^\d]', ' ', m).strip()
            if len(clean_nums) > 8:
                num_blocks.append("号码: " + clean_nums)

        # === Content Cleaner: strip ads, menus, comments, sidebars ===
        # Remove known ad/comment/menu containers by class/id pattern
        for junk_cls in [
            r'class="[^"]*(?:ad|ads|advert|banner|popup|modal|overlay|sidebar|side-bar|menu|nav|comment|footer|header|social|share|related|recommend|hot|trending|widget)[^"]*"',
            r'id="[^"]*(?:ad|ads|advert|banner|popup|modal|overlay|sidebar|side-bar|menu|nav|comment|footer|header)[^"]*"',
        ]:
            html = re.sub(r'<div[^>]*' + junk_cls + r'[\s\S]*?</div>', '', html, flags=re.I)
            html = re.sub(r'<section[^>]*' + junk_cls + r'[\s\S]*?</section>', '', html, flags=re.I)
            html = re.sub(r'<aside[^>]*' + junk_cls + r'[\s\S]*?</aside>', '', html, flags=re.I)
        # Remove remaining structural tags
        for tag in ["script", "style", "nav", "footer", "header", "noscript",
                     "iframe", "svg", "form", "aside", "figure", "figcaption"]:
            html = re.sub(r"<" + tag + r"[^>]*>[\s\S]*?</" + tag + ">", "", html, flags=re.I)
        html = re.sub(r"<!--[\s\S]*?-->", "", html)

        # Block elements -> newlines
        html = re.sub(r"<\s*/\s*(div|p|h[1-6]|li|tr|br|article|section)[^>]*>", "\n", html, flags=re.I)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"&nbsp;", " ", html)
        html = html_mod.unescape(html)

        text = re.sub(r"[ \t]+", " ", html)
        text = re.sub(r"\n\s*\n+", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = text.strip()

        # Keep meaningful lines
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 15]
        text = "\n".join(lines)

        # Prepend any lottery numbers found
        if num_blocks:
            text = "===== 开奖数据 =====\n" + "\n".join(num_blocks) + "\n\n" + text

        if len(text) > max_chars:
            cut = text.rfind("。", 0, max_chars)
            if cut < max_chars // 2:
                cut = text.rfind("\n", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            text = text[:cut] + "..."

        return text
    except Exception as e:
        return None


# ============ AI-Powered Adaptive Data Extraction ============
# Caching: query+text hash → (timestamp, result)
_AI_EXTRACT_CACHE = {}
_AI_CACHE_MAX = 128
_AI_CACHE_TTL = 600  # 10 minutes

def _ai_cache_key(query, text, schema_hint):
    """Hash query + first 500 chars of text + schema hint for cache key."""
    fingerprint = f"{query}|{text[:500]}|{schema_hint or ''}"
    return hashlib.md5(fingerprint.encode()).hexdigest()

def _ai_cache_get(key):
    entry = _AI_EXTRACT_CACHE.get(key)
    if entry:
        ts, result = entry
        if time.time() - ts < _AI_CACHE_TTL:
            return result
        else:
            del _AI_EXTRACT_CACHE[key]
    return None

def _ai_cache_set(key, result):
    if len(_AI_EXTRACT_CACHE) >= _AI_CACHE_MAX:
        oldest = sorted(_AI_EXTRACT_CACHE.items(), key=lambda x: x[1][0])[:16]
        for k, _ in oldest:
            del _AI_EXTRACT_CACHE[k]
    _AI_EXTRACT_CACHE[key] = (time.time(), result)


def _build_extraction_prompt(text, query, schema_hint):
    """Build a strict extraction prompt for DeepSeek."""
    schema_map = {
        "lottery": (
            'Output format: {"lottery_type":"...","draws":['
            '{"period":"2026xxx","numbers":["01","02",...],"date":"..."}]}'
        ),
        "sports": (
            'Output format: {"sport":"...","league":"...","data":['
            '{"match":"TeamA vs TeamB","score":"...","date":"...","stats":{}}, ...]}'
            '\nFor standings: {"standings":[{"rank":1,"team":"...","played":0,"won":0,"points":0}, ...]}'
            '\nFor player stats: {"players":[{"name":"...","team":"...","stats":{}}, ...]}'
        ),
        "financial": (
            'Output format: {"symbol":"...","name":"...","data":['
            '{"date":"...","price":0,"change":0,"volume":0}, ...]}'
            '\nFor rates: {"rates":[{"pair":"USD/CNY","rate":0,"change":0}, ...]}'
            '\nFor commodities: {"commodity":"...","price":0,"unit":"...","change":0}'
        ),
        "tabular": (
            'Output format: {"headers":[...],"rows":[[...],...]}'
        ),
    }
    schema_inst = schema_map.get(schema_hint, (
        'Output format: {"extracted":['
        '{"fact":"...","type":"number|date|entity|quote|summary","source_line":"..."}]}'
    ))

    return f"""You are a data extraction engine. Extract structured data from the text below relevant to the query.

QUERY: {query}

TEXT:
{text}

{schema_inst}

RULES:
- Return ONLY valid JSON. No markdown, no explanations, no code fences.
- Include every number/score/stat/price exactly as written in the text.
- If nothing relevant is found, return {{"extracted":[]}}
- Keep string values concise; prefer arrays for repeated structures.
- Do NOT hallucinate or invent data not present in the text.

JSON:"""


def _detect_schema_hint(query):
    """Auto-detect the best extraction schema based on query keywords."""
    q = query.lower()
    if any(k in q for k in ['彩票','开奖','号码','快乐8','大乐透','双色球','排列','福彩','体彩','中奖','kl8','dlt','ssq']):
        return 'lottery'
    if any(k in q for k in ['比分','赛程','积分','战绩','射手','助攻','篮板','盖帽','抢断',
                              'vs','对阵','首发','阵容','进球','得分','nba','cba','nfl','mlb','nhl',
                              '英超','西甲','意甲','德甲','法甲','中超','欧冠','亚冠',
                              '世界杯','欧洲杯','美洲杯','亚洲杯','联赛','杯赛','决赛',
                              '球队','俱乐部','球员','教练','裁判','转会','身价','主队','客队']):
        return 'sports'
    if any(k in q for k in ['股价','股票','基金','期货','外汇','黄金','白银','原油',
                              '比特币','以太坊','汇率','利率','指数','A股','港股','美股',
                              '上证','深证','纳斯达克','道指','标普','恒生','涨跌',
                              '市值','成交','开盘','收盘','财报','营收','利润']):
        return 'financial'
    if any(k in q for k in ['表格','列表','排名','排行','排行榜','前十','前10','前100','榜单','清单','目录','统计']):
        return 'tabular'
    return None


def extract_entities(user_msg, assistant_msg, api_key, timeout=10):
    """Lightweight entity extraction from a conversation turn.
    Returns list of {type, value, context} or [] on failure. Cheap — uses V3, <100 tokens."""
    if not api_key or len(user_msg) < 10:
        return []
    prompt = (
        "从下面这轮对话提取关键实体（人名/地名/产品/项目/偏好/重要事实），"
        "最多5个，无关紧要的不提取。只返回JSON数组，每项 {\"type\":\"person|place|product|preference|fact\","
        "\"value\":\"...\",\"context\":\"简短说明\"}。无相关实体则返回 []。\n\n"
        f"用户: {user_msg[:300]}\nAI: {assistant_msg[:300]}"
    )
    try:
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300, "temperature": 0
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]
        content = content.strip()
        entities = json.loads(content)
        return entities if isinstance(entities, list) else []
    except Exception as e:
        print(f"  [EntityExtract] {e}", file=sys.stderr)
        return []


def ai_extract(text, query, api_key, schema_hint=None, timeout=30):
    """
    Send compressed text to DeepSeek for structured data extraction.
    Returns {ok, extracted, raw, tokens_used} or {ok:False, error}.
    """
    if not api_key or not text:
        return {"ok": False, "error": "No API key or empty text"}

    cache_key = _ai_cache_key(query, text, schema_hint)
    cached = _ai_cache_get(cache_key)
    if cached:
        print(f"  [AI-Extract] cache hit ({len(text)} chars)")
        return cached

    system_prompt = _build_extraction_prompt(text, query, schema_hint)

    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a JSON data extraction engine. You only output valid JSON, nothing else."},
            {"role": "user", "content": system_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
        "stream": False
    })

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "USB-AI/4.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```\w*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)

        extracted = json.loads(content)
        tokens_used = usage.get("total_tokens", 0)

        result = {
            "ok": True,
            "extracted": extracted.get("extracted", extracted.get("draws", [])),
            "raw": content,
            "tokens_used": tokens_used,
            "lottery_type": extracted.get("lottery_type", ""),
            "draws": extracted.get("draws", []),
            "headers": extracted.get("headers", []),
            "rows": extracted.get("rows", [])
        }
        print(f"  [AI-Extract] ok: {len(result['extracted'])} items, {tokens_used} tokens")
        _ai_cache_set(cache_key, result)
        return result

    except urllib.error.HTTPError as e:
        err_body = ""
        try: err_body = e.read().decode("utf-8", errors="ignore")[:200]
        except: pass
        return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON parse failed: {e}", "raw": content if 'content' in dir() else ""}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _format_ai_extraction(extracted_items, max_items=6):
    """Convert AI-extracted data into icon-prefixed summary format."""
    if not extracted_items:
        return ""
    if isinstance(extracted_items, dict):
        extracted_items = [{"fact": f"{k}: {v}", "type": "summary"} for k, v in extracted_items.items()]
    lines = []
    for item in extracted_items[:max_items]:
        if isinstance(item, str):
            lines.append(f"• {item[:200]}")
            continue
        fact = item.get("fact", item.get("period", str(item)))
        typ = item.get("type", "")
        icon_map = {"number": "📊", "date": "🕐", "entity": "👤",
                     "quote": "💬", "summary": "📌"}
        icon = icon_map.get(typ, "-")
        # If it's a lottery draw entry, format compactly
        if "numbers" in item:
            nums = item["numbers"]
            if isinstance(nums, list):
                nums = " ".join(nums)
            lines.append(f"📊 {fact}: {nums}")
        else:
            lines.append(f"{icon} {fact[:200]}")
    return '\n'.join(lines)


# ============ Local Agent Tools (P1: File Tools + P2: Whitelist Shell) ============
# Path sandbox: all operations restricted to workspace/data/uploads directories.
_ALLOWED_PATHS = [
    os.path.join(SCRIPT_DIR, "workspace"),
    os.path.join(SCRIPT_DIR, "data"),
    os.path.join(SCRIPT_DIR, "uploads"),
]
for _p in _ALLOWED_PATHS:
    os.makedirs(_p, exist_ok=True)

_BLOCKED_PATTERNS = [
    r'^C:\\Windows',
    r'^C:\\Program Files',
    r'^C:\\Program Files \(x86\)',
    r'^/etc/', r'^/usr/',
    r'~/\.ssh', r'~/\.aws', r'~/\.config', r'~/\.gitconfig',
    r'C:\\Users\\[^\\]+\\\.ssh',
    r'C:\\Users\\[^\\]+\\AppData',
]

_SHELL_WHITELIST = {
    "python": {"args": r'^[a-zA-Z0-9_\-./\\: ]+\.py$', "desc": "Run Python script"},
    "pip":    {"args": r'^(install|list|show|freeze)\s+[a-zA-Z0-9_\-\.>=<]+$', "desc": "Python package management"},
    "git":    {"args": r'^(status|log|diff|branch|add|commit|push|pull)\s', "desc": "Git operations"},
    "npm":    {"args": r'^(install|run|test|build|start)\s', "desc": "NPM package management"},
    "node":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+\.js$', "desc": "Run JavaScript"},
    "ls":     {"args": r'^[a-zA-Z0-9_\-./\\: ]*$', "desc": "List directory"},
    "dir":    {"args": r'^[a-zA-Z0-9_\-./\\: ]*$', "desc": "List directory (Windows)"},
    "cat":    {"args": r'^[a-zA-Z0-9_\-./\\: ]+$', "desc": "View file"},
    "type":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+$', "desc": "View file (Windows)"},
    "find":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+\s', "desc": "Find files"},
    "grep":   {"args": r'^[a-zA-Z0-9_\-./\\:"]+\s', "desc": "Search file content"},
    "wc":     {"args": r'^[\-lwc ]+[a-zA-Z0-9_\-./\\: ]+$', "desc": "Count lines/words/chars"},
    "echo":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+$', "desc": "Output text"},
    "which":  {"args": r'^[a-zA-Z0-9_\-./\\:]+$', "desc": "Locate executable"},
    "pwd":    {"args": r'^$', "desc": "Current path"},
    "head":   {"args": r'^\-n\s+\d+\s+[a-zA-Z0-9_\-./\\: ]+$', "desc": "View file beginning"},
    "tail":   {"args": r'^\-n\s+\d+\s+[a-zA-Z0-9_\-./\\: ]+$', "desc": "View file end"},
}

_BLOCKED_COMMANDS = {
    'rm', 'rd', 'rmdir', 'del', 'erase',
    'shutdown', 'reboot', 'restart',
    'format', 'diskpart', 'fdisk', 'mkfs',
    'net', 'netstat', 'ipconfig', 'route',
    'powershell', 'pwsh', 'cmd', 'wsl',
    'sudo', 'su', 'chmod', 'chown', 'chattr',
    'reg', 'regedit', 'sc', 'taskkill', 'kill',
    'mount', 'umount', 'dd',
    'curl', 'wget', 'certutil', 'bitsadmin',
    'ssh', 'scp', 'sftp',
    'perl', 'ruby', 'php', 'gcc', 'g++', 'clang', 'make',
    'eval', 'exec', 'system', 'popen',
}

_TOOL_LOG = os.path.join(SCRIPT_DIR, "data", "tool_log.jsonl")


# P3 TOOL Protocol: AI output [TOOL:name args] → auto-execute → continue stream
_TOOL_PATTERN = re.compile(r'\[TOOL:(\w+)(?:\s+([^\]]*?))?\]')

_TOOL_NAME_MAP = {
    "read_file": ("file", "read_file"),
    "write_file": ("file", "write_file"),
    "append_file": ("file", "append_file"),
    "list_directory": ("file", "file_ls"),
    "create_directory": ("file", "file_mkdir"),
    "move_file": ("file", "file_mv"),
    "delete_file": ("file", "file_rm"),
    "file_info": ("file", "file_stat"),
    "run_command": ("shell", None),
    "run_shell": ("shell", None),
}

_TOOL_SYSTEM_PROMPT = """\n\n## 本地工具调用\n\n你可以使用以下工具操作本地电脑。工具会在你输出调用指令后自动执行，结果会注入对话。\n\nread_file(path): 读取文件内容。path 必须在 workspace/data/uploads 目录内。\nwrite_file(path, content): 写入文件，覆盖已存在文件。content 内 \\n 表示换行、\\t 制表、\\" 表示引号、\\\\ 表示反斜杠。\nappend_file(path, content): 追加内容到文件末尾。转义规则同 write_file。\nlist_directory(path): 列出目录内容。\ncreate_directory(path): 创建新目录。\nmove_file(src, dst): 移动或重命名文件。\ndelete_file(path): 删除文件。\nfile_info(path): 获取文件信息（大小、修改时间）。\nrun_command(command): 在沙箱中执行 Shell 命令。仅白名单命令可用。\nscreenshot(save_path): 截取屏幕截图。save_path 必传！指定保存路径为桌面：C:\\Users\\iobcn\\Desktop\\（以 \\ 结尾自动生成文件名）。不用 save_path 截图不会存到桌面！\nclick(x, y, button, clicks): 模拟鼠标点击。button: left/right/middle。需要用户确认。\ntype_text(text, interval): 在当前光标位置输入文本。非 ASCII 文本用剪贴板粘贴。需要用户确认。\nhotkey(keys): 发送键盘快捷键（如 ctrl+c）。blocked: Ctrl+Alt+Del/Win+R。需要用户确认。\nbrowser_open(url, newTab): 在默认浏览器中打开指定 URL（用于页面测试）。\ntask_create(interval, taskAction, label): 创建定时任务：interval=秒, taskAction=screenshot/ping。最小间隔 5 秒。\ntask_stop(taskId): 停止并删除指定定时任务。\n\n调用格式：\n[TOOL:read_file path="data/example.txt"]\n[TOOL:run_command command="ls workspace/"]\n[TOOL:screenshot save_path="C:\\Users\\iobcn\\Desktop\\"]\n[TOOL:click x="100" y="200" button="left"]\n[TOOL:type_text text="你好世界"]\n[TOOL:hotkey keys="ctrl+s"]\n[TOOL:browser_open url="http://localhost:8082"]\n[TOOL:task_create interval="60" taskAction="screenshot"]\n\n工具结果会自动注入，继续推理。一次只调用一个工具，等待结果后决定下一步。\n\n重要：工具执行完成后，只需简洁告诉用户结果（如"已完成"、"截图已保存到桌面"）。不要输出工具调用代码、base64数据、JSON原始结果。如果工具失败，只说原因（如"截图失败：桌面自动化未开启"）。\n\n\n## 交互规则\n\n与用户沟通时遵循：\n\n1. **消息含义明确** → 直接执行，不啰嗦\n2. **消息简短模糊**（如"计算器""优化""那个文件"）→ 不要猜测后直接做。用以下格式列出 2-3 个最可能的理解：\n\n[CHOICE:1] 选项描述（一句话说清做什么）\n[CHOICE:2] 选项描述\n\n格式要求：\n- 每个 [CHOICE] 独占一行，不要加破折号或编号\n- 选项描述以动词开头（"写一个...""搜索...""打开..."）\n- 选项后附简短提示（"回复数字即可，或直接说你的想法"）\n- 只真正模糊时用，明确消息不强行列选项\n\n示例：\n用户："计算器" → [CHOICE:1] 写一个网页版科学计算器 HTML\n[CHOICE:2] 用 Python 写命令行计算器\n[CHOICE:3] 搜索在线计算器推荐\n回复数字即可，或直接说你的想法"""


def _log_tool_action(action, ok=True, duration=0, tool="file"):
    """Log tool usage to data/tool_log.jsonl."""
    try:
        from datetime import datetime
        entry = {
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "user": "local",
            "tool": tool,
            "action": str(action)[:100],
            "ok": ok,
            "duration": round(duration, 2),
        }
        with open(_TOOL_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _unescape_content(s):
    """Convert JSON-style escape sequences to actual characters.
    Handles \\n, \\t, \\\", \\\\ in file content from AI TOOL calls.
    Uses placeholder to avoid double-processing (\\n should stay literal backslash+n)."""
    s = s.replace('\\\\', '\x00')  # placeholder for backslash
    s = s.replace('\\n', '\n')
    s = s.replace('\\t', '\t')
    s = s.replace('\\"', '"')
    s = s.replace('\x00', '\\')    # restore placeholder
    return s


def _sanitize_path(path):
    """Resolve and verify path is within allowed directories. Returns canonical path or raises."""
    resolved = os.path.realpath(path)
    for allowed in _ALLOWED_PATHS:
        if resolved.startswith(allowed + os.sep) or resolved == allowed:
            return resolved
    raise PermissionError(f"Path not in allowed directories: {path}")


def _check_not_blocked(path):
    """Verify path doesn't match any blocked pattern."""
    for pat in _BLOCKED_PATTERNS:
        if re.match(pat, path, re.IGNORECASE):
            raise PermissionError(f"Blocked path: {path}")


def _run_file_tool(tool, params):
    """Execute file operations within path sandbox. Returns {ok, result?, error?}."""
    t0 = time.time()
    try:
        if tool in ("read_file", "file_read"):
            path = _sanitize_path(params.get("path", ""))
            _check_not_blocked(path)
            if not os.path.isfile(path):
                return {"ok": False, "error": "Not a file or not found"}
            if os.path.getsize(path) > 1_000_000:
                return {"ok": False, "error": "File exceeds 1MB limit"}
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            _log_tool_action(f"read {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True, "content": content[:10000], "truncated": len(content) > 10000}

        elif tool in ("write_file", "file_write"):
            path = _sanitize_path(params.get("path", ""))
            _check_not_blocked(path)
            content = _unescape_content(params.get("content", ""))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            _log_tool_action(f"write {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True, "size": len(content)}

        elif tool in ("append_file", "file_append"):
            path = _sanitize_path(params.get("path", ""))
            _check_not_blocked(path)
            content = _unescape_content(params.get("content", ""))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)
            _log_tool_action(f"append {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True, "size": len(content)}

        elif tool in ("list_directory", "file_ls"):
            path = _sanitize_path(params.get("path", _ALLOWED_PATHS[0]))
            _check_not_blocked(path)
            if not os.path.isdir(path):
                return {"ok": False, "error": "Not a directory"}
            items = []
            for entry in os.scandir(path):
                items.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0,
                    "modified": entry.stat().st_mtime,
                })
            items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
            _log_tool_action(f"ls {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True, "items": items[:200], "total": len(items)}

        elif tool in ("create_directory", "file_mkdir"):
            path = _sanitize_path(params.get("path", ""))
            _check_not_blocked(path)
            os.makedirs(path, exist_ok=True)
            _log_tool_action(f"mkdir {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True, "path": path}

        elif tool in ("move_file", "file_mv"):
            src = _sanitize_path(params.get("src", ""))
            dst = _sanitize_path(params.get("dst", ""))
            _check_not_blocked(src)
            _check_not_blocked(dst)
            if not os.path.exists(src):
                return {"ok": False, "error": "Source not found"}
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
            _log_tool_action(f"mv {os.path.basename(src)} -> {os.path.basename(dst)}", duration=time.time()-t0)
            return {"ok": True}

        elif tool in ("delete_file", "file_rm"):
            path = _sanitize_path(params.get("path", ""))
            _check_not_blocked(path)
            if not os.path.exists(path):
                return {"ok": False, "error": "Not found"}
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                os.rmdir(path)
            else:
                return {"ok": False, "error": "Not a file or empty directory"}
            _log_tool_action(f"rm {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True}

        elif tool in ("file_info", "file_stat"):
            path = _sanitize_path(params.get("path", ""))
            _check_not_blocked(path)
            if not os.path.exists(path):
                return {"ok": False, "error": "Not found"}
            stat = os.stat(path)
            info = {
                "path": path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": getattr(stat, 'st_ctime', 0),
                "type": "dir" if os.path.isdir(path) else "file",
            }
            _log_tool_action(f"stat {os.path.basename(path)}", duration=time.time()-t0)
            return {"ok": True, "info": info}

        else:
            return {"ok": False, "error": f"Unknown tool: {tool}"}

    except PermissionError as e:
        _log_tool_action(f"{tool} blocked: {e}", ok=False, duration=time.time()-t0)
        return {"ok": False, "error": str(e)}
    except Exception as e:
        _log_tool_action(f"{tool} error: {e}", ok=False, duration=time.time()-t0)
        return {"ok": False, "error": str(e)[:200]}


def _run_shell_cmd(command, timeout=30, workdir=None):
    """Execute whitelisted shell command. No shell=True."""
    t0 = time.time()
    parts = command.strip().split()
    if not parts:
        return {"ok": False, "error": "Empty command"}

    cmd_name = parts[0].lower()

    # 0. Reject shell metacharacters in any argument (; | ` $() $() {} & || &&)
    _metachar = re.compile(r'[;&|`$(){}\[\]<>]')
    for p in parts:
        if _metachar.search(p):
            _log_tool_action(f"shell meta chars: {command[:80]}", ok=False, tool="shell", duration=time.time()-t0)
            return {"ok": False, "error": "Shell metacharacters not allowed"}

    # 1. Blocklist check
    if cmd_name in _BLOCKED_COMMANDS:
        _log_tool_action(f"shell blocked: {cmd_name}", ok=False, tool="shell", duration=time.time()-t0)
        return {"ok": False, "error": f"Command blocked: {cmd_name}"}

    # 2. Whitelist check
    if cmd_name not in _SHELL_WHITELIST:
        _log_tool_action(f"shell unknown: {cmd_name}", ok=False, tool="shell", duration=time.time()-t0)
        return {"ok": False, "error": f"Not in whitelist: {cmd_name}"}

    entry = _SHELL_WHITELIST[cmd_name]
    args_str = ' '.join(parts[1:])
    if not re.match(entry["args"], args_str):
        _log_tool_action(f"shell bad args: {cmd_name} {args_str[:50]}", ok=False, tool="shell", duration=time.time()-t0)
        return {"ok": False, "error": f"Args pattern mismatch: {args_str[:100]}"}

    # 2a. Block -exec/-ok/-execdir in find (bypass blocked commands)
    if cmd_name == "find":
        for p in parts[1:]:
            if p in ("-exec", "-ok", "-execdir"):
                _log_tool_action(f"shell find -exec blocked: {command[:80]}", ok=False, tool="shell", duration=time.time()-t0)
                return {"ok": False, "error": "find -exec/-ok not allowed"}

    # 3. Working directory
    cwd = workdir or _ALLOWED_PATHS[0]
    os.makedirs(cwd, exist_ok=True)

    # 4. Execute (no shell=True)
    try:
        import subprocess
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env={**os.environ, "PATH": os.environ.get("PATH", "")},
        )
        duration = time.time() - t0
        _log_tool_action(f"shell {command[:100]}", ok=result.returncode == 0, tool="shell", duration=duration)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "returnCode": result.returncode,
            "duration": round(duration, 2),
        }
    except subprocess.TimeoutExpired:
        _log_tool_action(f"shell timeout: {command[:50]}", ok=False, tool="shell", duration=time.time()-t0)
        return {"ok": False, "error": f"Timeout ({timeout}s)"}
    except FileNotFoundError:
        _log_tool_action(f"shell not found: {parts[0]}", ok=False, tool="shell", duration=time.time()-t0)
        return {"ok": False, "error": f"Command not found: {parts[0]}"}
    except Exception as e:
        _log_tool_action(f"shell error: {e}", ok=False, tool="shell", duration=time.time()-t0)
        return {"ok": False, "error": str(e)[:200]}


# ============ P3 TOOL Protocol Helper Functions ============


def _parse_tool_args(args_str):
    """Parse 'key=\"value\" key2=\"value2\"' into dict."""
    args = {}
    for m in re.finditer(r'(\w+)="([^"]*)"', args_str):
        args[m.group(1)] = m.group(2)
    return args


def _execute_tool_from_str(tool_name, args_str, api_key=None):
    """Parse [TOOL:name args] and execute via local tool system."""
    mapping = _TOOL_NAME_MAP.get(tool_name)
    if mapping:
        action_type, tool_method = mapping
        args = _parse_tool_args(args_str)
        if action_type == "file":
            result = _run_file_tool(tool_method, args)
        elif action_type == "shell":
            cmd = args.get("command", "")
            timeout = int(args.get("timeout", "30"))
            result = _run_shell_cmd(cmd, timeout)
        else:
            result = {"ok": False, "error": f"Unknown tool type: {action_type}"}
        _log_tool_action(f"P3 TOOL: {tool_name}", ok=result.get("ok", False), tool="p3_tool")
        return result

    # Desktop automation tools (routed via tool args directly)
    args = _parse_tool_args(args_str)
    if tool_name == "screenshot":
        result = tool_screenshot(region=args.get("region"), save_path=args.get("save_path"))
    elif tool_name == "click":
        result = tool_mouse_click(int(args.get("x", 0)), int(args.get("y", 0)),
                                  button=args.get("button", "left"),
                                  clicks=int(args.get("clicks", "1")))
    elif tool_name == "type_text":
        result = tool_type_text(args.get("text", ""),
                                interval=float(args.get("interval", "0.05")))
    elif tool_name == "hotkey":
        keys = args.get("keys", "")
        result = tool_hotkey(*[k.strip() for k in keys.split("+") if k.strip()])
    elif tool_name == "browser_open":
        result = tool_browser_open(args.get("url", ""),
                                   new_tab=args.get("newTab", "true").lower() == "true")
    elif tool_name == "task_create":
        result = tool_task_create(int(args.get("interval", "60")),
                                  args.get("taskAction", "ping"),
                                  args.get("label", ""))
    elif tool_name == "task_stop":
        result = tool_task_stop(args.get("taskId", ""))
    else:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}
    _log_tool_action(f"P3 TOOL: {tool_name}", ok=result.get("ok", False), tool="p3_tool")
    return result


def _fmt_tool_result(tool_name, result):
    """Format tool execution result as XML for AI continuation.
    Base64/image data is truncated to avoid context blow-up."""
    ok = result.get("ok", False)
    parts = [f'<tool_result tool="{tool_name}" ok="{str(ok).lower()}">']
    if result.get("content"):
        parts.append(str(result["content"])[:5000])
    if result.get("stdout"):
        parts.append(str(result["stdout"])[:3000])
    if result.get("stderr"):
        parts.append(f'<stderr>{str(result["stderr"])[:1000]}</stderr>')
    if result.get("saved"):
        parts.append(f'<saved>{result["saved"]}</saved>')
        if result.get("file_size_kb"):
            parts.append(f'<size>{result["file_size_kb"]}KB</size>')
    if result.get("image_b64"):
        # ⚠️ No file was saved! AI MUST retry with save_path.
        b64 = result["image_b64"]
        sz = result.get("size", [])
        parts.append(f'<error>文件未保存！截图仅返回了 base64 数据 ({len(b64)//1024}KB)。必须用 save_path="C:\\\\Users\\\\iobcn\\\\Desktop\\\\" 重新调用才能存到桌面！不要告诉用户截图已保存，因为根本没有保存文件。</error>')
    if result.get("error"):
        parts.append(f'<error>{result["error"]}</error>')
    if result.get("truncated"):
        parts.append("(output truncated)")
    parts.append('</tool_result>')
    return '\n'.join(parts)


def _inject_tool_prompt(body_json):
    """Append TOOL protocol instructions to system message."""
    for msg in body_json.get("messages", []):
        if msg.get("role") == "system":
            msg["content"] += _TOOL_SYSTEM_PROMPT
            return
    body_json["messages"].insert(0, {"role": "system", "content": _TOOL_SYSTEM_PROMPT})


def _get_lan_ip():
    """Detect LAN IP address (no deps)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


# ============ Desktop Automation (pyautogui, optional) ============
_AUTO_ENABLED = False

def _check_auto_deps():
    """Check if pyautogui + PIL are installed."""
    d = {}
    try: import pyautogui; d['pyautogui'] = True
    except ImportError: d['pyautogui'] = False
    try: from PIL import Image; d['pillow'] = True
    except ImportError: d['pillow'] = False
    return d

def tool_screenshot(region=None, save_path=None):
    """Screenshot → base64 PNG (or save to file if save_path given).
    Optional region=(x,y,w,h)."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    try:
        import pyautogui
        from PIL import Image
        import io, base64
        img = pyautogui.screenshot(region=region)
        w, h = img.size
        if w > 1280:
            img = img.resize((1280, int(h * 1280 / w)), Image.LANCZOS)
        # Auto-generate filename if save_path is a directory
        if save_path:
            sp = os.path.expandvars(os.path.expanduser(save_path))
            if os.path.isdir(sp) or sp.endswith(('/', '\\')):
                ts = time.strftime("%Y%m%d_%H%M%S")
                sp = os.path.join(sp, f"screenshot_{ts}.png")
            os.makedirs(os.path.dirname(sp) or '.', exist_ok=True)
            img.save(sp, format="PNG", optimize=True)
            fsize = os.path.getsize(sp)
            _log_tool_action("screenshot", ok=True, tool="auto")
            return {"ok": True, "saved": sp, "size": list(img.size),
                    "file_size_kb": round(fsize / 1024, 1)}
        # Return base64
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        _log_tool_action("screenshot", ok=True, tool="auto")
        return {"ok": True, "image_b64": base64.b64encode(buf.getvalue()).decode(),
                "size": list(img.size), "format": "png"}
    except ImportError:
        return {"ok": False, "error": "pip install pyautogui pillow"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_mouse_click(x, y, button="left", clicks=1):
    """Click at screen coordinates. Safety: bounds-checked."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    try:
        import pyautogui as pg
        sw, sh = pg.size()
        if not (0 <= x <= sw and 0 <= y <= sh):
            return {"ok": False, "error": f"坐标超出 {sw}x{sh}"}
        pg.click(x=x, y=y, button=button, clicks=clicks, interval=0.15)
        _log_tool_action("click", ok=True, tool="auto")
        return {"ok": True, "x": x, "y": y, "button": button}
    except ImportError:
        return {"ok": False, "error": "pip install pyautogui pillow"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_type_text(text, interval=0.05):
    """Type text at cursor. Non-ASCII: clipboard paste."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    if len(text) > 5000:
        return {"ok": False, "error": "文本过长（≤5000）"}
    try:
        import pyautogui as pg
        if text.isascii():
            pg.typewrite(text, interval=interval)
        else:
            import subprocess
            subprocess.run(["clip"], input=text.encode("utf-16-le") + b"\x00\x00", check=True)
            pg.hotkey("ctrl", "v")
        _log_tool_action("type_text", ok=True, tool="auto")
        return {"ok": True, "chars": len(text)}
    except ImportError:
        return {"ok": False, "error": "pip install pyautogui pillow"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_hotkey(*keys):
    """Keyboard shortcut. Blocks Ctrl+Alt+Del / Win+R."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    blocked = {frozenset(k.lower() for k in c)
               for c in [["ctrl","alt","delete"], ["ctrl","alt","del"],
                         ["win","r"], ["meta","r"]]}
    if frozenset(k.lower() for k in keys) in blocked:
        return {"ok": False, "error": "快捷键 %s 被安全策略阻止" % '+'.join(keys)}
    try:
        import pyautogui as pg
        pg.hotkey(*keys)
        _log_tool_action("hotkey", ok=True, tool="auto")
        return {"ok": True, "keys": list(keys)}
    except ImportError:
        return {"ok": False, "error": "pip install pyautogui pillow"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_browser_open(url, new_tab=True):
    """Open URL in default browser. For page testing."""
    # Never open the app's own URL — prevents infinite window spam
    import re
    if re.search(r'localhost:8082|127\.0\.0\.1:8082|0\.0\.0\.0:8082', url):
        return {"ok": False, "error": "不能打开USB-AI自身地址"}
    try:
        import webbrowser
        webbrowser.open(url, new=1 if new_tab else 0)
        _log_tool_action("browser_open", ok=True, tool="auto")
        return {"ok": True, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

# Scheduled tasks (simple interval-based timer)
_AUTO_TASKS = {}  # id -> {"interval": seconds, "action": func, "timer": threading.Timer, "running": bool}
_AUTO_TASK_COUNTER = 0

def _auto_task_runner(task_id, action, interval):
    """Timer callback: execute action then reschedule."""
    global _AUTO_TASKS
    if task_id not in _AUTO_TASKS or not _AUTO_TASKS[task_id]["running"]:
        return
    if action == "screenshot":
        tool_screenshot()
    elif action == "ping":
        pass  # Health keepalive
    # Reschedule
    t = threading.Timer(interval, _auto_task_runner, args=(task_id, action, interval))
    t.daemon = True
    _AUTO_TASKS[task_id]["timer"] = t
    t.start()

def tool_task_create(interval, action, label=""):
    """Create a repeating scheduled task."""
    global _AUTO_TASKS, _AUTO_TASK_COUNTER
    _AUTO_TASK_COUNTER += 1
    tid = f"auto_task_{_AUTO_TASK_COUNTER}"
    t = threading.Timer(interval, _auto_task_runner, args=(tid, action, interval))
    t.daemon = True
    _AUTO_TASKS[tid] = {"interval": interval, "action": action, "timer": t,
                         "running": True, "label": label}
    t.start()
    _log_tool_action("task_create", ok=True, tool="auto")
    return {"ok": True, "taskId": tid}

def tool_task_stop(task_id):
    """Stop a scheduled task."""
    global _AUTO_TASKS
    t = _AUTO_TASKS.pop(task_id, None)
    if t:
        t["running"] = False
        try: t["timer"].cancel()
        except: pass
        _log_tool_action("task_stop", ok=True, tool="auto")
        return {"ok": True}
    return {"ok": False, "error": f"任务 {task_id} 不存在"}

def tool_task_list():
    """List all active scheduled tasks."""
    global _AUTO_TASKS
    return {"ok": True, "tasks": [
        {"id": k, "action": v["action"], "interval": v["interval"],
         "label": v["label"], "running": v["running"]}
        for k, v in sorted(_AUTO_TASKS.items()) if v["running"]
    ]}


# ============ AIProxyHandler ============


class AIProxyHandler(http.server.SimpleHTTPRequestHandler):
    """静态文件服务器 + DeepSeek API 代理 + 网络搜索"""

    def do_GET(self):
        """Serve static files + DB API GET"""
        # Serve locally cached vendor assets (offline-first)
        if self.path.startswith("/static/"):
            rel = self.path[len("/static/"):]
            local = os.path.join(SCRIPT_DIR, "static", rel)
            if os.path.isfile(local):
                ext = os.path.splitext(local)[1].lower()
                ct = {".js": "application/javascript", ".css": "text/css"}.get(ext, "application/octet-stream")
                with open(local, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)
            return

        # Health check + diagnostics
        if self.path == "/api/diag":
            diag = {}
            for name, url in [("Bing","https://www.bing.com/"),("Sogou","https://www.sogou.com/"),("DDG","https://api.duckduckgo.com/?q=test&format=json")]:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent":_UA})
                    with urllib.request.urlopen(req, timeout=6) as r:
                        diag[name] = "OK (%d bytes)" % len(r.read())
                except Exception as e: diag[name] = "FAIL: %s" % str(e)[:80]
            # Check local SearXNG
            try:
                req = urllib.request.Request(_SEARXNG_URL + "/search?q=test&format=json", headers={"User-Agent":_UA, "Accept":"application/json"})
                with urllib.request.urlopen(req, timeout=4) as r:
                    diag["SearXNG"] = "RUNNING"
            except Exception as e:
                diag["SearXNG"] = "STOPPED: %s" % str(e)[:60]
            self._send_json(diag)
            return
        if self.path == "/api/ping":
            self._send_json({"ok": True, "engines": ["Sogou", "Bing", "DuckDuckGo", "SearXNG"], "version": "4.1"})
            return
        # Network info for QR code / mobile access
        if self.path == "/api/network-info":
            lan_ip = _get_lan_ip()
            self._send_json({
                "localhost": f"http://localhost:{PORT}",
                "lan": f"http://{lan_ip}:{PORT}",
                "lanIp": lan_ip,
                "port": PORT
            })
            return
        # Entity memory (GET)
        if self.path == "/api/entities":
            entities = db.get_top_entities(limit=10)
            self._send_json({"entities": entities})
            return
        # Local LLM status
        if self.path == "/api/local-llm/status":
            self._send_json({
                "loaded": _LOCAL_LLM is not None,
                "modelPath": _LOCAL_LLM_MODEL,
                "models": _find_gguf_models(),
                "hasDependency": _check_llama_cpp(),
            })
            return
        # DB API routes
        if self.path.startswith("/api/db/"):
            self._handle_db_get()
            return

        # Root -> index.html
        path = self.path.split("?")[0]
        if path == "/" or path == "":
            path = "/index.html"

        # Normalize
        if path.startswith("/"):
            path = path[1:]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.normpath(os.path.join(script_dir, path))
        # Prevent path traversal: file must be inside script directory
        if not filepath.startswith(os.path.normpath(script_dir) + os.sep):
            self.send_error(403)
            return

        if os.path.isfile(filepath):
            self.send_response(200)
            if filepath.endswith(".html"):
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif filepath.endswith(".js"):
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
            elif filepath.endswith(".css"):
                self.send_header("Content-Type", "text/css; charset=utf-8")
            elif filepath.endswith(".json"):
                self.send_header("Content-Type", "application/json; charset=utf-8")
            else:
                self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

    def do_POST(self):
        """Proxy API requests + DB write API"""
        if self.path == "/api/deepseek/stream":
            self._handle_deepseek_stream()
        elif self.path == "/api/deepseek":
            self._handle_deepseek()
        elif self.path == "/api/search":
            self._handle_search()
        elif self.path == "/api/fetch":
            self._handle_fetch()
        elif self.path == "/api/rag":
            self._handle_rag()
        elif self.path == "/api/ai-extract":
            self._handle_ai_extract()
        elif self.path == "/api/tool":
            self._handle_tool()
        elif self.path == "/api/classify":
            self._handle_classify()
        elif self.path == "/api/entities/extract":
            self._handle_entities_extract()
        elif self.path == "/api/local-llm/load":
            self._handle_local_load()
        elif self.path == "/api/local-llm/unload":
            _unload_local_model()
            self._send_json({"ok": True})
        # Desktop automation
        elif self.path == "/api/auto/screenshot":
            self._handle_auto_screenshot()
        elif self.path == "/api/auto/click":
            self._handle_auto_click()
        elif self.path == "/api/auto/type":
            self._handle_auto_type()
        elif self.path == "/api/auto/hotkey":
            self._handle_auto_hotkey()
        elif self.path == "/api/auto/browser":
            self._handle_auto_browser()
        elif self.path == "/api/auto/settings":
            self._handle_auto_settings()
        elif self.path == "/api/auto/task":
            self._handle_auto_task()
        elif self.path == "/api/auto/install":
            self._handle_auto_install()
        elif self.path.startswith("/api/db/"):
            self._handle_db_post()
        else:
            self.send_error(404)

    def _get_llm_url(self, model):
        """Return (url, needs_auth) for the given model.
        Cloud models use DeepSeek API. Local models (with ':' tag) use Ollama.
        '_local_' prefix models use llama-cpp-python (handled separately)."""
        if model.startswith('_local_'):
            return None, False  # Handled by _handle_local_{stream,sync}
        if ':' in model:  # Ollama model tag format
            return "http://localhost:11434/v1/chat/completions", False
        return "https://api.deepseek.com/v1/chat/completions", True

    def _inject_prompt_cache(self, body_json):
        """Prompt cache disabled — DeepSeek API may not support cache_control format.
        TODO: re-enable after verifying DeepSeek support for ephemeral cache_control."""
        return body_json

    def _local_chat_completion(self, messages, stream=False, max_tokens=4096):
        """Call local llama-cpp-python model. Returns (ok, result)."""
        with _LOCAL_LLM_LOCK:
            if _LOCAL_LLM is None:
                return False, {"error": "本地模型未加载"}
            prompt = ""
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    prompt += f"<|system|>\n{content}\n"
                elif role == "user":
                    prompt += f"<|user|>\n{content}\n"
                elif role == "assistant":
                    prompt += f"<|assistant|>\n{content}\n"
            prompt += "<|assistant|>\n"
            try:
                if stream:
                    return True, _LOCAL_LLM.create_completion(
                        prompt, max_tokens=max_tokens, stream=True,
                        temperature=0.7, stop=["<|user|>", "<|system|>"])
                result = _LOCAL_LLM.create_completion(
                    prompt, max_tokens=max_tokens, stream=False,
                    temperature=0.7, stop=["<|user|>", "<|system|>"])
                text = result.get("choices", [{}])[0].get("text", "")
                return True, {"choices": [{"message": {"content": text}}]}
            except Exception as e:
                return False, {"error": str(e)[:300]}

    def _handle_local_stream(self, body_json):
        """SSE streaming from local model."""
        messages = body_json.get("messages", [])
        ok, gen = self._local_chat_completion(messages, stream=True)
        if not ok:
            self.wfile.write(f'data: {json.dumps(gen)}\n\n'.encode())
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
            return ""
        import random
        full_text = ""
        for chunk in gen:
            delta = chunk.get("choices", [{}])[0].get("text", "")
            if not delta:
                continue
            full_text += delta
            sid = f"chatcmpl-{random.randint(100000,999999)}"
            data = json.dumps({
                "id": sid, "object": "chat.completion.chunk",
                "choices": [{"delta": {"content": delta}, "index": 0}]})
            self.wfile.write(f'data: {data}\n\n'.encode())
            self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()
        return full_text

    def _handle_local_sync(self, body_json):
        """Non-streaming response from local model."""
        ok, result = self._local_chat_completion(
            body_json.get("messages", []), stream=False)
        return result if ok else result  # Result dict on both paths

    def _handle_local_load(self):
        """POST /api/local-llm/load — load a GGUF model."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}
            model_path = body.get("modelPath", None)
            ok, msg = _load_local_model(model_path)
            self._send_json({"ok": ok, "message": msg})
        except Exception as e:
            self._send_json({"ok": False, "message": str(e)[:200]})

    # ============ Desktop Automation Handlers ============

    def _require_auto_token(self):
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403)
            return False
        return True

    def _handle_auto_screenshot(self):
        if not self._require_auto_token(): return
        body = self._read_body()
        result = tool_screenshot(region=body.get("region"), save_path=body.get("save_path"))
        self._send_json(result)

    def _handle_auto_click(self):
        if not self._require_auto_token(): return
        body = self._read_body()
        result = tool_mouse_click(int(body.get("x", 0)), int(body.get("y", 0)),
                                  button=body.get("button", "left"),
                                  clicks=body.get("clicks", 1))
        self._send_json(result)

    def _handle_auto_type(self):
        if not self._require_auto_token(): return
        body = self._read_body()
        result = tool_type_text(body.get("text", ""),
                                interval=body.get("interval", 0.05))
        self._send_json(result)

    def _handle_auto_hotkey(self):
        if not self._require_auto_token(): return
        body = self._read_body()
        keys = body.get("keys", [])
        if isinstance(keys, str): keys = keys.split("+")
        result = tool_hotkey(*keys)
        self._send_json(result)

    def _handle_auto_browser(self):
        """Open a URL in the default browser for page testing."""
        if not self._require_auto_token(): return
        body = self._read_body()
        url = body.get("url", "")
        if not url:
            self._send_json({"error": "缺少 url 参数"}, status=400)
            return
        # Safety: only http/https schemes
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            self._send_json({"error": f"不允许的协议: {parsed.scheme}"}, status=400)
            return
        result = tool_browser_open(url, new_tab=body.get("newTab", True))
        self._send_json(result)

    def _handle_auto_settings(self):
        """Enable/disable or query desktop automation status."""
        global _AUTO_ENABLED
        if not self._require_auto_token(): return
        body = self._read_body()
        if "enabled" in body:
            _AUTO_ENABLED = str(body["enabled"]).lower() in ("true", "1", "yes")
            print(f"  [AUTO] {'ENABLED' if _AUTO_ENABLED else 'DISABLED'}")
        deps = _check_auto_deps()
        self._send_json({"ok": True, "enabled": _AUTO_ENABLED,
                          "deps": deps,
                          "missingDeps": [k for k, v in deps.items() if not v]})

    def _handle_auto_task(self):
        """Create/list/stop scheduled tasks."""
        if not self._require_auto_token(): return
        body = self._read_body()
        action = body.get("action", "")  # create | stop | list
        if action == "create":
            interval = int(body.get("interval", 60))
            task_action = body.get("taskAction", "ping")
            label = body.get("label", "")
            if interval < 5:
                self._send_json({"ok": False, "error": "间隔不可小于 5 秒"})
                return
            result = tool_task_create(interval, task_action, label)
            self._send_json(result)
        elif action == "stop":
            result = tool_task_stop(body.get("taskId", ""))
            self._send_json(result)
        elif action == "list":
            self._send_json(tool_task_list())
        else:
            self._send_json({"ok": False, "error": "action 须为 create/stop/list"})

    def _handle_auto_install(self):
        """POST /api/auto/install — install or uninstall pyautogui + pillow.
        Prefers local runtime/auto-deps/ .whl files for offline install."""
        if not self._require_auto_token(): return
        body = self._read_body()
        action = body.get("action", "")
        if action == "install":
            try:
                import subprocess, glob
                auto_dir = os.path.join(SCRIPT_DIR, "runtime", "auto-deps")
                whls = glob.glob(os.path.join(auto_dir, "*.whl")) if os.path.isdir(auto_dir) else []
                if whls:
                    cmd = [sys.executable, "-m", "pip", "install"] + whls + ["--quiet"]
                else:
                    cmd = [sys.executable, "-m", "pip", "install", "pyautogui", "pillow", "--quiet"]
                # Strip proxy vars (Windows system proxy can break pip)
                pip_env = {k: v for k, v in os.environ.items()
                           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
                pip_env["no_proxy"] = "*"
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=pip_env)
                self._send_json({"ok": r.returncode == 0,
                                 "message": "安装成功" if r.returncode == 0 else r.stderr[:200],
                                 "source": "local" if whls else "online"})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)[:200]})
        elif action == "uninstall":
            try:
                import subprocess
                r = subprocess.run([sys.executable, "-m", "pip", "uninstall", "pyautogui", "pillow", "-y"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode == 0:
                    self._send_json({"ok": True, "message": "已卸载"})
                else:
                    self._send_json({"ok": False, "error": r.stderr[:200]})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)[:200]})
        else:
            self._send_json({"ok": False, "error": "action 须为 install/uninstall"})

    def _send_sse_error(self, msg):
        """Send an error as proper SSE event and close stream."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "http://localhost:%d" % PORT))
            self.end_headers()
            self.wfile.write(f'data: {{"error":"{msg}"}}\n\n'.encode())
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
        except Exception:
            pass  # Best effort — connection may already be dead

    def _handle_deepseek_stream(self):
        """Streaming SSE proxy with P3 TOOL protocol support."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        api_key = self.headers.get("X-API-Key", "")

        try:
            body_json = json.loads(body)
        except json.JSONDecodeError as e:
            self._send_sse_error(f"请求JSON解析失败: {str(e)[:200]}")
            return
        body_json["stream"] = True
        model = body_json.get("model", "")
        # Route to local model if model name starts with _local_
        if model.startswith('_local_'):
            ok, msg = _auto_load_local(model)
            if not ok:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", f"http://localhost:{PORT}"))
                self.end_headers()
                self.wfile.write(f'data: {{"error":"{msg}"}}\n\n'.encode())
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", f"http://localhost:{PORT}"))
            self.end_headers()
            self._handle_local_stream(body_json)
            return
        api_url, needs_auth = self._get_llm_url(model)

        # Inject P3 TOOL system prompt into system message
        try:
            _inject_tool_prompt(body_json)
        except Exception as e:
            self._send_sse_error(f"工具提示注入失败: {str(e)[:200]}")
            return
        body_json = self._inject_prompt_cache(body_json)

        # Send SSE headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "http://localhost:%d" % PORT))
        self.end_headers()

        max_rounds = 5
        for _ in range(max_rounds):
            headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
            if needs_auth:
                headers["Authorization"] = f"Bearer {api_key}"

            body_enc = json.dumps(body_json).encode("utf-8")
            import datetime as _dt
            _log_msg = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] STREAM -> {api_url} model={model} key={'***' if api_key else 'MISSING'} body={len(body_enc)}bytes"
            print(_log_msg)
            with open("server_debug.log", "a", encoding="utf-8") as _f: _f.write(_log_msg + "\n")
            req = urllib.request.Request(api_url, data=body_enc, headers=headers, method="POST")

            full_text = ""
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    while True:
                        chunk = resp.readline()
                        if not chunk:
                            break
                        line = chunk.decode('utf-8', errors='replace').strip()
                        # Swallow upstream [DONE] — we decide when to end the stream
                        if line.startswith('data: ') and line[6:].strip() == '[DONE]':
                            continue
                        self.wfile.write(chunk)
                        self.wfile.flush()
                        # Buffer content for TOOL detection
                        if line.startswith('data: '):
                            data_str = line[6:].strip()
                            if data_str:
                                try:
                                    dj = json.loads(data_str)
                                    delta = dj.get('choices', [{}])[0].get('delta', {})
                                    if delta.get('content'):
                                        full_text += delta['content']
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    pass
            except urllib.error.HTTPError as e:
                self.wfile.write(f'data: {{"error":"HTTP {e.code}"}}\n\n'.encode())
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
                return
            except Exception as e:
                import traceback, datetime as _dt
                _err_msg = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] STREAM API FAIL: {api_url} | {e}"
                print(_err_msg)
                traceback.print_exc()
                with open("server_debug.log", "a", encoding="utf-8") as _f:
                    _f.write(_err_msg + "\n")
                    traceback.print_exc(file=_f)
                self.wfile.write(f'data: {{"error":"{str(e)}"}}\n\n'.encode())
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
                return

            # Check for TOOL commands in accumulated response
            match = _TOOL_PATTERN.search(full_text)
            if not match:
                # No more tools — stream complete, send our own [DONE]
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
                return

            # Execute first tool found
            tool_name = match.group(1)
            tool_args_str = match.group(2) or ""
            result = _execute_tool_from_str(tool_name, tool_args_str, api_key)

            # Strip TOOL command from AI response (only text before TOOL)
            tool_pos = full_text.find(match.group(0))
            cleaned = full_text[:tool_pos].strip()

            # Format result as XML for AI to consume
            result_xml = _fmt_tool_result(tool_name, result)

            # Build continuation messages: AI text → tool result → next AI round
            body_json["messages"] = body_json["messages"] + [
                {"role": "assistant", "content": cleaned if cleaned else "..."},
                {"role": "user", "content": result_xml},
            ]

        # Max rounds exhausted — final [DONE]
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def _handle_deepseek(self):
        """Non-streaming DeepSeek proxy with P3 TOOL protocol support."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            api_key = self.headers.get("X-API-Key", "")
            body_json = json.loads(body)
            model = body_json.get("model", "")
            body_json["stream"] = False
            # Route to local model if model name starts with _local_
            if model.startswith('_local_'):
                ok, msg = _auto_load_local(model)
                if not ok:
                    self._send_json({"error": msg}, status=500)
                    return
                result = self._handle_local_sync(body_json)
                if "error" in result:
                    self._send_json(result, status=500)
                else:
                    self._send_json(result)
                return
            api_url, needs_auth = self._get_llm_url(model)

            # Inject P3 TOOL system prompt
            _inject_tool_prompt(body_json)
            body_json = self._inject_prompt_cache(body_json)

            max_rounds = 5
            resp_status = 200
            resp_headers_origin = self.headers.get("Origin", f"http://localhost:{PORT}")
            full_response = {"choices": [{"message": {"content": ""}}]}
            has_response = False

            for _ in range(max_rounds):
                body_enc = json.dumps(body_json).encode("utf-8")
                hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
                if needs_auth:
                    hdrs["Authorization"] = f"Bearer {api_key}"

                req = urllib.request.Request(api_url, data=body_enc, headers=hdrs, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        response_body = resp.read()
                        resp_status = resp.status
                        has_response = True
                except urllib.error.HTTPError as e:
                    response_body = e.read()
                    resp_status = e.code
                    has_response = True

                full_response = json.loads(response_body)
                full_text = full_response.get("choices", [{}])[0].get("message", {}).get("content", "")

                match = _TOOL_PATTERN.search(full_text)
                if not match:
                    # No more tools — send response
                    self.send_response(resp_status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", resp_headers_origin)
                    self.end_headers()
                    self.wfile.write(json.dumps(full_response).encode("utf-8"))
                    return

                # Execute tool
                tool_name = match.group(1)
                tool_args_str = match.group(2) or ""
                result = _execute_tool_from_str(tool_name, tool_args_str, api_key)
                tool_pos = full_text.find(match.group(0))
                cleaned = full_text[:tool_pos].strip()
                result_xml = _fmt_tool_result(tool_name, result)

                # Continuation
                body_json["messages"] = body_json["messages"] + [
                    {"role": "assistant", "content": cleaned if cleaned else "..."},
                    {"role": "user", "content": result_xml},
                ]

            # Max rounds — send last response anyway
            self.send_response(resp_status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", resp_headers_origin)
            self.end_headers()
            self.wfile.write(json.dumps(full_response).encode("utf-8"))
        except Exception as e:
            error = json.dumps({"error": {"message": str(e), "type": "proxy_error"}})
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "http://localhost:%d" % PORT))
            self.end_headers()
            self.wfile.write(error.encode())

    def _handle_search(self):
        """Web search endpoint — multi-engine with query optimization"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))
            raw_query = body.get("query", "")
            num = body.get("num", 10)

            if not raw_query:
                self._send_json({"results": [], "error": "Empty query"})
                return

            # Optimize query for search engines
            query = optimize_query(raw_query)
            print(f"  [search] raw={raw_query[:60]} -> q={query[:60]}")
            results = web_search(query, num=num)

            # === Zero-result recovery chain ===
            if not results:
                # Level 1: try news search (better at recent events)
                news_query = raw_query
                # For exam queries, add Chinese news site context
                if any(k in raw_query for k in ["中考","高考","真题","试题","作文","分数线","录取","成绩"]):
                    news_query = raw_query + " 广西 教育"
                results = search_news(news_query)
                print(f"  [search] news fallback: {len(results)} results")

            if not results:
                # Level 2: broaden query — remove year/location specificity
                broadened = re.sub(r'(20\d{2}[年]?|广西|广东|北京|上海|浙江|江苏|山东|四川|湖南|湖北|福建|河南|河北|江西|安徽|重庆|天津|辽宁|吉林|黑龙江|山西|陕西|云南|贵州|甘肃|青海|海南|西藏|宁夏|新疆|内蒙古)', '', raw_query)
                broadened = re.sub(r'\s+', ' ', broadened).strip()
                if broadened and broadened != raw_query and len(broadened) > 4:
                    print(f"  [search] broaden: {broadened[:60]}")
                    results = web_search(broadened, num=num)

            if not results:
                # Level 3: original raw query (no optimize)
                raw_stripped = re.sub(r'[？?！!。，,、\s]+', ' ', raw_query).strip()
                if raw_stripped != query and len(raw_stripped) > 4:
                    print(f"  [search] raw fallback: {raw_stripped[:60]}")
                    results = web_search(raw_stripped, num=num)

            if "天气" in raw_query: results = search_weather(raw_query) + results
            if any(k in raw_query for k in ["什么是","是谁","百科","定义"]): results = search_wiki(raw_query) + results
            if any(k in raw_query for k in ["新闻","最新"]):
                results = search_news(raw_query) + results
            if any(k in raw_query for k in ["中考","高考","真题","试题","作文","分数线","录取","成绩"]):
                results = search_news(raw_query) + search_edu(raw_query) + results
            for _tags, _fn, _need_raw in [
                (["黄金","金价","白银","铂金","铜价","钯金","比特币","以太坊","加密货币","狗狗币","BTC","ETH"], search_gold_price, False),
                (["原油","石油","油价","WTI","布伦特","Brent","燃料油"], search_oil_price, False),
                (["汽车","买车","报价","配置","保养","保险","油耗","二手","手机","iPhone","华为","小米","OPPO","vivo","三星","回收","置换"], search_products, True),
                (["汇率","美元","欧元","日元","英镑","人民币兑"], search_forex, True),
                (["战争","冲突","军事","导弹","制裁","袭击","局势","入侵","空袭",
                  "选举","当选","总统","抗议","罢工","政变","法案","外交",
                  "新闻","最新","热点","快讯","动态","进展","什么情况"], search_news, True),
                # ---- 新增路由 ----
                (["BNB","SOL","Solana","狗狗币","DOGE","SHIB","ADA","DOT","MATIC","币价","代币","市值"], search_coingecko, True),
                (["arxiv","论文","预印本","paper","研究","学术","AI研究","机器学习论文","deep learning"], search_arxiv, True),
                (["pubmed","医学文献","临床研究","药物研究","基因","生物医学"], search_pubmed, True),
                (["github","开源","代码仓库","star","fork","仓库","repo"], search_github, True),
                (["stackoverflow","报错","stack overflow","编程问题","代码错误","怎么实现"], search_stackoverflow, True),
                (["npm","node包","javascript库","react库","前端依赖"], search_npm, True),
                (["pypi","python包","pip install","python库"], search_pypi, True),
                (["b站","bilibili","热门视频","up主","弹幕","番剧"], search_bilibili_hot, False),
                (["微博热搜","微博热点","微博榜","热搜榜"], search_weibo_hot, False),
                (["知乎热榜","知乎热点","知乎话题"], search_zhihu_hot, False),
                (["地震","震级","地震带","发生地震"], search_earthquake, False),
                (["漏洞","CVE","安全漏洞","exploit","vulnerability","RCE","XSS"], search_cvedb, True),
                (["节假日","法定假日","公共假期","几号放假","假期安排"], search_holiday, False),
                (["GDP","CPI","通胀","失业率","贸易顺差","宏观经济","世界银行"], lambda q: search_world_bank("NY.GDP.MKTP.CD"), False),
                (["澎湃","深度报道","中国新闻","时政新闻"], search_pengpai_rss, True),
                (["新华社","官方新闻","新华","人民日报"], search_xinhua_rss, True),
                (["ip地址","我的ip","ip归属","ip查询","ip定位"], search_ipinfo, True),
                (["实体","是什么","百科","维基数据","wikidata"], search_wikidata_entity, True),
                (["黑客新闻","hacker news","技术热点","科技动态","ProductHunt"], search_hacker_news, True),
            ]:
                if any(k in raw_query for k in _tags):
                    results = (_fn(raw_query) if _need_raw else _fn()) + results

            # Quality check: if results are single-char dictionary garbage, retry with alternate query
            dict_sites = {'baike.baidu.com', 'hanyuguoxue.com', 'chagushici.com', 'zidian.gushici.net', 'shidianguji.com'}
            garbage_count = sum(1 for r in results if any(s in r.get('url', '') for s in dict_sites))
            if garbage_count >= len(results) * 0.6 and len(results) > 0:
                # Results are dictionary entries — try adding context keywords
                alt_query = re.sub(r'[的了吗呢吧啊呀]', '', raw_query)
                alt_query = re.sub(r'\s+', ' ', alt_query).strip()
                if alt_query != query and len(alt_query) > 4:
                    print(f"  [search] low quality, retry: {alt_query[:60]}")
                    results = web_search(alt_query, num=num)
            engines = list(set(r.get("engine", "") for r in results))
            print(f"  [OK] {len(results)} results from {', '.join(engines)}")

            self._send_json({"results": results, "query": query, "engines": engines, "rawQuery": raw_query})

        except Exception as e:
            import traceback
            print(f"  [SEARCH ERROR] {e}")
            traceback.print_exc()
            self._send_json({"results": [], "error": str(e)}, status=500)

    def _handle_rag(self):
        """7-step RAG pipeline: search→fetch→clean→summarize→rank→context→facts."""
        try:
            body = self._read_body()
            raw_query = body.get("query", "")
            num = body.get("num", 8)
            fetch_pages = body.get("fetch", 5)
            max_chars = body.get("maxChars", 6000)

            if not raw_query:
                self._send_json({"error": "Empty query"}, status=400)
                return

            # Detect lottery type early (skip useless web_search for lottery queries)
            lottery_type = None
            direct_lottery_text = ""
            lt_names = {'kl8':'快乐8','dlt':'大乐透','ssq':'双色球'}
            lt_urls = {'kl8':'https://www.00038.cn/kjh/kl8/','dlt':'https://www.00038.cn/kjh/dlt/','ssq':'https://www.00038.cn/kjh/ssq/'}
            if any(k in raw_query for k in ['快乐8','kl8']): lottery_type = 'kl8'
            elif '大乐透' in raw_query: lottery_type = 'dlt'
            elif '双色球' in raw_query: lottery_type = 'ssq'

            api_key = self.headers.get("X-API-Key", "")
            query = optimize_query(raw_query) if not lottery_type else raw_query
            # HyDE: for longer knowledge-seeking queries, generate a hypothetical
            # answer to bridge the vocabulary gap between questions and documents
            if len(query) >= 12 and api_key and not lottery_type \
               and not re.search(r'^(谁是|什么是|几点|多少钱|今天|现在)', query):
                hyde_q = generate_hyde_query(query, api_key, timeout=6)
                if hyde_q and hyde_q != query:
                    query = f"{query} {hyde_q[:60]}"
                    print(f"  [HyDE] {raw_query[:30]}... -> {hyde_q[:50]}...")

            # Step 1: Search or Direct Lottery Fetch
            if lottery_type:
                # Skip web search for lottery — it's useless (Bing splits Chinese terms)
                results = []
                lt_name = lt_names.get(lottery_type, lottery_type)
                # Level 1: AI extraction
                if api_key:
                    try:
                        lt_text = fetch_page_content(lt_urls[lottery_type], max_chars=4000)
                        if lt_text:
                            ai_result = ai_extract(lt_text, raw_query, api_key, schema_hint="lottery", timeout=25)
                            if ai_result.get("ok"):
                                draws = ai_result.get("draws", [])
                                if draws:
                                    lines = [f"【{lt_name} 最近{len(draws)}期开奖号码 — AI提取自 00038.cn】"]
                                    for d in draws:
                                        nums = d.get("numbers", [])
                                        if isinstance(nums, list): nums = " ".join(nums)
                                        period = d.get("period", "?")
                                        lines.append(f"第{period}期: {nums}")
                                    direct_lottery_text = '\n'.join(lines)
                                    print(f"  [RAG] AI lottery: {len(draws)} draws")
                    except Exception as e:
                        print(f"  [RAG] AI lottery failed: {e}")
                # Level 1.5: huiniao.top API (clean JSON, no HTML parsing)
                if not direct_lottery_text:
                    try:
                        draws = fetch_lottery_huiniao(lottery_type, num_draws=10)
                        if draws:
                            lines = [f"【{lt_name} 最近{len(draws)}期开奖号码 — 来源: huiniao.top API】"]
                            for d in draws:
                                lines.append(f"第{d['period']}期({' '.join(d['numbers'])}) {d.get('date','')}")
                            direct_lottery_text = '\n'.join(lines)
                            print(f"  [RAG] API lottery: {len(draws)} draws")
                    except Exception as e:
                        print(f"  [RAG] API lottery failed: {e}")
                # Level 2: Regex fallback (00038.cn HTML scraper)
                if not direct_lottery_text:
                    try:
                        draws = fetch_direct_lottery(lottery_type, num_draws=10)
                        if draws:
                            lines = [f"【{lt_name} 最近{len(draws)}期开奖号码 — 来源: 00038.cn】"]
                            for d in draws:
                                lines.append(f"第{d['period']}期: {' '.join(d['numbers'])}")
                            direct_lottery_text = '\n'.join(lines)
                            print(f"  [RAG] regex lottery: {len(draws)} draws")
                    except Exception as e:
                        print(f"  [RAG] regex lottery failed: {e}")
            else:
                # Run web_search + direct data sources in parallel (no blocking wait)
                import concurrent.futures as _cf
                _ex = _cf.ThreadPoolExecutor(max_workers=4)
                _futures = [_ex.submit(web_search, query, num)]
                # Data-driven dispatch: (tags, fetcher, needs_raw_query)
                for _tags, _fn, _need_raw in [
                    (["黄金","金价","白银","铂金","铜价","钯金","比特币","以太坊","加密货币","狗狗币","币价","BTC","ETH"], search_gold_price, False),
                    (["原油","石油","油价","WTI","布伦特","Brent","燃料油"], search_oil_price, False),
                    (["汽车","买车","报价","配置","保养","保险","油耗","二手","手机","iPhone","华为","小米","OPPO","vivo","三星","回收","置换"], search_products, True),
                    (["汇率","美元","欧元","日元","英镑","人民币兑"], search_forex, True),
                    (["天气","气温"], search_weather, True),
                    (["战争","冲突","军事","导弹","制裁","袭击","局势","入侵","空袭",
                      "选举","当选","总统","抗议","罢工","政变","法案","外交",
                      "新闻","最新","热点","快讯","动态","进展","什么情况"], search_news, True),
                    # ---- 新增 RAG 路由 ----
                    (["BNB","SOL","Solana","狗狗币","DOGE","SHIB","ADA","DOT","MATIC","币价","代币","市值"], search_coingecko, True),
                    (["arxiv","论文","预印本","paper","研究","学术","AI研究","机器学习论文","deep learning"], search_arxiv, True),
                    (["pubmed","医学","临床","药物","基因","生物医学","医学文献"], search_pubmed, True),
                    (["github","开源","代码仓库","star","仓库","repo"], search_github, True),
                    (["stackoverflow","报错","编程问题","代码错误"], search_stackoverflow, True),
                    (["npm","node包","javascript库","前端依赖"], search_npm, True),
                    (["pypi","python包","pip install","python库"], search_pypi, True),
                    (["b站","bilibili","热门视频"], search_bilibili_hot, False),
                    (["微博热搜","微博热点","热搜榜"], search_weibo_hot, False),
                    (["知乎热榜","知乎话题"], search_zhihu_hot, False),
                    (["地震","震级"], search_earthquake, False),
                    (["漏洞","CVE","安全漏洞","exploit","vulnerability"], search_cvedb, True),
                    (["节假日","法定假日","假期安排"], search_holiday, False),
                    (["澎湃","深度报道","中国时政"], search_pengpai_rss, True),
                    (["新华社","官方新闻"], search_xinhua_rss, True),
                    (["ip地址","ip归属","ip查询"], search_ipinfo, True),
                    (["实体","维基数据","wikidata"], search_wikidata_entity, True),
                    (["hacker news","技术热点","科技社区"], search_hacker_news, True),
                ]:
                    if any(k in raw_query for k in _tags):
                        _futures.append(_ex.submit(_fn, raw_query) if _need_raw else _ex.submit(_fn))
                # Wait max 8s for direct sources; web_search may take longer
                done, _ = _cf.wait(_futures, timeout=8)
                results = []
                for _f in done:
                    try: results.extend(_f.result())
                    except: pass
                _ex.shutdown(wait=False)  # Don't block on unfinished web_search

                # Step-Back: for long/specific queries, also search a broader
                # background query to capture context the specific query misses
                if len(query) >= 15 and api_key:
                    stepback_q = generate_stepback_query(query, api_key, timeout=5)
                    if stepback_q:
                        print(f"  [StepBack] {query[:30]}... -> {stepback_q}")
                        try:
                            sb_results = web_search(stepback_q, num=3, timeout=6)
                            if sb_results:
                                results = sb_results[:2] + results
                        except Exception as e:
                            print(f"  [StepBack search] {e}", file=sys.stderr)

                if not results:
                    # Retry: use raw_query directly (query may have lost key digits from optimize_query)
                    simpler = raw_query.strip()
                    if len(simpler) >= 2 and simpler != query:
                        print(f"  [RAG] retry raw: {simpler[:60]}")
                        results = web_search(simpler, num=num)
                    # Still nothing? Try English fallback for geopolitical/news queries
                    if not results and any(k in raw_query for k in ['战争','冲突','军事','导弹','制裁','局势','选举','总统','外交','新闻','最新','动态']):
                        _en_terms = [t for t in raw_query.split() if len(t) >= 2]
                        _en_map = {'美国':'US','以色列':'Israel','伊朗':'Iran','俄罗斯':'Russia','乌克兰':'Ukraine','中国':'China','朝鲜':'North Korea','韩国':'South Korea','印度':'India','日本':'Japan','战争':'war','冲突':'conflict','最新':'latest','新闻':'news','军事':'military','导弹':'missile','制裁':'sanctions','局势':'situation','选举':'election'}
                        _en_q = ' '.join([_en_map.get(t, t) for t in _en_terms if len(t) >= 2])
                        if _en_q != ' '.join(terms) and len(_en_q) > 5:
                            print(f"  [RAG] retry english: {_en_q}")
                            results = web_search(_en_q, num=num)
                            if results:
                                results = search_news(_en_q) + results

                # Relevance filter: remove dictionary/wiki results for technical queries
                results = [r for r in results if not any(d in r.get('url', '') for d in JUNK_DOMAINS)]
                # Relevance scoring: discard if results are clearly off-target
                # But for news/geopolitics queries, keep results — Chinese terms won't match English titles
                _is_news_query = any(k in raw_query for k in ['战争','冲突','军事','导弹','制裁','袭击','局势','入侵','空袭','选举','当选','总统','抗议','罢工','政变','法案','外交','新闻','最新','热点','快讯','动态','进展','什么情况'])
                if results and len(results) > 0 and not _is_news_query:
                    q_terms = set(query.lower().split())
                    q_terms.update(tokenize_query(query))
                    raw_terms = set(raw_query.lower().split())
                    raw_terms.update(tokenize_query(raw_query))
                    all_terms = q_terms | raw_terms
                    scores = []
                    for r in results:
                        title = (r.get('title', '') + ' ' + r.get('snippet', '')).lower()
                        score = sum(1 for t in all_terms if len(t) >= 2 and t in title)
                        scores.append(score)
                    if scores:
                        top_score = max(scores)
                        nonzero = sum(1 for s in scores if s > 0)
                        # Discard: < half relevant AND best < 3 matches
                        # OR only 1 result survives filter with weak match
                        if (nonzero < len(scores) * 0.5 and top_score < 3) or (len(scores) <= 1 and top_score < 3):
                            print(f"  [RAG] low relevance (nonzero={nonzero}/{len(scores)}, top={top_score}), discarding")
                            results = []

            # Step 2-4: Fetch → Clean → Summarize
            contexts = []
            fetched_urls = set()
            per_source_limit = max(200, min(1200, max_chars // max(fetch_pages, 1)))
            # Direct data sources: use snippet directly (already contains the data)
            for r in results[:fetch_pages]:
                url = r.get("url", "")
                engine = r.get("engine", "")
                if not url or url in fetched_urls: continue
                fetched_urls.add(url)
                if engine in DIRECT_ENGINES:
                    # Direct API data — snippet IS the content, no fetch needed
                    # Use title as unique key (URL may be shared, e.g. gold+silver from same API)
                    text = r.get("snippet", "")
                    if text and len(text) > 10:
                        contexts.append({"url":url,"title":r.get("title",""),"text":text,"length":len(text)})
                    continue
                if any(d in url for d in SNIPPET_ONLY_DOMAINS):
                    # Anti-bot blocked domains — skip fetch, use snippet directly
                    snippet = r.get("snippet", "")
                    if snippet and len(snippet) > 20:
                        contexts.append({"url":url,"title":r.get("title",""),"text":snippet[:per_source_limit],"length":len(snippet[:per_source_limit])})
                    continue
                text = fetch_page_content(url, max_chars=8000)
                if text and len(text) > 100:
                    compressed = compress_context(text, raw_query, max_chars=per_source_limit)
                    if compressed:
                        contexts.append({"url":url,"title":r.get("title",""),"text":compressed,"length":len(compressed)})
                else:
                    # Fetch failed (anti-bot, timeout, blocked) — fallback to search snippet
                    snippet = r.get("snippet", "")
                    if snippet and len(snippet) > 30:
                        contexts.append({"url":url,"title":r.get("title",""),"text":snippet[:per_source_limit],"length":len(snippet[:per_source_limit])})

            # Step 5: Search Re-ranking (already done in web_search)

            # Step 6: Context Builder
            from datetime import datetime as _dt
            _now = _dt.now()
            _search_time = _now.strftime('%Y-%m-%d %H:%M:%S')
            rag_context = f"""===== 时间信息 =====
Search Time: {_search_time} UTC+8
Current Date: {_now.strftime('%Y-%m-%d')}
"""
            # Prepend direct lottery data
            if direct_lottery_text:
                rag_context += "\n" + direct_lottery_text + "\n\n"
            summaries = []
            for ctx in contexts:
                s = None
                # Level 1: AI extraction
                if api_key:
                    try:
                        ai = ai_extract(ctx["text"], raw_query, api_key, schema_hint=_detect_schema_hint(raw_query), timeout=20)
                        if ai.get("ok") and ai.get("extracted"):
                            s = _format_ai_extraction(ai["extracted"], max_items=4)
                    except Exception:
                        pass
                # Level 2: Regex fallback
                if not s:
                    s = generate_summary(ctx["text"], raw_query, max_items=4)
                if s: summaries.append(f"[来源{len(summaries)+1}: {ctx['title']}]\n{s}")
            if summaries:
                rag_context += "===== 关键事实 =====\n" + '\n\n'.join(summaries) + "\n\n"
            rag_context += "===== 详细上下文 =====\n"
            for i, ctx in enumerate(contexts):
                rag_context += f"\n[来源{i+1}: {ctx['title']}]\n{ctx['text']}\n"

            # Step 7: Fact Extraction
            facts = []
            if direct_lottery_text:
                facts.append(direct_lottery_text)
            for ctx in contexts:
                extracted = None
                # Level 1: AI extraction (reuse cached if available)
                if api_key:
                    try:
                        ai = ai_extract(ctx["text"], raw_query, api_key, schema_hint=_detect_schema_hint(raw_query), timeout=20)
                        if ai.get("ok") and ai.get("extracted"):
                            extracted = _format_ai_extraction(ai["extracted"], max_items=3)
                    except Exception:
                        pass
                # Level 2: Regex fallback
                if not extracted:
                    extracted = generate_summary(ctx["text"], raw_query, max_items=3)
                if extracted: facts.append(extracted)



            print(f"  [RAG] {len(results)} results → {len(contexts)} pages → {len(rag_context)} chars context")
            self._send_json({
                "context": rag_context,
                "facts": facts,
                "sources": contexts,
                "searchResults": results,
                "query": query,
                "engines": list(set(r.get("engine","") for r in results))
            })
        except Exception as e:
            import traceback
            print(f"  [RAG ERROR] {e}")
            traceback.print_exc()
            self._send_json({"error": str(e)}, status=500)

    def _handle_ai_extract(self):
        """AI-powered data extraction from text."""
        try:
            body = self._read_body()
            text = body.get("text", "")
            query = body.get("query", "")
            schema_hint = body.get("schemaHint", None)
            api_key = self.headers.get("X-API-Key", "")

            if not text or not query:
                self._send_json({"error": "Missing text or query"}, status=400)
                return

            result = ai_extract(text, query, api_key, schema_hint, timeout=30)
            self._send_json(result)

        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_tool(self):
        """Execute local agent tool (file operations / whitelist shell)."""
        try:
            body = self._read_body()
            tool = body.get("tool", "")
            params = body.get("params", {})
            action_type = body.get("type", "file")  # "file" or "shell"

            if action_type == "shell":
                api_key = self.headers.get("X-API-Key", "")
                if not api_key:
                    self._send_json({"ok": False, "error": "API key required for shell commands"}, status=401)
                    return
                command = params.get("command", "")
                timeout = params.get("timeout", 30)
                workdir = params.get("workdir", None)
                result = _run_shell_cmd(command, timeout, workdir)
            else:
                result = _run_file_tool(tool, params)

            self._send_json(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, status=500)

    def _handle_classify(self):
        """Classify user intent. Uses regex (fast, reliable)."""
        try:
            body = self._read_body()
            query = body.get("query", "")
            if not query:
                self._send_json({"intent": "general", "method": "regex"})
                return

            # Regex-based classification (fast, no API cost)
            lottery_re = r'彩票|开奖|号码|快乐8|大乐透|双色球|排列|福彩|体彩|中奖|选五|选九|选十'
            realtime_re = r'天气|股价|股票|汇率|新闻|最新|今天|现在|实时|比分|赛程|比赛|世界杯|欧冠|NBA|足球|篮球|网球|F1|奥运|金牌|金牌榜|高考|中考|真题|试题|作文|分数线|录取|成绩|体育|中超|英超|西甲|意甲|亚运|冠军|电竞|汽车|车型|新能源|电动车|特斯拉|续航|电器|家电|电视|冰箱|洗衣机|空调|电脑|编程|代码|开发|芯片|半导体|软件|军事|军队|武器|导弹|航母|国防|科技|科学|航天|太空|火箭|人工智能|机器学习|量子|微博热搜|知乎热榜|b站|bilibili|地震|ip地址|节假日|热搜|热榜'
            financial_re = r'股票|股价|基金|A股|港股|美股|纳斯达克|道指|标普|恒生|上证|深证|黄金|白银|原油|比特币|以太坊|期货|外汇|利率|CPI|GDP|通胀|SOL|BNB|狗狗币|DOGE|代币|市值|coingecko'

            if re.search(lottery_re, query): intent = 'lottery'
            elif re.search(realtime_re, query): intent = 'realtime'
            elif re.search(financial_re, query): intent = 'financial'
            else: intent = 'general'

            self._send_json({"intent": intent, "method": "regex"})

        except Exception as e:
            self._send_json({"error": str(e)}, status=500)


    def _handle_fetch(self):
        """Fetch page content from a URL and return extracted text."""
        try:
            body = self._read_body()
            url = body.get("url", "")
            max_chars = body.get("maxChars", 5000)
            if not url:
                self._send_json({"error": "Missing url"}, status=400)
                return
            print(f"  [fetch] {url[:100]}")
            text = fetch_page_content(url, max_chars=max_chars)
            if text:
                self._send_json({"ok": True, "text": text, "url": url, "length": len(text)})
            else:
                self._send_json({"ok": False, "url": url, "error": "Failed to fetch"})
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    # ============ Database API handlers ============

    def _read_body(self):
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > 10_000_000:
                raise ValueError("Content too large")
            raw = self.rfile.read(cl)
            if cl > 0:
                return json.loads(raw)
            return {}
        except json.JSONDecodeError as e:
            print(f"  [API] JSON parse error: {e}", file=sys.stderr)
            log_error("api", "JSONDecodeError", str(e)[:200])
            raise
        except ValueError:
            raise

    def _parse_qs(self):
        """Parse query string params"""
        qs = urllib.parse.urlparse(self.path).query
        return dict(urllib.parse.parse_qsl(qs))

    def _handle_db_get(self):
        global db
        path = self.path.split("?")[0]
        try:
            if path == "/api/db/settings":
                self._send_json(db.get_settings())
            elif path == "/api/db/chats":
                cid = self._parse_qs().get("id")
                if cid:
                    chat = db.get_conversation(cid)
                    self._send_json(chat if chat else {"error": "Not found"}, status=404 if not chat else 200)
                else:
                    self._send_json(db.list_conversations())
            elif path == "/api/db/tasks":
                self._send_json(db.list_tasks())
            elif path == "/api/db/memories":
                self._send_json(db.list_memories())
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_db_post(self):
        global db
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403)
            return
        path = self.path.split("?")[0]
        try:
            body = self._read_body()
            if path == "/api/db/settings":
                # Never store API Key in DB
                body.pop("apiKey", None)
                db.save_settings(body)
                self._send_json({"ok": True})
            elif path == "/api/db/chats":
                cid = body.get("id") or self._parse_qs().get("id")
                if not cid:
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                db.save_conversation(cid, body.get("title", ""), body.get("messages", []), body.get("isAuto", False))
                self._send_json({"ok": True})
            elif path == "/api/db/tasks":
                tid = db.save_task(body)
                self._send_json({"ok": True, "id": tid})
            elif path == "/api/db/memories":
                mid = db.save_memory(body)
                self._send_json({"ok": True, "id": mid})
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_db_delete(self):
        global db
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403)
            return
        path = self.path.split("?")[0]
        try:
            params = self._parse_qs()
            if path == "/api/db/chats":
                cid = params.get("id")
                if not cid:
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                db.delete_conversation(cid)
                self._send_json({"ok": True})
            elif path == "/api/db/tasks":
                tid = params.get("id")
                if tid is None:
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                try:
                    tid = int(tid)
                    if tid <= 0:
                        self._send_json({"error": "Invalid id"}, status=400)
                        return
                except (TypeError, ValueError):
                    self._send_json({"error": "Invalid id"}, status=400)
                    return
                db.delete_task(tid)
                self._send_json({"ok": True})
            elif path == "/api/db/memories":
                mid = params.get("id")
                if not mid:
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                try:
                    db.delete_memory(int(mid))
                except ValueError:
                    self._send_json({"error": "Invalid id"}, status=400)
                    return
                self._send_json({"ok": True})
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_db_put(self):
        """Handle PUT for updating tasks/memories"""
        global db
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403)
            return
        path = self.path.split("?")[0]
        try:
            body = self._read_body()
            if path == "/api/db/tasks":
                tid = body.get("id")
                if tid is None:
                    try:
                        tid = int(self._parse_qs().get("id")) if self._parse_qs().get("id") else None
                    except (TypeError, ValueError):
                        tid = None
                if tid is None or (isinstance(tid, int) and tid <= 0):
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                db.update_task(int(tid), body)
                self._send_json({"ok": True})
            elif path == "/api/db/memories":
                mid = body.get("id")
                if mid is None:
                    try:
                        mid = int(self._parse_qs().get("id")) if self._parse_qs().get("id") else None
                    except (TypeError, ValueError):
                        mid = None
                if mid is None or (isinstance(mid, int) and mid <= 0):
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                db.update_memory(int(mid), body)
                self._send_json({"ok": True})
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    # ============ End DB handlers ============

    def _handle_entities_extract(self):
        """Extract entities from a conversation turn (fire-and-forget background thread)."""
        try:
            body = self._read_body()
            user_msg = body.get("userMsg", "")
            assistant_msg = body.get("assistantMsg", "")
            api_key = self.headers.get("X-API-Key", "")
            self._send_json({"ok": True, "queued": True})  # respond immediately

            def _bg():
                entities = extract_entities(user_msg, assistant_msg, api_key)
                for e in entities:
                    try:
                        db.upsert_entity(e.get("type", "fact"), e.get("value", ""), e.get("context", ""))
                    except Exception:
                        pass
            threading.Thread(target=_bg, daemon=True).start()
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _send_json(self, data, status=200):
        """Helper to send JSON response with restricted CORS.
        Silently ignores connection errors (client disconnected)."""
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
            pass  # Client disconnected — nothing we can do

    def _check_local_token(self):
        """Validate CSRF token for DB write endpoints."""
        return self.headers.get("X-Local-Token") == LOCAL_TOKEN

    def do_PUT(self):
        """Handle PUT requests for DB updates"""
        if self.path.startswith("/api/db/"):
            self._handle_db_put()
        else:
            self.send_error(404)

    def do_DELETE(self):
        """Handle DELETE requests for DB deletes"""
        if self.path.startswith("/api/db/"):
            self._handle_db_delete()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "http://localhost:%d" % PORT))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization, X-Local-Token")
        self.end_headers()

    def log_message(self, format, *args):
        """Override to add color/prefix"""
        msg = str(args[0]) if args else ""
        if "200" in msg or "101" in msg:
            icon = "[OK]"
        elif "3" in msg[:1]:
            icon = "-->"
        elif "4" in msg[:1]:
            icon = "[!]"
        elif "5" in msg[:1]:
            icon = "[ERR]"
        else:
            icon = "."
        print(f"  {icon} {self.address_string()} — {msg}")




def main():
    global db, LOCAL_TOKEN
    # Switch to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Initialize database
    db = Database(DB_PATH)
    print(f"  [DB] SQLite initialized: {DB_PATH}")
    # Load or persist LOCAL_TOKEN (data/local_token.txt)
    import secrets
    token_path = os.path.join(SCRIPT_DIR, "data", "local_token.txt")
    try:
        with open(token_path) as f:
            LOCAL_TOKEN = f.read().strip()
    except (FileNotFoundError, IOError):
        LOCAL_TOKEN = secrets.token_hex(16)
        try:
            with open(token_path, "w") as f:
                f.write(LOCAL_TOKEN)
        except Exception:
            pass
    _inject_token(LOCAL_TOKEN)
    print(f"  [CSRF] token injected: {LOCAL_TOKEN[:8]}...")
    # Pre-cache vendor assets for offline use
    _ensure_vendor_assets()
    # Check if local SearXNG is running
    try:
        req = urllib.request.Request(_SEARXNG_URL + "/search?q=test&format=json", headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            _ = json.loads(resp.read().decode("utf-8", errors="ignore"))
        print(f"  [SearXNG] local instance running at {_SEARXNG_URL} ✓")
        _engine_success("SearXNG")
    except Exception:
        print(f"  [SearXNG] not running (optional) — install: setup_searxng.bat")
        _engine_fail("SearXNG")


    # Use ThreadingMixIn so long requests don't block Ctrl+C
    from socketserver import ThreadingMixIn
    class ThreadedServer(ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True  # Threads die on exit
    lan_ip = _get_lan_ip()
    bind_addr = "127.0.0.1" if "--local-only" in sys.argv else "0.0.0.0"
    try:
        server = ThreadedServer((bind_addr, PORT), AIProxyHandler)
    except OSError as e:
        print(f"\n[FATAL] 端口 {PORT} 被占用: {e}")
        print(f"  请先关闭其他程序或执行: taskkill /F /IM python.exe")
        return
    if bind_addr == "0.0.0.0":
        print(f"  [NET] 局域网地址: http://{lan_ip}:{PORT}")
        print(f"  [SEC] 警告: 同一网络下其他设备可访问")
    else:
        print(f"  [SEC] 仅本地访问 (--local-only)")
    # QR code for mobile scanning (external API, no deps)
    import urllib.parse
    _qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(f'http://{lan_ip}:{PORT}')}"
    print(f"""
============================================
  USB-AI - 服务器模式
============================================
  本地地址: http://localhost:{PORT}
  局域网:   http://{lan_ip}:{PORT}
  手机扫码: {_qr_api}
  API代理:  /api/deepseek -> DeepSeek API
  多引擎搜索: /api/search -> Sogou + Bing + DDG + SearXNG(本地)
  数据存储: /api/db/*     -> SQLite
  按 Ctrl+C 停止服务器
============================================
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止。")
        server.shutdown()
    except Exception as e:
        print(f"\n[FATAL] 服务器崩溃: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        log_error("server", "FATAL", str(e)[:500])
        server.shutdown()
        print("\n服务器已停止（异常退出）。")


if __name__ == "__main__":
    main()
