# USB-AI

> 便携式 AI 对话网关 — 插上 U 盘就能跑

USB-AI 是一个运行在本地机器上的 AI 对话网关，单 Python 文件即可启动，提供 Web 界面与 AI 模型交互。支持多模型代理、联网搜索、21 个直达数据源、本地 Agent 工具和 P3 TOOL 协议。

## 快速开始

```bash
# 1. 启动服务器
python server.py

# 2. 浏览器打开
# http://localhost:8082
```

在设置页面填入 DeepSeek API Key 即可开始对话。也支持 Ollama 本地模型和 llama-cpp。

## 核心功能

- **多模型代理** — DeepSeek / Ollama 本地 / llama-cpp
- **联网搜索** — Bing + Sogou + SearXNG + DuckDuckGo，引擎健康自动追踪
- **21 个直达数据源** — GitHub / arXiv / CoinGecko / NVD / 微博 / B站 / 知乎 / 豆瓣 / 股市 / 天气 / 黄金 / 比特币 / 汇率 / 高校 / 快递 / IP / 诗歌 / 影视 / 健康 / 新闻 / 论文
- **本地 Agent 工具** — 文件操作 + Shell 白名单 + 桌面自动化（pyautogui）
- **P3 TOOL 协议** — SSE 流拦截 + 自动执行 + 续推理
- **反幻觉检测** — 虚假链接 / 假装操作 / 联网矛盾 / 数据幻觉自动警告
- **数学渲染** — KaTeX 支持 `$$` / `$` / `\(` 公式
- **代码高亮** — highlight.js 暗色主题
- **SVG 画图** — AI 生成内联 SVG 图形
- **对话管理** — 对话历史存储 / 侧边栏切换

## 依赖

| 依赖 | 用途 |
|------|------|
| Python 3.8+ | 运行环境 |
| numpy (可选) | IDF 计算加速 |

无需 Node.js、无需数据库、无需翻墙（国内镜像）。

## 配置

首次启动后，在 Web 界面设置页填入 API Key 和选择模型：

| 模型 | 类型 | 说明 |
|------|------|------|
| DeepSeek V4 Pro | 云端 | 最强推理 |
| DeepSeek V4 Flash | 云端 | 极速低成本 |
| DeepSeek R1 | 云端 | 推理链展示 |
| Ollama 本地模型 | 本地 | 需安装 Ollama |
| llama-cpp GGUF | 本地 | 本地大模型 |

## 项目结构

```
USB-AI/
├── server.py               # 主服务端（全部后端逻辑）
├── app.js                  # 前端主脚本
├── index.html              # 前端页面
├── conversation-manager.js # 对话管理
├── style.css               # 样式
├── docs/                   # 文档
│   ├── 操作手册.md          # 用户操作手册
│   └── 本地Agent工具设计.md  # Agent 工具设计
├── static/vendor/          # 离线 CDN 资源
└── data/                   # 运行时数据（本地）
```

## 安全

- 路径沙箱：文件操作限定 `workspace/ data/ uploads/`
- Shell 白名单 16 命令 + 40+ 黑名单 + 元字符阻断
- Shell 命令需 API Key 授权
- 全操作记入审计日志 `data/tool_log.jsonl`

## 技术栈

- **后端**: Python http.server（无框架，单文件 4450 行）
- **前端**: 原生 JavaScript + HTML5 + CSS3
- **搜索**: Bing Web Search / Sogou / SearXNG / DuckDuckGo
- **本地模型**: Ollama / llama-cpp

## 许可

MIT
