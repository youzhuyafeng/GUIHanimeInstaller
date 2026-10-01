# Hanime Installer

一个带图形界面的Hanime网站视频下载工具。把视频页面 URL 粘贴进去，点击按钮即可下载到指定目录。

除了从源码构建之外，您也可以直接下载打包好的可执行程序：[下载入口](https://github.com/youzhuyafeng/GUIHanimeInstaller/releases/download/v1.0.0/HanimeInstaller.exe)

## 功能

- 图形界面，无需命令行操作
- 输入视频页面 URL，自动解析出真实视频地址
- 保存目录可自定义，默认是**程序所在目录**
- 文件名可自定义；留空则自动命名为 `<标题第一段>_<URL 中 v 参数的值>`
- 实时进度条 + 下载速度 + 日志输出，下载在后台线程执行，界面不会卡死

## 环境要求

- Windows
- Python 3.10 或更高版本（3.9 已被 yt-dlp 标记为 deprecated，仍能跑但不推荐）
- 依赖见 `requirements.txt`：`requests`、`yt-dlp`、`pyinstaller`

## 从 git clone 开始


克隆下来后按下面的步骤走一遍即可使用：

```bash
git clone https://github.com/youzhuyafeng/GUIHanimeInstaller.git
cd GUIHanimeInstaller
pip install -r requirements.txt
```

装完依赖后，两种用法任选其一：

**方式一：直接运行源码**（最快，改代码后立刻生效）

```bash
py hanime_installer.py
```

**方式二：先打包成 exe，再双击运行**

```bash
build.bat
```

打包完成后双击 `dist\HanimeInstaller.exe` 即可，无需再依赖 Python 环境。

## 使用步骤

1. 在 **视频页面 URL** 输入框里粘贴视频页面地址，例如
   `https://www.hanime2.org/watch?v=1`
2. 在 **保存目录** 里确认或修改下载位置（默认已经是程序所在目录，点「浏览…」可以改）
3. 在 **文件名** 里填写想要的名字；**留空就用自动命名**（规则见下）
4. 点击 **开始下载**
5. 下方进度条显示下载进度，日志区显示每一步的详细信息；完成后会提示文件保存路径

## 工作原理

1. **请求页面** — 用 `requests` 带上浏览器请求头请求用户输入的页面 URL，拿到 HTML。
2. **解析 HTML** —
   - 找出 `<head>` 中 `rel="preload"` 且 `as="video"` 的 `<link>` 标签，
     取其 `href` 属性作为真实视频地址（HTML 实体会被还原，如 `&amp;` → `&`）；
   - 找出 `<meta name="title">`，取其 `content` 属性，**以空格分割后取第一部分**。
3. **确定文件名** — 用户填了就用用户的；否则拼成 `<标题第一段>_<URL 中 v 参数>`。
4. **下载视频** — 把视频地址交给 `yt-dlp` 下载，请求头与浏览器抓包保持一致
   （`referer` / `user-agent` 等）。

## 注意事项

- **不需要 cookie。** 解析出来的视频地址是带 `token` / `expires` 签名的 CDN 直链，
  本身即可自证身份，因此程序不发送任何 cookie，也不需要在仓库里存放会话数据。
- **直链有时效。** `expires` 参数过期后该地址即失效，重新点一次「开始下载」
  会重新解析出新的直链。
- 若页面结构变化（`<link>` / `<meta>` 标签改法），解析部分可能需要同步调整。
- 本工具仅用于下载你有权访问的内容，请遵守目标站点的服务条款与当地法律法规。
