# Kiểm tra bảo mật và nâng cấp chức năng — phiên 10

Ngày: 2026-11-01
Nhánh: `fix/optimize-training`
Phạm vi: tầng Flask (`server/`), dashboard PWA (`server/static/`), Android manifest, test hồi quy.
Không sửa dữ liệu gốc, không đổi đường dẫn API/tên trường JSON. Phiên này **không chạy
`git commit`**; trong lúc làm việc, một tiến trình khác đã tạo commit `360eb59` chứa
phần lớn thay đổi bên dưới (xem mục 5).

## 1. Hiện trạng trước khi sửa

Bản refactor G1 (tách `server/app.py` thành `app_state`, `app_services`, `routes/`) đang dở.
`pytest tests -q` cho kết quả **4 failed, 47 passed**:

- `test_device_token_authenticates_collect_and_scopes_home`
- `test_persistent_warning_writes_one_alert_not_one_per_scan`
- `test_reset_clears_runtime_state_but_keeps_rows`
- `test_share_code_lets_member_view_but_not_write`

Nguyên nhân: `app_services.py` import `db`, `home_engines`, `last_results`,
`alert_throttle` **theo giá trị** từ `app_state`. Fixture test thay
`app_state.db` bằng database tạm, nhưng route vẫn đọc database thật đã bind
lúc import. Ngoài lỗi test, đây còn là rủi ro cô lập dữ liệu: test có thể
đọc/ghi nhầm `data/smarthome.db`.

Checkpoint trước đó ghi nhận **17 failed** do `security_middleware.py` cũ
rate-limit cả trang `/`, static và dùng chung IP cho mọi test. Bản refactor
đã bỏ middleware này; phiên 10 viết lại và nối lại đúng cách.

## 2. Lỗi đã xác định và cách sửa

| # | Mức | Lỗi | Sửa |
|---|---|---|---|
| 1 | Cao | `app_services` giữ `db`/`home_engines`/`last_results`/`alert_throttle` theo giá trị | `import app_state`, truy cập động `app_state.db…`; `app.py` dùng `__getattr__` để `appmod.db` cũng thấy DB mới |
| 2 | Cao | Tin `X-Forwarded-For` vô điều kiện → client tự giả header để vượt rate limit | Chỉ dùng XFF khi `SMART_HOME_TRUST_PROXY=1`; mặc định dùng `remote_addr` |
| 3 | Cao | Rate limit áp lên cả `/`, `/static/*`, `/service-worker.js` → dashboard poll 3 request/2 giây bị 429 oan | Chỉ áp lên `/api/*`; ngưỡng thực tế: auth 30/phút, collect/scan/sensor 240/phút, API chung 300/phút |
| 4 | Trung bình | `request.view_args.items()` là `None` khi URL không khớp route → 404 thành 500 | Dùng `(request.view_args or {})` |
| 5 | Trung bình | `Permissions-Policy` đặt `accelerometer=(), gyroscope=()` → iPhone chặn DeviceMotion | Đổi thành `accelerometer=(self), gyroscope=(self), magnetometer=(self)` |
| 6 | Trung bình | Gửi HSTS cả khi chạy HTTP trong LAN | Chỉ gửi HSTS khi `request.is_secure` |
| 7 | Trung bình | `RateLimiter` không khóa, không giới hạn bộ nhớ | Thêm `threading.Lock`, dọn cửa sổ hết hạn, trần 4096 client cho cả `_requests` và `_blocked` |
| 8 | Trung bình | API trả HTML cho 400/404/413/500 → Android/PWA không đọc được `error` | Error handler trả JSON cho `/api/*`; trang HTML giữ trang lỗi mặc định |
| 9 | Trung bình | `max_dwell_minutes`, RSSI, timestamp nhận `NaN`/`Infinity` | `finite_float()` từ chối NaN/Infinity; dwell giới hạn 1–1440 phút |
| 10 | Thấp | `platform` thiết bị không giới hạn độ dài, hiển thị lại trên dashboard | Cắt tối đa 40 ký tự, fallback `android` |
| 11 | Thấp | Thiếu `/api/health` dù middleware có ý định bỏ qua health check | Thêm health check công khai, kiểm tra `SELECT 1`, trả 503 khi DB lỗi |
| 12 | Thấp | Android `allowBackup="true"` → session cookie/token có thể bị lấy qua backup | Đổi `android:allowBackup="false"` |
| 13 | Thấp | `alerts.webhook_url` có trong config nhưng không có code gửi | Gửi webhook CRITICAL trong thread nền: timeout 5 giây, không theo redirect |
| 14 | Chức năng | Backend có `PATCH /api/rooms/<id>` nhưng UI không có nút đổi tên phòng | Thêm nút **Đổi tên**, gửi lại `max_dwell_minutes` cũ để không đổi ngưỡng lưu trú |
| 15 | Phòng thủ | Chưa có lớp CSRF thứ hai ngoài cookie `SameSite=Lax` | Thao tác ghi có body bắt buộc `Content-Type: application/json`; POST không body vẫn hợp lệ |

## 3. Thay đổi theo file

