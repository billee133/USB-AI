============================================
  runtime/ — 便携运行环境
============================================

此目录用于存放U盘自带的便携运行环境。
部署后可在任何Windows电脑上零依赖启动。


📦 包含内容
-----------

  python/              便携Python 3.12 嵌入式版
    └── python.exe      (~30MB解压后)
                        无需安装、无需管理员权限
                        由 setup_runtime.bat 自动下载部署


🚀 部署方法
-----------

【方法一：自动部署（推荐）】
  在主电脑上运行:
    setup_runtime.bat
  → 选择 "1. 在线下载"
  → 自动下载 Python 嵌入版并解压到此处

【方法二：手动部署】
  1. 访问 https://www.python.org/downloads/windows/
  2. 下载 "Windows embeddable package (64-bit)"
  3. 将 zip 文件解压到此目录的 python\ 子目录
  4. 确认存在: runtime\python\python.exe


⚙ 工作原理
-----------

  启动服务器模式.bat 的检测顺序:
    1. PowerShell 5+  → Windows 10/11 已内置
    2. 系统 Python    → 如果电脑已安装
    3. 便携 Python    → U盘自带 (本目录)
    4. 降级          → 浏览器直连模式

  便携Python只需部署一次，之后插任何电脑都能用。


📏 空间占用
-----------

  下载的 zip 文件:    ~8 MB
  解压后 python\:    ~30 MB
  部署后自动删除 zip，净占用 ~30 MB


⚠ 注意事项
-----------

  - 嵌入式Python仅包含标准库（server.py够用）
  - 不需要管理员权限，不需要写注册表
  - 不会与系统已有的Python冲突
  - 完全绿色，U盘拔出后不留痕迹
