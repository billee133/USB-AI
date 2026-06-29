# 本地 Agent 工具设计 v2.0

> **实现状态**: P1 ✅ 文件工具 | P2 ✅ 白名单 Shell | P3 ✅ TOOL 协议

## 概述

允许 AI 在安全沙箱内操作本地电脑。三层架构，逐层实现。

---

## 第一层：文件工具（优先级 P1）

### API 路由

所有工具通过 POST `/api/tool` 接入。

### 工具列表

| 工具名 | 方法 | 参数 | 说明 |
|--------|------|------|------|
| `read_file` | file_read | path | 读文件，按行返回 |
| `write_file` | file_write | path, content | 写文件（覆盖） |
| `append_file` | file_append | path, content | 追加写入 |
| `list_directory` | file_ls | path | 列出目录内容 |
| `create_directory` | file_mkdir | path | 创建目录 |
| `move_file` | file_mv | src, dst | 移动/重命名 |
| `delete_file` | file_rm | path | 删除文件 |
| `file_info` | file_stat | path | 文件信息（大小/修改时间/类型） |

### 沙箱路径规则

```
ALLOWED_PATHS = {
    os.path.join(SCRIPT_DIR, "workspace"),
    os.path.join(SCRIPT_DIR, "data"),
    os.path.join(SCRIPT_DIR, "uploads"),
}

BLOCKED_PATTERNS = [
    r'^C:\\Windows',
    r'^C:\\Program Files',
    r'^C:\\Program Files \(x86\)',
    r'^/etc/',
    r'^/usr/',
    r'~/\.ssh',
    r'~/\.aws',
    r'~/\.config',
    r'~/\.gitconfig',
    r'C:\\Users\\[^\\]+\\\.ssh',
    r'C:\\Users\\[^\\]+\\AppData',
]
```

策略：
1. 路径必须经过 `os.path.realpath()` 解析
2. 必须在某个 ALLOWED_PATHS 之下（`resolved.startswith(allowed_path + os.sep)`）
3. 不得匹配任何 BLOCKED_PATTERNS
4. 跨平台：Windows 用 `\\?` 前缀规避 MAX_PATH 限制

### 安全函数

```python
def _sanitize_path(path):
    """安全检查路径。返回规范路径或抛出异常。"""
    resolved = os.path.realpath(path)
    for allowed in ALLOWED_PATHS:
        if resolved.startswith(allowed + os.sep) or resolved == allowed:
            return resolved
    raise PermissionError(f"路径不在允许范围内: {path}")

def _check_not_blocked(path):
    """检查是否在黑名单路径中。"""
    for pat in BLOCKED_PATTERNS:
        if re.match(pat, path, re.IGNORECASE):
            raise PermissionError(f"禁止访问: {path}")
```

### 安全边界（已实现）

| 规则 | 说明 |
|------|------|
| 文件大小上限 | read_file 限制 1MB |
| 输出截断 | 文件内容截断 10KB |
| 路径遍历 | realpath + allowed prefix 双重校验 |
| 系统路径封锁 | Windows/C:\Windows, /etc/, ~/.ssh 等 40+ 模式 |

---

## 第二层：白名单 Shell（优先级 P2）

### 白名单命令

每个命令包含：可执行文件 + 允许的参数模式。

