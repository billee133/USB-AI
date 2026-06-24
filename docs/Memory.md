# Memory.md — 项目记忆

> 最后更新: 2026-06-22 | USB-AI v4.2

## 当前进展

- 五文件架构：index.html(53行) + app.js(355行) + style.css(85行) + conversation-manager.js(169行) + server.py(2099行)
- 流式打字机 + Markdown/KaTeX/highlight.js 渲染
- ConversationManager 类管理会话，localStorage 持久化，刷新恢复
- **AI 自适应数据提取**：ai_extract() → DeepSeek 结构化提取，4 级回落
- **直达数据矩阵**：15+ 免费 API，0.5s 实时数据
- **AI 工具调用**：[SEARCH:查询词] 标记，AI 自主决定搜索
- **Token 优化**：零 Token 模式、响应缓存、历史压缩、按需 Prompt
- 侧边栏：新建对话即时出现，刷新不跳回旧记录
- 调试面板：设置中开关，RAG 返回数据量显示

## 数据源矩阵

| 品类 | 来源 | 类型 |
|------|------|------|
| 贵金属(金银铜钯) | GoldAPI | 直达API |
| 加密货币(8种) | Binance API | 直达API |
| 汇率 | OpenER API | 直达API |
| 原油(WTI/布伦特) | BusinessInsider 抓取 | 网页抓取 |
| 天气 | Open-Meteo | 直达API |
| 彩票(30+彩种) | huiniao.top API + 00038.cn | API+HTML |
| 汽车(报价/配置/保养) | 汽车之家 抓取 | 网页抓取 |
| 手机(价格/配置/回收) | 中关村在线 抓取 | 网页抓取 |
| 新闻 | Google News RSS | RSS |
| 百科 | Wikipedia API | 直达API |
| 通用搜索 | Bing + Sogou + DDG | 网页搜索 |
| 电商(京东/淘宝/拼多多) | 搜索+AI提取 | 搜索+AI |

## Token 优化模块

| 模块 | 机制 | 节省 |
|------|------|------|
| 零 Token 模式 | 问候/时间/帮助/计算 → 本地 JS 返回 | ~15% |
| 响应缓存 | localStorage + 24h TTL | 100% 重复查询 |
| 历史压缩 | 超过 8 轮生成摘要 | ~60% |
| Prompt 精简 | 按场景动态加载 | ~40% |
| 智能搜索门 | needSearch() + _isRealtime() | ~20% |

## 模型支持

- 云端：DeepSeek V4 Pro / V4 / V3 / R1
- 本地：Ollama 兼容（自动检测 `:` 标记路由到 localhost:11434）
- 状态栏显示当前模型徽章（云=蓝色，本地=绿色）

## 已确认结论

- Bing 中文拆分"世界杯"→"世界"+"杯"，需替代查询策略
- Sogou 需 Cookie，DDG 中文弱
- localStorage 被浏览器隐私设置阻止则全部存储失效
- CDN 库首次加载后浏览器缓存，离线不可用
- ThreadPoolExecutor with 语句退出时 wait=True 阻塞所有任务
- 直达 API 结果不能走 fetch_page_content（会把 API URL 当网页抓）

## 用户偏好

- U 盘便携，零安装
- 界面简洁，功能直接
- 不过度安全警告
- 默认不搜索，仅实时关键词触发
- AI 应主动获取数据而非说"我无法联网"

## 待办

- [ ] SearXNG 集成
- [ ] 离线 Service Worker
- [ ] llama.cpp 便携本地模型（单exe+GGUF放U盘）
- [ ] 流式响应中 [SEARCH:] 实时拦截
- [ ] 自动更新检查
