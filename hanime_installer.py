# -*- coding: utf-8 -*-
"""Hanime Installer - 一个带图形界面的视频下载器。

用法：把视频页面 URL 粘贴到输入框，点击"开始下载"。
程序会先请求该页面 HTML，解析出 <head> 中 rel="preload" as="video" 的
<link> 标签里的 href（真实视频地址）以及 <meta name="title"> 的 content
（用于命名文件），再交给 yt-dlp 下载。
"""

import html
import os
import queue
import re
import sys
import threading
import tkinter as tk
from html.parser import HTMLParser
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

try:
    import yt_dlp
except ImportError:  # pragma: no cover - 打包后不会走到这里
    yt_dlp = None

APP_NAME = "Hanime Installer"
APP_VERSION = "1.0.0"

DEFAULT_SITE = "https://www.hanime2.org/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
)

# 页面 HTML 的请求头（普通浏览器请求即可）。
PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "user-agent": DEFAULT_USER_AGENT,
}

# 视频请求头，与抓包得到的 curl 保持一致。
# 视频地址是带 token/expires 签名的 CDN 直链，本身即可自证身份，无需携带 cookie。
# referer 会在运行时按目标站点自动补全，因此换镜像站通常不用改代码。
VIDEO_HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "priority": "i",
    "referer": DEFAULT_SITE,
    "sec-ch-ua": '"Chromium";v="154", "Microsoft Edge";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "video",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": DEFAULT_USER_AGENT,
}

# Windows 文件名非法字符
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
# 兜底用的正则，当 HTMLParser 没解析到结果时再试一次
_LINK_RE = re.compile(
    r'<link\b[^>]*\brel=["\']preload["\'][^>]*>', re.IGNORECASE
)
_META_TITLE_RE = re.compile(
    r'<meta\b[^>]*\bname=["\']title["\'][^>]*>', re.IGNORECASE
)
_ATTR_RE = re.compile(r'([\w-]+)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))')


class PageParser(HTMLParser):
    """从页面 HTML 中取出视频地址与标题。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.video_url = None
        self.title = None
        self._in_head = False

    # -- HTMLParser 回调 ---------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self._in_head = True
        elif tag == "link":
            self._handle_link(dict(attrs))
        elif tag == "meta":
            self._handle_meta(dict(attrs))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False

    # -- 解析逻辑 ----------------------------------------------------------
    def _handle_link(self, attrs):
        if self.video_url:
            return
        rel = (attrs.get("rel") or "").lower()
        if "preload" not in rel.split():
            return
        if (attrs.get("as") or "").lower() != "video":
            return
        href = attrs.get("href")
        if href:
            # 只接受 <head> 里的标签；但若整页都没有，保留第一次命中的结果兜底
            if self._in_head or not self.video_url:
                self.video_url = html.unescape(href.strip())

    def _handle_meta(self, attrs):
        if self.title:
            return
        if (attrs.get("name") or "").lower() != "title":
            return
        content = attrs.get("content")
        if content:
            self.title = html.unescape(content.strip())


def parse_page(page_html):
    """解析页面，返回 (video_url, title)。"""
    parser = PageParser()
    parser.feed(page_html)
    parser.close()

    video_url, title = parser.video_url, parser.title

    # HTMLParser 偶尔会因为畸形 HTML 提前中断，这里用正则兜底
    if not video_url:
        for tag in _LINK_RE.findall(page_html):
            attrs = _extract_attrs(tag)
            if "preload" in attrs.get("rel", "").lower().split() \
                    and attrs.get("as", "").lower() == "video":
                video_url = html.unescape(attrs.get("href", "").strip())
                break
    if not title:
        for tag in _META_TITLE_RE.findall(page_html):
            attrs = _extract_attrs(tag)
            if attrs.get("name", "").lower() == "title":
                title = html.unescape(attrs.get("content", "").strip())
                break

    return video_url or None, title or None


def _extract_attrs(tag_text):
    attrs = {}
    for match in _ATTR_RE.finditer(tag_text):
        value = match.group(3) or match.group(4) or match.group(5) or ""
        attrs[match.group(1).lower()] = value
    return attrs


# Windows 保留设备名，不能直接用作文件名
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# 用户手填文件名时，末尾若是这些扩展名就先剥掉，免得存成 abc.mp4.mp4
_MEDIA_EXTS = (".mp4", ".mkv", ".webm", ".flv", ".ts", ".m4v", ".mov", ".avi")


def sanitize_filename(name, fallback="video"):
    """清洗成 Windows 下的合法文件名。"""
    name = _ILLEGAL_CHARS.sub("_", (name or "").strip()).strip(" .")
    if name.upper().split(".")[0] in _RESERVED_NAMES:
        name = "_" + name
    return name or fallback


def title_to_filename(title, fallback="video"):
    """meta title 以空格分割取第一部分，并清洗成合法文件名。"""
    if not title:
        return fallback
    return sanitize_filename(title.split()[0], fallback)


def extract_url_param(url, key):
    """取 URL 查询串中某个参数的值；取不到返回 None。"""
    try:
        values = parse_qs(urlsplit(url or "").query).get(key)
    except ValueError:
        return None
    if not values:
        return None
    return values[0].strip() or None


def build_default_filename(title, page_url, fallback="video"):
    """默认文件名 = 标题第一段 + "_" + 输入 URL 中 v 参数的值。

    URL 里没有 v 参数时就只用标题部分。
    """
    name = title_to_filename(title, fallback)
    v_value = extract_url_param(page_url, "v")
    if v_value:
        safe_v = sanitize_filename(v_value, fallback="")
        if safe_v:
            return f"{name}_{safe_v}"
    return name


def normalize_user_filename(name, fallback="video"):
    """处理用户手填的文件名：清洗非法字符，并剥掉多余的视频扩展名。"""
    cleaned = sanitize_filename(name, fallback)
    for ext in _MEDIA_EXTS:
        if cleaned.lower().endswith(ext) and len(cleaned) > len(ext):
            return sanitize_filename(cleaned[: -len(ext)], fallback)
    return cleaned


def app_dir():
    """程序所在目录（打包成 exe 后即 exe 所在目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def build_video_headers(video_url, page_url):
    """按目标地址补全 referer 等头部信息。

    注意这里不设置 range 头：yt-dlp 自己管理 Range（断点续传时要改写它），
    写死会破坏续传逻辑。
    """
    headers = dict(VIDEO_HEADERS)
    parts = urlsplit(page_url or video_url)
    if parts.scheme and parts.netloc:
        headers["referer"] = f"{parts.scheme}://{parts.netloc}/"
    else:
        headers["referer"] = DEFAULT_SITE
    return headers


