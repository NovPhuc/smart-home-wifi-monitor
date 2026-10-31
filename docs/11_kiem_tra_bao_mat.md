# 11 — Kiểm tra bảo mật

Phiên 2026‑10‑31. Phạm vi: `server/app.py`, `src/smarthome/storage.py`, giao diện web,
**MCP server CHORUS** (`C:\chorus`) và hạ tầng proxy (`C:\cliproxy`).

Cách làm: đọc mã theo từng lớp tấn công, rồi **chứng minh bằng thực nghiệm** — bộ thăm dò
`C:\chorus\security-probe.js` (12 hạng mục, có cả nhánh tấn công và nhánh hợp lệ) và
`pytest` (51 test). Không kết luận dựa trên suy đoán.

---

## 1. Đã sửa trong phiên này

| # | Lỗ hổng | Mức | Bằng chứng trước khi sửa | Cách sửa |
|---|---------|-----|--------------------------|----------|
| 1 | **CSRF qua "simple request"** ở kênh HTTP của CHORUS | CAO | Trang web bất kỳ POST `Content-Type: text/plain` tới `http://127.0.0.1:8787/mcp` — trình duyệt **không** preflight nên request tới nơi và công cụ vẫn chạy. Thăm dò ghi được Shared Memory từ `Origin: https://evil.example` | Bắt buộc `Content-Type: application/json` (ép preflight) + chặn `Origin` lạ + Bearer token |
| 2 | **DNS rebinding** — không kiểm tra `Host` | TB | `Host: attacker.example` → HTTP 200, trả 14 công cụ | Danh sách trắng `Host`: `127.0.0.1:<cổng>`, `localhost:<cổng>`, `[::1]:<cổng>` |
| 3 | **Không xác thực kênh HTTP** | TB | Không kèm `Authorization` → HTTP 200, gọi được cả `chorus_ask` (tốn hạn mức NVIDIA) | Bearer token 32 byte, so sánh bằng `crypto.timingSafeEqual`; token lưu `hub/http-token.txt` |
| 4 | Thân request tới 32 MB | Thấp | Gửi 12 MB vẫn được nhận | Hạ trần còn 8 MB, trả 413 |
| 5 | **Điểm tiêm lệnh** qua `proxyKeyEnv` | TB | Tên biến trong `chorus.config.json` được nhúng thẳng vào lệnh PowerShell: `[Environment]::GetEnvironmentVariable('<tên>','User')` | Kiểm tra tên biến khớp `^[A-Za-z_][A-Za-z0-9_]{0,63}$` trước khi dùng |
| 6 | **Đăng ký không giới hạn** ⇒ vô hiệu hoá giới hạn dò mã chia sẻ | TB | `join_code_limiter` tính theo `user_id`; tạo tài khoản mới là lại có 5 lượt thử. Mã 6 số (10⁶ khả năng) sẽ bị dò hết | Thêm `register_limiter`: 10 lần/giờ theo IP, trả 429. Kèm test `test_register_rate_limited_per_ip` |
| 7 | **File chứa khoá cho mọi người dùng Windows đọc và ghi** | CAO (máy dùng chung) | `data\secret_key`, `data\smarthome.db`, `.env`, `hub\http-token.txt` đều có `BUILTIN\Users: Write, ReadAndExecute`. Đọc được `secret_key` là **ký được cookie phiên ⇒ giả mạo bất kỳ tài khoản** | `C:\chorus\harden-permissions.ps1`: tắt kế thừa, chỉ giữ người dùng hiện tại + SYSTEM + Administrators (có `-Revert`) |

---

## 2. Đã được vá TRƯỚC phiên này — tôi kiểm chứng lại

Các mục dưới đây từng là lỗ hổng thật; mã hiện tại đã xử lý và tôi đã đọc lại để xác nhận.

| Lỗ hổng | Trạng thái hiện tại |
|---|---|
| `SECRET_KEY = "change-this-development-secret"` (hằng số công khai ⇒ giả mạo phiên) | ✅ `resolve_secret_key()`: ưu tiên env, không có thì sinh khoá ngẫu nhiên lưu `data/secret_key`. Không còn khoá mặc định |
| Không giới hạn đăng nhập ⇒ dò mật khẩu | ✅ `login_limiter` 5 lần/15 phút theo email |
| Dò mã chia sẻ 6 số | ✅ `join_code_limiter` 5 lần/15 phút theo user |
| Lộ email đã đăng ký qua độ trễ | ✅ `DUMMY_PASSWORD_HASH` — vẫn băm khi không tìm thấy user |
| Không giới hạn thân request | ✅ `MAX_CONTENT_LENGTH = 1_000_000` |
| Mật khẩu không có trần | ✅ 8–128 ký tự (chặn DoS bằng mật khẩu khổng lồ) |
| Thiếu header bảo mật | ✅ `after_request`: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, CSP đầy đủ (kiểm tra sống: `XFO=DENY`, CSP có) |
| **CSV formula injection** khi xuất `scans.csv` | ✅ `csv_formula_safe()` chèn `'` trước ô bắt đầu bằng `= + - @` (tên phòng/tên thiết bị do người dùng đặt) |

---

## 3. Đã kiểm tra và **an toàn**

