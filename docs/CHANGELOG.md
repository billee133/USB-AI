# USB-AI 变更日志

## v4.5.5（2026-06-29）

### 新增：便携本地模型（llama-cpp-python 集成）
通过 pip 包实现本地推理，零项目体积增量，可快速装卸。

- `_load_local_model()` / `_unload_local_model()`：动态加载/卸载 GGUF 模型
- `_auto_load_local()`：请求时自动按 `_local_` 前缀找 `.gguf` → 加载 → 推理
- `_find_gguf_models()`：扫描 `runtime/models/` 下的 `.gguf` 文件
- `_local_chat_completion()`：流式 + 非流式双模式推理（`stop` token 控制）
- GET `/api/local-llm/status`：查询 {loaded, modelPath, models[], hasDependency}
- POST `/api/local-llm/load`：手动加载指定或首个 GGUF
- POST `/api/local-llm/unload`：卸载模型释放内存
- `_check_llama_cpp()`：探测包是否安装，不安装则自动降级到 Ollama/API

### 前端更新
- 设置下拉框动态填充：`llama-cpp 本地` 分组取自 `/api/local-llm/status` 的 models 列表
- 前端 API Key 检查跳过 `_local_` 模型（无需 Key）

### 安装/卸载脚本
- `setup_local_model.bat`：pip install llama-cpp-python + 下载 Qwen2.5-0.5B GGUF
- `uninstall_local_model.bat`：pip uninstall llama-cpp-python，零残留回退

### 其他
- `.gitignore` 新增 `*.gguf` 规则

---

## v4.5.4（2026-06-29）

### 新增：局域网二维码 + Network API
- 启动时自动检测 LAN IP，打印二维码 URL（`api.qrserver.com`，无依赖）
- 新增 `/api/network-info` 端点：返回 `{localhost, lan, lanIp, port}`
- 提取 `_get_lan_ip()` 工具函数，复用 LAN IP 检测逻辑
- 移除旧 `socket.gethostbyname()` 调用，统一走 `_get_lan_ip()`

---

## v4.5.3（2026-06-29）

### Bug 修复
- `/static/` 路径双拼错误：`os.path.join(_VENDOR_DIR, rel)` 产生 `vendor/vendor/` 前缀 → 修复为 `os.path.join(SCRIPT_DIR, "static", rel)`
- 经验证：所有 6 个 vendor 静态文件均从本地正确服务，CDN fallback 正常

---

## v4.5.2（2026-06-29）

### 新增：三引擎健康追踪（Engine Health Tracker）
- 统一 `_ENGINE_FAILS` 字典追踪 DDG/Bing/Sogou 失败计数
- 连续失败 3 次后自动禁用引擎，所有引擎禁用时自动重置
- 替换旧 DDG-only 熔断器（`_DDG_FAILURES`）

### 新增：考试搜索优化
- $search_edu()$：Sogou `site:` 针对 10 个中国教育域名（edu.cn/neea.edu.cn 等）
- 零结果三级回退链：news search → broaden（去年份/地区）→ raw query
- 铁律 3：已结束的考试是公开信息，AI 不得拒绝回答

### 新增：静态资源离线（Static Vendor Assets）
- 6 个 CDN 资源首次启动时缓存到 `static/vendor/`
- 本地优先 + CDN fallback（CSS/JS 双模式）
- `/static/` 路由在 `do_GET` 中优先服务 vendor 文件

### 分类扩展
- exam 关键词（中考/真题/试题/作文/分数线）+ 6 大类（体育/汽车/电器/电脑/军事/科技）
- 前后端 REALTIME_RE 同步

---

## v4.5.1（2026-06-29）

### 新增：P3 TOOL 协议
- SSE 流拦截 `[TOOL:name args]` 指令，自动执行工具，续推理
- 非流式模式同样支持 TOOL 协议（5 轮循环上限）
- System Prompt 自动注入：10 个工具的描述和调用格式
- `<tool_result>` XML 格式封装工具结果供 AI 消费
- 前端 `_cleanToolMarkers()` 过滤显示中的 `[TOOL:]` 原始标记
- 抑制上游 `[DONE]`，仅在全部工具轮次结束后发送最终 `[DONE]`
- 支持文件工具（read/write/ls/mkdir/mv/rm/append/stat）和 Shell 工具（run_command）
- 日志按 `p3_tool` 类别记录到 `data/tool_log.jsonl`

### 编码修复
- `server.py` 添加 `# -*- coding: utf-8 -*-`（Chinese in TOOL prompt）

