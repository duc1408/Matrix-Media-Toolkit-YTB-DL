# Matrix Media Toolkit - YTB-DL - Trình tải YouTube Siêu Tốc & Đa Luồng

Đây là phiên bản nâng cấp toàn diện từ dự án gốc, chuyển đổi thành một công cụ tải video/audio YouTube siêu nhanh bằng Python (tên mới: **Matrix Media Toolkit - YTB-DL**), tích hợp trình tăng tốc **aria2c**, xử lý song song đa luồng và cung cấp giao diện đồ họa **Desktop GUI** cực đẹp.

## 🚀 Các tính năng nâng cấp nổi bật

1. **Giao diện Desktop Đồ họa (GUI) Hiện đại**:
   - Giao diện tối chuyên nghiệp (Dark Mode Flat Design) viết bằng Tkinter thuần, mở nhanh lập tức và không có bất cứ lỗi thư viện nào.
   - Cơ chế chạy ngầm (Threading) chống đơ ứng dụng khi tải các danh sách phát dài.
   - Nạp trực tiếp tệp `.txt` hoặc Playlist trực quan qua hộp thoại duyệt file Windows.
2. **Bộ tăng tốc tải xuống aria2c (Lõi nâng cấp)**:
   - Tích hợp trực tiếp công cụ `aria2c` vào lõi tải của phần mềm.
   - Cấu hình mở tối đa **16 kết nối đồng thời (connections) trên mỗi tệp tin**, chia nhỏ dữ liệu tải song song giúp vắt kiệt băng thông mạng và rút ngắn thời gian tải tối đa.
3. **Đa luồng tải Playlist & Hàng loạt (Concurrent Downloads)**:
   - Cho phép nhập vào một tệp văn bản `.txt` chứa danh sách link hoặc một link Playlist.
   - Sử dụng thư viện `ThreadPoolExecutor` của Python để tải song song nhiều video cùng lúc (mặc định tải 3 video song song, cấu hình tùy ý) thay vì phải đợi tải xong từng cái.
4. **Cơ chế tránh bóp băng thông mới nhất (Bypass Throttling)**:
   - Sử dụng các tham số mới nhất của API `yt-dlp` mô phỏng client thiết bị thực tế (`android`, `web`) để vượt qua các thuật toán bóp tốc độ của YouTube.
   - Tự động kiểm tra và cập nhật phiên bản mới nhất của thư viện `yt-dlp` khi khởi chạy.
5. **Tự động tải & Cấu hình aria2c Portable (Chỉ dành cho Windows)**:
   - Nếu máy tính Windows của bạn chưa cài `aria2c`, công cụ sẽ tự động tải phiên bản portable từ GitHub và tích hợp vào PATH chạy của tiến trình mà không yêu cầu cấu hình thủ công phức tạp!

---

## 🛠️ Hướng dẫn Cài đặt Môi trường

### 1. Yêu cầu hệ thống
* **Python**: Phiên bản `3.8` trở lên.
* **FFmpeg**: Cần thiết để ghép tệp video + audio chất lượng cao và chuyển đổi định dạng MP3.