- `server/security_middleware.py` — viết lại toàn bộ: rate limit theo IP + nhóm
  endpoint, request guard JSON-only, lọc SQLi/XSS ở query/path, header bổ sung,
  JSON error handler, `reset_rate_limits(app)`.
- `server/app.py` — nối middleware vào `create_app()`; thêm `/api/health`; bí
  danh động cho test/script cũ (`appmod.db`, `appmod.persist_result`…).
- `server/app_services.py` — bỏ import theo giá trị; thêm `finite_float()`,
  `notify_alert()`, `_post_webhook()`; `persist_result()` nhận `home_name`.
- `server/routes/room_views.py` — validate dwell hữu hạn/trong khoảng; cap
  `platform`; giữ mã lỗi 409 cho trùng tên phòng.
- `server/routes/track_views.py` — validate RSSI/timestamp hữu hạn; cap
  `orientation`, `device_id`; truyền tên nhà vào `persist_result`; webhook cho
  cảnh báo cảm biến CRITICAL.
- `server/static/app.js` — nút đổi tên phòng + handler `renameRoom()`.
- `server/static/account.css` — `.row-actions` và nút phụ màu xanh.
- `server/static/service-worker.js` — bump cache `an-tam-home-v5`.
- `android_collector/app/src/main/AndroidManifest.xml` — `allowBackup="false"`.
- `tests/test_api_integration.py` — fixture reset rate limit; thêm 12 test hồi quy.
- `README.md`, `.env.example` — hướng dẫn health, rate limit, trust proxy, CSRF.
- `config.yaml` — giữ `alerts.webhook_url` (nay đã có code dùng).

## 4. Kiểm chứng

### Unit/integration test

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m pytest tests -q
```

Kết quả thật: **63 passed** (51 test cũ + 12 test mới).

Các test mới bao phủ:

- health công khai và health degraded khi DB lỗi;
- 404 API trả JSON;
- POST body `text/plain` bị 415;
- `Permissions-Policy` cho phép accelerometer/gyroscope; HSTS chỉ trên HTTPS;
- dwell `NaN`/`Infinity`/âm/quá lớn bị 400;
- RSSI `NaN`/`Infinity` bị 400;
- `platform` bị cắt 40 ký tự;
- `X-Forwarded-For` bị bỏ qua mặc định, chỉ dùng khi bật trust proxy;
- rate limiter chặn rồi reset được;
- webhook CRITICAL có `home`/`home_id`, không redirect; WARNING không gửi.

### Chạy server thật

Dùng DB tạm trong `%TEMP%`, không đụng `data/smarthome.db`:

```text
SMOKE OK
```

Các bước đã chạy qua HTTP thật:

1. `GET /api/health` → 200, `database=ok`.
2. `GET /api/khong-ton-tai` → 404 JSON `NOT_FOUND`.
3. `GET /` → 200; `Permissions-Policy` có `accelerometer=(self)`,
   `gyroscope=(self)`; không có HSTS trên HTTP; CSP vẫn có.
4. Đăng ký tài khoản → tạo phòng → `PATCH` đổi tên → `GET /api/rooms` thấy tên mới.
5. Gửi `max_dwell_minutes: NaN` → 400.
6. POST `text/plain` tới `/api/auth/logout` → 415 JSON.
7. `POST /api/reset` không body → 200.
8. Gửi liên tục `/api/status` → xuất hiện 429 kèm `Retry-After`; `GET /` vẫn 200.

## 5. Rủi ro còn lại

- **Rate limit nằm trong RAM, theo từng tiến trình.** Chạy nhiều worker thì mỗi
  worker có bộ đếm riêng; với máy chủ gia đình một tiến trình là đủ.
- **Chưa có CSRF token.** Đang dựa vào `SameSite=Lax` + JSON-only + không bật
  CORS. Nếu sau này mở CORS cho domain khác, phải thêm token hoặc kiểm tra
  `Origin`.
- **`SMART_HOME_TRUST_PROXY=1` là nguy hiểm nếu bật sai.** Chỉ bật khi có
  reverse proxy tin cậy thật sự.
- **HTTP trong LAN là cleartext.** iPhone cần HTTPS để dùng DeviceMotion; xem
  hướng dẫn SSL trong README.
- **Webhook không có retry/queue.** Mất mạng đúng lúc cảnh báo thì webhook mất;
  cảnh báo vẫn nằm trong bảng `alerts` của SQLite.
- **G1/G2/G3/G4 của kế hoạch viết lại vẫn dở.** Phiên này chỉ hoàn thiện phần
  bảo mật + vá lỗi cô lập dữ liệu + nâng cấp nhỏ; chưa làm SSE, tách `app.js`,
  multi-task/ensemble hay sinh lại báo cáo.
- **Trạng thái git:** commit `360eb59` (message "Phien 9-G1…") đã được tạo bởi
  một tiến trình khác trong lúc phiên này đang chạy, chứa phần lớn thay đổi code.
  Phiên này không chạy `git commit`/`git push`. Sau commit, working tree chỉ còn
  `PROGRESS.md` (mục phiên 10) và bản cập nhật của chính tài liệu này; chờ người
  dùng duyệt trước khi làm gì thêm với git.
