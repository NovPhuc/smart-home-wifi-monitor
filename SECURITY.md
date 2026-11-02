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

Sliding window theo (nhóm endpoint, **IP client** — không trộn User-Agent),
chặn 60 giây khi vượt ngưỡng. Lưu ở **RAM** mặc định; nếu đặt `REDIS_HOST` thì lưu ở **Redis** để nhiều instance chia sẻ hạn mức (xem §1.9):

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
  `CertificatePinner`. **Xác thực chuỗi chứng chỉ luôn do trust store hệ thống
  làm**; ghim SPKI SHA-256 là lớp **tăng cường thêm**, chỉ áp dụng khi
  `res/raw/cert_pins.txt` có ít nhất một pin thật. Chưa điền pin thì app dùng
  đúng hành vi mặc định của Android (không ghim thêm gì).

  > Bản trước đây tự viết một `X509TrustManager` chỉ kiểm tra hạn dùng chứng chỉ,
  > kèm `HostnameVerifier` trả về `true` khi chưa có pin — nên ở đúng trạng thái
  > mặc định (file pin chỉ có dòng chú thích) app chấp nhận **mọi** chứng chỉ và
  > **mọi** tên miền. Đã vá: uỷ thác xác thực chuỗi cho `TrustManagerFactory` mặc
  > định trước rồi mới áp pin; `pinnedSslContext()` trả `null` khi chưa cấu hình
  > pin để giữ nguyên mặc định của hệ thống. Chi tiết: `docs/11_kiem_tra_bao_mat.md` §8.

  Pin đọc từ `res/raw/cert_pins.txt`, sinh bằng:

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
- [ ] Chạy bộ kiểm tra ở §5 (ba script, mỗi cái một việc).
- [ ] Không commit `.env`, `data/secret_key`, chứng chỉ khóa riêng.

## 4. Phản ứng sự cố

1. Đổi `SMART_HOME_SECRET_KEY` (hủy mọi session cũ), thu hồi token thiết bị
   nghi vấn trong dashboard.
2. Rà log `[Bao mat]` — rate limit và mẫu tấn công bị chặn đều có cảnh báo.
3. Luân chuyển chứng chỉ: sinh pin mới, thêm vào `cert_pins.txt` (giữ pin cũ
   đến khi toàn bộ thiết bị cập nhật).

## 5. Bộ kiểm tra bảo mật

Ba script, mỗi cái một việc — đừng gộp chúng làm một vì mục đích khác nhau:

| Script | Việc | Kết quả |
|--------|------|---------|
| `scripts/security_audit.py` | Kiểm tra **cấu hình đang chạy**: các lớp bảo mật có mặt, `data/secret_key`, `.env`, HTTPS, webhook | In `[OK]/[CANH BAO]/[THIEU]` ra màn hình |
| `scripts/full_security_audit.py` | Quét **mã nguồn tĩnh**: SQL injection, hardcoded secret, crypto yếu, rò log, dependency, DB, git history | Ghi `SECURITY_AUDIT_REPORT.md` |
| `scripts/security_sweep.py` | Quét **phân quyền**: gọi mọi route `/api/*` không kèm phiên, và một lần với bearer token sai | In danh sách endpoint hở (kỳ vọng: không có) |

```powershell
python scripts/security_audit.py          # cấu hình
python scripts/full_security_audit.py     # quét mã -> SECURITY_AUDIT_REPORT.md
python scripts/security_sweep.py          # quét phân quyền (cần PYTHONPATH=src)
```

### Đọc báo cáo

`SECURITY_AUDIT_REPORT.md` **sinh tự động**, đừng sửa tay. Chạy lại script rồi đọc lại —
nếu số liệu trong báo cáo khác với kết quả chạy mới nhất thì báo cáo đã cũ.

Hai lỗi false positive đã từng làm báo cáo sai nghiêm trọng (69 findings trong khi chỉ có
4 là thật), nay đã sửa trong scanner — ghi lại để không tái phạm khi thêm pattern mới:

