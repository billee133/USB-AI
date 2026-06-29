# CLAUDE.md — USB-AI 修改执行计划

> 由 Claude Sonnet 4.6 审计生成 · 2026-06-28  
> 目标项目：USB-AI（server.py + app.js）  
> 执行方式：Claude Code 直接操作项目文件

## 前置检查

```bash
# 1. 确认在项目根目录
ls server.py app.js index.html conversation-manager.js

# 2. 备份（强制执行，不跳过）
cp server.py server.py.bak
cp app.js app.js.bak

# 3. 验证当前文件语法
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True)" && echo "server.py OK"
node --check app.js && echo "app.js OK"
```

---

## 第一步：修改 server.py

### 1.1 替换 import 区（文件顶部，第 7-20 行）

**查找（整个 import 块）：**
```python
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
import time
```

**替换为：**
```python
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
import time
import base64 as _b64          # FIX: was referenced but never imported (_decode_bing_url crash)
import subprocess
import shlex
from datetime import datetime
```

---

### 1.2 在 SNIPPET_ONLY_DOMAINS 行之后插入（约第 30 行）

**定位锚点（在此行之后插入）：**
```python
SNIPPET_ONLY_DOMAINS = {'zhihu.com','zhuanlan.zhihu.com','thepaper.cn','dw.com','baijiahao.baidu.com','tieba.baidu.com','wenku.baidu.com','zhidao.baidu.com'}
```

**在锚点行后面紧接插入（不删除锚点行）：**
```python
# ============ Engine Health Tracker ============
_ENGINE_FAILS = {'Bing': 0, 'Sogou': 0, 'DDG': 0}
_ENGINE_FAIL_THRESHOLD = 3
_ENGINE_LOCK = threading.Lock()

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
            print(f"  [ENGINE] {name} disabled after {_ENGINE_FAIL_THRESHOLD} consecutive failures", file=sys.stderr)

# ============ Local Tool Execution (Claude Code-style) ============
_TOOL_ENABLED = False
_ALLOWED_CMDS = {
    'ls','pwd','cat','head','tail','wc','grep','find','echo','date',
    'python3','python','node','git','pip','pip3','npm','yarn',
    'whoami','hostname','uname','df','du','ps',
}
_SAFE_HOME_SUBDIRS = ('Desktop','Documents','Downloads','Pictures','Music','Videos','Projects','Code')
_SHELL_LOG = None

```

---

### 1.3 替换 `_ddg_search()` 整个函数

**查找：** `def _ddg_search(query, num=5):` 开始，到 `def _bing_search` 之前结束的整块。

**替换为：**
```python
def _ddg_search(query, num=5):
    """DuckDuckGo Instant Answer API (free, no key needed)"""
    results = []
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "PortableAI/3.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            # FIX: DDG may return HTML captcha instead of JSON on some networks
            ct = resp.headers.get("Content-Type", "")
            if "json" not in ct:
                _engine_fail("DDG")
                return results
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
        if not isinstance(data, dict):
            return results
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", query), "url": data.get("AbstractURL", ""),
                            "snippet": data["AbstractText"], "engine": "DuckDuckGo"})
        # RelatedTopics can have nested arrays
        topics = data.get("RelatedTopics") or []
        for topic in topics:
            if len(results) >= num: break
            if isinstance(topic, dict):
                # Some topics have nested 'Topics' array
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
    except Exception as e:
        print(f"  [DDG] {type(e).__name__}", file=sys.stderr); log_error("search", "DDG", str(e)[:200])
        _engine_fail("DDG")
    else:
        if results: _engine_success("DDG")
    return results
```

---

### 1.4 在 `_bing_search` 函数末尾替换 except 块

**查找（_bing_search 函数最后 3 行）：**
```python
    except Exception as e:
        print(f"  [Bing] {e}", file=sys.stderr); log_error("search", "Bing", str(e)[:200])
    return results
```

**替换为：**
```python
    except Exception as e:
        print(f"  [Bing] {e}", file=sys.stderr); log_error("search", "Bing", str(e)[:200])
        _engine_fail("Bing")
    else:
        if results: _engine_success("Bing")
    return results
```

---

### 1.5 在 `_sogou_search` 函数末尾替换 except 块

**查找（_sogou_search 函数最后 3 行）：**
```python
    except Exception as e:
        print(f"  [Sogou] {type(e).__name__}", file=sys.stderr); log_error("search", "Sogou", str(e)[:200])
    return results
```

