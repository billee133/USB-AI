# Learning.md — 经验教训

> USB-AI v4.2 开发复盘

## Bug 复盘

1. **LOCAL_TOKEN 多次声明** — 注入逻辑用追加而非替换。教训：占位符替换 > 追加。
2. **role==='ai' vs 'assistant'** — 实时流用 'ai'，CM 存储用 'assistant'。教训：统一角色常量。
3. **JS 字符串真实换行** — Python 替换遗留 \n。教训：写入 JS 后必须 node --check。
4. **\b 对中文无效** — Python/JS 中 \b 匹配 \w/\W 边界。教训：中文用直接字符匹配。
5. **concurrent.futures 子线程不可见** — 需在函数内部再次 import。
6. **closeToolCard 只清引用不删 DOM** — UI 状态变更必须同步 DOM 操作。
7. **renderChats 过滤 AUTO_CHAT_ID** — 区分"临时恢复缓存"和"历史记录"。
8. **doSend 无 try/finally** — busy 标志永久卡死。教训：async 函数必须 try/finally 兜底。
9. **direct_sources 设而不用** — 写了 URL dict 但从未读取。教训：写完赋值立即确认消费端。
10. **打字机每帧全量渲染** — 30ms 全量 marked+KaTeX+hljs。教训：流式纯文本，渲染跑一次。
11. **newConversation 不更新 autosave** — 刷新跳回旧记录。教训：状态变更同步所有存储键。
12. **ThreadPoolExecutor with 阻塞** — exit 时 wait=True 强制等慢搜索。教训：RAG 用 shutdown(wait=False)。
13. **直达数据走 fetch_page_content** — API URL 当网页抓，数据丢失。教训：直达引擎跳过网页抓取。
14. **金银同 URL 被去重** — fetched_urls set 去重吞掉银价。教训：直达引擎不应检查 URL 重复。
15. **query 变量未初始化** — 彩票分支跳过后赋值，_send_json 崩溃 500。
16. **GBK 终端编码** — •(U+2022) 不在 GBK 中，Windows print 崩溃。教训：ASCII-safe 字符。

## 反直觉结论

- Bing 对中文复合词拆分严重，"快乐8"→"快"+"乐"，返回词典而非彩票
- \b\d+\b 在 Python 3 Unicode 模式下不匹配中文旁边的数字（中文是 \w）
- setInterval 比 requestAnimationFrame 更适合打字机（rAF 切后台不触发）
- marked.js CDN 失败了不会报错，typeof marked 为 undefined
- AI 模型说"我无法联网"不等于真没联网——它根本不知道 RAG 已经执行了搜索
- 免费 API（GoldAPI/Binance/OpenER）的数据质量远高于搜索引擎返回的网页抓取
- ThreadPoolExecutor 的 with 语句在 Python 中默认 wait=True，会悄悄阻塞