```python
SHELL_WHITELIST = {
    "python": {"args": r'^[a-zA-Z0-9_\-./\\: ]+\.py$', "desc": "运行 Python 脚本"},
    "pip":    {"args": r'^(install|list|show|freeze)\s+[a-zA-Z0-9_\-\.>=<]+$', "desc": "Python 包管理"},
    "git":    {"args": r'^(status|log|diff|branch|add|commit|push|pull)\s', "desc": "Git 操作"},
    "npm":    {"args": r'^(install|run|test|build|start)\s', "desc": "NPM 包管理"},
    "node":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+\.js$', "desc": "运行 JS"},
    "ls":     {"args": r'^[a-zA-Z0-9_\-./\\: ]*$', "desc": "列出目录"},
    "dir":    {"args": r'^[a-zA-Z0-9_\-./\\: ]*$', "desc": "列出目录(Windows)"},
    "cat":    {"args": r'^[a-zA-Z0-9_\-./\\: ]+$', "desc": "查看文件"},
    "type":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+$', "desc": "查看文件(Windows)"},
    "find":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+\s', "desc": "查找文件"},
    "grep":   {"args": r'^[a-zA-Z0-9_\-./\\:"]+\s', "desc": "搜索文件内容"},
    "wc":     {"args": r'^[\-lwc ]+[a-zA-Z0-9_\-./\\: ]+$', "desc": "计数"},
    "echo":   {"args": r'^[a-zA-Z0-9_\-./\\: ]+$', "desc": "输出文本"},
    "which":  {"args": r'^[a-zA-Z0-9_\-./\\:]+$', "desc": "查找可执行文件"},
    "pwd":    {"args": r'^$', "desc": "当前路径"},
    "head":   {"args": r'^\-n\s+\d+\s+[a-zA-Z0-9_\-./\\: ]+$', "desc": "查看文件开头"},
    "tail":   {"args": r'^\-n\s+\d+\s+[a-zA-Z0-9_\-./\\: ]+$', "desc": "查看文件末尾"},
}
```

### 禁止命令（硬阻断）

```python
BLOCKED_COMMANDS = {
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
```

### 执行函数（已实现）

```python
def _run_shell_cmd(command, timeout=30, workdir=None):
    """在白名单内执行 shell 命令。禁止 shell=True。"""
    t0 = time.time()
    parts = command.strip().split()
    if not parts:
        return {"ok": False, "error": "Empty command"}

    cmd_name = parts[0].lower()

    # 0. 元字符阻断：; | ` $() 等
    _metachar = re.compile(r'[;&|`$(){}\[\]<>]')
    for p in parts:
        if _metachar.search(p):
            return {"ok": False, "error": "Shell metacharacters not allowed"}

    # 1. 黑名单检查
    if cmd_name in BLOCKED_COMMANDS:
        return {"ok": False, "error": f"Command blocked: {cmd_name}"}
    # 2. 白名单检查
    if cmd_name not in SHELL_WHITELIST:
        return {"ok": False, "error": f"Not in whitelist: {cmd_name}"}
    entry = SHELL_WHITELIST[cmd_name]
    args_str = ' '.join(parts[1:])
    if not re.match(entry["args"], args_str):
        return {"ok": False, "error": f"Args pattern mismatch: {args_str[:100]}"}

    # 2a. find -exec 硬阻断
    if cmd_name == "find":
        for p in parts[1:]:
            if p in ("-exec", "-ok", "-execdir"):
                return {"ok": False, "error": "find -exec/-ok not allowed"}

    # 3. 工作目录
    cwd = workdir or os.path.join(SCRIPT_DIR, "workspace")
    os.makedirs(cwd, exist_ok=True)

    # 4. 执行（无 shell=True）
    import subprocess
    try:
        result = subprocess.run(
            parts, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
            env={**os.environ, "PATH": os.environ.get("PATH", "")},
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout ({timeout}s)"}
    except FileNotFoundError:
        return {"ok": False, "error": f"Command not found: {parts[0]}"}

    # 5. 日志
    _log_tool_action(f"shell {command[:100]}")
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout[:5000],
        "stderr": result.stderr[:2000],
        "returnCode": result.returncode,
    }
```

### 日志

所有命令写入 `data/tool_log.jsonl`：

```json
{"time":"2026-06-28 14:00:00","user":"local","tool":"shell","action":"git status","ok":true,"duration":1.2}
```

---

## 第三层：结构化工具调用协议（优先级 P3）

### Protocol

AI 输出：

```
[TOOL:read_file path="workspace/main.py"]
```

系统拦截流程：

```
1. AI 输出 → 正则拦截 [TOOL:...] 指令
2. 验证参数 JSON 合法性
3. 执行工具（文件/RPC/Shell）
4. 结果格式化为 XML 标签注入：
   <tool_result tool="read_file" ok="true">
   文件内容...
   </tool_result>
5. 继续 AI 推理（保持 SSE 流不断）
```

### 设计原则

```python
TOOL_PATTERN = re.compile(r'\[TOOL:(\w+)\s+([^\]]*)\]')
```

### System Prompt 注入

在发送给 AI 的 system prompt 末尾追加：

```
## 本地工具调用

