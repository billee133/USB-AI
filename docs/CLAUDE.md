# CLAUDE.md — USB-AI

> AI 助手行为准则 · v4.5.7

## 代码风格

- 纯函数优先，避免全局状态
- 一个函数只做一件事
- 禁止 try/catch 空吞异常，必须有日志或回退
- 修改前先验证当前文件能编译

## 测试要求

- JS: `node --check app.js` 零错误
- Python: `py_compile.compile('server.py', doraise=True)` 零错误
- 修改后必须验证

## 禁止事项

- 禁止在 JS 字符串中使用真实换行符，一律用 `\n`
- 禁止 `role==='ai'` 硬编码，须同时接受 `'assistant'`
- 禁止 localStorage 无保护写入
- 禁止编辑后不验证语法
- 禁止 save innerHTML，只保存原始 Markdown
- 禁止 async 函数无 try/finally — busy/loading 状态必须在 finally 中重置
- 禁止直达数据源走 fetch_page_content — API URL 当网页抓会丢数据
- 禁止 ThreadPoolExecutor with 语句在 RAG 中使用 — exit 时 wait=True 阻塞所有任务
- 禁止百度系域名直接 fetch — baijiahao/zhidao/tieba/wenku 走 SNIPPET_ONLY_DOMAINS 片段兜底
- 禁止修改 `conversation-manager.js`、`style.css`（除非明确要求）
- 禁止修改 `data/` 目录下的文件（SQLite 数据库 + token 文件）

## 输出标准

- 修改完成后给出变更摘要
- 不输出未请求的额外功能
- 报错时输出具体错误信息和行号
- 每个修复标注 Token 节省百分比

## 搜索策略

- 默认禁止联网搜索
- 仅实时关键词或用户明确要求时触发
- 直达数据源（GoldAPI/Binance/OpenER等）与网页搜索并行执行
- 新闻搜索三级回退：Google News → Bing News → Sogou site: 中文站
- 地缘政治查询：自动拆词 + 英文回退 + 跳过相关性过滤
- 反爬域名（知乎/澎湃/百度系）→ 不用 fetch，直接用搜索片段
- DuckDuckGo 熔断器：连续失败3次后本会话跳过
- 上下文压缩用 BM25 评分（TF·IDF + 长度归一化），替代关键词计数
- RAG 上下文注入搜索时间（Search Time / Current Date）辅助时效判断
- 年份/期号保护：`\b\d{1,2}\b` 只过滤1-2位数字，保留 3+ 位（年份2025、期号24101等）

## AI 提取策略

- `ai_extract()` 发送压缩文本到 DeepSeek，替代硬编码正则
- 架构：缓存(MD5指纹+TTL 10min+LRU 128条) → AI请求 → JSON解析 → 缓存写入
- schema 自动检测：lottery/sports/financial/tabular/generic，按 query 关键词匹配
- 回落链：AI提取 → 正则提取 → 原始文本直传 → 搜索片段，四级降级，用户永不见"提取失败"
- 彩票查询优先 AI 提取（00038.cn HTML），失败回落 huiniao.top API 再回落正则
- 通用摘要：每篇 fetched page 先走 `ai_extract()`，失败再用 `generate_summary()` 正则
- Token 成本：~500-800 tokens/次，DeepSeek ~$0.28/1M input ≈ $0.0002/次
- prompt 铁则：只输出 JSON，不解释，不臆造，无代码块；温度 0.1；max_tokens 1024

## 工具安全规则

- 路径沙箱：所有文件操作 restricted to `workspace/ data/ uploads/`，realpath 解析后前缀白名单
- 系统路径黑名单：`C:\Windows`, `/etc/`, `~/.ssh`, `AppData` 等硬阻断
- Shell 执行：禁止 `shell=True`，subprocess.run 传列表
- 命令白名单（16个）：python/pip/git/npm/node/ls/cat/find/grep/wc/echo/which/pwd/head/tail/dir
- 命令黑名单（40+）：rm/shutdown/format/powershell/curl/wget/ssh/sudo 等
- 参数正则锚定：每个白名单命令有 args 模式，不匹配拒绝
- find -exec/-ok/-execdir：硬阻断，防止绕过黑名单执行删除/下载
- Shell 元字符阻断：`; | \` $() ` 等出现在任何参数中直接拒绝
- Shell 命令需 API Key：`_handle_tool` 中 type=shell 检查 X-API-Key，文件工具不要求
- 日志：所有工具调用写入 `data/tool_log.jsonl`（时间/动作/耗时/成功）
- 文件大小上限：1MB（读取），10KB（输出截断）
- 审计：全部可追溯，`_log_tool_action()` 统一写入
- P3 TOOL 协议：SSE 流拦截 `[TOOL:name args]`，自动执行工具，续推理（最多 5 轮）
- P3 System Prompt 注入：工具描述自动追加到 system message
- 前端 `_cleanToolMarkers()`：移除显示中的 `[TOOL:]` 标记

## 桌面自动化规则

- 依赖检测：`_check_auto_deps()` 检查 pyautogui + pillow 是否安装
- 启用需 `_AUTO_ENABLED = True`，通过设置面板打勾或 POST /api/auto/settings
- 安装：`POST /api/auto/install {action:"install"}` — 优先 `runtime/auto-deps/*.whl`，无则在线
- 卸载：`POST /api/auto/install {action:"uninstall"}` — 零残留，不影响其他功能
- 所有自动化端点需 `X-Local-Token` 认证
- 浏览器打开仅允许 http/https scheme（`urlparse` 校验）
- 键盘快捷键阻止 Ctrl+Alt+Del / Win+R
- P3 TOOL 协议支持：screenshot/click/type_text/hotkey/browser_open/task_create/task_stop
- app.js 封装确认框：`_doInstallAuto()` / `_doUninstallAuto()` / `_doEnableAuto()`
- 页面加载静默查询状态，不弹确认框

## LOCAL_TOKEN 持久化

- 首次启动生成 `secrets.token_hex(16)`，存入 `data/local_token.txt`
- 后续启动从该文件读取，重启不变
- 用于前端 X-Local-Token 认证，防止页面 token 失效

## 模型列表（8个有效）

| API模型名 | 说明 |
|-----------|------|
| deepseek-v4-pro | V4 Pro — 最强推理 |
| deepseek-v4-flash | V4 Flash — 极速低成本 |
| deepseek-chat | V3 — 日常对话 |
| deepseek-reasoner | R1 — 推理链 |
| deepseek-r1:1.5b | R1 1.5B — Ollama 本地 |
| qwen2.5:0.5b | Qwen 0.5B — Ollama 本地 |
| _local_*.gguf | llama-cpp 本地推理（需 pip install llama-cpp-python） |

注意：`deepseek-v4`（裸名）不是有效模型，已移除。

## 项目交付标准

- 修改 server.py 后必须重启服务器
- 修改 app.js/conversation-manager.js 后必须更新 index.html 版本号
- 修改功能后同步更新 docs/ 下对应文档
- 桌面自动化功能部署后必须测试 `/api/auto/settings` 和 `/api/auto/screenshot`
- LOCAL_TOKEN 变更后必须同步 index.html