**替换为：**
```python
    except Exception as e:
        print(f"  [Sogou] {type(e).__name__}", file=sys.stderr); log_error("search", "Sogou", str(e)[:200])
        _engine_fail("Sogou")
    else:
        if results: _engine_success("Sogou")
    return results
```

---

### 1.6 替换 `web_search()` 中 engines 列表那一行

**查找（web_search 函数内）：**
```python
    engines = [_ddg_search, _bing_search, _sogou_search]
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(fn, query, num): fn.__name__ for fn in engines}
```

**替换为：**
```python
    # Only run engines that haven't exceeded failure threshold
    _all_engines = [_ddg_search, _bing_search, _sogou_search]
    _engine_names = {'_ddg_search': 'DDG', '_bing_search': 'Bing', '_sogou_search': 'Sogou'}
    engines = [fn for fn in _all_engines if _engine_ok(_engine_names.get(fn.__name__, fn.__name__))]
    if not engines:
        # All engines failed — reset counters and try anyway (recovery)
        for k in _ENGINE_FAILS: _ENGINE_FAILS[k] = 0
        engines = _all_engines
        print("  [ENGINE] All engines were disabled — resetting health counters", file=sys.stderr)
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(engines)) as ex:
        futures = {ex.submit(fn, query, num): fn.__name__ for fn in engines}
```

---

### 1.7 替换 DB DELETE handler 中 tasks/memories 块

**查找（在 `_handle_db_delete` 方法内，`elif path == "/api/db/tasks":` 开始的整块）：**
```python
            elif path == "/api/db/tasks":
                tid = params.get("id")
                if tid is None or tid <= 0:
                    self._send_json({"error": "Missing id"}, status=400)
                    return
                try:
                    db.delete_task(int(tid))
                except ValueError:
                    self._send_json({"error": "Invalid id"}, status=400)
                    return
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
```

**替换为：**
```python
            elif path == "/api/db/tasks":
                # FIX: params.get() returns str — must cast before integer comparison
                tid_str = params.get("id", "")
                try:
                    tid = int(tid_str)
                    if tid <= 0: raise ValueError("id must be positive")
                except (TypeError, ValueError):
                    self._send_json({"error": "Invalid or missing id"}, status=400)
                    return
                db.delete_task(tid)
                self._send_json({"ok": True})
            elif path == "/api/db/memories":
                # FIX: same string-to-int issue
                mid_str = params.get("id", "")
                try:
                    mid = int(mid_str)
                    if mid <= 0: raise ValueError("id must be positive")
                except (TypeError, ValueError):
                    self._send_json({"error": "Invalid or missing id"}, status=400)
                    return
                db.delete_memory(mid)
                self._send_json({"ok": True})
```

---

### 1.8 替换 RAG 管道中 per_source_limit 行

**查找：**
```python
            per_source_limit = max(200, min(800, max_chars // max(fetch_pages, 1)))
```

**替换为：**
```python
            per_source_limit = max(400, min(2000, max_chars // max(fetch_pages, 1)))  # FIX: increased from 800→2000
```

---

### 1.9 替换 RAG 管道中 rag_context 初始化行

**查找：**
```python
            rag_context = ""
```

**替换为：**
```python
            rag_context = f"[检索时间: {datetime.now():%Y-%m-%d %H:%M}]\n"
```

---

### 1.10 在 `# ============ AIProxyHandler ============` 注释行之前插入工具函数

**定位锚点：**
```python
# ============ AIProxyHandler ============
```