你可以调用以下工具操作本地电脑：

<tool name="read_file" args="path">读取文件内容。path 必须在 workspace/ data/ uploads/ 目录内。</tool>
<tool name="write_file" args="path, content">写入文件。覆盖已存在文件。</tool>
<tool name="run_command" args="command">执行白名单 Shell 命令（git/python/pip/npm/ls/cat/echo 等）。</tool>
<tool name="list_directory" args="path">列出目录内容。</tool>

调用格式：
[TOOL:read_file path="main.py"]
[TOOL:run_command command="git status"]

工具结果会自动注入对话，无需重复请求。
```

### 与 SSE 流的整合

当前 SSE 流是单向的（AI→客户端）。工具调用需要断流 → 执行 → 续流。

方案 A（已实现）：服务端拦截
```
AI Proxy → 检测 TOOL 模式 → 中断 SSE → 执行工具 → 本地调用 DeepSeek 续推理 → 恢复 SSE
```
优点：前端不需要改动（仅加一个清理函数）
实现细节：
- 上游 `[DONE]` 被服务端吞咽，仅最终轮次发送全局 `[DONE]`
- 每轮 AI 输出的 `[TOOL:]` 文本被客户端 `_cleanToolMarkers()` 移除
- `<tool_result>` XML 标记注入到下一轮请求的 messages 中，不由前端显示
- 最多 5 轮自动续推理，超限后强制返回

### 安全配置

```python
TOOL_CONFIG = {
    "enabled": True,
    "require_auth": True,       # 需要 X-Local-Token
    "max_file_size": 1_000_000, # 1MB
    "max_output": 10_000,       # 工具输出最多 10k 字符
    "shell_timeout": 30,        # shell 超时
    "allowed_paths": ["workspace", "data", "uploads"],
}
```

---

## 实现路线图

| 阶段 | 内容 | 依赖 | 预估 | 状态 |
|------|------|------|------|------|
| P1 | 文件工具 + 路径沙箱 | 无 | 2h | ✅ 已实现 |
| P1 | `/api/tool` 路由 | 文件工具 | 1h | ✅ 已实现 |
| P2 | 白名单 Shell + 日志 | P1 | 2h | ✅ 已实现 |
| P3 | TOOL 协议 + System Prompt 注入 | P1+P2 | 2h | ✅ 已实现 |
| 测试 | 全部 8 个文件工具 + 15+ Shell 命令 + TOOL 循环 | P3 | 1h | ⏳ 待实现 |
| SEC | Shell 元字符阻断 + find -exec 防护 | P2 | 0.5h | ✅ 已实现 |
| SEC | API Key 认证（shell 命令需鉴权） | P2 | 0.5h | ✅ 已实现 |

## 安全审计清单（已实现）

```
✅ subprocess.run(..., shell=True) 禁止 — 传列表
✅ 白名单 16 命令，参数正则锚定
✅ 黑名单 40+ 命令硬阻断
✅ find -exec/-ok/-execdir 参数级阻断
✅ Shell 元字符阻断：; | ` $() {} <> 全部拒绝
✅ API Key 认证：shell 命令无 Key 返回 401
✅ 路径沙箱：realpath + allowed prefix + blocked patterns
✅ 系统目录封锁：C:\Windows, /etc/, ~/.ssh, AppData 等
✅ 网络下载禁止：curl/wget/certutil/bitsadmin 在黑名单
✅ 无 shell 降级：不执行 cmd/powershell/wsl
✅ 文件大小保护：read 上限 1MB
✅ 全日志：data/tool_log.jsonl 记录每次调用
✅ P3 TOOL 协议：SSE 流拦截 + 自动执行 + 续推理（最多 5 轮）
```

## 禁止清单（硬性规则）

```
❌ subprocess.run(..., shell=True)
❌ 无白名单执行任意命令
❌ 监听 0.0.0.0（必须 127.0.0.1）
❌ 写入系统目录（/etc, C:\Windows, ~/.ssh）
❌ 执行网络下载（curl/wget/certutil）
❌ 无超时的 Shell 命令
❌ 不记录日志的工具调用
```
