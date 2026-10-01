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
- Python 3.10 或更高版本（3.9 已被 yt-dlp 标记为 deprecated，仍能跑但不推荐）
- 依赖见 `requirements.txt`：`requests`、`yt-dlp`、`pyinstaller`

## 从 git clone 开始

仓库里**只有源码，没有 exe**（`dist/` 已被 `.gitignore` 排除）。
克隆下来后按下面的步骤走一遍即可使用：

```bash
git clone https://github.com/youzhuyafeng/GUIHanimeInstaller.git
cd GUIHanimeInstaller
pip install -r requirements.txt
```

装完依赖后，两种用法任选其一：

**方式一：直接运行源码**（最快，改代码后立刻生效）

```bash
py -3 hanime_installer.py
```

> 用 `py -3` 而不是 `python`，是因为部分机器上默认的 `python` 是 3.9。

**方式二：先打包成 exe，再双击运行**（给不想装 Python 的人用）

```bash
build.bat
```

打包完成后双击 `dist\HanimeInstaller.exe` 即可，无需再依赖 Python 环境。

## 使用步骤

1. 在 **视频页面 URL** 输入框里粘贴视频页面地址，例如
   `https://www.hanime2.org/video/xxxx/`
2. 在 **保存目录** 里确认或修改下载位置（默认已经是程序所在目录，点「浏览…」可以改）
3. 点击 **开始下载**
4. 下方进度条显示下载进度，日志区显示每一步的详细信息；完成后会提示文件保存路径

## 打包成可执行程序

直接双击运行 `build.bat`，它会自动挑选可用的 Python 解释器、安装依赖并调用 PyInstaller。
等价的手工命令是：

```bash
py -3 -m PyInstaller --noconfirm --onefile --windowed ^
    --name HanimeInstaller --collect-all yt_dlp hanime_installer.py
```

产物位于 `dist\HanimeInstaller.exe`，是一个单文件免安装程序（约 25 MB）。

> `--windowed` 表示不弹出黑色控制台窗口；`--collect-all yt_dlp` 确保 yt-dlp 的
> 提取器与数据文件都被打包进去。

## 工作原理

1. **请求页面** — 用 `requests` 带上浏览器请求头请求用户输入的页面 URL，拿到 HTML。
2. **解析 HTML** —
   - 找出 `<head>` 中 `rel="preload"` 且 `as="video"` 的 `<link>` 标签，
     取其 `href` 属性作为真实视频地址（HTML 实体会被还原，如 `&amp;` → `&`）；
   - 找出 `<meta name="title">`，取其 `content` 属性，**以空格分割后取第一部分**作为文件名。
3. **下载视频** — 把视频地址交给 `yt-dlp` 下载，请求头与浏览器抓包保持一致
   （`referer` / `user-agent` 等）。

解析优先使用标准库 `html.parser`，并额外用正则做了一层兜底，防止畸形 HTML 导致解析中断。

## 注意事项

- **不需要 cookie。** 解析出来的视频地址是带 `token` / `expires` 签名的 CDN 直链，
  本身即可自证身份，因此程序不发送任何 cookie，也不需要在仓库里存放会话数据。
- **`referer` 按站点自动补全。** 程序会用页面 URL 的 `scheme://host/` 作为 `referer`，
  因此换用镜像站时通常无需改代码。
- **`range` 请求头没有硬编码。** yt-dlp 会自己管理 `Range` 头（断点续传时需要改写它），
  手动写死反而会破坏续传逻辑。
- **直链有时效。** `expires` 参数过期后该地址即失效，重新点一次「开始下载」
  会重新解析出新的直链。
- 若页面结构变化（`<link>` / `<meta>` 标签改法），解析部分可能需要同步调整。
- 本工具仅用于下载你有权访问的内容，请遵守目标站点的服务条款与当地法律法规。
