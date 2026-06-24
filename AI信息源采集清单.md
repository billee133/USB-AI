# AI 信息源采集清单（2026）

> 用于 AI 助手联网搜索 / RAG 上下文注入的数据源全集。按类型分类，标注免费状态、密钥要求、中文支持、CORS、部署方式。
>
> 结合 USB-AI 两种模式给出适配建议：**直连模式**（浏览器 fetch，受 CORS 约束）/ **代理模式**（server.py 转发，无 CORS 限制）

---

## 一、通用网页搜索 — 免费 / 无 Key

| 信息源 | 密钥 | 中文 | CORS | 部署 | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|---|
| **DuckDuckGo Instant Answer** | ❌ 无 | ⚠ 一般 | ✅ 允许 | 直连 | `https://api.duckduckgo.com/?q=...&format=json` | ✅ 直连模式首选（当前已用） |
| **Wikipedia REST API** | ❌ 无 | ✅ 中文版 | ✅ 允许 | 直连 | `https://zh.wikipedia.org/api/rest_v1/` | ✅ 直连，知识问答强 |
| **Wikidata SPARQL** | ❌ 无 | ✅ | ✅ 允许 | 直连 | `https://query.wikidata.org/sparql?format=json` | ✅ 结构化知识图谱 |
| **Hacker News API** | ❌ 无 | ❌ 英文 | ✅ 允许 | 直连 | `https://hn.algolia.com/api/v1/search?query=...` | ✅ 技术资讯 |
| **arXiv API** | ❌ 无 | ⚠ 英文为主 | ✅ 允许 | 直连 | `http://export.arxiv.org/api/query` | ✅ 学术论文 |
| **PubMed E-utilities** | ❌ 无 | ❌ 英文 | ✅ 允许 | 直连 | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` | ✅ 医学文献 |
| **Semantic Scholar API** | ❌ 无（有速率） | ⚠ 英文 | ✅ 允许 | 直连 | `https://api.semanticscholar.org/graph/v1/` | ✅ 学术关系网络 |
| **OpenAlex API** | ❌ 无 | ⚠ 英文 | ✅ 允许 | 直连 | `https://api.openalex.org/works?search=...` | ✅ 学术（Semantic Scholar 替代） |
| **Reddit API** | ⚠ 需注册 | ✅ | ✅ | 直连 | `https://www.reddit.com/search.json?q=...` | ⚠ 2025 起收费，有限 |
| **GitHub Search API** | ⚠ 需 token | ✅ | ✅ | 直连 | `https://api.github.com/search/repositories?q=...` | ✅ 代码搜索 |

---

## 二、通用网页搜索 — 需 Key / 有免费额度

| 信息源 | 免费额度 | 中文 | 部署 | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **Bing Web Search API** | 1000 次/月 | ✅ 强 | 代理 | 微软，需 Azure key | ⚠ 代理模式，中文质量好 |
| **Brave Search API** | 2000 次/月 | ⚠ 一般 | 代理 | 独立索引，隐私优先 | ⚠ 代理模式 |
| **Google Custom Search** | 100 次/天 | ✅ | 代理 | 限自定义搜索引擎内 | ⚠ 配额低 |
| **SerpAPI** | 100 次/月 | ✅ | 代理 | 聚合 Google 结果，付费 | ❌ 太贵 |
| **Tavily API** | 1000 次/月 | ⚠ | 代理 | 专为 AI 设计，返回清洗后内容 | ⚠ AI 优化但需 key |
| **Boson 博查 API** | 5000 点 | ✅ 强 | 代理 | 国产，中文友好 | ✅ 中文代理推荐 |
| **Metaso 秘塔搜索 API** | 5000 点 | ✅ 强 | 代理 | 国产，0.03 元/次，多模态 | ✅ 中文场景强 |
| **Exa (原 Metaphor)** | 1000 次/月 | ⚠ | 代理 | 神经搜索，语义检索 | ⚠ 语义搜索 |

---

## 三、元搜索 / 聚合引擎（自托管，无 Key 无限流）

