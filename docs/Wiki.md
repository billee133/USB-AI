# Wiki.md — 项目百科

> USB-AI v4.2 | 最后更新: 2026-06-22

## 架构

```
浏览器 → index.html(53行) + app.js(355行) + style.css(85行) + conversation-manager.js(169行)
       │
       ├── /api/deepseek/stream   (SSE 流式代理)
       ├── /api/deepseek          (标准代理)
       ├── /api/rag               (RAG 管道：搜索→抓取→压缩→AI提取→上下文)
       ├── /api/search            (多引擎搜索 + 15+ 直达数据源)
       ├── /api/ai-extract        (AI 结构化数据提取)
       ├── /api/classify          (意图分类)
       ├── /api/fetch             (网页正文抓取)
       ├── /api/db/*              (SQLite 配置/对话)
       └── /api/ping              (健康检查)
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/ping | GET | 服务器健康检查 |
| /api/deepseek | POST | DeepSeek API 代理（非流式） |
| /api/deepseek/stream | POST | SSE 流式代理 |
| /api/search | POST | 多引擎搜索 (Bing+Sogou+DDG) + 直达数据 |
| /api/rag | POST | RAG 管道 (搜索→抓取→摘要→事实提取) |
| /api/ai-extract | POST | AI 结构化数据提取 |
| /api/classify | POST | 意图分类 |
| /api/fetch | POST | 网页正文抓取 |
| /api/db/settings | GET/POST | 服务端配置 |
| /api/db/chats | GET/POST/DELETE | 对话历史 CRUD |

## 本地模型路由

模型名含 `:` → 自动路由到 `http://localhost:11434`（Ollama）

云模型 → `https://api.deepseek.com/v1/chat/completions`

## 数据源矩阵

| 品类 | 来源 | 延迟 |
|------|------|------|
| 贵金属(金/银/铜/钯) | GoldAPI | <1s |
| 加密货币(8种) | Binance API | <1s |
| 汇率 | OpenER API | <1s |
| 原油(WTI/布伦特) | BusinessInsider | <3s |
| 天气 | Open-Meteo | <1s |
| 彩票(30+彩种) | huiniao API + 00038 | <1s |
| 汽车(报价/配置) | 汽车之家 抓取 | <3s |
| 手机(价格/回收) | 中关村在线 抓取 | <3s |
| 新闻 | Google News RSS | <2s |
| 百科 | Wikipedia API | <2s |
| 通用搜索 | Bing+Sogou+DDG | <10s |

## 存储

| Key | 用途 |
|-----|------|
| portable_chats | 对话历史列表 |
| portable_autosave | 崩溃恢复缓存 |
| uai_cfg | 用户配置 |
| uai_theme | 主题偏好 |
| uai_debug | 调试面板开关 |

## 渲染管线

原始 Markdown → 提取 LaTeX → marked.js → KaTeX → highlight.js → DOM

## Token 优化管线

用户输入 → _classify() → local? → 零Token处理
                       → cache? → 缓存返回
                       → search? → RAG → LLM
                       → llm → _compressHistory() → LLM