def silence_stdio():
    """打包成 windowed exe 后 sys.stdout/stderr 为 None，第三方库写入会崩溃。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
        elif hasattr(stream, "reconfigure"):
            # 控制台可能是 GBK，遇到非 ASCII 直接替换而不是抛异常
            try:
                stream.reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


class InstallerApp:
    def __init__(self, root):
        self.root = root
        self.log_queue = queue.Queue()
        self.worker = None

        root.title(f"{APP_NAME} v{APP_VERSION}")
        root.geometry("680x500")
        root.minsize(600, 440)

        self.url_var = tk.StringVar()
        self.dir_var = tk.StringVar(value=app_dir())
        self.name_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()
        self._poll_log_queue()

    # -- 界面 --------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="视频页面 URL：").grid(row=0, column=0, sticky="w", **pad)
        url_entry = ttk.Entry(frame, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", **pad)
        url_entry.focus_set()

        ttk.Label(frame, text="保存目录：").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.dir_var).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="浏览…", command=self._choose_dir).grid(row=1, column=2, sticky="e", **pad)

        ttk.Label(frame, text="文件名：").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.name_var).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)
        ttk.Label(
            frame,
            text="留空则自动命名为：<标题第一段>_<URL 中 v 参数的值>（无 v 参数时只用标题）",
            foreground="#666666",
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=10)

        self.download_btn = ttk.Button(frame, text="开始下载", command=self._start_download)
        self.download_btn.grid(row=4, column=1, sticky="w", **pad)

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)

        ttk.Label(frame, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(frame, text="日志：").grid(row=7, column=0, sticky="nw", **pad)
        self.log_text = tk.Text(frame, height=10, wrap="word", state="disabled")
        self.log_text.grid(row=7, column=1, columnspan=2, sticky="nsew", **pad)

        scroll = ttk.Scrollbar(frame, command=self.log_text.yview)
        scroll.grid(row=7, column=3, sticky="ns", pady=6)
        self.log_text.configure(yscrollcommand=scroll.set)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(7, weight=1)

    def _choose_dir(self):
        current = self.dir_var.get() or app_dir()
        chosen = filedialog.askdirectory(initialdir=current, title="选择保存目录")
        if chosen:
            self.dir_var.set(os.path.normpath(chosen))

    # -- 日志 --------------------------------------------------------------
    def log(self, message):
        self.log_queue.put(message)

    def _poll_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_log_queue)

    def _set_progress(self, percent):
        self.progress["value"] = max(0.0, min(100.0, percent))

    # -- 下载流程 ----------------------------------------------------------
    def _start_download(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "已有下载任务正在进行。")
            return

        page_url = self.url_var.get().strip()
        if not page_url:
            messagebox.showwarning(APP_NAME, "请先输入视频页面 URL。")
            return
        if not re.match(r"^https?://", page_url, re.IGNORECASE):
            page_url = "https://" + page_url

        out_dir = self.dir_var.get().strip() or app_dir()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"无法创建保存目录：\n{exc}")
            return

        # 文件名留空 -> 用「标题第一段_v参数」自动命名（需要先解析页面）
        custom_name = self.name_var.get().strip()

        if yt_dlp is None:
            messagebox.showerror(APP_NAME, "缺少 yt-dlp 依赖，请先执行：pip install yt-dlp")
            return

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._set_progress(0)
        self.status_var.set("正在分析页面…")
        self.download_btn.configure(state="disabled")

        self.worker = threading.Thread(
            target=self._download_worker, args=(page_url, out_dir, custom_name), daemon=True
        )
        self.worker.start()

    def _download_worker(self, page_url, out_dir, custom_name=""):
        try:
            self.log(f"[1/3] 请求页面：{page_url}")
            response = requests.get(page_url, headers=PAGE_HEADERS, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            self.log(f"      页面返回 {response.status_code}，共 {len(response.text)} 字符")

            self.log("[2/3] 解析 <link rel=\"preload\" as=\"video\"> 与 <meta name=\"title\">")
            video_url, title = parse_page(response.text)
            if not video_url:
                self._fail("未能从页面中找到 rel=\"preload\" as=\"video\" 的 <link> 标签。")
                return
            video_url = urljoin(page_url, video_url)

            if custom_name:
                filename = normalize_user_filename(custom_name)
                self.log(f"      文件名   ：{filename}（用户指定）")
            else:
                v_value = extract_url_param(page_url, "v")
                filename = build_default_filename(title, page_url)
                source = f"标题「{title.split()[0]}」" if title else "默认名"
                if v_value:
                    source += f" + v={v_value}"
                self.log(f"      文件名   ：{filename}（自动：{source}）")

            self.log(f"      视频地址：{video_url}")
            self.log(f"      标题     ：{title or '(未找到)'}")

            self.log("[3/3] 调用 yt-dlp 开始下载…")
            self._run_ytdlp(video_url, filename, out_dir, page_url)

        except requests.RequestException as exc:
            self._fail(f"请求页面失败：{exc}")
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程静默崩溃
            self._fail(f"发生未预期的错误：{exc}")

    def _run_ytdlp(self, video_url, filename, out_dir, page_url):
        def hook(status):
            if status.get("status") == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate")
                done = status.get("downloaded_bytes") or 0
                speed = status.get("speed")
                if total:
                    self._set_progress(done * 100.0 / total)
                text = f"      下载中 {status.get('_percent_str', '').strip()}"
                if speed:
                    text += f"  速度 {speed / 1024 / 1024:.2f} MB/s"
                self.status_var.set(text.strip())
            elif status.get("status") == "finished":
                self._set_progress(100)
                self.log("      下载完成，正在收尾…")

        ydl_opts = {
            "outtmpl": os.path.join(out_dir, f"{filename}.%(ext)s"),
            "http_headers": build_video_headers(video_url, page_url),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "continuedl": True,
            "retries": 5,
            "fragment_retries": 5,
            "progress_hooks": [hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            path = ydl.prepare_filename(info) if info else None

        if path and not os.path.exists(path):
            # yt-dlp 可能会因为容器/编码改写扩展名
            base, _ = os.path.splitext(path)
            for ext in (".mp4", ".mkv", ".webm", ".flv", ".ts"):
                if os.path.exists(base + ext):
                    path = base + ext
                    break

        self.log(f"[完成] 已保存到：{path or os.path.join(out_dir, filename)}")
        self._done("下载完成")

    # -- 状态收尾 ----------------------------------------------------------
    def _fail(self, message):
        self.log(f"[失败] {message}")
        self._done("下载失败")
        self.root.after(0, lambda: messagebox.showerror(APP_NAME, message))

    def _done(self, status):
        self.status_var.set(status)
        self.root.after(0, lambda: self.download_btn.configure(state="normal"))


def main():
    silence_stdio()
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