| 信息源 | 部署 | 中文 | 引擎数 | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **SearXNG** | Docker | ✅ | 70+ | 开源元搜索，聚合 Google/Bing/DDG/Wikipedia 等 | ✅✅ 代理模式终极方案 |
| **free-web-search** | Docker | ⚠ | 70+ | SearXNG 封装，专为 AI，`localhost:8888` | ✅ 基于 SearXNG，开箱即用 |
| **Whoogle** | Docker | ✅ | 1 | Google 代理，无广告无追踪 | ⚠ 单引擎 |
| **4get** | Docker | ✅ | 多 | 轻量元搜索 | ⚠ 小众 |

**SearXNG 是当前 AI Agent 联网搜索的事实标准**。Docker 一键部署，70+ 引擎聚合，无限流，免费。USB-AI 代理模式可对接。

---

## 四、中文专用信息源

| 信息源 | 密钥 | CORS | 获取方式 | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **搜狗搜索** | ❌ 无 | ❌ | 代理抓 HTML | 中文质量好，需 cookie 反爬 | ✅ server.py 已实现 |
| **百度搜索** | ❌ 无 | ❌ | 代理抓 HTML | 中文最强，反爬严 | ⚠ 反爬升级频繁 |
| **必应中文** | ⚠ API key | ❌ | 代理 | 中文质量好 | ⚠ 配额 |
| **微信公众号文章** | ❌ 无 | ❌ | 代理抓搜狗微信 | `weixin.sogou.com` | ⚠ 搜狗微信入口已收紧 |
| **知乎** | ❌ 无 | ❌ | 代理抓 HTML / 第三方 | 需登录，反爬严 | ⚠ 难度高 |
| **微博搜索** | ⚠ 需 cookie | ❌ | 代理抓 HTML | `s.weibo.com` | ⚠ 需登录态 |
| **小红书** | ⚠ 需 cookie | ❌ | 代理抓 HTML | 反爬极严 | ❌ 不推荐 |
| **豆瓣** | ❌ 无 | ❌ | 代理抓 HTML | 书影音评价 | ⚠ 可抓 |
| **百度百科** | ❌ 无 | ❌ | 代理抓 HTML | 中文知识 | ✅ 代理可抓 |
| **头条搜索** | ❌ 无 | ❌ | 代理抓 HTML | `so.toutiao.com` | ⚠ 可抓 |

---

## 五、知识库 / 百科（结构化知识）

| 信息源 | 密钥 | 中文 | CORS | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **Wikipedia REST API** | ❌ 无 | ✅ | ✅ | 多语言，最全 | ✅ 直连首选 |
| **Wikidata SPARQL** | ❌ 无 | ✅ | ✅ | 结构化知识图谱 | ✅ 实体查询 |
| **DBpedia SPARQL** | ❌ 无 | ⚠ | ✅ | Wikipedia 结构化版 | ⚠ 维护减弱 |
| **百度百科** | ❌ 无 | ✅ | ❌ | 代理抓取 | ✅ 代理模式 |
| **萌娘百科** | ❌ 无 | ✅ | ❌ | ACG 内容 | ⚠ 小众 |
| **MBA 智库** | ❌ 无 | ✅ | ❌ | 商业管理 | ⚠ 垂直 |
| **ICIBA 金山词霸** | ❌ 无 | ✅ | ✅ | 词典翻译 | ⚠ 词典 |

---

## 六、新闻 / 资讯（实时）

| 信息源 | 密钥 | 中文 | CORS | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **NewsAPI.org** | ⚠ 需 key | ⚠ | ✅ | 100 次/天免费 | ⚠ 配额低 |
| **GNews API** | ⚠ 需 key | ✅ | ✅ | 100 次/天 | ⚠ |
| **Currents API** | ⚠ 需 key | ⚠ | ✅ | 600 次/月 | ⚠ |
| **Google News RSS** | ❌ 无 | ✅ | ✅ | `https://news.google.com/rss/search?q=...&hl=zh` | ✅ 直连，实时新闻 |
| **Bing News RSS** | ❌ 无 | ✅ | ✅ | RSS 抓取 | ✅ 直连 |
| **新华网 RSS** | ❌ 无 | ✅ | ✅ | 官方新闻 | ✅ 直连 |
| **澎湃新闻 RSS** | ❌ 无 | ✅ | ✅ | 质量高 | ✅ 直连 |
| **微博热搜** | ❌ 无 | ✅ | ❌ | 代理抓 HTML | ⚠ 需代理 |
| **知乎热榜** | ❌ 无 | ✅ | ❌ | 代理抓 HTML | ⚠ 需代理 |
| **今日头条** | ❌ 无 | ✅ | ❌ | 代理抓 HTML | ⚠ 需代理 |

