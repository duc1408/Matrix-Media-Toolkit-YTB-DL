#!/usr/bin/env python3
"""
Matrix Media Toolkit - YTB-DL
Giao diện Đồ họa Desktop (GUI) Cyberpunk Matrix Theme hiện đại, chuyên nghiệp.
"""

import os
import sys
import re
import queue
import threading
import time
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import concurrent.futures
import yt_dlp

# Cấu hình UTF-8 cho Windows để tránh lỗi ký tự tiếng Việt
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Nhập cấu hình và nhân lõi từ ytdl
try:
    from ytdl import (
        DownloadConfig,
        execute_download_core,
        setup_binaries,
        check_and_update_ytdlp,
        detect_playlist,
        is_txt_file,
        validate_youtube_url,
        clean_youtube_url,
        DEFAULT_SINGLE_TEMPLATE,
        DEFAULT_PLAYLIST_TEMPLATE,
        DEFAULT_OUTPUT_DIR
    )
except ImportError as e:
    messagebox.showerror(
        "Lỗi Khởi Chạy (Import Error)",
        f"Chi tiết lỗi: {e}\n\n"
        "Nguyên nhân thường gặp:\n"
        "1. Bạn chưa cài đặt thư viện cần thiết trong môi trường Python hiện tại.\n"
        "2. Vui lòng mở CMD/PowerShell và chạy lệnh:\n"
        "   pip install -r requirements.txt\n"
        "   (hoặc: pip install yt-dlp questionary)"
    )
    sys.exit(1)

# Bảng màu Matrix Cyberpunk Theme chuyên nghiệp
COLOR_BG = "#080c14"            # Nền tối không gian sâu
COLOR_CARD = "#0f172a"          # Slate sẫm màu
COLOR_BORDER = "#1e293b"        # Đường viền Slate mỏng mặc định
COLOR_INPUT_BG = "#1e293b"      # Nền ô nhập liệu
COLOR_TEXT_PRIMARY = "#f8fafc"  # Chữ trắng sáng
COLOR_TEXT_MUTED = "#64748b"    # Chữ xám nhạt
COLOR_ACCENT = "#10b981"        # Matrix Neon Emerald
COLOR_ACCENT_HOVER = "#34d399"  # Neon Emerald Hover
COLOR_DESTRUCTIVE = "#ef4444"   # Đỏ neon hủy/xóa
COLOR_DESTRUCTIVE_HOVER = "#f87171"
COLOR_WARN = "#f59e0b"          # Vàng cam cảnh báo
COLOR_TERMINAL_BG = "#020617"   # Nền nhật ký đen sẫm


