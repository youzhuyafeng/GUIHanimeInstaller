# Hanime Installer

一个带图形界面的视频下载工具。把视频页面 URL 粘贴进去，点击按钮即可下载到指定目录。

## 功能

- 图形界面（tkinter），无需命令行操作
- 输入视频页面 URL，自动解析出真实视频地址
- 保存目录可自定义，默认是**程序所在目录**
- 实时进度条 + 下载速度 + 日志输出，下载在后台线程执行，界面不会卡死
- 可打包成单文件 `.exe`，双击即可运行

## 环境要求

- Windows
- Python 3.10 或更高版本（3.9 已被 yt-dlp 标记为 deprecated，仍可运行但不推荐）
- 依赖见 `requirements.txt`：`requests`、`yt-dlp`、`pyinstaller`

```bash
pip install -r requirements.txt
```

## 使用方法

### 方式一：直接使用打包好的程序

双击 `dist\HanimeInstaller.exe` 即可打开界面（无需安装 Python）。

### 方式二：从源码运行

```bash
python hanime_installer.py
```

### 操作步骤

1. 在 **视频页面 URL** 输入框里粘贴视频页面地址，例如
   `https://www.hanime2.org/video/xxxx/`
2. 在 **保存目录** 里确认或修改下载位置（默认已经是程序所在目录，点「浏览…」可以改）
3. 点击 **开始下载**
4. 下方进度条显示下载进度，日志区显示每一步的详细信息；完成后会提示文件保存路径

## 打包成可执行程序

在项目目录下双击运行 `build.bat`，或在命令行执行：

```bash
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name HanimeInstaller --collect-all yt_dlp hanime_installer.py
```

产物位于 `dist\HanimeInstaller.exe`，是一个单文件免安装程序。

> `--windowed` 表示不弹出黑色控制台窗口；`--collect-all yt_dlp` 确保 yt-dlp 的
> 提取器与数据文件都被打包进去。

## 工作原理

1. **请求页面** — 用 `requests` 带上浏览器请求头请求用户输入的页面 URL，拿到 HTML。
   同时读取程序目录下的 `hanime_cookies.txt`（若存在）。
2. **解析 HTML** —
   - 找出 `<head>` 中 `rel="preload"` 且 `as="video"` 的 `<link>` 标签，
     取其 `href` 属性作为真实视频地址（HTML 实体会被还原，如 `&amp;` → `&`）；
   - 找出 `<meta name="title">`，取其 `content` 属性，**以空格分割后取第一部分**作为文件名。
3. **下载视频** — 把视频地址交给 `yt-dlp` 下载，请求头与浏览器抓包保持一致
   （`referer` / `user-agent` 等，cookie 以 Netscape 格式的 cookiefile 交给 yt-dlp 管理）。

解析优先使用标准库 `html.parser`，并额外用正则做了一层兜底，防止畸形 HTML 导致解析中断。

## 注意事项

- **Cookie 放在外部文件里。** 程序启动下载时会读取**程序同目录**下的
  `hanime_cookies.txt`（exe 打包后就是 exe 所在目录）。把浏览器 DevTools →
  Network → 任意请求 → Request Headers 里的 `cookie:` 那一整行值粘贴进去即可，
  形如 `a=1; b=2; c=3`，一行写完、可换行。
  该文件已加入 `.gitignore`，**不会被提交到仓库**，请勿把真实 cookie 写进源码。
  如果这个文件不存在，程序会不带 cookie 下载并提示，此时部分视频可能返回 403。
- **Cookie 会过期。** 会话数据失效后需要重新从浏览器复制一份，覆盖
  `hanime_cookies.txt` 的内容。
- **`referer` 按站点自动补全。** 程序会用页面 URL 的 `scheme://host/` 作为 `referer`，
  因此换用镜像站时通常无需改代码。
- **`range` 请求头没有硬编码。** yt-dlp 会自己管理 `Range` 头（断点续传时需要改写它），
  手动写死反而会破坏续传逻辑。
- 若页面结构变化（`<link>` / `<meta>` 标签改法），解析部分可能需要同步调整。
- 本工具仅用于下载你有权访问的内容，请遵守目标站点的服务条款与当地法律法规。
