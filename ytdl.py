#!/usr/bin/env python3
"""
Matrix Media Toolkit - YTB-DL - Phiên bản nâng cấp tối ưu tốc độ tải và đa luồng
Tích hợp aria2c, bypass throttling và tải song song hàng loạt.

Usage:
    python ytdl.py [YOUTUBE_URL_OR_TXT_FILE] [OPTIONS]
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional
import zipfile
import urllib.request
import shutil
import concurrent.futures
import threading
import time

# Cấu hình UTF-8 cho Windows để tránh lỗi UnicodeEncodeError khi in tiếng Việt
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import questionary
from questionary import Style
import yt_dlp

# Cấu hình phong cách giao diện questionary
CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("separator", "fg:gray"),
        ("instruction", "fg:gray"),
    ]
)

# Các hằng số cấu hình mặc định
DEFAULT_OUTPUT_DIR = "./downloads"
DEFAULT_VIDEO_FORMAT = "bestvideo*+bestaudio/best"
DEFAULT_SINGLE_TEMPLATE = "%(title)s.%(ext)s"
DEFAULT_PLAYLIST_TEMPLATE = "%(playlist)s/%(playlist_index)03d - %(title)s.%(ext)s"

# Mẫu tên tệp cấu hình sẵn
NAMING_TEMPLATES = {
    "default": {
        "single": DEFAULT_SINGLE_TEMPLATE,
        "playlist": DEFAULT_PLAYLIST_TEMPLATE,
        "description": "Mặc định (Tên video)",
    },
    "rich_metadata": {
        "single": "%(upload_date)s - %(channel)s - %(title)s.%(ext)s",
        "playlist": "%(playlist)s/%(playlist_index)03d - %(upload_date)s - %(channel)s - %(title)s.%(ext)s",
        "description": "Đầy đủ thông tin (Ngày - Kênh - Tên)",
    },
    "minimalist": {
        "single": "%(id)s.%(ext)s",
        "playlist": "%(playlist)s/%(playlist_index)03d - %(id)s.%(ext)s",
        "description": "Tối giản (Chỉ ID video)",
    },
}

# Khóa luồng và danh sách theo dõi tiến trình
print_lock = threading.Lock()
active_downloads = {}
active_downloads_lock = threading.Lock()


def safe_print(*args, **kwargs):
    """Hàm in an toàn trong môi trường đa luồng."""
    with print_lock:
        print(*args, **kwargs)


def setup_binaries() -> None:
    """Kiểm tra và tự động cấu hình aria2c cho môi trường Windows nếu thiếu."""
    # Kiểm tra xem hệ thống đã có aria2c chưa
    if shutil.which("aria2c"):
        return

    # Kiểm tra trong thư mục bin cục bộ
    local_bin = Path(__file__).parent / "bin"
    local_bin.mkdir(exist_ok=True)
    
    aria2c_exe = local_bin / "aria2c.exe"
    if aria2c_exe.exists():
        os.environ["PATH"] = str(local_bin) + os.pathsep + os.environ["PATH"]
        return

    if sys.platform != "win32":
        safe_print("\n  [CẢNH BÁO] Không tìm thấy 'aria2c' trong hệ thống.")
        safe_print("  Để tối ưu tốc độ tải, hãy cài đặt aria2c thông qua brew hoặc apt.")
        return

    safe_print("\n" + "=" * 60)
    safe_print("  Tự động tải công cụ tăng tốc aria2c cho Windows...")
    safe_print("=" * 60)

    url = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
    zip_path = local_bin / "aria2.zip"

    try:
        safe_print("  Đang tải file zip từ GitHub...")
        urllib.request.urlretrieve(url, zip_path)
        
        safe_print("  Đang giải nén aria2c.exe...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith("aria2c.exe"):
                    data = zip_ref.read(member)
                    aria2c_exe.write_bytes(data)
                    break
        
        if zip_path.exists():
            zip_path.unlink()
            
        safe_print("  Tải thành công aria2c!")
        os.environ["PATH"] = str(local_bin) + os.pathsep + os.environ["PATH"]
        safe_print("=" * 60 + "\n")
    except Exception as e:
        safe_print(f"  [LỖI] Không thể tải tự động aria2c: {e}")
        safe_print("  Chương trình sẽ tiếp tục chạy bằng trình tải mặc định của yt-dlp.")


def check_and_update_ytdlp() -> None:
    """Tự động kiểm tra và nâng cấp thư viện yt-dlp để vượt qua bóp băng thông mới nhất."""
    safe_print("  Đang kiểm tra và cập nhật yt-dlp lên bản mới nhất để tránh bị lỗi...")
    try:
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        safe_print("  Cập nhật yt-dlp hoàn tất!")
    except Exception as e:
        safe_print(f"  Bỏ qua cập nhật tự động (hoặc không có mạng/quyền): {e}")


class DownloadConfig:
    """Lớp lưu trữ cấu hình tải xuống."""

    def __init__(self):
        self.url: str = ""
        self.is_playlist: bool = False
        self.output_dir: str = DEFAULT_OUTPUT_DIR
        self.format: str = DEFAULT_VIDEO_FORMAT
        self.naming_template: str = DEFAULT_SINGLE_TEMPLATE
        self.audio_only: bool = False
        self.embed_thumbnail: bool = False
        self.embed_subs: bool = False
        self.add_metadata: bool = False
        self.sponsorblock: bool = False
        self.proxy: Optional[str] = None
        self.geo_bypass: bool = True
        
        # Thêm biến lưu file cookies.txt
        self.cookies: Optional[str] = None
        self.cookies_from_browser: Optional[str] = None
        
        # Các thông số tối ưu tốc độ
        self.use_aria2c: bool = True
        self.max_connections: int = 16
        self.concurrent_downloads: int = 3
        self.bypass_throttling: bool = True

    def get_output_template(self) -> str:
        """Lấy mẫu đường dẫn tệp đầu ra đầy đủ."""
        return str(Path(self.output_dir) / self.naming_template)

    def to_yt_dlp_opts(self) -> dict[str, Any]:
        """Chuyển đổi cấu hình sang các tham số cho yt-dlp."""
        opts = {
            "format": self.format,
            "outtmpl": self.get_output_template(),
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            "ignoreerrors": True,
            "no_warnings": False,
            "quiet": True,  # Ẩn bớt log mặc định để giao diện gọn gàng
            "nokeepalive": False,
        }

        # Thiết lập tránh bóp băng thông (Bypass Throttling)
        if self.bypass_throttling:
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "web"],
                    "skip": ["dash", "hls"]
                }
            }
            opts["socket_timeout"] = 30
            opts["retries"] = 10

        # Tích hợp công cụ tăng tốc aria2c
        if self.use_aria2c and shutil.which("aria2c"):
            opts["external_downloader"] = "aria2c"
            opts["external_downloader_args"] = {
                "default": [
                    f"--max-connection-per-server={self.max_connections}",
                    f"--split={self.max_connections}",
                    "--min-split-size=1M",
                    "--summary-interval=1"
                ]
            }

        postprocessors = []

        if self.audio_only:
            opts["format"] = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",  # Tối ưu hóa chất lượng audio 320kbps
                }
            )

        if self.embed_thumbnail:
            opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail"})

        if self.embed_subs:
            opts["writesubtitles"] = True
            opts["subtitleslangs"] = ["en", "vi"]
            opts["embedsubtitles"] = True
            postprocessors.append(
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                }
            )
            postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        if self.add_metadata:
            postprocessors.append({"key": "FFmpegMetadata"})

        if self.sponsorblock:
            opts["sponsorblock_remove"] = ["all"]
            postprocessors.append(
                {
                    "key": "SponsorBlock",
                    "categories": ["all"],
                }
            )
            postprocessors.append(
                {
                    "key": "ModifyChapters",
                    "remove_sponsor_segments": ["all"],
                }
            )

        if self.proxy:
            opts["proxy"] = self.proxy

        if self.geo_bypass:
            opts["geo_bypass"] = True

        if self.cookies:
            opts["cookiefile"] = self.cookies

        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)

        if postprocessors:
            opts["postprocessors"] = postprocessors

        return opts


def progress_hook(d: dict[str, Any]) -> None:
    """Theo dõi tiến trình tải để hiển thị trực quan thông tin tốc độ và trạng thái."""
    video_id = d.get("info_dict", {}).get("id") or "Unknown"
    title = d.get("info_dict", {}).get("title") or "Unknown Video"
    
    # Rút ngắn tiêu đề để tránh vỡ dòng CLI
    display_title = title[:30] + "..." if len(title) > 33 else title

    if d["status"] == "downloading":
        percent = d.get("_percent_str", "").strip()
        # Tính toán phần trăm thủ công nếu _percent_str bị trống hoặc N/A
        if not percent or percent == "N/A" or "%" not in percent:
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total > 0:
                percent = f"{(downloaded / total) * 100:.1f}%"
            else:
                percent = "0.0%"
        else:
            percent = percent.strip()

        speed = d.get("_speed_str", "N/A").strip()
        eta = d.get("_eta_str", "N/A").strip()
        
        with active_downloads_lock:
            # Xác định xem có đang ở chế độ tải đa luồng hay không
            is_multi = len(active_downloads) > 1
            active_downloads[video_id] = percent
            
        if is_multi:
            # Chế độ tải song song: Giảm tần suất in log để tránh nhấp nháy màn hình
            try:
                pct_val = float(percent.replace("%", "").strip())
            except ValueError:
                pct_val = 0.0
                
            last_pct_attr = f"_last_pct_{video_id}"
            last_printed = getattr(progress_hook, last_pct_attr, -5.0)
            
            # Chỉ in ra khi tăng 5% hoặc hoàn tất
            if pct_val - last_printed >= 5.0 or pct_val >= 99.9:
                setattr(progress_hook, last_pct_attr, pct_val)
                safe_print(f"  [Tải song song] {display_title}: {percent} | Tốc độ: {speed} | Còn lại: {eta}")
        else:
            # Chế độ tải đơn luồng: In đè cùng dòng (\r) mượt mà
            filename = d.get("filename", "Unknown")
            display_name = Path(filename).name
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            with print_lock:
                print(
                    f"\r  Đang tải: {percent} | Tốc độ: {speed} | Còn lại: {eta} | {display_name}",
                    end="",
                    flush=True,
                )

    elif d["status"] == "finished":
        with active_downloads_lock:
            active_downloads.pop(video_id, None)
        safe_print(f"\n  [Hoàn thành] Đã tải xong: {title}")

    elif d["status"] == "error":
        with active_downloads_lock:
            active_downloads.pop(video_id, None)
        safe_print(f"\n  [LỖI] Lỗi xảy ra khi tải video: {title}")


def postprocessor_hook(d: dict[str, Any]) -> None:
    """Theo dõi tiến trình hậu kỳ (gộp file, chuyển định dạng)."""
    if d["status"] == "started":
        pp_name = d.get("postprocessor", "Unknown")
        safe_print(f"  [Hậu kỳ] Đang thực hiện xử lý: {pp_name}...")
    elif d["status"] == "finished":
        safe_print(f"  [Hậu kỳ] Hoàn thành xử lý hậu kỳ.")


def validate_youtube_url(url: str) -> bool:
    """Kiểm tra URL đầu vào có phải là link YouTube hợp lệ không."""
    youtube_patterns = [
        r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^https?://(www\.)?youtube\.com/playlist\?list=[\w-]+",
        r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
        r"^https?://(www\.)?youtube\.com/@[\w-]+",
        r"^https?://(www\.)?youtube\.com/channel/[\w-]+",
        r"^https?://(www\.)?youtube\.com/c/[\w-]+",
        r"^https?://youtu\.be/[\w-]+",
        r"^https?://music\.youtube\.com/",
    ]

    for pattern in youtube_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    return False


def clean_youtube_url(url: str) -> str:
    """
    Nếu URL là liên kết xem video 'watch?v=' hoặc 'youtu.be/' nhưng có kèm tham số list/mix,
    ta sẽ cắt bỏ tham số list để tránh tải nhầm cả danh sách phát.
    """
    if "watch?v=" in url:
        match = re.search(r"v=([^&]+)", url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
    elif "youtu.be/" in url:
        if "?" in url:
            url = url.split("?")[0]
    return url


def is_txt_file(path_str: str) -> bool:
    """Kiểm tra đường dẫn đầu vào có phải là tệp văn bản .txt hợp lệ hay không."""
    try:
        path = Path(path_str)
        return path.exists() and path.is_file() and path.suffix.lower() == ".txt"
    except Exception:
        return False


def detect_playlist(url: str, cookies_from_browser: Optional[str] = None, cookiefile: Optional[str] = None) -> tuple[bool, Optional[dict]]:
    """Phân tích URL để xem có phải danh sách phát (playlist) hay video đơn."""
    url = clean_youtube_url(url)
    safe_print("\n  Đang phân tích URL...")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                return False, None

            is_playlist = info.get("_type") == "playlist" or "entries" in info

            if is_playlist:
                entry_count = len(info.get("entries", []))
                playlist_title = info.get("title", "Danh sách không rõ")
                safe_print(
                    f"  Phát hiện: Playlist - '{playlist_title}' ({entry_count} videos)"
                )
            else:
                video_title = info.get("title", "Video không rõ")
                safe_print(f"  Phát hiện: Video đơn lẻ - '{video_title}'")

            return is_playlist, info

    except yt_dlp.utils.DownloadError as e:
        safe_print(f"  Lỗi phân tích URL: {e}")
        return False, None


def list_formats(url: str) -> None:
    """Liệt kê toàn bộ định dạng video sẵn có."""
    safe_print("\n  Đang lấy danh sách định dạng từ máy chủ...\n")

    ydl_opts = {
        "listformats": True,
        "quiet": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        safe_print(f"\n  Lỗi lấy danh sách định dạng: {e}")


def execute_download_core(config: DownloadConfig) -> bool:
    """Nhân lõi thực hiện tải video sử dụng cấu hình thiết lập."""
    config.url = clean_youtube_url(config.url)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        opts = config.to_yt_dlp_opts()
        opts["ignoreerrors"] = False  # Đảm bảo quăng ngoại lệ hoặc trả mã lỗi chính xác để theo dõi
        with yt_dlp.YoutubeDL(opts) as ydl:
            exit_code = ydl.download([config.url])
            return exit_code == 0
    except yt_dlp.utils.DownloadError as e:
        safe_print(f"  [LỖI TẢI XUỐNG] {e}")
        return False
    except Exception as e:
        safe_print(f"  [LỖI CHƯƠNG TRÌNH] {e}")
        return False


def execute_download(config: DownloadConfig, urls_list: list[str] = None) -> bool:
    """Khởi tạo và thực hiện tải video kèm thông báo trạng thái/banner đầy đủ."""
    if urls_list and len(urls_list) > 1:
        # Nếu có danh sách link, tiến hành tải song song đa luồng
        download_multiple_urls(urls_list, config)
        return True
    else:
        # Tải video đơn lẻ
        if urls_list:
            config.url = urls_list[0]
            config.is_playlist = False
            config.naming_template = DEFAULT_SINGLE_TEMPLATE
            
        print(f"\n{'='*60}")
        print("  Bắt đầu tải xuống")
        print(f"{'='*60}")
        print(f"  URL: {config.url}")
        print(f"  Thư mục lưu: {config.output_dir}")
        print(f"  Định dạng: {'Chỉ trích xuất MP3 (320kbps)' if config.audio_only else config.format}")
        print(f"  Mẫu tên file: {config.naming_template}")
        print(f"  Bộ tăng tốc aria2c: {'KÍCH HOẠT (16 kết nối/luồng)' if config.use_aria2c and shutil.which('aria2c') else 'Không dùng'}")
        
        options_list = []
        if config.embed_thumbnail:
            options_list.append("Nhúng ảnh thu nhỏ")
        if config.embed_subs:
            options_list.append("Nhúng phụ đề")
        if config.add_metadata:
            options_list.append("Thêm Metadata")
        if config.sponsorblock:
            options_list.append("SponsorBlock (Xóa QC)")
        if config.geo_bypass:
            options_list.append("Geo-Bypass")
        if config.proxy:
            options_list.append(f"Proxy: {config.proxy}")

        if options_list:
            print(f"  Tùy chọn phụ: {', '.join(options_list)}")

        print(f"{'='*60}\n")

        start_time = time.time()
        try:
            success = execute_download_core(config)
            duration = time.time() - start_time
            if success:
                print(f"\n{'='*60}")
                print(f"  Tải hoàn tất thành công! (Thời gian: {duration:.1f} giây)")
                print(f"{'='*60}\n")
            return success
        except KeyboardInterrupt:
            print("\n\n  Hủy tải xuống bởi người dùng.")
            return False
        except Exception as e:
            print(f"\n  Lỗi hệ thống: {e}")
            return False


def download_multiple_urls(urls: list[str], base_config: DownloadConfig) -> None:
    """Tải song song hàng loạt link video bằng PoolExecutor."""
    total_urls = len(urls)
    safe_print(f"\n{'='*60}")
    safe_print(f"  Bắt đầu tải song song đồng thời ({total_urls} videos)")
    safe_print(f"  Số luồng tối đa hoạt động: {base_config.concurrent_downloads}")
    safe_print(f"  Tăng tốc mỗi luồng bằng aria2c (16 kết nối): {'Có' if base_config.use_aria2c and shutil.which('aria2c') else 'Không'}")
    safe_print(f"{'='*60}\n")

    # Điền giả định ban đầu để kích hoạt log hiển thị kiểu đa luồng
    with active_downloads_lock:
        for idx, url in enumerate(urls):
            active_downloads[f"init_{idx}"] = "0.0%"

    def worker(url: str, index: int):
        config = DownloadConfig()
        config.url = clean_youtube_url(url)
        config.is_playlist = False
        config.output_dir = base_config.output_dir
        config.format = base_config.format
        config.naming_template = base_config.naming_template
        config.audio_only = base_config.audio_only
        config.embed_thumbnail = base_config.embed_thumbnail
        config.embed_subs = base_config.embed_subs
        config.add_metadata = base_config.add_metadata
        config.sponsorblock = base_config.sponsorblock
        config.proxy = base_config.proxy
        config.geo_bypass = base_config.geo_bypass
        config.use_aria2c = base_config.use_aria2c
        config.max_connections = base_config.max_connections
        config.bypass_throttling = base_config.bypass_throttling
        config.cookies = base_config.cookies
        config.cookies_from_browser = base_config.cookies_from_browser
        
        # Định dạng thứ tự cho danh sách phát nếu có mẫu số thứ tự
        if base_config.is_playlist:
            config.naming_template = base_config.naming_template.replace("%(playlist_index)03d", f"{index:03d}")
            config.naming_template = config.naming_template.replace("%(playlist_index)s", str(index))
        
        with active_downloads_lock:
            active_downloads.pop(f"init_{index-1}", None)

        try:
            success = execute_download_core(config)
            return success
        except Exception as e:
            safe_print(f"  [LỖI] Luồng {index} gặp sự cố: {e}")
            return False

    start_time = time.time()
    success_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=base_config.concurrent_downloads) as executor:
        futures = {executor.submit(worker, url, idx + 1): url for idx, url in enumerate(urls)}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
            except Exception as e:
                safe_print(f"  [LỖI LUỒNG] Lỗi ngoại lệ xảy ra trên link {url}: {e}")

    with active_downloads_lock:
        active_downloads.clear()

    end_time = time.time()
    duration = end_time - start_time
    
    safe_print(f"\n{'='*60}")
    safe_print(f"  Hoàn tất tiến trình tải hàng loạt!")
    safe_print(f"  Thành công: {success_count}/{total_urls} video(s)")
    safe_print(f"  Tổng thời gian tải: {duration:.1f} giây")
    safe_print(f"{'='*60}\n")


def show_advanced_menu(config: DownloadConfig) -> Optional[DownloadConfig]:
    """Hiển thị menu cài đặt chi tiết nâng cao."""
    while True:
        print("\n")
        choice = questionary.select(
            "Cấu hình tải xuống nâng cao:",
            choices=[
                "1. Chọn định dạng & Chất lượng tải",
                "2. Cấu hình thư mục lưu & Mẫu đặt tên",
                "3. Tùy chọn xử lý hậu kỳ (Phụ đề, Xóa SponsorBlock)",
                "4. Tùy chọn Tăng tốc & Đa luồng (Aria2c, Luồng tải)",
                "5. Bắt đầu tải xuống",
                "← Quay lại Menu chính",
            ],
            style=CUSTOM_STYLE,
        ).ask()

        if choice is None or choice == "← Quay lại Menu chính":
            return None

        if "1. Chọn định dạng" in choice:
            config = format_selection_menu(config)

        elif "2. Cấu hình thư mục" in choice:
            config = output_path_menu(config)

        elif "3. Tùy chọn xử lý" in choice:
            config = post_processing_menu(config)

        elif "4. Tùy chọn Tăng tốc" in choice:
            config = speed_optimization_menu(config)

        elif "5. Bắt đầu tải" in choice:
            return config


def format_selection_menu(config: DownloadConfig) -> DownloadConfig:
    """Menu chọn chất lượng hoặc chuyển định dạng nhạc."""
    choice = questionary.select(
        "Chọn định dạng & Chất lượng tải:",
        choices=[
            "1. Video chất lượng tốt nhất (Best Quality)",
            "2. Video 1080p (Cân bằng - Khuyên dùng)",
            "3. Video 720p (Tải nhanh)",
            "4. Chỉ tải nhạc chất lượng cao (MP3 320kbps)",
            "5. Tùy chọn nâng cao (Nhập mã định dạng thủ công)",
            "← Quay lại",
        ],
        style=CUSTOM_STYLE,
    ).ask()

    if choice is None or "Quay lại" in choice:
        return config

    if "Best Quality" in choice:
        config.audio_only = False
        config.format = "bestvideo*+bestaudio/best"
        print("  Đã chọn: Tải video chất lượng tốt nhất.")

    elif "1080p" in choice:
        config.audio_only = False
        config.format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        print("  Đã chọn: Video độ phân giải tối đa 1080p.")

    elif "720p" in choice:
        config.audio_only = False
        config.format = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        print("  Đã chọn: Video độ phân giải tối đa 720p (Ưu tiên tốc độ).")

    elif "MP3" in choice:
        config.audio_only = True
        print("  Đã chọn: Chỉ trích xuất nhạc chất lượng cao MP3 320kbps.")

    elif "Tùy chọn nâng cao" in choice:
        list_formats(config.url)
        custom = questionary.confirm(
            "Bạn có muốn nhập mã định dạng cụ thể không?",
            default=False,
            style=CUSTOM_STYLE,
        ).ask()

        if custom:
            format_code = questionary.text(
                "Nhập mã định dạng (Ví dụ: '137+140' hoặc 'best'):", style=CUSTOM_STYLE
            ).ask()
            if format_code:
                config.format = format_code
                config.audio_only = False
                print(f"  Đã cấu hình mã định dạng: {format_code}")

    return config


def output_path_menu(config: DownloadConfig) -> DownloadConfig:
    """Cấu hình thư mục lưu tệp và mẫu đặt tên tên tệp tải về."""
    new_dir = questionary.text(
        "Nhập đường dẫn thư mục lưu:", default=config.output_dir, style=CUSTOM_STYLE
    ).ask()

    if new_dir:
        config.output_dir = new_dir

    template_choices = [
        f"A. {NAMING_TEMPLATES['default']['description']}",
        f"B. {NAMING_TEMPLATES['rich_metadata']['description']}",
        f"C. {NAMING_TEMPLATES['minimalist']['description']}",
        "D. Nhập mẫu đặt tên thủ công",
        "← Quay lại",
    ]

    choice = questionary.select(
        "Chọn mẫu đặt tên tên file đầu ra:", choices=template_choices, style=CUSTOM_STYLE
    ).ask()

    if choice is None or "Quay lại" in choice:
        return config

    if "A." in choice:
        template_key = "default"
    elif "B." in choice:
        template_key = "rich_metadata"
    elif "C." in choice:
        template_key = "minimalist"
    elif "D." in choice:
        custom_template = questionary.text(
            "Nhập mẫu đặt tên tùy chỉnh (Sử dụng cú pháp của yt-dlp):",
            default="%(title)s.%(ext)s",
            style=CUSTOM_STYLE,
        ).ask()

        if custom_template:
            if config.is_playlist and "%(playlist)s" not in custom_template:
                config.naming_template = f"%(playlist)s/{custom_template}"
            else:
                config.naming_template = custom_template
            print(f"  Mẫu đặt tên mới: {config.naming_template}")
        return config
    else:
        return config

    if config.is_playlist:
        config.naming_template = NAMING_TEMPLATES[template_key]["playlist"]
    else:
        config.naming_template = NAMING_TEMPLATES[template_key]["single"]

    print(f"  Đã đặt mẫu đặt tên file: {config.naming_template}")
    return config


def post_processing_menu(config: DownloadConfig) -> DownloadConfig:
    """Cấu hình các bộ xử lý hậu kỳ của ffmpeg/yt-dlp."""
    selected = questionary.checkbox(
        "Chọn các tác vụ xử lý hậu kỳ phụ:",
        choices=[
            questionary.Choice("Nhúng ảnh Thumbnail vào file tải về", checked=config.embed_thumbnail),
            questionary.Choice("Tải và nhúng Phụ đề", checked=config.embed_subs),
            questionary.Choice("Ghi đè thông tin siêu dữ liệu (Metadata)", checked=config.add_metadata),
            questionary.Choice("Sử dụng SponsorBlock (Cắt bỏ các phân đoạn quảng cáo)", checked=config.sponsorblock),
        ],
        style=CUSTOM_STYLE,
    ).ask()

    if selected is not None:
        config.embed_thumbnail = "Nhúng ảnh Thumbnail vào file tải về" in selected
        config.embed_subs = "Tải và nhúng Phụ đề" in selected
        config.add_metadata = "Ghi đè thông tin siêu dữ liệu (Metadata)" in selected
        config.sponsorblock = "Sử dụng SponsorBlock (Cắt bỏ các phân đoạn quảng cáo)" in selected

        enabled = [opt[:20] + "..." for opt in selected] if selected else ["Không chọn tác vụ nào"]
        print(f"  Đã cấu hình các tùy chọn: {', '.join(enabled)}")

    return config


def speed_optimization_menu(config: DownloadConfig) -> DownloadConfig:
    """Menu tùy chỉnh công cụ tăng tốc aria2c và cấu hình xử lý đa luồng."""
    # 1. Bật tắt aria2c
    config.use_aria2c = questionary.confirm(
        "Sử dụng công cụ tải siêu tốc aria2c?", default=config.use_aria2c, style=CUSTOM_STYLE
    ).ask()

    if config.use_aria2c:
        # 2. Số kết nối song song cho mỗi video
        conn = questionary.text(
            "Số lượng kết nối song song trên mỗi video (Mặc định: 16):", 
            default=str(config.max_connections), 
            style=CUSTOM_STYLE
        ).ask()
        try:
            config.max_connections = max(1, min(16, int(conn)))
        except ValueError:
            pass

    # 3. Số luồng tải video đồng thời
    concurrent = questionary.text(
        "Số lượng video tải song song cùng lúc (Khi tải Playlist/Danh sách):",
        default=str(config.concurrent_downloads),
        style=CUSTOM_STYLE
    ).ask()
    try:
        config.concurrent_downloads = max(1, int(concurrent))
    except ValueError:
        pass

    # 4. Tránh bóp băng thông
    config.bypass_throttling = questionary.confirm(
        "Bật cơ chế Bypass Throttling từ YouTube?",
        default=config.bypass_throttling,
        style=CUSTOM_STYLE
    ).ask()

    print(f"  Cấu hình tốc độ: Aria2c={'Bật' if config.use_aria2c else 'Tắt'} ({config.max_connections} kết nối) | Tải song song: {config.concurrent_downloads} video | Tránh bóp băng thông: {'Bật' if config.bypass_throttling else 'Tắt'}")
    return config


def show_main_menu(config: DownloadConfig) -> Optional[str]:
    """Hiển thị menu chính lựa chọn chế độ chạy."""
    print("\n")
    return questionary.select(
        "Chọn chế độ tải xuống của bạn:",
        choices=[
            "1. Tải nhanh theo cấu hình mặc định (Khuyên dùng)",
            "2. Cấu hình chi tiết & Tối ưu hóa trước khi tải",
            "3. Thoát chương trình",
        ],
        style=CUSTOM_STYLE,
    ).ask()


def main():
    """Điểm khởi chạy chính của công cụ CLI."""
    parser = argparse.ArgumentParser(
        description="Matrix Media Toolkit - YTB-DL - Trình tải YouTube tương tác siêu tốc nâng cấp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ chạy:
  python ytdl.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
  python ytdl.py danhsach_link.txt
        """,
    )
    parser.add_argument("url", help="Đường dẫn URL video/playlist hoặc đường dẫn tới file chứa danh sách link .txt")
    parser.add_argument("-v", "--version", action="version", version="ytdl-optimized 2.0.0")

    # Thêm các tùy chọn chạy không tương tác (Headless / Scripting)
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Chạy không tương tác (tải ngay theo cấu hình dòng lệnh)")
    parser.add_argument("--format", "-f", help="Định dạng tải (ví dụ: 'best', '1080p', '720p')")
    parser.add_argument("--output", "-o", help="Thư mục lưu video")
    parser.add_argument("--audio", "-a", action="store_true", help="Chỉ trích xuất âm thanh (MP3)")
    parser.add_argument("--connections", "-c", type=int, default=16, help="Số lượng kết nối tối đa cho aria2c (1-16)")
    parser.add_argument("--concurrent", "-p", type=int, default=3, help="Số video tải song song từ playlist/file")
    parser.add_argument("--cookies-from-browser", "-b", help="Đọc cookies từ trình duyệt (ví dụ: 'chrome', 'firefox', 'edge') để vượt bot hoặc tải video giới hạn")
    parser.add_argument("--cookies", "-k", help="Đường dẫn đến file cookies.txt để xác thực tài khoản bypass bot check")

    args = parser.parse_args()

    # In Banner chào mừng
    print("\n" + "=" * 60)
    print("  Matrix Media Toolkit - YTB-DL - Trình tải YouTube Siêu Tốc & Đa Luồng")
    print("  Tích Hợp: aria2c (16 kết nối) & Bypass Throttling")
    print("=" * 60)

    # 1. Cập nhật yt-dlp & Kiểm tra thiết lập aria2c
    check_and_update_ytdlp()
    setup_binaries()

    # Kiểm tra sự hiện diện của ffmpeg
    if not shutil.which("ffmpeg"):
        print("\n  [CẢNH BÁO] Không tìm thấy 'ffmpeg' trong hệ thống.")
        print("  Việc gộp các luồng Video + Audio chất lượng cao hoặc xuất MP3 có thể bị lỗi.")

    # 2. Phân tích tham số truyền vào (Link hay File)
    config = DownloadConfig()
    config.cookies_from_browser = args.cookies_from_browser
    config.cookies = args.cookies
    urls_list = []
    
    if is_txt_file(args.url):
        config.is_playlist = True
        try:
            with open(args.url, "r", encoding="utf-8") as f:
                for line in f:
                    line_url = line.strip()
                    if line_url and not line_url.startswith("#"):
                        urls_list.append(line_url)
            print(f"\n  [Tải danh sách] Đã nạp thành công {len(urls_list)} đường dẫn từ file: {args.url}")
        except Exception as e:
            print(f"\n  [LỖI] Không thể đọc tệp tin danh sách: {e}")
            sys.exit(1)
    else:
        # Phân tích xem có phải playlist không
        config.url = args.url
        is_playlist, info = detect_playlist(args.url, cookies_from_browser=args.cookies_from_browser, cookiefile=args.cookies)
        config.is_playlist = is_playlist
        
        if info is None:
            # Nếu phân tích lỗi, in thông báo và thoát
            print("\n  [LỖI] Không thể kết nối hoặc phân tích URL này. Vui lòng kiểm tra lại link.")
            sys.exit(1)
            
        if is_playlist and info and "entries" in info:
            for entry in info["entries"]:
                if entry:
                    entry_url = entry.get("url")
                    if not entry_url and entry.get("id"):
                        entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    if entry_url:
                        urls_list.append(entry_url)

    # 3. Đặt mẫu đặt tên file mặc định tương ứng
    if config.is_playlist:
        config.naming_template = DEFAULT_PLAYLIST_TEMPLATE
    else:
        config.naming_template = DEFAULT_SINGLE_TEMPLATE

    # 4. Kiểm tra xem môi trường có hỗ trợ tương tác console hay chạy ở chế độ Headless
    is_interactive = sys.stdin.isatty() and not args.non_interactive

    if not is_interactive:
        print("\n  [Headless] Chạy ở chế độ không tương tác...")
        if args.output:
            config.output_dir = args.output
        if args.audio:
            config.audio_only = True
        if args.connections:
            config.max_connections = max(1, min(16, args.connections))
        if args.concurrent:
            config.concurrent_downloads = max(1, args.concurrent)
        if args.format:
            if args.format == "1080p":
                config.format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
            elif args.format == "720p":
                config.format = "bestvideo[height<=720]+bestaudio/best[height<=720]"
            else:
                config.format = args.format

        execute_download(config, urls_list)
        sys.exit(0)

    # 5. Vòng lặp menu chính điều phối tác vụ (Nếu là tương tác trực tiếp)
    while True:
        choice = show_main_menu(config)

        if choice is None or "Thoát chương trình" in choice:
            print("\n  Cảm ơn bạn đã sử dụng công cụ! Tạm biệt.\n")
            sys.exit(0)

        elif "Tải nhanh" in choice:
            execute_download(config, urls_list)
            
            again = questionary.confirm(
                "Bạn có muốn tải tiếp video/danh sách khác không?", default=False, style=CUSTOM_STYLE
            ).ask()

            if not again:
                print("\n  Cảm ơn bạn đã sử dụng công cụ! Tạm biệt.\n")
                sys.exit(0)
            else:
                new_url = questionary.text(
                    "Nhập đường dẫn URL hoặc file .txt mới:", style=CUSTOM_STYLE
                ).ask()

                if new_url:
                    args.url = new_url
                    config = DownloadConfig()
                    urls_list = []
                    
                    if is_txt_file(new_url):
                        config.is_playlist = True
                        with open(new_url, "r", encoding="utf-8") as f:
                            for line in f:
                                line_url = line.strip()
                                if line_url and not line_url.startswith("#"):
                                    urls_list.append(line_url)
                        print(f"\n  [Tải danh sách] Đã nạp {len(urls_list)} link.")
                    else:
                        config.url = new_url
                        is_playlist, info = detect_playlist(new_url, cookies_from_browser=config.cookies_from_browser, cookiefile=config.cookies)
                        config.is_playlist = is_playlist
                        
                        if info is None:
                            print("\n  [LỖI] Không thể phân tích URL này.")
                            continue
                            
                        if is_playlist:
                            config.naming_template = DEFAULT_PLAYLIST_TEMPLATE
                            if info and "entries" in info:
                                for entry in info["entries"]:
                                    if entry:
                                        entry_url = entry.get("url")
                                        if not entry_url and entry.get("id"):
                                            entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                                        if entry_url:
                                            urls_list.append(entry_url)
                        else:
                            config.naming_template = DEFAULT_SINGLE_TEMPLATE

        elif "Cấu hình chi tiết" in choice:
            updated_config = show_advanced_menu(config)
            if updated_config:
                config = updated_config
                execute_download(config, urls_list)

                again = questionary.confirm(
                    "Bạn có muốn tải tiếp video/danh sách khác không?", default=False, style=CUSTOM_STYLE
                ).ask()

                if not again:
                    print("\n  Cảm ơn bạn đã sử dụng công cụ! Tạm biệt.\n")
                    sys.exit(0)
                else:
                    new_url = questionary.text(
                        "Nhập đường dẫn URL hoặc file .txt mới:", style=CUSTOM_STYLE
                    ).ask()

                    if new_url:
                        args.url = new_url
                        config = DownloadConfig()
                        urls_list = []
                        
                        if is_txt_file(new_url):
                            config.is_playlist = True
                            with open(new_url, "r", encoding="utf-8") as f:
                                for line in f:
                                    line_url = line.strip()
                                    if line_url and not line_url.startswith("#"):
                                        urls_list.append(line_url)
                        else:
                            config.url = new_url
                            is_playlist, info = detect_playlist(new_url, cookies_from_browser=config.cookies_from_browser, cookiefile=config.cookies)
                            config.is_playlist = is_playlist
                            
                            if info is None:
                                print("\n  [LỖI] Không thể phân tích URL này.")
                                continue
                                
                            if is_playlist:
                                config.naming_template = DEFAULT_PLAYLIST_TEMPLATE
                                if info and "entries" in info:
                                    for entry in info["entries"]:
                                        if entry:
                                            entry_url = entry.get("url")
                                            if not entry_url and entry.get("id"):
                                                entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                                            if entry_url:
                                                urls_list.append(entry_url)
                            else:
                                config.naming_template = DEFAULT_SINGLE_TEMPLATE


if __name__ == "__main__":
    main()