### 2. Cài đặt FFmpeg
* **Windows**:
  1. Tải bản build mới nhất của FFmpeg từ [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
  2. Giải nén và thêm thư mục chứa tệp `ffmpeg.exe` (thường là thư mục `bin`) vào biến môi trường **PATH** của hệ thống.
* **macOS**: Cài đặt qua Homebrew:
  ```bash
  brew install ffmpeg
  ```
* **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt update && sudo apt install ffmpeg -y
  ```

### 3. Cài đặt các thư viện Python
Di chuyển vào thư mục dự án và cài đặt các thư viện phụ thuộc:
```bash
pip install -r requirements.txt
```

---

## 📖 Hướng dẫn Sử dụng

### 🎮 Chạy bằng Giao diện Desktop GUI (Khuyên dùng)
Khởi chạy giao diện đồ họa bằng câu lệnh:
```bash
python gui.py
```
Giao diện sẽ hiển thị đầy đủ:
- Ô nhập link và nút **📂 Chọn file .txt** để tải hàng loạt.
- Tùy chọn chất lượng: Video chất lượng tốt nhất, 1080p, 720p, chỉ lấy Audio MP3 320kbps.
- Hộp chọn tốc độ kết nối aria2c và số luồng tải song song đồng thời.
- Các nút tích hợp: Nhúng thumbnail, phụ đề, SponsorBlock cắt quảng cáo.
- Thanh tiến trình trực quan chạy % và hộp nhật ký chi tiết trực tiếp.

---

### Chế độ CLI 1: Giao diện Menu Tương tác (Interactive CLI)
Chỉ cần chạy lệnh sau kèm theo link video hoặc tệp `.txt`:
```bash
python ytdl.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```
Hệ thống sẽ hiển thị menu lựa chọn cấu hình tiếng Việt tương tác trên terminal.

---

### Chế độ CLI 2: Tải hàng loạt bằng File văn bản `.txt`
Tạo một file `.txt` chứa danh sách các đường dẫn video YouTube (mỗi dòng một link, có thể xem file ví dụ mẫu [urls.txt.example](file:///c:/Users/admin12/Downloads/DL%20YTB/urls.txt.example)):
```text
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=9bZkp7q19f0
```
Sau đó chạy lệnh:
```bash
python ytdl.py urls.txt.example
```
Công cụ sẽ tự động phát hiện file danh sách và tải song song các video cùng lúc.

---

### Chế độ CLI 3: Chạy Không tương tác (Headless / Scripting)
Nếu muốn sử dụng công cụ trong các script tự động hóa hoặc cron job không hỗ trợ nhập liệu, bạn có thể truyền các tham số sau:

* **Tải nhanh không hỏi menu (`-y` hoặc `--non-interactive`)**:
  ```bash
  python ytdl.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -y
  ```
* **Chỉ lấy nhạc MP3 320kbps (`-a` hoặc `--audio`)**:
  ```bash
  python ytdl.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -y -a
  ```
* **Cấu hình chất lượng video cụ thể (`-f` hoặc `--format`)**:
  - `1080p`: Tải tối đa độ phân giải 1080p (độ tương thích tốt, cân bằng).
  - `720p`: Tải nhanh chất lượng 720p.
  ```bash
  python ytdl.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -y -f 1080p
  ```
* **Tải playlist với 5 luồng song song (`-p` hoặc `--concurrent`)**:
  ```bash
  python ytdl.py "LINK_PLAYLIST" -y -p 5
  ```
* **Cấu hình số luồng kết nối aria2c tải file (`-c` hoặc `--connections`)**:
  ```bash
  python ytdl.py "URL" -y -c 8
  ```
* **Tùy biến thư mục lưu file đầu ra (`-o` or `--output`)**:
  ```bash
  python ytdl.py "URL" -y -o "./my_videos"
  ```
* **Sử dụng Cookies xác thực (`-k` hoặc `--cookies`) để vượt lỗi DPAPI và Botcheck**:
  Khi tải các video bị giới hạn độ tuổi hoặc gặp lỗi chặn bot (`Sign in to confirm you're not a bot`) hoặc lỗi giải mã trình duyệt trên Windows (`Failed to decrypt with DPAPI`):
  1. Cài đặt tiện ích mở rộng xuất cookies trên trình duyệt (ví dụ: *Get cookies.txt LOCALLY* hoặc *Tab Cookies*).
  2. Truy cập YouTube, đăng nhập tài khoản của bạn, sau đó xuất cookies định dạng Netscape ra một file (ví dụ: `cookies.txt`).
  3. Sử dụng file cookies này để tải xuống:
     - **Qua dòng lệnh (CLI)**:
       ```bash
       python ytdl.py "URL" -y --cookies cookies.txt
       ```
     - **Qua giao diện đồ họa (GUI)**:
       Nhấp chọn nút **🍪 Chọn file cookies** để chọn tệp `cookies.txt` đã lưu, sau đó nhấn **🚀 TẢI XUỐNG** bình thường.