| Hạng mục | Cách kiểm chứng |
|---|---|
| **SQL injection** | Mọi truy vấn trong `storage.py` dùng tham số `?`. Chỗ duy nhất nội suy là `PRAGMA user_version = {SCHEMA_VERSION}` với hằng số module |
| **IDOR** (sửa/xoá dữ liệu của nhà khác) | Mọi thao tác ghi đều truyền `home["id"]` **cùng** `room_id`/`device_id` vào câu lệnh (`delete_room(home_id, room_id)`), nên bản ghi nhà khác không khớp |
| **Cách ly dữ liệu giữa các nhà** | Kiểm tra sống: tài khoản thứ hai thấy `room` rỗng và `history = 0` |
| **Path traversal** — CHORUS | `chorus_memory_read`, `chorus_skill_read`, `resources/read` với 4 biến thể `../../Windows/win.ini`, `/etc/passwd`, `C:\Windows\win.ini` → không ra ngoài hub. Hàm `slug()` chỉ giữ `[a-z0-9._-]` |
| **Path traversal** — `send_from_directory` | Tên file là hằng số `"service-worker.js"` |
| **Command injection** trong huấn luyện | `subprocess.run([...])` dạng danh sách, `shell=False`, `home_id` là `int` |
| **XSS** | JS dùng `escapeHTML()` cho mọi nội dung chèn vào `innerHTML`; Jinja tự escape; CSP `script-src 'self'` |
| **Tiêm mã Python** | Không có `eval`, `exec`, `pickle`, `yaml.load`, `os.system`, `shell=True` |
| **Token thiết bị** | `secrets.token_urlsafe(28)` (224 bit), chỉ lưu SHA-256, trả về đúng một lần |
| **Hạ cấp xác thực** | `request_home_context()`: có header `Authorization` mà token sai thì trả `None`, **không** âm thầm dùng session (đã có chú thích trong mã) |
| **Rò khoá qua công cụ MCP** | `chorus_status` và mọi công cụ khác không trả `nvapi-…` hay khoá proxy |
| **Mã hoá phiên** | `HttpOnly=True`, `SameSite=Lax`, `Secure` tự bật khi chạy HTTPS |

**Kết quả chạy lại:**

```
pytest tests -q                          -> 51 passed
node C:\chorus\selftest-mcp.js           -> 28/28 đạt (có gọi model thật)
node C:\chorus\security-probe.js         -> 0 lỗ hổng còn lại / 12 hạng mục
```

---

## 4. Kiểm tra chức năng (kèm trong phiên này)

Chạy sống trên `http://127.0.0.1:5000`: **13/14 bước đạt** — trang chủ 200, đăng ký, thêm phòng,
tạo mã ghép thiết bị, tạo mã chia sẻ, trạng thái, hiệu chuẩn, demo scan, lịch sử, cảnh báo,
metrics, xuất CSV, header bảo mật, đăng xuất.

Luồng demo: 3 lần quét đầu trả `COLLECTING` (model mẫu chưa đủ mẫu để chốt phòng), từ lần 4 ra
`Bedroom` với độ tin cậy 96% → 99%, sinh 2 sự kiện lịch sử. Đây là hành vi **có sẵn của model**,
không phải lỗi; giao diện đã có thông báo "Model mẫu đang khởi động…" cho giai đoạn này.

---

## 5. Khuyến nghị (chưa sửa — cần bạn quyết)

| # | Vấn đề | Vì sao chưa sửa | Đề xuất |
|---|--------|-----------------|---------|
| 1 | Chạy HTTP trần trên LAN (`0.0.0.0:5000`) ⇒ cookie phiên đi dạng rõ, có thể bị nghe lén | Đổi sang HTTPS ảnh hưởng Android Collector và NSD | Đặt `SMART_HOME_SSL_CERT`/`SMART_HOME_SSL_KEY` (mã đã hỗ trợ sẵn và tự bật `Secure` cookie) |
| 2 | mDNS quảng bá `_antam._tcp` trên LAN | Cần cho tính năng tự tìm máy chủ của app | Tắt bằng `mdns_enabled: false` nếu không dùng |
| 3 | `CLIPROXY_API_KEY` nằm trong 4 file cấu hình app (`mcp.json`, `.claude.json`, `config.toml`, `opencode.json`) | Là khoá nội bộ cho proxy trên máy, không phải khoá NVIDIA | Chấp nhận được; nếu muốn chặt hơn thì bỏ `--env` khi cài và dựa vào biến môi trường User |
| 4 | Chống CSRF của API dựa vào `SameSite=Lax` | Đã đủ với trình duyệt hiện đại; `request.get_json(force=True)` bỏ qua `Content-Type` | Thêm lớp hai: từ chối thân không phải `application/json` ở các phương thức ghi |

---

## 6. Chạy lại kiểm tra

```powershell
# Bảo mật MCP (12 hạng mục)
node C:\chorus\security-probe.js

# Chức năng MCP (28 phép thử, cần proxy đang chạy)
node C:\chorus\selftest-mcp.js

# Bộ test dự án
cd E:\Downloads\smart-home-wifi-monitor2310\smart-home-wifi-monitor
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests -q

# Siết / hoàn tác quyền file chứa khoá
C:\chorus\harden-permissions.ps1
C:\chorus\harden-permissions.ps1 -Revert
```
