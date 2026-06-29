# CLAUDE.md — USB-AI v5 升级执行计划

> 由 Claude Sonnet 4.6 生成 · 2026-06-29
> 执行方：Claude Code（在 USB-AI 项目根目录运行）
> 目标：将 USB-AI 升级为真正零依赖、可本地运行、具备桌面自动化能力的便携 AI 系统

---

## 前置检查（必须先执行）

```bash
# 确认在 USB-AI 项目根目录
ls server.py app.js index.html conversation-manager.js

# 备份当前版本
cp server.py server.py.v4bak
cp app.js app.js.v4bak
cp index.html index.html.v4bak

# 语法验证当前文件
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True)" && echo "✅ server.py OK"
node --check app.js && echo "✅ app.js OK"

# 记录当前状态
echo "=== 升级前文件大小 ===" > docs/UPGRADE_LOG.md
ls -lh server.py app.js >> docs/UPGRADE_LOG.md
date >> docs/UPGRADE_LOG.md
```

---

## 第一步：目录结构升级

```bash
# 创建新目录结构
mkdir -p runtime/python-win
mkdir -p runtime/python-mac
mkdir -p runtime/llama
mkdir -p runtime/models
mkdir -p static/vendor
mkdir -p tasks
mkdir -p screenshots

# 创建 .gitkeep 占位
touch runtime/python-win/.gitkeep
touch runtime/python-mac/.gitkeep
touch runtime/llama/.gitkeep
touch runtime/models/.gitkeep
touch tasks/.gitkeep
touch screenshots/.gitkeep

# 更新 .gitignore（如有）
cat >> .gitignore << 'EOF'
runtime/python-win/
runtime/python-mac/
runtime/llama/
runtime/models/*.gguf
data.db
__pycache__/
*.pyc
*.bak
EOF
```

---

## 第二步：前端库本地化（断网可用）

在 `server.py` 中新增一个静态文件下载任务，在 `main()` 函数启动时自动检测并下载前端依赖到 `static/vendor/`。

### 2.1 在 server.py 顶部 imports 之后，PORT 定义之前，插入静态资源管理模块

**查找定位锚点：**
```python
PORT = 8082
```

**在此行之前插入：**
```python
# ============ Static Vendor Assets (offline-first) ============
_VENDOR_ASSETS = {
    "marked.min.js":    "https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js",
    "highlight.min.js": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js",
    "katex.min.js":     "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js",
    "katex.min.css":    "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css",
    "github-dark.min.css": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css",
    "auto-render.min.js":  "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js",
}

def _ensure_vendor_assets(vendor_dir):
    """Download missing vendor assets for offline use. Runs once at startup."""
    os.makedirs(vendor_dir, exist_ok=True)
    missing = [k for k, v in _VENDOR_ASSETS.items() if not os.path.exists(os.path.join(vendor_dir, k))]
    if not missing:
        print(f"  [VENDOR] All {len(_VENDOR_ASSETS)} assets cached locally")
        return True
    print(f"  [VENDOR] Downloading {len(missing)} missing assets...")
    ok = 0
    for name in missing:
        url = _VENDOR_ASSETS[name]
        dest = os.path.join(vendor_dir, name)
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
    print(f"  [VENDOR] {ok}/{len(missing)} downloaded. Offline fallback available for cached assets.")
    return ok > 0

```

### 2.2 在 main() 函数中，db 初始化之后，调用 vendor 下载

**查找：**
```python
    db = Database(DB_PATH)
    print(f"  [DB] SQLite initialized: {DB_PATH}")
```

**在这两行之后插入：**
```python
    # Pre-cache vendor assets for offline use
    _VENDOR_DIR = os.path.join(SCRIPT_DIR, "static", "vendor")
    threading.Thread(target=_ensure_vendor_assets, args=(_VENDOR_DIR,), daemon=True).start()
```

### 2.3 在 do_GET 中添加 /static/ 路由（本地文件服务）

**查找：**
```python
        if self.path == "/api/tool/status":
```

