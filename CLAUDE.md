# CLAUDE.md — USB-AI

> 便携式 AI 网关项目 · v4.6.3

## 项目概述

USB-AI 是运行在本地机器上的 AI 对话网关。核心功能：
- 多模型代理（DeepSeek API / Ollama 本地 / llama-cpp）
- 联网搜索（Bing + Sogou + SearXNG + DuckDuckGo）
- 21 个直达数据源（GitHub/arXiv/CoinGecko/NVD/B站/微博...）
- 本地 Agent 工具（文件操作 + 白名单 Shell + 桌面自动化）
- P3 TOOL 协议（SSE 流拦截 + 自动执行 + 续推理）

## 项目结构

```
USB-AI/
├── server.py              # 主服务端（+360KB），全部后端逻辑
├── app.js                 # 前端主脚本
├── index.html             # 前端页面
├── conversation-manager.js # 对话管理
├── style.css              # 样式
├── docs/                  # 技术文档
│   ├── CLAUDE.md          # AI 行为准则（v4.6.1）
│   ├── CHANGELOG.md       # 变更日志
│   ├── 操作手册.md         # 用户操作手册
│   └── 本地Agent工具设计.md # Agent 工具技术设计
├── .claude/               # Claude Code 项目记忆
│   └── memory/
├── static/vendor/         # 离线 CDN 资源（6 个）
├── runtime/               # 运行时依赖
│   ├── python-win/        # Windows 嵌入式 Python
│   ├── llama/             # llama-cpp 模型
│   ├── searxng/           # SearXNG 自建搜索
│   ├── auto-deps/         # 桌面自动化离线 whl
│   └── models/            # GGUF 本地模型
├── data/                  # 运行时数据
│   ├── conversations.db   # 对话历史
│   ├── local_token.txt    # LOCAL_TOKEN 持久化
│   └── tool_log.jsonl     # 工具调用审计日志
├── tasks/                 # 定时任务
├── screenshots/           # 截图保存
└── workspace/             # 文件工具沙箱
```

## 开发规则

### 语法验证（必做）
- Python: `python -c "import py_compile; py_compile.compile('server.py', doraise=True)"`
- JS: `node --check app.js`

### 修改后必须做的事
- 修改 server.py → 重启服务器
- 修改 app.js / conversation-manager.js → 更新 index.html 版本号
- 修改功能 → 同步更新 docs/ 下对应文档
- 版本变更 → 更新 CHANGELOG.md + 本文件版本号

### 前端关键机制
- **脚本加载顺序**：vendor JS（marked/katex/hljs）通过动态 `<script>` 标签异步加载，`app.js` 初始化 IIFE 必须在 vendor 就绪后才执行（当前用 30ms 轮询 `typeof marked`）。加载前 `renderMessage()` 走 FALLBACK 路径（手写正则，无语法高亮/数学渲染）。
- **SVG 渲染**：`renderMessage()` 检测 `pre code.language-svg` → 剥离 `<script>` → 替换为内联 SVG。AI 系统提示含 SVG 画图指令。
- **数学公式**：支持 `$$...$$`（显示）、`\[...\]`（显示）、`$...$`（行内，需含 LaTeX 命令）、`\(...\)`（行内）。
- **复制按钮**：必须 `setAttribute('onclick','cp(this)')` 不能用 `.onclick = function(){}`——innerHTML 序列化会丢失 JS 事件。
- **代码高亮**：`github-dark.min.css` 暗色主题，代码块背景 `#1e1e1e`。hljs 加载后自动重高亮已渲染代码块。

### 前端 v4.6.2 新增机制
- **Sticky 代码工具栏**：`.code-toolbar` 用 `position: sticky; top: 0`。`.msg .b pre` 不可设 `overflow-x: auto`（CSS 规范：任何非 visible overflow 祖先破坏 sticky 上下文）。
- **预览面板**：iframe sandbox 必须含 `allow-same-origin`，仅 `allow-scripts` 导致 null origin 内容空白。
- **SSE 错误处理**：客户端解析器检查 `ch.error`，服务端异常通过 `_send_sse_error()` 发送标准格式。

