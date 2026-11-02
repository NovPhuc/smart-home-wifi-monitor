# Bảo mật phiên + CSV header, tinh chỉnh giao diện

Ngày: 2026-11-02. Phạm vi: vá 2 lỗ hổng còn tồn tại sau các phiên bảo mật 8–10
(hạn phiên đăng nhập và CSV injection ở dòng header export), kèm tinh chỉnh
giao diện nhỏ. Không đổi API, không thêm thư viện, không đụng thuật toán/dữ liệu.

## 1. Vá bảo mật

### 1.1 Hạn phiên đăng nhập (CAO — đã phân tích ở phiên soát bảo mật)

Vấn đề: cookie Flask chỉ được ký chứ không có hạn phía server. Cookie bị chụp
(HTTP trong LAN, malware) hợp lệ vô thời hạn, và logout chỉ xóa session phía
browser hiện tại nên không thu hồi được bản sao đã chụp.

Cách vá — phiên mang dấu thời gian `_iat` khi được cấp:

- `server/app_security.py`: `SESSION_MAX_AGE_HOURS` (env
  `SMART_HOME_SESSION_MAX_AGE_HOURS`, mặc định **168 giờ = 7 ngày**, `0` = tắt),
  `mark_session_issued()` gọi ngay sau đăng nhập/đăng ký, `session_expired()`.
  Phiên thiếu `_iat` (cookie cũ trước khi có cơ chế này) cũng bị coi là hết hạn:
  mọi người đăng nhập lại đúng một lần sau nâng cấp, không có cookie "lọt lưới".
- `server/security_middleware.py`: `install_session_guard` — before_request xóa
  session khi có `user_id` và phiên quá hạn; route trả 401 chuẩn `AUTH_REQUIRED`.
- `server/app.py`: guard được đăng ký **đầu tiên** trong chuỗi before_request
  (rẻ nhất và mọi tầng sau nhìn thấy trạng thái đăng nhập đúng).
- `server/routes/auth_views.py`: đặt `_iat` trong `register` và `login`.

Đánh đổi ghi rõ trong README: Android Collector khôi phục phiên sau 7 ngày sẽ
phải đăng nhập lại — chấp nhận được cho máy chủ gia đình.

### 1.2 CSV injection ở dòng header (TRUNG BÌNH)

Vấn đề: `/api/collect` nhận tên AP tùy ý từ client (chỉ cắt 64 ký tự). Export
CSV đã vệ sinh **giá trị ô** bằng `csv_formula_safe()` nhưng **dòng header**
ghi nguyên tên AP — key như `=HYPERLINK(...)` sẽ chạy công thức khi chủ nhà mở
file bằng Excel.

Cách vá (`server/routes/track_views.py`): áp `csv_formula_safe()` cho cả
`fieldnames` lẫn key của row — hai phía cùng một hàm nên luôn khớp nhau, giá trị
RSSI vẫn map đúng cột sau khi đổi tên.

## 2. Tinh chỉnh giao diện

Chỉ dùng lại token thiết kế sẵn có, không thêm thư viện, không đụng bố cục:

| Thay đổi | Lý do | Vị trí |
|---|---|---|
| `font-variant-numeric: tabular-nums` cho số liệu live (stat, metric, probability, giờ, đếm) | số đổi mỗi 2 giây không rung ngang chiều chữ số | `style.css` |
| Badge `#alertCount` thành `.has-pending` (nền hổ phách) khi có cảnh báo | cảnh báo chưa xử lý phải thấy ngay từ tổng quan | `style.css` + `monitoring.js` |
| Thanh accent mint `inset 3px` trên nav active | định hướng mục đang xem trên sidebar | `style.css` |
| Scrollbar mảnh `thin` + màu `#2c4058` cho vùng cuộn hẹp | thanh mặc định Windows sáng và dày, phá nền tối | `style.css` |
| `scroll-snap-type: x proximity` cho timeline | cuộn ngang ăn khớp từng item khi vuốt | `style.css` |
| `.probability` 8px → 9px | chữ quá nhỏ trên desktop | `style.css` |
| `::selection` màu mint | đồng bộ nhận diện khi bôi đen | `style.css` |

## 3. Sự cố môi trường trong phiên (ghi nhận)

Giữa phiên, `.venv` bị hỏng ngoài ý muốn: mất `pyvenv.cfg` và phần lớn
site-packages (torch, flask, pytest, numpy, pandas, scipy, sklearn… chỉ còn
vài file rải rác). Hai tiến trình `server\app.py` cũ (`.venv` và Python hệ
thống) giữ handle vào file `.pyd` khiến pip không ghi đè được (WinError 5).

Đã sửa (có xin phép trước khi dừng server): dừng 2 tiến trình → tạo lại
`pyvenv.cfg` (Python 3.11.9) → `ensurepip` → cài lại `flask pytest requests
zeroconf joblib torch numpy pandas scipy scikit-learn pyyaml …` → cài lại
editable package. Sau sửa: `import` đủ mọi gói, **pytest 84/84**.

## 4. Kiểm chứng thật

- `pytest tests -q`: **84 passed** (82 cũ + 2 mới: `test_expired_session_is_rejected`,
  `test_csv_export_header_neutralizes_formula_in_ap_name`).
- `node --check server/static/js/monitoring.js`: OK.
- Smoke trình duyệt thật (Chromium qua OpenCode): đăng ký tài khoản test →
  dashboard hiện đúng tên nhà, **phiên giữ vững qua reload**; `getComputedStyle`
  xác nhận 4 cải tiến CSS đang hiệu lực (accent nav, tabular-nums, scrollbar
  thin, class `.count`); console chỉ có đúng 1 lỗi 401 của bước probe phiên
  trước đăng nhập (flow cũ, không phải lỗi mới).
- `/api/health` sau khi mở lại server: `{"status":"ok","database":"ok"}`.
- Cập nhật `.env.example` + `README.md` (mục Bảo mật) cho biến
  `SMART_HOME_SESSION_MAX_AGE_HOURS`.

## 5. Còn lại (ưu tố tiếp theo từ bản phân tích bảo mật)

- HTTPS trong LAN (tự ký cert + ghim pin Android đã có khung sẵn) — cần quyết
  định hạ tầng của người dùng.
- Token/cookie plaintext trong SharedPreferences Android → EncryptedSharedPreferences.
- Login limiter khóa theo email vẫn cho phép DoS khóa tài khoản nạn nhân.
- Webhook chỉ nhận `https://`; hash BSSID nên có salt khi thu dữ liệu thật.