**在此行之前插入：**
```python
        if self.path.startswith("/static/"):
            # Serve locally cached vendor assets
            rel = self.path[len("/static/"):]
            local = os.path.join(SCRIPT_DIR, "static", rel)
            if os.path.isfile(local):
                ext = os.path.splitext(local)[1].lower()
                ct = {".js": "application/javascript", ".css": "text/css",
                      ".woff2": "font/woff2", ".woff": "font/woff"}.get(ext, "application/octet-stream")
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
```

### 2.4 在 index.html 中，将 CDN 链接改为本地优先 + CDN 回落

**查找 index.html 中：**
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
```

**替换为（每个 CDN 链接按此模式修改）：**
```html
<script>
(function(){
  var local='/static/vendor/marked.min.js';
  var cdn='https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js';
  var s=document.createElement('script');
  s.src=local;
  s.onerror=function(){var f=document.createElement('script');f.src=cdn;document.head.appendChild(f);};
  document.head.appendChild(s);
})();
</script>
```

> **注意：** 对所有 CDN 脚本和样式链接重复上述 local-first 模式。CSS 链接用 `<link>` + `onerror` 回落到 CDN。

---

## 第三步：便携本地模型（llama.cpp 集成）

### 3.1 在 server.py 全局常量区插入本地模型配置

**查找：**
```python
_SHELL_LOG = None   # Set at startup
```

**在此行之后插入：**
```python
# ============ Local Model (llama.cpp portable) ============
_LLAMA_EXE_PATHS = [
    os.path.join(SCRIPT_DIR, "runtime", "llama", "llama-server.exe"),  # Windows
    os.path.join(SCRIPT_DIR, "runtime", "llama", "llama-server"),       # Linux/Mac
    "llama-server",   # System PATH fallback
]
_DEFAULT_MODEL_PATHS = [
    os.path.join(SCRIPT_DIR, "runtime", "models", "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    os.path.join(SCRIPT_DIR, "runtime", "models", "tinyllama-1.1b-chat-v1.0.q4_k_m.gguf"),
]
_LLAMA_PORT = 8083
_llama_proc = None   # subprocess.Popen instance when running

def _find_llama_exe():
    for p in _LLAMA_EXE_PATHS:
        if os.path.isfile(p):
            return p
    return None

def _find_local_model():
    for p in _DEFAULT_MODEL_PATHS:
        if os.path.isfile(p):
            return p
    return None

def _start_local_model():
    """Start llama-server as a subprocess. Returns True if started."""
    global _llama_proc
    if _llama_proc and _llama_proc.poll() is None:
        return True  # Already running
    exe = _find_llama_exe()
    model = _find_local_model()
    if not exe or not model:
        return False
    cmd = [exe, "--model", model, "--port", str(_LLAMA_PORT),
           "--ctx-size", "4096", "--threads", str(max(2, os.cpu_count() - 1)),
           "--n-gpu-layers", "99",  # GPU auto-detect; falls back to CPU if none
           "--host", "127.0.0.1", "--log-disable"]
    try:
        _llama_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)  # Wait for server to bind
        return _llama_proc.poll() is None
    except Exception as e:
        print(f"  [LLAMA] Start failed: {e}", file=sys.stderr)
        return False

def _stop_local_model():
    global _llama_proc
    if _llama_proc:
        try: _llama_proc.terminate()
        except: pass
        _llama_proc = None

```

### 3.2 在 do_GET 中添加本地模型状态端点

**查找：**
```python
        if self.path == "/api/tool/status":
```

**在此行之前插入：**
```python
        if self.path == "/api/local-model/status":
            exe = _find_llama_exe()
            model = _find_local_model()
            running = _llama_proc is not None and _llama_proc.poll() is None
            self._send_json({
                "available": exe is not None and model is not None,
                "running": running,
                "exe": exe, "model": os.path.basename(model) if model else None,
                "port": _LLAMA_PORT,
                "endpoint": f"http://127.0.0.1:{_LLAMA_PORT}/v1"
            })
            return