### 前端 v4.6.3 新增机制
- **反幻觉机制**：系统 prompt 追加 7 条幻觉防范铁律。`_hallucinationCheck()` 函数检测虚假链接、假装操作、联网矛盾、数据幻觉。黄色警告横幅 CSS。
- **搜索开关修复**：关闭搜索时 prompt 不再教 AI 用 `[SEARCH:]`，改为动态判断 `search` 状态。`_isRealtime` 不再强制绕过搜索开关。
- **上下文感知路由**：有对话历史时，单数字消息（如"4"）不被本地数学路由拦截，正常发送给 AI。
- **错误信息兜底**：`e.message||e.name||String(e)` 防止 AbortError 等显示 "undefined"。
- **XSS 修复**：幻觉检测输出中的 URL 用 `esc()` 转义。
- **AbortController 优化**：4 处 `abort()` 加上中文 reason，主请求超时从 60s 延长到 90s。

### 禁止事项
- 不修改 `conversation-manager.js`、`style.css`（除非明确要求）
- 不修改 `data/` 目录下的数据库和 token 文件
- 不修改 `SNIPPET_ONLY_DOMAINS`、`JUNK_DOMAINS` 等安全常量
- 不改变端口号 `PORT = 8082`
- JS 字符串不用真实换行符，用 `\n`
- 不硬编码 `role === 'ai'`，须同时接受 `'assistant'`

### 搜索管线
- 默认不联网，仅实时关键词触发
- 引擎健康追踪：连续失败 3 次自动禁用，全禁时自动重置
- 直达数据源优先于网页搜索（21 个数据源按关键词路由）
- 所有新数据源失败静默降级（返回 `[]`），不影响 web_search

### 安全
- 路径沙箱：文件操作限定 `workspace/ data/ uploads/`
- Shell 白名单 16 命令 + 40+ 黑名单 + 元字符阻断
- Shell 命令需 API Key，文件工具不要求
- 全操作记入 `data/tool_log.jsonl`
- `subprocess.run` 永远传列表，禁止 `shell=True`

## 测试
- 功能变更后运行所有受影响的数据源函数
- 代理环境（127.0.0.1:7892）下部分 HTTPS API 会失败（WorldBank/arXiv/ipapi），属环境问题非代码 bug
- 微博/知乎依赖反爬，可能间歇性空返回

## 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|---------|
| v4.6.3 | 2026-07-04 | 反幻觉机制 + 搜索开关修复 + 上下文路由 + 错误兜底 + XSS修复 |
| v4.6.2 | 2026-07-02 | Sticky工具栏 + SSE错误处理 + 预览修复 + 超时优化 |
| v4.6.1 | 2026-07-01 | 前端重设计：暗色移除、代码高亮、SVG图形、数学$$ |
| v4.6.0 | 2026-07-01 | 20 信息源扩展 |
| v4.5.9 | 2026-07-01 | 截图 save_path 强制 + write_file 转义修复 |
| v4.5.8 | 2026-06-30 | SearXNG 集成 |
| v4.5.6 | 2026-06-29 | 桌面自动化 |
| v4.5.5 | 2026-06-29 | llama-cpp 本地模型 |
| v4.5.1 | 2026-06-29 | P3 TOOL 协议 |
| v4.5 | 2026-06-29 | AI 自适应提取 + 本地 Agent 工具 |

完整变更见 [docs/CHANGELOG.md](docs/CHANGELOG.md)。

## Agent skills

### Issue tracker

任务记录在 `docs/` 目录下的项目文档中，无外部 Issue 系统。See `docs/agents/issue-tracker.md`.

### Triage labels

使用默认标签名。See `docs/agents/triage-labels.md`.

### Domain docs

单上下文布局 — 项目级 `CONTEXT.md` + `docs/adr/`。See `docs/agents/domain.md`.