---

## 七、学术 / 专业（深度知识）

| 信息源 | 密钥 | 中文 | CORS | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **arXiv API** | ❌ 无 | ⚠ | ✅ | 预印本论文 | ✅ 直连 |
| **PubMed E-utilities** | ❌ 无 | ❌ | ✅ | 生物医学 | ✅ 直连 |
| **Semantic Scholar** | ❌ 无 | ⚠ | ✅ | AI 驱动学术 | ✅ 直连 |
| **OpenAlex** | ❌ 无 | ⚠ | ✅ | 2.5 亿作品，Semantic Scholar 替代 | ✅ 直连 |
| **CrossRef API** | ❌ 无 | ⚠ | ✅ | DOI 元数据 | ✅ 直连 |
| **CORE API** | ⚠ 需 key | ⚠ | ✅ | 开放获取论文 | ⚠ |
| **Unpaywall API** | ❌ 无 | ❌ | ✅ | 找论文免费全文 | ✅ 直连 |
| **知网 CNKI** | ⚠ 付费 | ✅ | ❌ | 中文学术，需机构 | ❌ 闭源 |
| **万方** | ⚠ 付费 | ✅ | ❌ | 中文学术 | ❌ 闭源 |
| **维普** | ⚠ 付费 | ✅ | ❌ | 中文学术 | ❌ 闭源 |

---

## 八、社交 / 实时（舆情 / 趋势）

| 信息源 | 密钥 | 中文 | CORS | 说明 | USB-AI 适配 |
|---|---|---|---|---|---|
| **Twitter/X API** | ⚠ 需 key（贵） | ✅ | ✅ | 2023 起大幅收费 | ❌ 太贵 |
| **Mastodon API** | ❌ 无 | ✅ | ✅ | 去中心化，实例 API | ✅ 直连 |
| **Reddit API** | ⚠ 需注册 | ✅ | ✅ | 2025 收费 | ⚠ |
| **Telegram API** | ⚠ 需 bot token | ✅ | ✅ | 频道消息 | ⚠ |
| **Discord API** | ⚠ 需 bot token | ✅ | ✅ | 服务器消息 | ⚠ |
| **微博热搜** | ❌ 无 | ✅ | ❌ | 代理抓取 | ⚠ 需代理 |
| **抖音热搜** | ❌ 无 | ✅ | ❌ | 代理抓取 | ⚠ 需代理 |
| **B 站热搜** | ❌ 无 | ✅ | ✅ | `api.bilibili.com` | ✅ 直连可用 |

---

## 九、MCP 搜索服务（2026 新趋势，本地优先无 Key）

| 信息源 | 部署 | 中文 | 说明 | USB-AI 适配 |
|---|---|---|---|---|
| **free-search-mcp** | 本地 | ✅ | MCP 服务器，无 key 无限，Claude/GPT 可用 | ⚠ MCP 协议，USB-AI 非 MCP 架构 |
| **Open-WebSearch MCP** | 本地 | ✅ | 开源 AI 联网插件 | ⚠ 同上 |
| **Tavily MCP** | 本地+key | ⚠ | Tavily 的 MCP 封装 | ⚠ 需 key |

> MCP（Model Context Protocol）是 2024 年 Anthropic 推出的 AI 工具协议，2026 年成为 Agent 联网搜索主流方案之一。USB-AI 当前非 MCP 架构，可作为未来扩展方向。

---

## 十、垂直领域数据源