1. `RC4|DES|ECB` khớp cả chuỗi **`DESC`** trong `ORDER BY ... DESC` và **`DES`** trong
   `description`/`oldest`. Phải dùng `\b(?:RC4|DES|ECB)\b` và phân biệt hoa thường.
2. `Log\.(d|i|w|e)\(.*password|token|secret` — thiếu nhóm nên phép `|` tách cả biểu thức,
   khiến **mọi dòng chứa chữ "token"** đều bị báo là ghi log bí mật (kể cả khai báo
   `private lateinit var collectorToken`). Phải là
   `Log\.(?:d|i|w|e)\([^)]*(?:password|token|secret)`.

### Ký hiệu miễn trừ

Dòng đã được soát tay và xác nhận an toàn thì thêm `# nosec` (hoặc `// nosec` cho Kotlin)
kèm lý do. Scanner bỏ qua những dòng này, và bỏ qua cả dòng bắt đầu bằng `#`.
Ví dụ: `f"SELECT COUNT(*) FROM {table} WHERE {key}=?"  # nosec — bảng cố định trong test`.
Đừng lạm dụng: mỗi `# nosec` là một chỗ ai đó phải tin, nên luôn ghi rõ vì sao.

### Kết quả lần chạy gần nhất

`full_security_audit.py` → **4 findings, tất cả INFO** (0 CRITICAL/HIGH/MEDIUM/LOW).
Cả 4 đều là thiết kế đã được chấp nhận và ghi trong tài liệu này:

| Finding | Xử lý |
|---------|-------|
| mDNS enabled | Cần cho tính năng tự tìm máy chủ; tắt bằng `mdns_enabled: false` nếu không dùng |
| Pin expiration `2027-11-01` | Nhắc luân chuyển chứng chỉ trước hạn — xem §4 |
| Cleartext HTTP tới LAN (`http://$host:$port`) | Thỏa thuận thiết kế ở §1.6 |
| `cleartextTrafficPermitted="true"` | Cùng lý do trên; HTTPS bắt buộc khi ra ngoài LAN |

`security_sweep.py` → **39 tổ hợp / 34 route `/api/*`, 0 endpoint hở phân quyền**
(chỉ 4 endpoint công khai có chủ đích: `login`, `logout`, `register`, `health`).

### 1.9. Lưu trữ phân tán cho trạng thái dùng chung (Redis)

Mặc định ứng dụng chạy một tiến trình và giữ hạn mức trong RAM. Khi chạy nhiều
instance (gunicorn nhiều worker, hoặc nhiều container sau load balancer), hạn mức
trong RAM là **mỗi tiến trình một bản** — 2 worker thì giới hạn thực tế gấp đôi.

Đặt `REDIS_HOST` (và tuỳ chọn `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`) để chuyển
hạn mức sang Redis dùng chung:

| | RAM (mặc định) | Redis (`REDIS_HOST` được đặt) |
|---|---|---|
| Phạm vi | một tiến trình | mọi instance dùng chung khoá |
| Cấu trúc | `deque` + `threading.Lock` | sorted set + script Lua |
| Redis chết | — | ghi cảnh báo, tự lùi về RAM cho tiến trình đó |

Script Lua gộp *trim → đếm → kiểm tra chặn → ghi* vào một lượt, nên không có khe
hở giữa lúc đọc và lúc ghi. Nếu tách thành hai lượt (đọc `ZCARD` rồi `ZADD`),
60 request đồng thời với ngưỡng 10 cho qua **29** request; sau khi gộp còn đúng
**10**. Đo bằng `scripts/rate_limit_probe.py`.

Khoá định danh client là **chỉ IP**, cố ý không trộn `User-Agent`: UA do client
tự đặt nên đưa vào khoá là tự cho kẻ tấn công thêm bucket mới mỗi request.

Nếu Redis chết giữa chừng, ứng dụng **không** im lặng: nó ghi cảnh báo
`[Redis] Không nối được ... RATE LIMIT CHẠY RAM, không chia sẻ giữa các instance`
để người vận hành biết mức bảo vệ đã giảm.
