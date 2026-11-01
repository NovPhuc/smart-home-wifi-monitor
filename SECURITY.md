# Bảo mật hệ thống — An Tâm Home (bản 2310)

Tài liệu tổng hợp các lớp bảo mật đã triển khai, lý do lựa chọn và cách cấu
hình khi vận hành thật. Thiết kế bám theo bối cảnh **máy chủ gia đình trong
LAN + tunnel HTTPS** của khóa luận, ưu tiên đơn giản, không cần dịch vụ ngoài.

## 1. Các lớp bảo mật

### 1.1. Xác thực và phiên

- Mật khẩu băm bằng Werkzeug (`generate_password_hash`, PBKDF2-SHA256);
  không bao giờ lưu/gửi mật khẩu thô.
- Session cookie: `HttpOnly`, `SameSite=Lax`, `Secure` khi bật
  `SMART_HOME_SECURE_COOKIE=1` hoặc server chạy HTTPS thật.
- Khóa ký session: lấy từ `SMART_HOME_SECRET_KEY`; thiếu thì tự sinh và lưu
  `data/secret_key` (không vào Git) — bản cũ dùng chuỗi cố định công khai.
- Thiết bị thu thập: Bearer token 28 ký tự, lưu **SHA-256 hash** trong bảng
  `collector_devices`, chỉ hiển thị một lần lúc tạo, thu hồi được.

### 1.2. Phân quyền

- Tài khoản thành viên tham gia qua **mã chia sẻ 6 số** chỉ được **xem**:
  vị trí, lịch sử, cảnh báo, tiến độ hiệu chuẩn, metric.
- Mọi thao tác ghi (phòng, thiết bị, thu thập, huấn luyện, xóa) yêu cầu chủ
  nhà (`HOME_OWNER_REQUIRED`). `require_mutation_context` cũng chặn tài
  khoản chia sẻ ghi dữ liệu qua session.

### 1.3. Rate limiting (server/security_middleware.py)

Sliding window trong RAM theo (nhóm endpoint, client IP+UA), chặn 60 giây
khi vượt ngưỡng:

| Nhóm | Ngưỡng | Ghi chú |
|------|--------|---------|
| `auth` (đăng nhập, đăng ký, tham gia nhà) | 30/phút | kết hợp với `AttemptLimiter` chặn dò theo email |
| `collect` / `scan` / `sensor` | 240/phút | đủ cho phiên hiệu chuẩn ~200 mẫu |
| `api` (còn lại) | 300/phút | dashboard hỏi 3 request/2 giây ≈ 90/phút |

- `/static/*` và `/api/health` không giới hạn.
- Chỉ đặt `SMART_HOME_TRUST_PROXY=1` khi server thật sự sau reverse proxy
  tin cậy; bật sai cho phép client tự khai `X-Forwarded-For` vượt hạn mức.

### 1.4. Request guard và input validation

- Bắt buộc `Content-Type: application/json` cho POST/PUT/PATCH/DELETE
  (lớp phòng CSRF thứ hai bên cạnh cookie SameSite).
- Giới hạn body 1 MB (`MAX_CONTENT_LENGTH`).
- Chặn sớm query/path chứa mẫu SQL injection/XSS (OWASP); lớp chốt vẫn là
  truy vấn tham số hóa và Jinja escape.

### 1.5. Security headers

| Header | Giá trị |
|--------|---------|
| Content-Security-Policy | `default-src 'self'` — không `unsafe-eval` |
| X-Content-Type-Options | `nosniff` |
| X-Frame-Options | `DENY` (+ `frame-ancestors 'none'`) |
| Strict-Transport-Security | chỉ gửi khi kết nối thật là HTTPS |
| Permissions-Policy | `accelerometer=(self), gyroscope=(self)` (dashboard dùng DeviceMotion), còn lại `()` |
| Cross-Origin-Opener/Resource-Policy | `same-origin` |
| Cache-Control | `no-store` cho mọi `/api/*` |

Lỗi API trả JSON có mã lỗi chuẩn (400/401/403/404/409/413/415/429), không lộ
stack trace cho client.

### 1.6. HTTPS và certificate pinning

