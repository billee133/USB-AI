# CLAUDE.md — USB-AI

> AI 助手行为准则 · v4.3

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
- 禁止保存 innerHTML，只保存原始 Markdown
- 禁止 async 函数无 try/finally — busy/loading 状态必须在 finally 中重置
- 禁止直达数据源走 fetch_page_content — API URL 当网页抓会丢数据
- 禁止 ThreadPoolExecutor with 语句在 RAG 中使用 — exit 时 wait=True 阻塞所有任务
- 禁止百度系域名直接 fetch — baijiahao/zhidao/tieba/wenku 走 SNIPPET_ONLY_DOMAINS 片段兜底

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

## 模型列表（6个有效）

| API模型名 | 说明 |
|-----------|------|
| deepseek-v4-pro | V4 Pro — 最强推理 |
| deepseek-v4-flash | V4 Flash — 极速低成本 |
| deepseek-chat | V3 — 日常对话 |
| deepseek-reasoner | R1 — 推理链 |
| deepseek-r1:1.5b | R1 1.5B — Ollama 本地 |
| qwen2.5:0.5b | Qwen 0.5B — Ollama 本地 |

注意：`deepseek-v4`（裸名）不是有效模型，已移除。

## 项目交付标准

- 修改 server.py 后必须重启服务器
- 修改 app.js/conversation-manager.js 后必须更新 index.html 版本号
- 修改功能后同步更新 docs/ 下对应文档