```

### 3.3 在 do_POST 中添加本地模型启停端点

**查找：**
```python
        elif self.path == "/api/tool/settings":
            self._handle_tool_settings()
```

**在此行之后插入：**
```python
        elif self.path == "/api/local-model/start":
            started = _start_local_model()
            self._send_json({"ok": started, "port": _LLAMA_PORT if started else None})
        elif self.path == "/api/local-model/stop":
            _stop_local_model()
            self._send_json({"ok": True})
```

### 3.4 在 main() 退出时清理本地模型进程

**查找（main 函数末尾 KeyboardInterrupt 处理）：**
```python
    except KeyboardInterrupt:
        print("\n[停止] USB-AI 服务器已停止")
```

**替换为：**
```python
    except KeyboardInterrupt:
        print("\n[停止] USB-AI 服务器已停止")
        _stop_local_model()
```

### 3.5 在 app.js 中添加本地模型路由逻辑

**查找（app.js 中 streamUrl 或 API 路由函数）：**
```javascript
function streamUrl(){return _isServer?'/api/deepseek/stream':null}
```

**替换为：**
```javascript
let _localModelInfo=null;
async function _checkLocalModel(){
  if(!_isServer)return null;
  try{const r=await fetch('/api/local-model/status');if(r.ok){_localModelInfo=await r.json();}}catch(e){}
  return _localModelInfo;
}
function streamUrl(){return _isServer?'/api/deepseek/stream':null}
function _getApiEndpoint(modelName){
  // Route to local llama-server if model is local and server is running
  if(_localModelInfo?.running && (modelName||'').includes('local')){
    return {
      stream: null,  // llama-server supports SSE but via different path
      standard: `http://127.0.0.1:${_localModelInfo.port}/v1/chat/completions`
    };
  }
  return {stream:'/api/deepseek/stream', standard:'/api/deepseek'};
}
```

---

## 第四步：桌面自动化代理（类 OpenClaw）

### 4.1 在 server.py 全局区添加自动化工具函数

**找到：**
```python
def _log_tool_op(op, detail):
```

**在此函数之后插入：**
```python
# ============ Desktop Automation (Claude Code-style computer use) ============
_AUTO_ENABLED = False   # Must be explicitly enabled in settings

def _check_auto_deps():
    """Check if automation dependencies are available."""
    deps = {}
    try:
        import pyautogui
        deps['pyautogui'] = True
    except ImportError:
        deps['pyautogui'] = False
    try:
        import PIL
        deps['pillow'] = True
    except ImportError:
        deps['pillow'] = False
    return deps