- Server: `python server/app.py` với `SMART_HOME_SSL_CERT`/`SMART_HOME_SSL_KEY`
  sẽ chạy HTTPS thật (SSL context, cookie Secure tự bật).
- Android (`android_collector`): `network_security_config.xml` + lớp
  `CertificatePinner` ghim SPKI SHA-256 cho mọi kết nối **https://** (tunnel,
  domain). Pin đọc từ `res/raw/cert_pins.txt`, sinh bằng:

  ```powershell
  openssl x509 -in cert.pem -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64
  ```

- **Thỏa thuận thiết kế có chủ đích**: kết nối **http:// trong LAN do NSD tự
  tìm** không ghim pin (HTTP không có chứng chỉ). Máy chủ gia đình không có
  chứng chỉ công khai cho địa chỉ LAN; dữ liệu thu là RSSI với BSSID đã băm
  SHA-256, ranh giới tin cậy của LAN là điểm truy cập WiFi. Khi ra ngoài LAN
  (qua tunnel), đường truyền bắt buộc là HTTPS có ghim.

### 1.7. Chống trùng dữ liệu và hash BSSID

- `src/smarthome/ap_hashing.py`: `hash_bssid` viết thường BSSID trước khi
  băm — script PC (netsh trả chữ hoa) và Android (trả chữ thường) cho
  **cùng một tên AP**; vector kiểm chứng trong `tests/test_core.py`.
- `record_wifi_scan` loại bản trùng theo (a) cùng `scan_timestamp` từ client,
  hoặc (b) client cũ: nội dung RSSI giống hệt trong vòng 10 giây. Schema v3
  thêm `scan_ts`, `wifi_hash` bằng migration `ALTER TABLE` an toàn, dữ liệu
  cũ không bị đụng.

### 1.8. Webhook cảnh báo CRITICAL

- `alerts.webhook_url` trong `config.yaml` (ntfy.sh/Telegram gateway/HTTP tùy
  chọn). Cảnh báo CRITICAL (va chạm, nghi ngờ té ngã, bất thường nghiêm trọng)
  được đẩy ra webhook trong thread nền, timeout 5 giây, không theo redirect,
  lỗi không làm hỏng pipeline suy luận.

## 2. Biến môi trường

| Biến | Ý nghĩa | Mặc định |
|------|---------|----------|
| `SMART_HOME_SECRET_KEY` | khóa ký session (32 byte hex) | tự sinh, lưu `data/secret_key` |
| `SMART_HOME_SECURE_COOKIE` | `1` = cookie chỉ qua HTTPS | `0` |
| `SMART_HOME_SSL_CERT` / `SMART_HOME_SSL_KEY` | chứng chỉ HTTPS của server | không đặt = HTTP LAN |
| `SMART_HOME_TRUST_PROXY` | `1` = tin `X-Forwarded-For` | `0` |
| `SMART_HOME_DATABASE` | đường dẫn SQLite | `data/smarthome.db` |

## 3. Checklist vận hành

- [ ] Đặt `SMART_HOME_SECRET_KEY` hoặc xác nhận `data/secret_key` đã tồn tại.
- [ ] Khi ra ngoài LAN: tạo cặp cert (tự ký hoặc tunnel), đặt
      `SMART_HOME_SSL_CERT/KEY`, bật `SMART_HOME_SECURE_COOKIE=1`.
- [ ] Sinh pin từ chứng chỉ, điền vào `cert_pins.txt` và
      `network_security_config.xml`, thay domain placeholder.
- [ ] Cấu hình `alerts.webhook_url` nếu muốn cảnh báo đẩy ra ngoài.
- [ ] Chạy `python scripts/security_audit.py` để kiểm tra lại toàn bộ.
- [ ] Không commit `.env`, `data/secret_key`, chứng chỉ khóa riêng.

## 4. Phản ứng sự cố

1. Đổi `SMART_HOME_SECRET_KEY` (hủy mọi session cũ), thu hồi token thiết bị
   nghi vấn trong dashboard.
2. Rà log `[Bao mat]` — rate limit và mẫu tấn công bị chặn đều có cảnh báo.
3. Luân chuyển chứng chỉ: sinh pin mới, thêm vào `cert_pins.txt` (giữ pin cũ
   đến khi toàn bộ thiết bị cập nhật).