| 领域 | 信息源 | 密钥 | 说明 |
|---|---|---|---|
| **天气** | Open-Meteo API | ❌ 无 | 免费，无需 key，全球 |
| **天气** | 和风天气 API | ⚠ 需 key | 中文友好，免费额度 |
| **金融** | Yahoo Finance API | ❌ 无 | 股票数据（非官方） |
| **金融** | Tushare | ⚠ 需 token | A 股数据，免费额度 |
| **金融** | Alpha Vantage | ⚠ 需 key | 美股，500 次/天 |
| **地理** | Nominatim (OSM) | ❌ 无 | 地理编码，免费 |
| **IP** | ipapi.co | ❌ 无 | IP 地理位置 |
| **时间** | WorldTimeAPI | ❌ 无 | 时区时间 |
| **汇率** | exchangerate-api | ⚠ 需 key | 汇率，免费额度 |
| **代码** | GitHub Search API | ⚠ 需 token | 代码仓库 |
| **代码** | npm registry API | ❌ 无 | npm 包信息 |
| **代码** | PyPI JSON API | ❌ 无 | PyPI 包信息 |

---

## USB-AI 场景推荐方案

### 直连模式（浏览器，受 CORS 约束）

**可用信息源**（CORS 友好 + 无 key）：
1. **DuckDuckGo Instant Answer** — 通用搜索（当前已用）
2. **Wikipedia REST API** — 知识问答
3. **Wikidata SPARQL** — 结构化实体
4. **arXiv / PubMed / Semantic Scholar / OpenAlex** — 学术
5. **Google News RSS / Bing News RSS / 新华网 RSS / 澎湃 RSS** — 新闻
6. **Hacker News API** — 技术资讯
7. **B 站热搜 API** — 中文趋势
8. **Open-Meteo** — 天气
9. **npm / PyPI API** — 包信息

**直连模式搜索降级链**：
```
DDG Instant Answer → Wikipedia → RSS 新闻聚合 → 空结果
```

### 代理模式（server.py，无 CORS 限制）

**推荐架构**（分三档）：

| 档位 | 方案 | 信息源 | 适用 |
|---|---|---|---|
| **基础** | 现状 | DDG + Sogou + Bing HTML 抓取 | 当前已实现 |
| **增强** | + RSS | 基础 + Google News RSS + 新华/澎湃 RSS + 微博热搜抓取 | 中文新闻质量提升 |
| **终极** | + SearXNG | 基础 + 自托管 SearXNG（70+ 引擎聚合） | 主力电脑，质量最高 |

**代理模式推荐降级链**：
```
SearXNG(自托管) → Sogou+Bing+DDG 三引擎 → RSS 新闻 → Wikipedia → 空结果
```

### 关键建议

1. **直连模式**：补全 Wikipedia API + RSS 新闻源（零成本，CORS 友好）
2. **代理模式**：新增 SearXNG 自托管选项（Docker，主力电脑部署一次，70+ 引擎聚合）
3. **中文场景**：代理模式保留 Sogou HTML 抓取（已实现），新增百度/微博热搜抓取
4. **学术场景**：直连即可用 arXiv/PubMed/Semantic Scholar/OpenAlex（全免费无 key）
5. **避免**：Twitter/X API（太贵）、小红书/知乎（反爬极严，ROI 低）

---

## 信息源质量排序（中文场景）

| 排名 | 信息源 | 质量 | 成本 |
|---|---|---|---|
| 1 | SearXNG（自托管，含 Google/Bing） | ★★★★★ | Docker 部署 |
| 2 | Boson 博查 API | ★★★★☆ | 5000 点免费 |
| 3 | Metaso 秘塔 API | ★★★★☆ | 5000 点免费 |
| 4 | Sogou + Bing + DDG 三引擎抓取 | ★★★☆☆ | 免费（当前已用） |
| 5 | DDG Instant Answer 直连 | ★★☆☆☆ | 免费 |
| 6 | Wikipedia 中文 | ★★★☆☆ | 免费（知识而非新闻） |

---

*清单版本 2026-06-19 · 共收录 80+ 信息源 · 按 USB-AI 双模式分类适配*