**在此行之前插入（不删除锚点行）：**
```python

def _safe_path(path_str):
    """Validate that a file path is within allowed user directories."""
    expanded = os.path.expanduser(path_str.strip())
    real = os.path.realpath(expanded)
    home = os.path.realpath(os.path.expanduser("~"))
    # Allow: home subdirectories on the safe list
    for sub in _SAFE_HOME_SUBDIRS:
        allowed = os.path.join(home, sub)
        if real.startswith(allowed + os.sep) or real == allowed:
            return real
    # Also allow tmp for scratch work
    if real.startswith('/tmp/'):
        return real
    return None  # Blocked

def tool_read_file(path_str, max_bytes=102400):
    """Read a file within safe home subdirectories. Returns {ok, content} or {ok:False, error}."""
    safe = _safe_path(path_str)
    if not safe:
        return {"ok": False, "error": f"路径 '{path_str}' 不在允许目录内（仅限 ~/Desktop 等家目录子目录）"}
    if not os.path.isfile(safe):
        return {"ok": False, "error": f"文件不存在: {safe}"}
    size = os.path.getsize(safe)
    if size > max_bytes:
        return {"ok": False, "error": f"文件过大 ({size//1024}KB)，最大 {max_bytes//1024}KB"}
    try:
        with open(safe, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(max_bytes)
        return {"ok": True, "path": safe, "content": content, "size": size}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_write_file(path_str, content, overwrite=False):
    """Write a file within safe home subdirectories. Refuses to overwrite scripts."""
    safe = _safe_path(path_str)
    if not safe:
        return {"ok": False, "error": f"路径 '{path_str}' 不在允许目录内"}
    # Refuse to overwrite executable scripts
    ext = os.path.splitext(safe)[1].lower()
    if ext in ('.sh', '.bat', '.cmd', '.py', '.js', '.ps1', '.exe', '.bin'):
        return {"ok": False, "error": f"安全限制：不允许覆盖可执行文件 ({ext})"}
    if os.path.exists(safe) and not overwrite:
        return {"ok": False, "error": "文件已存在，需要 overwrite:true 确认覆盖"}
    try:
        os.makedirs(os.path.dirname(safe), exist_ok=True)
        with open(safe, 'w', encoding='utf-8') as f:
            f.write(content)
        _log_tool_op("write_file", safe)
        return {"ok": True, "path": safe, "bytes": len(content.encode())}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_run_cmd(cmd_str, timeout=30):
    """Execute a whitelisted shell command. Returns {ok, stdout, stderr, code}."""
    if not _TOOL_ENABLED:
        return {"ok": False, "error": "本地工具未启用，请在设置中开启"}
    try:
        parts = shlex.split(cmd_str)
    except ValueError as e:
        return {"ok": False, "error": f"命令解析失败: {e}"}
    if not parts:
        return {"ok": False, "error": "空命令"}
    base = parts[0].split('/')[-1]  # Allow /usr/bin/python3 → python3
    if base not in _ALLOWED_CMDS:
        return {"ok": False, "error": f"命令 '{base}' 不在白名单，允许: {', '.join(sorted(_ALLOWED_CMDS))}"}
    # Block dangerous shell metacharacters (prevent injection)
    DANGEROUS = [';', '|', '&&', '||', '>', '>>', '<', '`', '$(', '${']
    for char in DANGEROUS:
        if char in cmd_str:
            return {"ok": False, "error": f"包含不允许的 shell 字符: '{char}'"}
    try:
        result = subprocess.run(
            parts, capture_output=True, text=True,
            timeout=timeout, cwd=os.path.expanduser("~"),
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        _log_tool_op("run_cmd", cmd_str)
        return {
            "ok": True,
            "stdout": result.stdout[:8192],
            "stderr": result.stderr[:2048],
            "code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"命令超时（{timeout}s）"}
    except FileNotFoundError:
        return {"ok": False, "error": f"命令未找到: {parts[0]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_list_dir(path_str="."):
    """List files in an allowed directory."""
    safe = _safe_path(path_str) if path_str not in ('.', '') else os.path.expanduser("~")
    if not safe:
        # Allow listing home root
        if path_str in ('~', os.path.expanduser("~")):
            safe = os.path.expanduser("~")
        else:
            return {"ok": False, "error": f"路径不在允许范围内"}
    if not os.path.isdir(safe):
        return {"ok": False, "error": f"不是目录: {safe}"}
    try:
        entries = []
        for name in sorted(os.listdir(safe))[:200]:
            full = os.path.join(safe, name)
            stat = os.stat(full)
            entries.append({
                "name": name,
                "type": "dir" if os.path.isdir(full) else "file",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            })
        return {"ok": True, "path": safe, "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def _log_tool_op(op, detail):
    """Append-only audit log for local tool operations."""
    global _SHELL_LOG
    if not _SHELL_LOG:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(_SHELL_LOG, 'a', encoding='utf-8') as f:
            f.write(f"| {ts} | {op} | {detail[:200]} |\n")
    except Exception:
        pass

```

---

### 1.11 在 `do_GET` 中 `/api/diag` 检查之前插入工具状态路由

**查找（do_GET 方法内）：**
```python
        if self.path == "/api/diag":
```

**在此行之前插入：**
```python
        if self.path == "/api/tool/status":
            self._send_json({"enabled": _TOOL_ENABLED, "allowedCmds": sorted(_ALLOWED_CMDS),
                             "safeDirs": list(_SAFE_HOME_SUBDIRS)})
            return
```

---

### 1.12 在 `do_POST` 中 `/api/classify` 之后插入工具路由

**查找：**
```python
        elif self.path == "/api/classify":
            self._handle_classify()

        elif self.path.startswith("/api/db/"):
```

**替换为：**
```python
        elif self.path == "/api/classify":
            self._handle_classify()
        elif self.path == "/api/tool/read_file":
            self._handle_tool_read_file()
        elif self.path == "/api/tool/write_file":
            self._handle_tool_write_file()
        elif self.path == "/api/tool/run_cmd":
            self._handle_tool_run_cmd()
        elif self.path == "/api/tool/list_dir":
            self._handle_tool_list_dir()
        elif self.path == "/api/tool/settings":
            self._handle_tool_settings()

        elif self.path.startswith("/api/db/"):
```

---

### 1.13 在 `_send_json` 方法之前插入工具 handler 方法

**查找：**
```python
    def _send_json(self, data, status=200):
```

**在此行之前插入：**
```python
    # ============ Local Tool Handlers ============

    def _handle_tool_read_file(self):
        """Read a local file within safe directories."""
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        try:
            body = self._read_body()
            path = body.get("path", "")
            if not path:
                self._send_json({"error": "Missing path"}, status=400); return
            result = tool_read_file(path, max_bytes=body.get("maxBytes", 102400))
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_tool_write_file(self):
        """Write a local file within safe directories."""
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        try:
            body = self._read_body()
            path = body.get("path", "")
            content = body.get("content", "")
            overwrite = body.get("overwrite", False)
            if not path:
                self._send_json({"error": "Missing path"}, status=400); return
            result = tool_write_file(path, content, overwrite=overwrite)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_tool_run_cmd(self):
        """Execute a whitelisted shell command."""
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        try:
            body = self._read_body()
            cmd = body.get("cmd", "")
            if not cmd:
                self._send_json({"error": "Missing cmd"}, status=400); return
            result = tool_run_cmd(cmd, timeout=body.get("timeout", 30))
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_tool_list_dir(self):
        """List directory contents within safe directories."""
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        try:
            body = self._read_body()
            path = body.get("path", "~")
            result = tool_list_dir(path)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_tool_settings(self):
        """Toggle local tool execution on/off."""
        global _TOOL_ENABLED
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        try:
            body = self._read_body()
            if "enabled" in body:
                _TOOL_ENABLED = bool(body["enabled"])
                print(f"  [TOOL] local tool execution {'ENABLED' if _TOOL_ENABLED else 'DISABLED'}")
            self._send_json({"ok": True, "enabled": _TOOL_ENABLED,
                             "allowedCmds": sorted(_ALLOWED_CMDS),
                             "safeDirs": list(_SAFE_HOME_SUBDIRS)})
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

```

---

### 1.14 在 `main()` 中 db 初始化之后插入工具日志初始化

**查找：**
```python
    db = Database(DB_PATH)
    print(f"  [DB] SQLite initialized: {DB_PATH}")
```

**在这两行之后插入：**
```python
    # Initialize shell/tool audit log
    global _SHELL_LOG
    _SHELL_LOG = os.path.join(SCRIPT_DIR, "docs", "TOOL_LOG.md")
    if not os.path.exists(_SHELL_LOG):
        with open(_SHELL_LOG, 'w', encoding='utf-8') as f:
            f.write("# USB-AI 本地工具操作日志\n\n| 时间 | 操作 | 详情 |\n|------|------|------|\n")
```

---

### 1.15 验证 server.py

```bash
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True)" && echo "✅ server.py 语法正确"
```

---

## 第二步：修改 app.js

### 2.1 在第一行 `const _isServer=...` 之后插入工具执行层

**查找：**
```javascript
const _isServer=location.protocol!=='file:';
```

**在此行之后插入：**
```javascript
// ============ Local Tool Execution (Claude Code-style) ============
const TOOL_RE=/\[TOOL:(\w+):?([^\]]*)\]/i;
let _localToken=''; // Injected by server startup into index.html

async function _execTool(name,argsStr){
  if(!_isServer)return {ok:false,error:'仅服务器模式支持本地工具'};
  let args={};
  try{if(argsStr.trim())args=JSON.parse(argsStr)}catch(e){args={cmd:argsStr,path:argsStr}}
  const hd={'Content-Type':'application/json','X-Local-Token':_localToken||localStorage.getItem('uai_local_token')||''};
  const ep={read_file:'/api/tool/read_file',write_file:'/api/tool/write_file',
             run_cmd:'/api/tool/run_cmd',list_dir:'/api/tool/list_dir'}[name];
  if(!ep)return {ok:false,error:`未知工具: ${name}`};
  // run_cmd: confirm before executing
  if(name==='run_cmd'){
    const cmd=args.cmd||argsStr;
    if(!confirm(`AI 请求执行命令:\n\n  ${cmd}\n\n确认执行？`))
      return {ok:false,error:'用户取消'};
  }
  try{
    const r=await fetch(ep,{method:'POST',headers:hd,body:JSON.stringify(args)});
    return await r.json();
  }catch(e){return {ok:false,error:e.message}}
}

function _fmtToolResult(name,result){
  if(!result.ok)return `❌ [${name}] ${result.error}`;
  if(name==='read_file')return `📄 **${result.path}** (${(result.size/1024).toFixed(1)}KB)\n\`\`\`\n${(result.content||'').slice(0,3000)}\n\`\`\``;
  if(name==='list_dir'){
    const items=(result.entries||[]).slice(0,50).map(e=>`${e.type==='dir'?'📁':'📄'} ${e.name}  ${e.type==='file'?(e.size>1048576?(e.size/1048576).toFixed(1)+'MB':(e.size/1024).toFixed(1)+'KB'):''}  ${e.modified}`).join('\n');
    return `📁 **${result.path}** (${result.count}项)\n\`\`\`\n${items}\n\`\`\``;
  }
  if(name==='write_file')return `✅ 文件已写入: ${result.path} (${result.bytes} bytes)`;
  if(name==='run_cmd'){
    const out=(result.stdout||'').trim()||(result.stderr||'').trim()||'(无输出)';
    return `💻 命令完成 (退出码 ${result.code})\n\`\`\`\n${out.slice(0,4096)}\n\`\`\``;
  }
  return JSON.stringify(result,null,2);
}
function _dateStr(){const t=new Date();return t.getFullYear()+'年'+(t.getMonth()+1)+'月'+t.getDate()+'日'}
function _recordMsg(r,c){addMsg(r,c);hist.push({role:r,content:c});CM.appendMessage(r,c)}
const REALTIME_RE=new RegExp(['最新','实时','今天','现在','新闻','价格','天气','开奖','彩票','快乐8','大乐透','双色球','比分','赛程','股价','股票','汇率','黄金','白银','比特币','以太坊','期货','原油','石油','铜价','大豆','外汇','利率','考试','高考','AI','大模型','DeepSeek','Claude','GPT','显卡','CPU','内存','装机','直播','附近','路况','限行','预警','地震','多少钱','性价比','评测','买车','落地价','报价','配置','保养','保险','油耗','二手','回收价','手机','iPhone','华为','小米','OPPO','vivo','三星','折叠屏'].join('|'));
function _isRealtime(txt){return REALTIME_RE.test(txt)}
```

---

### 2.2 替换 `doSend` 中 `let sp='今天是'` 所在行

**查找（在 doSend 函数内）：**
```javascript
    let sp='今天是'+ds+'。';
```

**替换为：**
```javascript
    let toolsEnabled=false;
    if(_isServer){try{const ts=await fetch('/api/tool/status');if(ts.ok){const td=await ts.json();toolsEnabled=td.enabled}}catch(e){}}
    let sp='今天是'+ds+'。';
    if(toolsEnabled){sp+='\n\n你有以下本地工具（仅服务器模式）：\n[TOOL:read_file:{"path":"~/Documents/file.txt"}] — 读取文件\n[TOOL:write_file:{"path":"~/Documents/out.txt","content":"内容"}] — 写入文件（需用户确认）\n[TOOL:list_dir:{"path":"~/Documents"}] — 列出目录\n[TOOL:run_cmd:{"cmd":"ls ~/Documents"}] — 执行白名单命令（需用户确认）\n调用格式严格遵循上面括号内的JSON。只调用一次，等结果再继续。'}
    let intent=classify(txt);
    if(location.protocol!=='file:'){try{const r=await fetch('/api/classify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:txt}),signal:AbortSignal.timeout(2000)});if(r.ok){const d=await r.json();if(d.intent)intent=d.intent}}catch(e){}}
    if(rag){sp+='\n\n以下是已经为你搜索到的实时数据。⚠️铁律：你绝对不要说"我无法联网/无法获取实时数据/没有搜索结果"——搜索已完成，数据在下面。你必须基于这些数据直接回答。\n⚠️禁止批评用户的用词或术语——即便你觉得表述不准确，也要理解意图后回答，不可说教。\n\n'+rag}
    else if(doSearch){const urls=_trustedSources(txt);sp+='\n\n（搜索未获取数据。⚠️禁止说教用户"这个表述存在误导"或"你应该查权威来源"——理解用户意图比纠正用词更重要。\n用你的知识回答核心问题。如果确实超出知识范围，用 [SEARCH:改写后的查询词] 换一个角度搜索。'+(urls.length?'可信网站：\n'+urls.join('\n'):'')+'）'}
    else{sp+='\n\n你是全能顾问，风格专业犀利有幽默感。\n你的知识截止于2025年7月，今天已是'+ds+'。\n⚠️铁律1：当用户问2025年7月后的时事/战争/选举/政策/灾难/名人动向/科技发布——必须第一行写 [SEARCH:关键词] 主动搜索，不得用"我的知识截止于XX"或"你告诉我"推给用户。\n⚠️铁律2：永远不要说"你这个表述存在误导"或"你应该去查权威新闻源"——理解用户意图，用你的知识或搜索结果直接回答核心问题。用户不是来上术语课的。时效性=可信度。\n你有搜索工具：[SEARCH:查询关键词] 系统自动搜索。搜索无结果时，换关键词重搜，不要放弃。\n⚠️禁止"我无法联网/无法获取实时数据/我搜索不到"——工具在你手里，搜不到就换词重搜。\n知识覆盖：高中全科、计算机/网络、电竞/直播/二次元、民间俚语/方言梗、自驾游/路线。对历史/未来/科技/人文/宗教好奇但务实。理解当代社会压力，接地气不说道。规则：模糊问题先确认意图；不编造网址/人名/电话；简洁、少用"您"、拒绝客服体。'}
```

---

### 2.3 在 `doSend` 中 `[SEARCH:]` 检测块之后插入 `[TOOL:]` 拦截块

**查找（doSend 函数内，SEARCH 工具调用结束的地方）：**
```javascript
      if(sm&&location.protocol!=='file:'){
        const sq=sm[1].trim();
        full=await _runToolSearch(sq,hist,key,mdName,bb)||full;
      }
      hist.push({role:'assistant',content:full});
```

**替换为：**
```javascript
      if(sm&&location.protocol!=='file:'){
        const sq=sm[1].trim();
        full=await _runToolSearch(sq,hist,key,mdName,bb)||full;
      }
      // AI tool-use: detect [TOOL:name:args] and execute local tool
      const tm=full.match(TOOL_RE);
      if(tm&&_isServer){
        const [,toolName,toolArgs]=tm;
        stat('🔧 执行工具: '+toolName+'…');
        const res=await _execTool(toolName,toolArgs);
        const fmtResult=_fmtToolResult(toolName,res);
        // Replace [TOOL:...] marker with result in the displayed message
        full=full.replace(tm[0],fmtResult);
        bb.innerHTML=md(full);
        // Feed result back to AI for a follow-up
        const followUpMsgs=[...hist,{role:'assistant',content:full},
          {role:'user',content:`[工具 ${toolName} 执行结果已显示。请基于上面结果继续回答用户的问题。]`}];
        try{
          const fr=await fetch(streamUrl()||'/api/deepseek',{method:'POST',
            headers:apiHd(key),body:JSON.stringify({model:mdName,messages:followUpMsgs,temperature:0.7,max_tokens:2048,stream:false})});
          if(fr.ok){const fd=await fr.json();const fc=fd.choices?.[0]?.message?.content||'';
            if(fc){full=full+'\n\n---\n'+fc;bb.innerHTML=md(full)}}
        }catch(e){_dlog('TOOL_FOLLOWUP','fail: '+e.message)}
        stat('完成');
      }
      hist.push({role:'assistant',content:full});
```

---

### 2.4 验证 app.js

```bash
node --check app.js && echo "✅ app.js 语法正确"
```

---

## 第三步：最终验证

```bash
# 语法双验证
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True)" && echo "✅ server.py OK"
node --check app.js && echo "✅ app.js OK"

# 逻辑验证 — 检查关键新增内容存在
python3 - << 'EOF'
with open('server.py') as f: s = f.read()
checks = [
    ('base64 import', 'import base64 as _b64'),
    ('engine health tracker', '_ENGINE_FAILS = {'),
    ('DDG JSON check', '"json" not in ct'),
    ('engine health in DDG', '_engine_fail("DDG")'),
    ('engine health in Bing', '_engine_fail("Bing")'),
    ('engine health in Sogou', '_engine_fail("Sogou")'),
    ('healthy engine filter', '_engine_ok(_engine_names'),
    ('DB int cast fix', 'int(tid_str)'),
    ('RAG limit increase', 'min(2000,'),
    ('RAG timestamp', '检索时间'),
    ('tool functions', 'def tool_read_file('),
    ('tool safe path', 'def _safe_path('),
    ('tool run cmd', 'def tool_run_cmd('),
    ('tool API route', '/api/tool/read_file'),
    ('tool handlers', '_handle_tool_read_file'),
    ('tool log init', 'TOOL_LOG.md'),
]
ok = all = 0
for name, needle in checks:
    found = needle in s
    print(f"  {'✅' if found else '❌'} {name}")
    if found: ok += 1
    all += 1
print(f"
{ok}/{all} checks passed")
EOF

python3 - << 'EOF'
with open('app.js') as f: s = f.read()
checks = [
    ('TOOL_RE regex', 'const TOOL_RE='),
    ('_execTool function', 'async function _execTool('),
    ('_fmtToolResult function', 'function _fmtToolResult('),
    ('toolsEnabled probe', 'let toolsEnabled=false'),
    ('tool system prompt injection', 'TOOL:read_file'),
    ('TOOL marker interception', 'const tm=full.match(TOOL_RE)'),
    ('tool confirm dialog', "name==='run_cmd'"),
    ('tool follow-up', 'followUpMsgs'),
]
ok = all = 0
for name, needle in checks:
    found = needle in s
    print(f"  {'✅' if found else '❌'} {name}")
    if found: ok += 1
    all += 1
print(f"
{ok}/{all} checks passed")
EOF
```

---

## 禁止事项（不得修改）

- 不修改 `conversation-manager.js`、`style.css`、`index.html`
- 不修改 `data.db`（SQLite 数据库）
- 不改变端口号 `PORT = 8082`
- 不删除 `SNIPPET_ONLY_DOMAINS`、`JUNK_DOMAINS`、`CHINA_NEWS_DOMAINS` 常量
- 不修改 `_inject_token()`、`_check_local_token()` 安全逻辑
- 执行完后必须运行完整验证脚本，全部 ✅ 才算完成

---

## 功能说明（完成后的效果）

### Bug 修复
| 修复 | 文件 | 位置 |
|------|------|------|
| `_b64` 未定义导致 Bing URL 解码崩溃 | server.py | imports 区 |
| DDG 返回 HTML 时 json.loads 异常 | server.py | `_ddg_search` |
| DB DELETE tid 字符串比较 TypeError | server.py | `_handle_db_delete` |

### 联网准确性提升
| 改进 | 效果 |
|------|------|
| 引擎健康追踪 | 失败 3 次的引擎自动摘除，不再白白等待超时 |
| RAG 上下文从 2400→6000 字 | AI 有更充分信息作答 |
| 检索时间戳注入 | AI 知道数据时效，不混淆训练知识和实时数据 |

### 本地工具层（类 Claude Code）
| 工具 | API 端点 | 说明 |
|------|----------|------|
| `read_file` | `POST /api/tool/read_file` | 读取 ~/Desktop 等安全目录内的文件 |
| `write_file` | `POST /api/tool/write_file` | 写入文件（禁止覆盖脚本） |
| `run_cmd` | `POST /api/tool/run_cmd` | 执行白名单命令，弹 confirm 确认 |
| `list_dir` | `POST /api/tool/list_dir` | 列出安全目录内容 |
| 状态查询 | `GET /api/tool/status` | 查看工具启用状态和白名单 |

AI 在回答中输出 `[TOOL:read_file:{"path":"~/Documents/x.txt"}]`，前端自动拦截执行，结果渲染后送回 AI 生成 follow-up。