---

## v4.5（2026-06-29）

### 新增：AI 自适应数据提取
- `ai_extract()` 函数：发送压缩文本到 DeepSeek 做结构化提取，替代硬编码正则
- 缓存：MD5 指纹 + TTL 10 分钟 + LRU 128 条
- Schema 自动检测：lottery / sports / financial / tabular / generic
- `/api/ai-extract` 路由：直接调用 AI 提取
- RAG 集成：彩票查询先走 AI 提取（00038.cn HTML），回落 huiniao.top API 再回落正则
- RAG 集成：每篇 fetched page 先走 `ai_extract()` 做通用摘要，失败再用正则
- 四级降级：AI 提取 → 正则提取 → 原始文本 → 搜索片段

### 新增：本地 Agent 工具
- P1：8 个文件操作（read/write/append/ls/mkdir/mv/rm/stat）+ 路径沙箱
- P2：16 个白名单 Shell 命令（python/pip/git/npm/node/ls/cat/find/grep/wc/echo/which/pwd/head/tail/dir）
- `/api/tool` 路由：统一接入文件工具和 Shell 命令
- 日志：所有工具调用写入 `data/tool_log.jsonl`

### 安全
- Shell 元字符阻断：`; | \` $() {} <>` 全部拒绝
- `find -exec/-ok/-execdir` 参数级硬阻断
- Shell 命令需 `X-API-Key` 认证（文件工具不需要）
- 40+ 命令黑名单（rm/shutdown/format/powershell/curl/wget/ssh/sudo 等）
- 路径沙箱：realpath + allowed prefix (workspace/data/uploads) + blocked patterns

### 文档
- `docs/CLAUDE.md` v4.4 → v4.5：新增 AI 提取策略、工具安全规则
- `docs/操作手册.md` v4.4 → v4.5：新增 FAQ
- `docs/本地Agent工具设计.md` v1.0 → v2.0：代码对齐、安全审计清单

### 新增：P3 TOOL 协议（v4.5.1）
- SSE 流拦截 `[TOOL:name args]` 指令，自动执行工具，续推理
- 非流式模式同样支持 TOOL 协议（5 轮循环上限）
- System Prompt 自动注入：10 个工具的描述和调用格式
- `<tool_result>` XML 格式封装工具结果供 AI 消费
- 前端 `_cleanToolMarkers()` 过滤显示中的 `[TOOL:]` 原始标记
- 抑制上游 `[DONE]`，仅在全部工具轮次结束后发送最终 `[DONE]`
- 支持文件工具（read/write/ls/mkdir/mv/rm/append/stat）和 Shell 工具（run_command）
- 日志按 `p3_tool` 类别记录到 `data/tool_log.jsonl`

---

## v4.4（2026-06-28）

### Bug 修复
- P0 Bug 1：`_b64` 未定义 → `import base64 as _b64`，Bing 图片解码恢复
- P0 Bug 2：DELETE/PUT handler `str vs int` 类型错误 → 加 try/except int() 转换
- P0 Bug 3：DDG 无限重试 → Content-Type 检查 + 3 次指数退避重试 + 熔断器（连续 2 次失败后跳过）

### 搜索优化
- DDG 熔断器：全局计数器 `_DDG_FAILURES` + 线程锁，熔断后每搜索省 ~7s
- 年份保护：`\b\d+\b` → `\b\d{1,2}\b`，2025/24101 等 3+ 位数字不再被优化器吃掉
- RAG 重试用 `raw_query.strip()` 而非已降级的 query
- English fallback：`terms` → `_en_terms` 从 `raw_query` 派生，避免作用域泄露

### RAG 上下文容量
- app.js: `num:4→8, fetch:1→5, maxChars:1200→6000`
- server.py: `per_source_limit 800→1200, fetch_page_content max_chars 5000→8000`
- 实测：2286 → 稳定 4000-6000 chars

### BM25 上下文压缩
- `compress_context()`：TF·IDF（k1=1.5, b=0.75）+ 长度归一化 + 中文 bigram
- 加分：精确短语匹配 +5、标题关键词 +3、≥3 term 共现 +2
- numpy 有则用 np.log，无则退化为 math.log

### 时间注入
- RAG 上下文注入 `Search Time` / `Current Date`，辅助 AI 时效判断

### 文档
- `docs/CLAUDE.md` v4.3 → v4.4：DDG 熔断器、BM25 压缩、时间注入
- `docs/操作手册.md` v4.3 → v4.4：DDG FAQ

---

## v4.3 及之前

（略）