def tool_screenshot(region=None):
    """Take a screenshot and return as base64 PNG."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用，请在设置中开启"}
    try:
        import pyautogui
        from PIL import Image
        import io, base64
        img = pyautogui.screenshot(region=region)
        # Downscale to 1280px max width for token efficiency
        w, h = img.size
        if w > 1280:
            scale = 1280 / w
            img = img.resize((1280, int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        _log_tool_op("screenshot", f"size={img.size}")
        return {"ok": True, "image_b64": b64, "size": img.size, "format": "png"}
    except ImportError:
        return {"ok": False, "error": "需要安装 pyautogui 和 pillow: pip install pyautogui pillow"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_mouse_click(x, y, button="left", clicks=1):
    """Move mouse and click at screen coordinates."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    # Safety: reject coordinates outside screen bounds
    try:
        import pyautogui
        sw, sh = pyautogui.size()
        if not (0 <= x <= sw and 0 <= y <= sh):
            return {"ok": False, "error": f"坐标超出屏幕范围 ({sw}x{sh})"}
        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=0.15)
        _log_tool_op("mouse_click", f"({x},{y}) {button}x{clicks}")
        return {"ok": True, "x": x, "y": y, "button": button, "clicks": clicks}
    except ImportError:
        return {"ok": False, "error": "需要安装 pyautogui: pip install pyautogui"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_type_text(text, interval=0.05):
    """Type text at current cursor position."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    if len(text) > 5000:
        return {"ok": False, "error": "文本过长（最大 5000 字符）"}
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.hotkey('ctrl', 'a')
        # For non-ASCII, use clipboard paste
        if not text.isascii():
            import subprocess as sp
            # Cross-platform clipboard
            if sys.platform == 'darwin':
                sp.run(['pbcopy'], input=text.encode(), check=True)
                pyautogui.hotkey('command', 'v')
            elif sys.platform == 'win32':
                import subprocess
                subprocess.run(['clip'], input=text.encode('utf-16'), check=True)
                pyautogui.hotkey('ctrl', 'v')
            else:
                sp.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
                pyautogui.hotkey('ctrl', 'v')
        _log_tool_op("type_text", f"len={len(text)}")
        return {"ok": True, "chars": len(text)}
    except ImportError:
        return {"ok": False, "error": "需要安装 pyautogui: pip install pyautogui"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def tool_hotkey(*keys):
    """Press a keyboard shortcut (e.g. ctrl+c, alt+tab)."""
    if not _AUTO_ENABLED:
        return {"ok": False, "error": "桌面自动化未启用"}
    # Whitelist dangerous key combos
    BLOCKED = {frozenset(k.lower() for k in combo) for combo in [
        ['ctrl','alt','delete'], ['ctrl','alt','del'],
        ['win','r'], ['meta','r'],  # Run dialog
    ]}
    key_set = frozenset(k.lower() for k in keys)
    if key_set in BLOCKED:
        return {"ok": False, "error": f"快捷键 {'+'.join(keys)} 被安全策略阻止"}
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        _log_tool_op("hotkey", '+'.join(keys))
        return {"ok": True, "keys": list(keys)}
    except ImportError:
        return {"ok": False, "error": "需要安装 pyautogui: pip install pyautogui"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

```

### 4.2 在 do_POST 中添加自动化路由

**查找：**
```python
        elif self.path == "/api/local-model/stop":
            _stop_local_model()
            self._send_json({"ok": True})
```

**在此之后插入：**
```python
        elif self.path == "/api/auto/screenshot":
            self._handle_auto_screenshot()
        elif self.path == "/api/auto/click":
            self._handle_auto_click()
        elif self.path == "/api/auto/type":
            self._handle_auto_type()
        elif self.path == "/api/auto/hotkey":
            self._handle_auto_hotkey()
        elif self.path == "/api/auto/settings":
            self._handle_auto_settings()
```

### 4.3 在 AIProxyHandler 中添加自动化 handler 方法

**找到 `_handle_tool_settings` 方法结尾，在其后插入：**
```python
    # ============ Desktop Automation Handlers ============

    def _handle_auto_screenshot(self):
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        body = self._read_body()
        result = tool_screenshot(region=body.get("region"))
        self._send_json(result)

    def _handle_auto_click(self):
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        body = self._read_body()
        x, y = body.get("x", 0), body.get("y", 0)
        result = tool_mouse_click(int(x), int(y),
                                   button=body.get("button", "left"),
                                   clicks=body.get("clicks", 1))
        self._send_json(result)

    def _handle_auto_type(self):
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        body = self._read_body()
        result = tool_type_text(body.get("text", ""),
                                 interval=body.get("interval", 0.05))
        self._send_json(result)

    def _handle_auto_hotkey(self):
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        body = self._read_body()
        keys = body.get("keys", [])
        if isinstance(keys, str): keys = keys.split("+")
        result = tool_hotkey(*keys)
        self._send_json(result)

    def _handle_auto_settings(self):
        global _AUTO_ENABLED
        if not self._check_local_token():
            self._send_json({"error": "Forbidden"}, status=403); return
        body = self._read_body()
        if "enabled" in body:
            _AUTO_ENABLED = bool(body["enabled"])
            print(f"  [AUTO] Desktop automation {'ENABLED' if _AUTO_ENABLED else 'DISABLED'}")
        deps = _check_auto_deps()
        self._send_json({
            "ok": True,
            "enabled": _AUTO_ENABLED,
            "deps": deps,
            "missingDeps": [k for k, v in deps.items() if not v]
        })

```

### 4.4 在 app.js 中扩展 [TOOL:] 支持自动化工具

**查找 `_execTool` 函数中的 `ep` 映射：**
```javascript
  const ep={read_file:'/api/tool/read_file',write_file:'/api/tool/write_file',
             run_cmd:'/api/tool/run_cmd',list_dir:'/api/tool/list_dir'}[name];
```

**替换为：**
```javascript
  const ep={
    read_file:'/api/tool/read_file', write_file:'/api/tool/write_file',
    run_cmd:'/api/tool/run_cmd',     list_dir:'/api/tool/list_dir',
    screenshot:'/api/auto/screenshot', click:'/api/auto/click',
    type_text:'/api/auto/type',        hotkey:'/api/auto/hotkey'
  }[name];
```

**查找 `_fmtToolResult` 函数，在末尾 `return JSON.stringify...` 之前插入：**
```javascript
  if(name==='screenshot'){
    if(!result.ok) return `❌ [screenshot] ${result.error}`;
    return `📸 截图 ${result.size[0]}×${result.size[1]}px\n![screenshot](data:image/png;base64,${result.image_b64})`;
  }
  if(name==='click') return result.ok?`🖱️ 点击 (${result.x}, ${result.y})`:`❌ ${result.error}`;
  if(name==='type_text') return result.ok?`⌨️ 已输入 ${result.chars} 字符`:`❌ ${result.error}`;
  if(name==='hotkey') return result.ok?`⌨️ 快捷键: ${result.keys.join('+')}`:`❌ ${result.error}`;
```

**在 System Prompt 中，工具描述部分（含 `TOOL:read_file` 的那行），补充自动化工具描述：**

找到：
```javascript
    if(toolsEnabled){sp+='...[TOOL:list_dir:{"path":"~/Documents"}] — 列出目录\n[TOOL:run_cmd:{"cmd":"ls ~/Documents"}] — 执行白名单命令（需用户确认）\n...';}
```

在该字符串末尾、关闭引号之前追加：
```
[TOOL:screenshot:{}] — 截取屏幕截图\n[TOOL:click:{"x":100,"y":200}] — 鼠标点击（需用户确认）\n[TOOL:type_text:{"text":"你好"}] — 输入文本（需用户确认）\n[TOOL:hotkey:{"keys":["ctrl","c"]}] — 键盘快捷键（需用户确认）\n
```

**在 `_execTool` 中，`run_cmd` 的 confirm 判断下方，追加自动化工具的 confirm：**

找到：
```javascript
  if(name==='run_cmd'){
    const cmd=args.cmd||argsStr;
    if(!confirm(`AI 请求执行命令:\n\n  ${cmd}\n\n确认执行？`))
      return {ok:false,error:'用户取消'};
  }
```

在此 if 块之后插入：
```javascript
  if(['click','type_text','hotkey'].includes(name)){
    const desc={click:`点击坐标 (${args.x},${args.y})`,type_text:`输入文本: "${(args.text||'').slice(0,50)}"`,hotkey:`快捷键: ${(args.keys||[]).join('+')}`}[name];
    if(!confirm(`AI 请求控制您的桌面:\n\n  ${desc}\n\n确认执行？`))
      return {ok:false,error:'用户取消'};
  }
```

---

## 第五步：局域网二维码 + 移动端入口

### 5.1 在 server.py main() 中输出局域网地址和二维码

**查找 main() 中的启动成功信息输出：**
```python
    print(f"  [SERVER] 访问地址: http://localhost:{PORT}")
```

**替换为：**
```python
    # Detect LAN IP
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as _s:
            _s.connect(("8.8.8.8", 80))
            LAN_IP = _s.getsockname()[0]
    except Exception:
        LAN_IP = "127.0.0.1"

    print(f"  [SERVER] 本机访问: http://localhost:{PORT}")
    print(f"  [SERVER] 局域网访问: http://{LAN_IP}:{PORT}")
    print(f"  [SERVER] 手机扫码访问 ↓")
    # ASCII QR code (no deps)
    _qr_url = f"http://{LAN_IP}:{PORT}"
    try:
        import urllib.parse
        qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(_qr_url)}"
        print(f"  [SERVER] 二维码: {qr_api}")
    except Exception:
        pass
    print(f"  [SERVER] 或手动输入: {_qr_url}")
```

### 5.2 在 do_GET 中添加 /api/network-info 端点

**在 `/api/tool/status` 路由之前插入：**
```python
        if self.path == "/api/network-info":
            import socket
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as _s:
                    _s.connect(("8.8.8.8", 80))
                    lan_ip = _s.getsockname()[0]
            except Exception:
                lan_ip = "127.0.0.1"
            self._send_json({
                "localhost": f"http://localhost:{PORT}",
                "lan": f"http://{lan_ip}:{PORT}",
                "lanIp": lan_ip,
                "port": PORT
            })
            return
```

---

## 第六步：依赖安装脚本（首次使用自动化功能时）

创建新文件 `setup_auto.bat`（Windows）：

```batch
@echo off
title USB-AI — 安装自动化依赖
cd /d "%~dp0"

echo ============================================
echo   USB-AI — 桌面自动化依赖安装
echo ============================================
echo.
echo 此脚本安装以下 Python 包:
echo   - pyautogui  (鼠标/键盘控制)
echo   - pillow     (截图处理)
echo.
echo 如果您只需要文件操作和 AI 对话功能，
echo 可以跳过此安装。
echo.
set /p CONFIRM="是否继续安装? [Y/n]: "
if /i "%CONFIRM%"=="n" goto :skip

REM Use portable Python if available, fallback to system Python
set PY=%~dp0runtime\python-win\python.exe
if not exist "%PY%" set PY=python

echo.
echo [安装] pyautogui + pillow...
"%PY%" -m pip install pyautogui pillow --quiet
if not errorlevel 1 (
    echo [OK] 安装成功！
    echo      在 USB-AI 设置中开启"桌面自动化"即可使用
) else (
    echo [错误] 安装失败，请检查 Python 是否可用
    echo        或手动执行: pip install pyautogui pillow
)
goto :done

:skip
echo 已跳过安装。
:done
echo.
pause
```

创建新文件 `setup_auto.sh`（Mac/Linux）：

```bash
#!/usr/bin/env bash
echo "============================================"
echo "  USB-AI — 安装桌面自动化依赖"
echo "============================================"
echo ""
echo "将安装: pyautogui pillow"
echo ""
read -p "是否继续? [Y/n] " answer
if [[ "$answer" == "n" || "$answer" == "N" ]]; then
    echo "已跳过"
    exit 0
fi

# On Linux, xdotool may be needed for type_text
if [[ "$(uname)" == "Linux" ]]; then
    echo "[提示] Linux 下还需要 xclip: sudo apt install xclip"
fi

python3 -m pip install pyautogui pillow --quiet && \
    echo "[OK] 安装成功！在 USB-AI 设置中开启桌面自动化即可使用" || \
    echo "[错误] 安装失败，请手动执行: pip install pyautogui pillow"
```

---

## 最终验证

```bash
# 语法验证
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True)" && echo "✅ server.py OK"
node --check app.js && echo "✅ app.js OK"

# 逻辑验证 — 检查所有新增内容
python3 - << 'EOF'
with open('server.py') as f: s = f.read()
checks = [
    ("vendor assets dict",      "_VENDOR_ASSETS = {"),
    ("ensure_vendor_assets fn", "def _ensure_vendor_assets("),
    ("static file server",      "path.startswith(\"/static/\")"),
    ("llama exe paths",         "_LLAMA_EXE_PATHS = ["),
    ("start_local_model fn",    "def _start_local_model():"),
    ("stop_local_model fn",     "def _stop_local_model():"),
    ("local model GET route",   "/api/local-model/status"),
    ("local model POST routes", "/api/local-model/start"),
    ("screenshot fn",           "def tool_screenshot("),
    ("mouse click fn",          "def tool_mouse_click("),
    ("type text fn",            "def tool_type_text("),
    ("hotkey fn",               "def tool_hotkey("),
    ("auto GET route",          "/api/auto/screenshot"),
    ("auto settings handler",   "def _handle_auto_settings("),
    ("network info route",      "/api/network-info"),
    ("lan ip detection",        "8.8.8.8"),
    ("llama cleanup on exit",   "_stop_local_model()"),
    ("vendor thread start",     "_ensure_vendor_assets, args="),
]
ok = 0
for name, needle in checks:
    found = needle in s
    print(f"  {'✅' if found else '❌'} {name}")
    if found: ok += 1
print(f"\n{ok}/{len(checks)} server.py checks passed")
EOF

python3 - << 'EOF'
with open('app.js') as f: s = f.read()
checks = [
    ("local model check fn",    "_checkLocalModel"),
    ("local model endpoint",    "_getApiEndpoint"),
    ("auto screenshot ep",      "screenshot:'/api/auto/screenshot'"),
    ("auto click ep",           "click:'/api/auto/click'"),
    ("screenshot format result","image/png;base64"),
    ("auto tool confirm dialog", "控制您的桌面"),
    ("auto tool sysprompt",     "TOOL:screenshot"),
]
ok = 0
for name, needle in checks:
    found = needle in s
    print(f"  {'✅' if found else '❌'} {name}")
    if found: ok += 1
print(f"\n{ok}/{len(checks)} app.js checks passed")
EOF

# 目录结构验证
echo ""
echo "=== 目录结构 ==="
ls -la runtime/ static/ tasks/ screenshots/ 2>/dev/null || echo "部分目录待创建"

# 记录升级完成
echo "" >> docs/UPGRADE_LOG.md
echo "=== 升级完成 ===" >> docs/UPGRADE_LOG.md
date >> docs/UPGRADE_LOG.md
ls -lh server.py app.js >> docs/UPGRADE_LOG.md
echo "✅ USB-AI v5 升级完成"
```

---

## 禁止事项

- 不修改 `data.db`（用户数据）
- 不修改 `docs/ERROR_LOG.md`、`docs/Memory.md`（项目记忆）
- 不删除现有 API 端点（向下兼容）
- 不改变 `PORT = 8082`
- `_AUTO_ENABLED` 默认必须为 `False`（桌面自动化默认关闭）
- 桌面自动化工具每次操作必须有 `confirm()` 确认，绝对不能静默执行
- 不向公网暴露服务器（`--host 0.0.0.0` 仅局域网模式，且要提示用户）

---

## 升级后功能说明

| 功能 | 触发方式 | 依赖 |
|------|----------|------|
| 前端库离线 | 自动（后台下载） | 无 |
| 本地 AI 模型 | 设置中切换模型 / 断网自动降级 | llama.cpp exe + GGUF 文件 |
| 文件读写 | AI 输出 `[TOOL:read_file:...]` | 无（已有） |
| 截图 | AI 输出 `[TOOL:screenshot:{}]` | pyautogui + pillow |
| 鼠标点击 | AI 输出 `[TOOL:click:{"x":...}]` | pyautogui |
| 键盘输入 | AI 输出 `[TOOL:type_text:...]` | pyautogui |
| 快捷键 | AI 输出 `[TOOL:hotkey:...]` | pyautogui |
| 局域网访问 | 启动时自动输出 IP | 无 |
| 手机扫码 | 启动时打印二维码链接 | 无 |

### 典型使用流程（桌面自动化）

1. 用户说："帮我截图看一下当前屏幕"
2. AI 回答包含 `[TOOL:screenshot:{}]`
3. 前端拦截，弹出截图，返回 base64 图片给 AI
4. AI 分析截图，输出下一步操作：`[TOOL:click:{"x":450,"y":320}]`
5. 前端弹出确认框 → 用户同意 → 执行点击
6. AI 继续截图确认结果 → 任务完成

这就是类 OpenClaw / Claude Computer Use 的"视觉-行动"循环，完全在本地运行，无需云端。
