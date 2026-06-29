# USB-AI 错误日志

> 自动记录 AI 助手运行期间的所有错误和异常
> 格式：时间 | 级别 | 模块 | 错误类型 | 描述 | 修复状态

---

## 日志条目

| # | 时间 | 级别 | 模块 | 类型 | 描述 | 状态 |
|---|------|------|------|------|------|------|
| 0 | 2026-06-19 | INFO | system | init | 错误日志系统初始化 | ✅ |

---

## 问题速查

### 搜索相关
- **搜索返回 0 结果** → 检查服务器状态栏是否为 🖥 服务器 ✓，检查 CMD 窗口是否有网络错误日志
- **"未检索到"** → 联网搜索未开启或搜索无结果，换搜索词重试
- **Bing 被墙** → 开发机网络环境限制，用户机器通常正常

### 服务器相关
- **Ctrl+C 无反应** → 已修复为 ThreadingMixIn 多线程模式
- **启动后浏览器不弹出** → 已修复 `>/dev/null` → `>nul`
- **文件上传截断** → base64 传输已修复

### AI 回答相关
- **AI 说"无法获取实时数据"** → 检查系统提示是否包含搜索结果；关闭搜索时应使用知识模式
- **打字机卡住** → 已修复 requestAnimationFrame → setTimeout
- **JSON 解析错误** → 前端 repairJSON 自动修复

### 代码相关
- **JS 语法错误** → 运行 `node -e "..."` 检查
- **Python 语法错误** → 运行 `python -c "import py_compile; ..."` 检查
| 2026-06-19 13:48:24 | ERROR | search | Bing | name '_UA' is not defined | 待修复 |
| 2026-06-19 13:48:24 | ERROR | search | Sogou | name '_UA' is not defined | 待修复 |
| 2026-06-19 15:19:44 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-19 15:21:26 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-19 15:24:47 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-19 15:25:02 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-19 15:27:07 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-19 15:27:21 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-20 14:05:39 | ERROR | search | DDG | Expecting value: line 1 column 1 (char 0) | 待修复 |
| 2026-06-20 21:58:42 | ERROR | search | DDG | Expecting value: line 1 column 1 (char 0) | 待修复 |
| 2026-06-23 14:27:11 | ERROR | search | Bing | <urlopen error _ssl.c:1107: The handshake operation timed out> | 待修复 |
| 2026-06-23 15:11:19 | ERROR | search | DDG | Expecting value: line 1 column 1 (char 0) | 待修复 |
| 2026-06-23 15:12:19 | ERROR | search | DDG | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-23 15:12:32 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-23 15:12:34 | ERROR | search | DDG | The read operation timed out | 待修复 |
| 2026-06-23 15:16:48 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-23 15:16:53 | ERROR | search | DDG | <urlopen error _ssl.c:1107: The handshake operation timed out> | 待修复 |
| 2026-06-23 15:19:31 | ERROR | search | Bing | The read operation timed out | 待修复 |
| 2026-06-23 22:33:11 | ERROR | search | DDG | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-23 22:33:19 | ERROR | search | Bing | <urlopen error [Errno 2] No such file or directory> | 待修复 |
| 2026-06-28 20:11:32 | ERROR | search | DDG | Non-JSON response: application/x-javascript | 待修复 |
| 2026-06-28 20:15:57 | ERROR | search | DDG | Non-JSON response: application/x-javascript | 待修复 |