class CustomProgressBar(tk.Canvas):
    """Thanh tiến trình tùy chỉnh Flat Design sử dụng Canvas, tự động co giãn."""
    def __init__(self, parent, height=24, bg="#111827", fg=COLOR_ACCENT, border_color=COLOR_BORDER, **kwargs):
        super().__init__(parent, height=height, bg=bg, highlightthickness=1, highlightbackground=border_color, **kwargs)
        self.height = height
        self.fg = fg
        self.bg = bg
        self.percent = 0.0
        self.rect = self.create_rectangle(0, 0, 0, height, fill=fg, outline="")
        self.text = self.create_text(100, height // 2, text="0.0%", fill="#ffffff", font=("Segoe UI", 9, "bold"))
        self.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        self.width = event.width
        self.coords(self.text, self.width // 2, self.height // 2)
        w = (self.percent / 100.0) * self.width
        self.coords(self.rect, 0, 0, w, self.height)

    def set_progress(self, percent):
        self.percent = max(0.0, min(100.0, percent))
        if hasattr(self, "width"):
            w = (self.percent / 100.0) * self.width
            self.coords(self.rect, 0, 0, w, self.height)
        self.itemconfigure(self.text, text=f"{self.percent:.1f}%")


class YtdlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Matrix Media Toolkit - YTB-DL")
        self.root.geometry("840x700")
        self.root.minsize(840, 700)
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(True, True)

        # Hàng đợi đồng bộ dữ liệu giữa luồng nền và luồng giao diện chính
        self.gui_queue = queue.Queue()
        self.download_thread = None
        self.is_downloading = False
        self.urls_to_download = []
        self.total_urls = 0
        self.success_count = 0
        self.active_jobs = {} # registry cho tải song song
        self.dot_flashing = False

        # Tự động cấu hình các công cụ bổ trợ
        setup_binaries()
        
        # Thiết kế giao diện
        self.create_widgets()
        
        # Bắt đầu vòng lặp quét hàng đợi
        self.root.after(100, self.process_queue)

        # Chạy kiểm tra cập nhật yt-dlp ẩn
        threading.Thread(target=check_and_update_ytdlp, daemon=True).start()

    def create_widgets(self):
        # Thiết lập style cho ttk combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", 
                        fieldbackground=COLOR_INPUT_BG, 
                        background=COLOR_BORDER, 
                        foreground=COLOR_TEXT_PRIMARY,
                        bordercolor=COLOR_BORDER,
                        arrowcolor=COLOR_TEXT_PRIMARY)
        
        # --- TIÊU ĐỀ THƯƠNG HIỆU ---
        header_frame = tk.Frame(self.root, bg=COLOR_BG)
        header_frame.pack(fill="x", pady=(15, 5))
        
        title_label = tk.Label(
            header_frame, 
            text="❖ MATRIX MEDIA TOOLKIT ❖", 
            font=("Consolas", 18, "bold"), 
            fg=COLOR_ACCENT, 
            bg=COLOR_BG
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame, 
            text="YTB-DL ENGINE  •  HIGH-SPEED MULTI-THREADED DOWNLOADER", 
            font=("Segoe UI", 8, "bold"), 
            fg=COLOR_TEXT_MUTED, 
            bg=COLOR_BG
        )
        subtitle_label.pack(pady=(2, 0))

        # Đường viền nhấn Neon ngăn cách
        sep_line = tk.Frame(self.root, height=2, bg=COLOR_ACCENT)
        sep_line.pack(fill="x", padx=20, pady=10)

        # --- KHUNG NHẬP LIỆU CHÍNH (MAIN CARD CONTAINER) ---
        main_card = tk.Frame(
            self.root, 
            bg=COLOR_CARD, 
            bd=1, 
            relief="solid", 
            highlightthickness=1,
            highlightbackground=COLOR_BORDER
        )
        main_card.pack(fill="x", padx=20, pady=5)
        
        # Padding nội bộ của main card
        card_content = tk.Frame(main_card, bg=COLOR_CARD, padx=15, pady=12)
        card_content.pack(fill="x")

        # Tiêu đề các cột (Grid layout)
        headers_frame = tk.Frame(card_content, bg=COLOR_CARD)
        headers_frame.pack(fill="x", pady=(0, 4))
        headers_frame.grid_columnconfigure(0, minsize=40)
        headers_frame.grid_columnconfigure(1, weight=3)
        headers_frame.grid_columnconfigure(2, weight=2)
        headers_frame.grid_columnconfigure(3, weight=2)
        headers_frame.grid_columnconfigure(4, minsize=30)
        headers_frame.grid_columnconfigure(5, minsize=30)

        tk.Label(headers_frame, text="#", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Consolas", 9, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(headers_frame, text="Đường dẫn (URL YouTube)", fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5)
        tk.Label(headers_frame, text="Tên lưu (Tùy chọn)", fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
        tk.Label(headers_frame, text="Thư mục lưu tệp", fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=5)
        tk.Label(headers_frame, text="", bg=COLOR_CARD).grid(row=0, column=4)
        tk.Label(headers_frame, text="", bg=COLOR_CARD).grid(row=0, column=5)

        # Thùng chứa các dòng nhập liệu (Grid layout)
        self.rows_container = tk.Frame(card_content, bg=COLOR_CARD)
        self.rows_container.pack(fill="x")
        self.rows_container.grid_columnconfigure(0, minsize=40)
        self.rows_container.grid_columnconfigure(1, weight=3)
        self.rows_container.grid_columnconfigure(2, weight=2)
        self.rows_container.grid_columnconfigure(3, weight=2)
        self.rows_container.grid_columnconfigure(4, minsize=30)
        self.rows_container.grid_columnconfigure(5, minsize=30)
        
        self.rows = []
        
        # Mặc định thêm sẵn 3 dòng
        for _ in range(3):
            self.add_row()

        # Khung chứa các nút điều khiển & chất lượng (Control Frame)
        ctrl_layout_frame = tk.Frame(card_content, bg=COLOR_CARD)
        ctrl_layout_frame.pack(fill="x", pady=(12, 0))

        # Chọn chất lượng
        tk.Label(
            ctrl_layout_frame, 
            text="CHẤT LƯỢNG:", 
            fg=COLOR_TEXT_PRIMARY, 
            bg=COLOR_CARD, 
            font=("Consolas", 9, "bold")
        ).pack(side="left", padx=(0, 5))

        self.format_combo = ttk.Combobox(
            ctrl_layout_frame, 
            values=[
                "Video 1080p (Cân bằng - Khuyên dùng)",
                "Video chất lượng tốt nhất (Best Quality)",
                "Video 720p (Ưu tiên tốc độ tải)",
                "Chỉ tải nhạc chất lượng cao (MP3 320kbps)"
            ], 
            state="readonly",
            width=32
        )
        self.format_combo.current(0)
        self.format_combo.pack(side="left", padx=5)

        # Nút Thêm dòng / Xóa dòng
        self.btn_add_row = tk.Button(
            ctrl_layout_frame, 
            text="➕ THÊM DÒNG", 
            command=self.add_row, 
            bg=COLOR_BORDER, 
            fg=COLOR_TEXT_PRIMARY, 
            bd=0, 
            padx=10, 
            pady=3, 
            font=("Consolas", 8, "bold"), 
            activebackground=COLOR_INPUT_BG, 
            cursor="hand2"
        )
        self.btn_add_row.pack(side="left", padx=(15, 5))
        self.bind_hover(self.btn_add_row, COLOR_INPUT_BG, COLOR_BORDER)
        
        self.btn_del_row = tk.Button(
            ctrl_layout_frame, 
            text="➖ XÓA DÒNG", 
            command=self.delete_row, 
            bg=COLOR_BORDER, 
            fg=COLOR_TEXT_PRIMARY, 
            bd=0, 
            padx=10, 
            pady=3, 
            font=("Consolas", 8, "bold"), 
            activebackground=COLOR_INPUT_BG, 
            cursor="hand2"
        )
        self.btn_del_row.pack(side="left", padx=5)
        self.bind_hover(self.btn_del_row, COLOR_INPUT_BG, COLOR_BORDER)

        # Nút Tải xuống (Vibrant Neon Green)
        self.btn_download = tk.Button(
            ctrl_layout_frame, 
            text="⚡ BẮT ĐẦU TẢI", 
            command=self.start_download, 
            bg=COLOR_ACCENT, 
            fg="#080c14", 
            bd=0, 
            padx=25, 
            pady=6, 
            font=("Consolas", 10, "bold"),
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground="#080c14",
            cursor="hand2"
        )
        self.btn_download.pack(side="right")
        self.bind_hover(self.btn_download, COLOR_ACCENT_HOVER, COLOR_ACCENT)

        # --- KHUNG TIẾN TRÌNH & THÔNG TIN ---
        progress_frame = tk.Frame(self.root, bg=COLOR_BG)
        progress_frame.pack(fill="x", padx=20, pady=(5, 2))

        # Thanh tiến trình chi tiết
        self.progress_bar = CustomProgressBar(progress_frame, height=22, bg="#111827", fg=COLOR_ACCENT, border_color=COLOR_BORDER)
        self.progress_bar.pack(fill="x", pady=(5, 5))

        # --- KHUNG CHỈ SỐ DASHBOARD (DASHBOARD STATS CARDS) ---
        stats_frame = tk.Frame(self.root, bg=COLOR_BG)
        stats_frame.pack(fill="x", padx=20, pady=(2, 8))
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=1)
        stats_frame.grid_columnconfigure(2, weight=1)

        # Card Tốc độ
        self.card_speed_frame = tk.Frame(stats_frame, bg=COLOR_CARD, bd=1, relief="solid", highlightthickness=0, highlightbackground=COLOR_BORDER)
        self.card_speed_frame.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.lbl_speed_val = tk.Label(self.card_speed_frame, text="⚡ TỐC ĐỘ: N/A", fg=COLOR_ACCENT, bg=COLOR_CARD, font=("Consolas", 10, "bold"), pady=6)
        self.lbl_speed_val.pack()

        # Card Thời gian còn lại
        self.card_eta_frame = tk.Frame(stats_frame, bg=COLOR_CARD, bd=1, relief="solid", highlightthickness=0, highlightbackground=COLOR_BORDER)
        self.card_eta_frame.grid(row=0, column=1, padx=6, sticky="ew")
        self.lbl_eta_val = tk.Label(self.card_eta_frame, text="⏱️ CÒN LẠI: N/A", fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, font=("Consolas", 10, "bold"), pady=6)
        self.lbl_eta_val.pack()

        # Card Tiến độ
        self.card_progress_frame = tk.Frame(stats_frame, bg=COLOR_CARD, bd=1, relief="solid", highlightthickness=0, highlightbackground=COLOR_BORDER)
        self.card_progress_frame.grid(row=0, column=2, padx=(6, 0), sticky="ew")
        self.lbl_progress_val = tk.Label(self.card_progress_frame, text="📊 TIẾN ĐỘ: SẴN SÀNG", fg=COLOR_ACCENT, bg=COLOR_CARD, font=("Consolas", 10, "bold"), pady=6)
        self.lbl_progress_val.pack()

        # --- HỘP CONSOLE LOG (Matrix terminal vibe) ---
        log_card = tk.Frame(
            self.root, 
            bg=COLOR_CARD, 
            bd=1, 
            relief="solid", 
            highlightthickness=1,
            highlightbackground=COLOR_BORDER
        )
        log_card.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        # Thanh tiêu đề Terminal
        log_header_frame = tk.Frame(log_card, bg=COLOR_CARD, pady=4, padx=8)
        log_header_frame.pack(fill="x")
        
        # Flashing indicator / dot
        self.status_dot = tk.Label(log_header_frame, text="●", fg="#64748b", bg=COLOR_CARD, font=("Segoe UI", 12))
        self.status_dot.pack(side="left")
        
        log_title = tk.Label(log_header_frame, text="NHẬT KÝ HOẠT ĐỘNG (SYSTEM LOG)", fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, font=("Segoe UI", 9, "bold"))
        log_title.pack(side="left", padx=5)
        
        log_content = tk.Frame(log_card, bg=COLOR_TERMINAL_BG, padx=8, pady=8)
        log_content.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_content, 
            bg=COLOR_TERMINAL_BG, 
            fg=COLOR_TEXT_PRIMARY, 
            insertbackground=COLOR_ACCENT, 
            bd=0, 
            font=("Consolas", 9), 
            wrap="word"
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        # Định nghĩa các tag màu sắc cho console
        self.log_text.tag_config("info", foreground=COLOR_TEXT_MUTED)
        self.log_text.tag_config("success", foreground="#10b981", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("warn", foreground="#f59e0b", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("error", foreground="#ef4444", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("pp", foreground="#22d3ee") # Cyan for ffmpeg postprocessor

        scrollbar = ttk.Scrollbar(log_content, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # Tự động nạp cookies mặc định
        default_cookies = self.detect_default_cookies()
        if default_cookies:
            self.append_log(f"🍪 Tự động phát hiện và nạp cookies xác thực: {Path(default_cookies).name}\n", "success")
        else:
            self.append_log("Khởi động hệ thống giao diện GUI thành công.\nSử dụng aria2c làm nhân tăng tốc mặc định.\n", "info")

    def bind_hover(self, widget, color_enter, color_leave):
        """Tạo hiệu ứng đổi màu hover cho nút bấm hiện đại."""
        widget.bind("<Enter>", lambda e: widget.configure(bg=color_enter))
        widget.bind("<Leave>", lambda e: widget.configure(bg=color_leave))

    def setup_entry_effects(self, entry, var, placeholder):
        """Thiết lập hiệu ứng viền đổi màu và placeholder cho ô nhập liệu."""
        border_frame = entry.master
        
        def on_focus_in(e):
            border_frame.configure(highlightbackground=COLOR_ACCENT)
            if var.get() == placeholder:
                var.set("")
                entry.configure(fg=COLOR_TEXT_PRIMARY)
                
        def on_focus_out(e):
            border_frame.configure(highlightbackground=COLOR_BORDER)
            if not var.get().strip():
                var.set(placeholder)
                entry.configure(fg=COLOR_TEXT_MUTED)
                
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        
        # Khởi tạo trạng thái ban đầu
        if not var.get().strip() or var.get() == placeholder:
            var.set(placeholder)
            entry.configure(fg=COLOR_TEXT_MUTED)
        else:
            entry.configure(fg=COLOR_TEXT_PRIMARY)

    def flash_dot(self):
        """Hiệu ứng nhấp nháy cho đèn báo hệ thống khi đang tải."""
        if not self.dot_flashing:
            self.status_dot.configure(fg="#64748b")
            return
        current_color = self.status_dot.cget("fg")
        next_color = "#047857" if current_color == COLOR_ACCENT else COLOR_ACCENT
        self.status_dot.configure(fg=next_color)
        self.root.after(500, self.flash_dot)

    def detect_default_cookies(self):
        """Tự động tìm kiếm file cookies.txt trong thư mục hiện tại."""
        for name in ["cookies.txt", "www.youtube.com_cookies.txt"]:
            path = Path(name)
            if path.exists():
                return str(path.absolute())
        return None

    def add_row(self, url="", name="", path=DEFAULT_OUTPUT_DIR):
        """Thêm một dòng nhập liệu link và đích lưu vào danh sách bằng Grid."""
        row_idx = len(self.rows)
        if row_idx >= 8:
            messagebox.showwarning("Cảnh báo", "Bạn chỉ nên tải tối đa 8 link song song để tránh bị YouTube chặn IP.")
            return

        # Số thứ tự
        lbl = tk.Label(self.rows_container, text=f"#{row_idx + 1:02d}", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Consolas", 9, "bold"), anchor="w")
        lbl.grid(row=row_idx, column=0, padx=5, pady=4, sticky="w")

        # Ô nhập URL
        url_var = tk.StringVar(value=url)
        url_border = tk.Frame(self.rows_container, bg=COLOR_INPUT_BG, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        url_border.grid(row=row_idx, column=1, padx=5, pady=4, sticky="ew")
        url_entry = tk.Entry(url_border, textvariable=url_var, bg=COLOR_INPUT_BG, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_TEXT_PRIMARY, bd=0, relief="flat", font=("Segoe UI", 9))
        url_entry.pack(padx=2, pady=2, fill="both", expand=True)
        self.setup_entry_effects(url_entry, url_var, "Nhập hoặc dán link YouTube...")

        # Ô nhập tên file lưu
        name_var = tk.StringVar(value=name)
        name_border = tk.Frame(self.rows_container, bg=COLOR_INPUT_BG, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        name_border.grid(row=row_idx, column=2, padx=5, pady=4, sticky="ew")
        name_entry = tk.Entry(name_border, textvariable=name_var, bg=COLOR_INPUT_BG, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_TEXT_PRIMARY, bd=0, relief="flat", font=("Segoe UI", 9))
        name_entry.pack(padx=2, pady=2, fill="both", expand=True)
        self.setup_entry_effects(name_entry, name_var, "Tên file (Tùy chọn)...")

        # Ô nhập đường dẫn lưu
        path_var = tk.StringVar(value=path)
        path_border = tk.Frame(self.rows_container, bg=COLOR_INPUT_BG, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        path_border.grid(row=row_idx, column=3, padx=5, pady=4, sticky="ew")
        path_entry = tk.Entry(path_border, textvariable=path_var, bg=COLOR_INPUT_BG, fg=COLOR_TEXT_PRIMARY, insertbackground=COLOR_TEXT_PRIMARY, bd=0, relief="flat", font=("Segoe UI", 9))
        path_entry.pack(padx=2, pady=2, fill="both", expand=True)
        
        # Path doesn't have placeholder text, but it has focus highlight!
        def on_path_focus_in(e):
            path_border.configure(highlightbackground=COLOR_ACCENT)
        def on_path_focus_out(e):
            path_border.configure(highlightbackground=COLOR_BORDER)
        path_entry.bind("<FocusIn>", on_path_focus_in)
        path_entry.bind("<FocusOut>", on_path_focus_out)

        # Nút chọn thư mục
        def browse():
            selected = filedialog.askdirectory(initialdir=path_var.get())
            if selected:
                path_var.set(selected)

        btn_browse = tk.Button(self.rows_container, text="📂", command=browse, bg=COLOR_BORDER, fg=COLOR_TEXT_PRIMARY, bd=0, padx=5, pady=1, font=("Segoe UI", 8), activebackground=COLOR_INPUT_BG, cursor="hand2")
        btn_browse.grid(row=row_idx, column=4, padx=2, pady=4, sticky="e")
        self.bind_hover(btn_browse, COLOR_INPUT_BG, COLOR_BORDER)

        # Nút dọn dẹp hàng riêng lẻ (Clear row inputs)
        def clear_row():
            url_var.set("Nhập hoặc dán link YouTube...")
            url_entry.configure(fg=COLOR_TEXT_MUTED)
            name_var.set("Tên file (Tùy chọn)...")
            name_entry.configure(fg=COLOR_TEXT_MUTED)
            path_var.set(DEFAULT_OUTPUT_DIR)

        btn_clear = tk.Button(self.rows_container, text="🗑️", command=clear_row, bg=COLOR_BORDER, fg=COLOR_DESTRUCTIVE, bd=0, padx=5, pady=1, font=("Segoe UI", 8), activebackground=COLOR_INPUT_BG, cursor="hand2")
        btn_clear.grid(row=row_idx, column=5, padx=(2, 5), pady=4, sticky="e")
        self.bind_hover(btn_clear, COLOR_INPUT_BG, COLOR_BORDER)

        self.rows.append({
            "lbl": lbl,
            "url_var": url_var,
            "name_var": name_var,
            "path_var": path_var,
            "url_border": url_border,
            "url_entry": url_entry,
            "name_border": name_border,
            "name_entry": name_entry,
            "path_border": path_border,
            "path_entry": path_entry,
            "browse_btn": btn_browse,
            "clear_btn": btn_clear
        })

    def delete_row(self):
        """Xóa dòng cuối cùng trong bảng nhập liệu."""
        if len(self.rows) <= 1:
            messagebox.showwarning("Cảnh báo", "Bạn phải giữ lại ít nhất 1 dòng nhập liệu.")
            return
        last_row = self.rows.pop()
        last_row["lbl"].destroy()
        last_row["url_border"].destroy()
        last_row["name_border"].destroy()
        last_row["path_border"].destroy()
        last_row["browse_btn"].destroy()
        last_row["clear_btn"].destroy()

    def append_log(self, text, tag=None):
        """Ghi thêm log vào ô log console và tự động cuộn xuống cuối, hỗ trợ định dạng màu sắc."""
        self.log_text.configure(state="normal")
        
        # Tự động phát hiện tag dựa trên nội dung log nếu không được truyền vào trực tiếp
        if not tag:
            if any(w in text for w in ["[LỖI]", "[ERROR]", "❌", "Error:"]):
                tag = "error"
            elif any(w in text for w in ["[CẢNH BÁO]", "[WARNING]", "⚠️"]):
                tag = "warn"
            elif any(w in text for w in ["[Xong tệp]", "✅", "Thành công", "successfully"]):
                tag = "success"
            elif any(w in text for w in ["[Xử lý]", "⚙️", "Extracting", "Merging", "Post-process"]):
                tag = "pp"
            else:
                tag = "info"

        self.log_text.insert("end", text, tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def start_download(self):
        """Khởi động luồng tải xuống chính."""
        if self.is_downloading:
            self.cancel_download()
            return

        # Thu thập các dòng đã nhập và loại bỏ placeholders
        download_list = []
        for idx, row in enumerate(self.rows):
            url = row["url_var"].get().strip()
            if url == "Nhập hoặc dán link YouTube..." or not url:
                continue
            name = row["name_var"].get().strip()
            if name == "Tên file (Tùy chọn)...":
                name = ""
            path = row["path_var"].get().strip()
            if not path:
                path = DEFAULT_OUTPUT_DIR
                
            download_list.append({
                "url": clean_youtube_url(url),
                "name": name,
                "path": path
            })

        if not download_list:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập ít nhất một đường dẫn (URL) YouTube hợp lệ để tải xuống.")
            return

        # Vô hiệu hóa các nút điều khiển
        self.is_downloading = True
        self.btn_download.configure(text="🛑 HỦY TẢI", bg=COLOR_DESTRUCTIVE, fg="#ffffff", activebackground=COLOR_DESTRUCTIVE_HOVER, activeforeground="#ffffff")
        self.btn_add_row.configure(state="disabled")
        self.btn_del_row.configure(state="disabled")
        self.format_combo.configure(state="disabled")
        for row in self.rows:
            row["url_entry"].configure(state="disabled", bg="#1a1a24")
            row["name_entry"].configure(state="disabled", bg="#1a1a24")
            row["path_entry"].configure(state="disabled", bg="#1a1a24")
            row["url_border"].configure(bg="#1a1a24")
            row["name_border"].configure(bg="#1a1a24")
            row["path_border"].configure(bg="#1a1a24")
            row["browse_btn"].configure(state="disabled")
            row["clear_btn"].configure(state="disabled")

        self.progress_bar.set_progress(0.0)
        
        # Reset Dashboard
        self.lbl_speed_val.configure(text="⚡ TỐC ĐỘ: ĐANG KẾT NỐI")
        self.lbl_eta_val.configure(text="⏱️ CÒN LẠI: N/A")
        self.lbl_progress_val.configure(text="📊 TIẾN ĐỘ: 0%")

        # Chạy hiệu ứng nhấp nháy đèn báo
        self.dot_flashing = True
        self.status_dot.configure(fg=COLOR_ACCENT)
        self.flash_dot()

        self.append_log(f"\n--- BẮT ĐẦU TIẾN TRÌNH TẢI XUỐNG ---\nSố lượng liên kết nạp được: {len(download_list)}\n", "success")

        # Thiết lập cấu hình DownloadConfig với các tối ưu tự động
        config = DownloadConfig()
        config.output_dir = DEFAULT_OUTPUT_DIR

        # Cấu hình chất lượng
        fmt_choice = self.format_combo.current()
        if fmt_choice == 0:  # 1080p
            config.audio_only = False
            config.format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif fmt_choice == 1:  # Best
            config.audio_only = False
            config.format = "bestvideo*+bestaudio/best"
        elif fmt_choice == 2:  # 720p
            config.audio_only = False
            config.format = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif fmt_choice == 3:  # MP3
            config.audio_only = True

        # Tự động cấu hình aria2c siêu tốc
        config.use_aria2c = True
        config.max_connections = 16
        config.concurrent_downloads = 3

        # Tự động nạp cookies nếu có sẵn
        config.cookies = self.detect_default_cookies()
        config.cookies_from_browser = None

        # Bắt đầu chạy ngầm luồng tải xuống chính
        self.download_thread = threading.Thread(target=self.bg_download, args=(config, download_list), daemon=True)
        self.download_thread.start()

    def cancel_download(self):
        """Hủy tiến trình tải xuống hiện tại."""
        confirm = messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn hủy tiến trình tải xuống này?")
        if confirm:
            self.append_log("\n⚠️ Đã gửi yêu cầu hủy tải xuống. Giao diện đang được khôi phục...\n", "warn")
            self.reset_ui()

    def reset_ui(self):
        """Khôi phục lại giao diện ban đầu sau khi tải xong hoặc bị hủy."""
        self.is_downloading = False
        self.dot_flashing = False
        self.btn_download.configure(text="⚡ BẮT ĐẦU TẢI", bg=COLOR_ACCENT, fg="#080c14", activebackground=COLOR_ACCENT_HOVER, activeforeground="#080c14")
        self.btn_add_row.configure(state="normal")
        self.btn_del_row.configure(state="normal")
        self.format_combo.configure(state="readonly")
        
        for row in self.rows:
            row["url_entry"].configure(state="normal", bg=COLOR_INPUT_BG)
            row["name_entry"].configure(state="normal", bg=COLOR_INPUT_BG)
            row["path_entry"].configure(state="normal", bg=COLOR_INPUT_BG)
            row["url_border"].configure(bg=COLOR_INPUT_BG)
            row["name_border"].configure(bg=COLOR_INPUT_BG)
            row["path_border"].configure(bg=COLOR_INPUT_BG)
            row["browse_btn"].configure(state="normal")
            row["clear_btn"].configure(state="normal")
            
        self.active_jobs.clear()
        
        # Reset Dashboard
        self.lbl_speed_val.configure(text="⚡ TỐC ĐỘ: N/A")
        self.lbl_eta_val.configure(text="⏱️ CÒN LẠI: N/A")
        self.lbl_progress_val.configure(text="📊 TIẾN ĐỘ: SẴN SÀNG")
        self.status_dot.configure(fg="#64748b")

    def bg_download(self, base_config, download_list):
        """Tiến trình tải chạy nền, phân tích link/playlist và thực hiện tải."""
        app_self = self
        final_tasks = []
        cookies_file = base_config.cookies
        
        app_self.gui_queue.put({"type": "log", "message": "🔎 Đang phân tích các liên kết...", "tag": "info"})
        
        for task in download_list:
            url = task["url"]
            name = task["name"]
            path = task["path"]
            
            is_playlist, info = detect_playlist(url, cookiefile=cookies_file)
            if is_playlist and info and "entries" in info:
                playlist_title = info.get("title", "Playlist")
                app_self.gui_queue.put({"type": "log", "message": f"Detected: Playlist - '{playlist_title}' ({len(info['entries'])} videos)", "tag": "success"})
                base_config.is_playlist = True
                for entry in info["entries"]:
                    if entry:
                        entry_url = entry.get("url")
                        if not entry_url and entry.get("id"):
                            entry_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        if entry_url:
                            final_tasks.append({
                                "url": entry_url,
                                "name": "", # Playlist không dùng chung custom name
                                "path": os.path.join(path, playlist_title)
                            })
            else:
                final_tasks.append({
                    "url": url,
                    "name": name,
                    "path": path
                })

        app_self.total_urls = len(final_tasks)
        app_self.success_count = 0

        if app_self.total_urls == 0:
            app_self.gui_queue.put({"type": "error", "message": "Không tìm thấy liên kết hợp lệ để tải."})
            return

        # 2. Thực hiện tải
        if app_self.total_urls > 1:
            # Tải nhiều video song song
            app_self.gui_queue.put({"type": "log", "message": f"🚀 Bắt đầu tải song song {app_self.total_urls} video với tối đa {base_config.concurrent_downloads} luồng...", "tag": "success"})
            app_self.gui_queue.put({"type": "overall_progress", "percent": 0.0})

            def worker(task_item: dict, idx: int):
                video_url = task_item["url"]
                custom_name = task_item["name"]
                output_dir = task_item["path"]

                # Tạo config con
                config = DownloadConfig()
                config.url = video_url
                config.is_playlist = False
                config.output_dir = output_dir
                config.format = base_config.format
                
                # Áp dụng đặt tên file lưu tùy biến
                if custom_name:
                    config.naming_template = f"{custom_name}.%(ext)s"
                else:
                    config.naming_template = DEFAULT_SINGLE_TEMPLATE

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
                config.cookies_from_browser = base_config.cookies_from_browser
                config.cookies = base_config.cookies

                try:
                    # Ghi đè tiến trình để xuất vào GUI
                    opts = config.to_yt_dlp_opts()
                    opts["progress_hooks"] = [app_self.get_gui_progress_hook()]
                    opts["postprocessor_hooks"] = [app_self.get_gui_postprocessor_hook()]
                    opts["ignoreerrors"] = False
                    
                    class LoggerWrapper:
                        def debug(self, msg):
                            if "[debug]" not in msg and "[download]" not in msg:
                                app_self.gui_queue.put({"type": "log", "message": msg, "tag": "info"})
                        def warning(self, msg):
                            app_self.gui_queue.put({"type": "log", "message": f"[CẢNH BÁO] {msg}", "tag": "warn"})
                        def error(self, msg):
                            app_self.gui_queue.put({"type": "log", "message": f"[LỖI] {msg}", "tag": "error"})
                    opts["logger"] = LoggerWrapper()

                    with yt_dlp.YoutubeDL(opts) as ydl:
                        exit_code = ydl.download([config.url])
                        return exit_code == 0
                except Exception as e:
                    app_self.gui_queue.put({"type": "log", "message": f"❌ Lỗi luồng tải {idx}: {e}", "tag": "error"})
                    return False

            success_count = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=base_config.concurrent_downloads) as executor:
                futures = {executor.submit(worker, task, i+1): task for i, task in enumerate(final_tasks)}
                for future in concurrent.futures.as_completed(futures):
                    task_done = futures[future]
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                            app_self.gui_queue.put({"type": "item_success", "url": task_done["url"]})
                    except Exception as e:
                        app_self.gui_queue.put({"type": "log", "message": f"❌ Lỗi xảy ra trên link {task_done['url']}: {e}", "tag": "error"})
            
            app_self.gui_queue.put({
                "type": "all_finished",
                "success": True,
                "message": f"🎉 Đã hoàn tất tải hàng loạt! Thành công: {success_count}/{app_self.total_urls} video(s)"
            })
        else:
            # Tải 1 video đơn
            task_item = final_tasks[0]
            config = base_config
            config.url = task_item["url"]
            config.output_dir = task_item["path"]
            config.is_playlist = False

            if task_item["name"]:
                config.naming_template = f"{task_item['name']}.%(ext)s"
            else:
                config.naming_template = DEFAULT_SINGLE_TEMPLATE

            try:
                opts = config.to_yt_dlp_opts()
                opts["progress_hooks"] = [app_self.get_gui_progress_hook()]
                opts["postprocessor_hooks"] = [app_self.get_gui_postprocessor_hook()]
                opts["ignoreerrors"] = False
                
                class LoggerWrapper:
                    def debug(self, msg):
                        if "[debug]" not in msg and "[download]" not in msg:
                            app_self.gui_queue.put({"type": "log", "message": msg, "tag": "info"})
                    def warning(self, msg):
                        app_self.gui_queue.put({"type": "log", "message": f"[CẢNH BÁO] {msg}", "tag": "warn"})
                    def error(self, msg):
                        app_self.gui_queue.put({"type": "log", "message": f"[LỖI] {msg}", "tag": "error"})
                opts["logger"] = LoggerWrapper()

                with yt_dlp.YoutubeDL(opts) as ydl:
                    exit_code = ydl.download([config.url])
                    
                if exit_code == 0:
                    app_self.gui_queue.put({"type": "all_finished", "success": True, "message": "🎉 Tải video đơn thành công!"})
                else:
                    app_self.gui_queue.put({"type": "all_finished", "success": False, "message": "❌ Tải video đơn thất bại!"})
            except Exception as e:
                app_self.gui_queue.put({"type": "all_finished", "success": False, "message": f"❌ Lỗi tải: {e}"})

    def get_gui_progress_hook(self):
        """Tạo progress hook tùy chỉnh đẩy dữ liệu về hàng đợi GUI."""
        def hook(d):
            video_id = d.get("info_dict", {}).get("id") or "Unknown"
            title = d.get("info_dict", {}).get("title") or "Unknown Video"
            
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "").strip()
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
                
                self.gui_queue.put({
                    "type": "progress",
                    "video_id": video_id,
                    "title": title,
                    "percent": percent,
                    "speed": speed,
                    "eta": eta
                })
            elif d["status"] == "finished":
                self.gui_queue.put({
                    "type": "log",
                    "message": f"✅ [Xong tệp] Tải xong tệp video: {title}\n",
                    "tag": "success"
                })
        return hook

    def get_gui_postprocessor_hook(self):
        """Tạo postprocessor hook tùy chỉnh để cập nhật trạng thái xử lý hậu kỳ của ffmpeg."""
        def hook(d):
            pp_name = d.get("postprocessor", "Unknown")
            if d["status"] == "started":
                self.gui_queue.put({"type": "log", "message": f"⚙️ [Xử lý] Đang ghép hoặc xuất định dạng: {pp_name}...\n", "tag": "pp"})
            elif d["status"] == "finished":
                self.gui_queue.put({"type": "log", "message": f"⚙️ [Xử lý] Hoàn thành xử lý {pp_name}.\n", "tag": "success"})
        return hook

    def process_queue(self):
        """Đọc và xử lý các thông điệp trong hàng đợi GUI định kỳ (Chạy trên Main UI Thread)."""
        try:
            while True:
                msg = self.gui_queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "log":
                    self.append_log(msg.get("message"), msg.get("tag"))

                elif msg_type == "progress":
                    video_id = msg.get("video_id")
                    percent_str = msg.get("percent").replace("%", "").strip()
                    speed = msg.get("speed")
                    eta = msg.get("eta")
                    title = msg.get("title")

                    try:
                        pct_val = float(percent_str)
                    except ValueError:
                        pct_val = 0.0

                    self.active_jobs[video_id] = pct_val
                    
                    if self.total_urls > 1:
                        # Chế độ tải song song: Tính toán và hiển thị tiến trình tổng quan
                        total_percent = (sum(self.active_jobs.values()) + (self.success_count * 100)) / (self.total_urls)
                        self.progress_bar.set_progress(total_percent)
                        
                        # Cập nhật Dashboard stats
                        self.lbl_speed_val.configure(text=f"⚡ TỐC ĐỘ: {speed}")
                        self.lbl_eta_val.configure(text=f"⏱️ CÒN LẠI: {eta}")
                        self.lbl_progress_val.configure(text=f"📊 TIẾN ĐỘ: ĐÃ TẢI {self.success_count}/{self.total_urls}")

                        # In log cập nhật cho video cụ thể theo chu kỳ 10%
                        last_pct_attr = f"_gui_pct_{video_id}"
                        last_printed = getattr(self, last_pct_attr, -5.0)
                        if pct_val - last_printed >= 10.0 or pct_val >= 99.9:
                            setattr(self, last_pct_attr, pct_val)
                            self.append_log(f" ⏳ [Đang tải] {title[:35]}... : {percent_str}% | Tốc độ: {speed} | Còn lại: {eta}\n", "info")
                    else:
                        # Chế độ tải đơn luồng
                        self.progress_bar.set_progress(pct_val)
                        
                        # Cập nhật Dashboard stats
                        self.lbl_speed_val.configure(text=f"⚡ TỐC ĐỘ: {speed}")
                        self.lbl_eta_val.configure(text=f"⏱️ CÒN LẠI: {eta}")
                        self.lbl_progress_val.configure(text=f"📊 TIẾN ĐỘ: {pct_val:.1f}%")

                elif msg_type == "item_success":
                    self.success_count += 1
                    percent = (self.success_count / self.total_urls) * 100
                    self.lbl_progress_val.configure(text=f"📊 TIẾN ĐỘ: ĐÃ XONG {self.success_count}/{self.total_urls}")

                elif msg_type == "all_finished":
                    self.reset_ui()
                    messagebox.showinfo("Hoàn tất", msg.get("message"))
                    self.append_log(f"\n--- TIẾN TRÌNH KẾT THÚC ---\nKết quả: {msg.get('message')}\n", "success")

                elif msg_type == "error":
                    self.reset_ui()
                    messagebox.showerror("Lỗi", msg.get("message"))
                    self.append_log(f"\n❌ Gặp sự cố ngắt quãng: {msg.get('message')}\n", "error")

                self.gui_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)


def main():
    root = tk.Tk()
    app = YtdlGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
