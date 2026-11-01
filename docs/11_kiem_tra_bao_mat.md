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

---

## 7. Soát lại sau khi tách `app.py` thành module (phiên 9)

Phiên 9 tách `app.py` (917 dòng) thành `app_state`, `app_security`, `app_services`,
`security_middleware` và `routes/` (5 blueprint). Rủi ro lớn nhất của kiểu tách này là
**một endpoint bị mất trang trí `@login_required`** — không có gì báo lỗi, chỉ âm thầm hở.
Vì vậy tôi kiểm bằng cách liệt kê URL map rồi gọi **không kèm phiên đăng nhập**.

### 7.1 Quét phân quyền — `scripts/security_sweep.py`

```
Đã quét 39 tổ hợp (route, method) trong 34 route /api/*
Không endpoint nào trả dữ liệu khi chưa xác thực (ngoài danh sách công khai).
Danh sách công khai có chủ đích: /api/auth/login, /api/auth/logout,
                                 /api/auth/register, /api/health
```

Mỗi tổ hợp được gọi **hai lần**: một lần không có phiên, một lần kèm
`Authorization: Bearer ath_khong-he-ton-tai` — để bắt cả trường hợp token sai bị
âm thầm hạ cấp thành quyền của session. Không trường hợp nào trả 200.

Lưu ý: `POST /api/auth/logout` trả 200 khi chưa đăng nhập là **đúng**, không phải hở —
nó chỉ xoá một phiên rỗng, không tiết lộ dữ liệu và không thao tác lên dữ liệu của ai.
Script đã ghi rõ lý do trong danh sách công khai.

### 7.2 Các lớp bảo mật mới — đã kiểm chứng sống

| Lớp | Cách kiểm chứng | Kết quả |
|---|---|---|
| Giới hạn tần suất theo nhóm endpoint | Gửi 35 request tới `/api/auth/login` (nhóm `auth` = 30/60s) | 30 request đầu → 401, request 31–35 → **429**. Đúng ngưỡng |
| `X-Forwarded-For` không được tin mặc định | 35 request, **mỗi request một XFF khác nhau** | Vẫn bị chặn ở request 31 ⇒ header không làm thay đổi danh tính client. Chỉ tin khi `SMART_HOME_TRUST_PROXY=1` |
| Chặn body không phải JSON cho thao tác ghi (lớp CSRF thứ hai) | POST `/api/rooms` với `text/plain` và `application/x-www-form-urlencoded` | Cả hai → **415**. Đây là thứ HTML form không thể vượt qua |
| HSTS chỉ khi HTTPS | Đọc mã + chạy HTTP | Không gửi HSTS trên kết nối không TLS |
| Lỗi API trả JSON, không lộ nội bộ | Đọc mã | Log traceback ở server, client chỉ nhận `{"error":"INTERNAL_ERROR"}` |

Mã `RateLimiter` dùng `time.monotonic()` (không bị ảnh hưởng khi đồng hồ hệ thống đổi),
có `threading.Lock`, và có trần `MAX_TRACKED_CLIENTS = 4096` kèm dọn cửa sổ cũ — nên
kẻ đổi IP liên tục không làm phình bộ nhớ.

### 7.3 Ghi nhận (không phải lỗ hổng)

`security_middleware` có thêm lớp lọc mẫu SQLi/XSS bằng regex trên query/path. Đây
**không phải biện pháp bảo vệ** — regex danh sách đen luôn bypass được, và lớp này không
hề chạm tới JSON body (nơi tên phòng/tên nhà thực sự nằm). Nó được ghi chú đúng vai trò
là "chặn sớm request tầm thường để đỡ nhiễu log"; hàng rào thật vẫn là truy vấn tham số
hoá + Jinja escape, và cả hai đều đã có. Điểm cần lưu ý là **rủi ro chặn nhầm** nếu sau
này có endpoint nhận chuỗi tự do qua query string.

### 7.4 Kiểm chứng cuối phiên 9

```
python scripts/security_sweep.py   -> 39 tổ hợp, 0 hở phân quyền
pytest tests -q                    -> 79 passed
node C:\chorus\selftest-mcp.js     -> 28/28 đạt
node C:\chorus\security-probe.js   -> 0 lỗ hổng / 12 hạng mục
```

---

## 8. Lỗ hổng NGHIÊM TRỌNG trong cert pinning của app Android (đã vá)

`android_collector` có lớp "certificate pinning" cho kết nối HTTPS. Lớp này **tự viết
`X509TrustManager`** và cài đè lên mặc định của Android:

```kotlin
override fun checkServerTrusted(chain, authType) {
    chain.forEach { it.checkValidity() }        // chỉ xem hạn dùng
    if (pins.isNotEmpty() && chain.none { pinOf(it) in pins }) throw ...
}
override fun getAcceptedIssuers() = arrayOf()
```

### Vì sao đây là lỗ hổng

`checkServerTrusted` **không hề xác thực chuỗi chứng chỉ tới một root tin cậy**. Nó chỉ
kiểm tra ngày hết hạn và (khi có pin) kiểm tra pin. Nghĩa là khi chưa cấu hình pin, **mọi
chứng chỉ tự ký đều được chấp nhận** — chứng chỉ của kẻ tấn công cũng vậy.

Tệ hơn, `HostnameVerifier` được thay bằng:

```kotlin
fun isPinned(hostname, session, context): Boolean {
    val pins = loadPins(context)
    if (pins.isEmpty()) return true     // <-- luôn đúng tên miền
    ...
}
```

⇒ khi chưa có pin, **kiểm tra tên miền cũng bị tắt**.

### Trạng thái mặc định là trạng thái dính lỗi

`app/src/main/res/raw/cert_pins.txt` chỉ chứa **dòng chú thích**; `loadPins()` lọc bỏ chúng
và trả về danh sách rỗng. Vậy nhánh fail-open chính là nhánh **đang chạy trong bản build
thật**, đúng như nhận xét trong chính file đó ("chưa điền pin thật thì app vẫn chạy bằng
trust store hệ thống") — nhận xét này **sai**: trust store hệ thống không được dùng đến.

Hệ quả: mọi kết nối `https://` của app chấp nhận chứng chỉ bất kỳ và tên miền bất kỳ. Kẻ
tấn công trong cùng mạng có thể đánh tráo và đọc được **email + mật khẩu đăng nhập** và
**token thiết bị** gửi lên máy chủ. Đây là kiểu lỗi mà một tính năng bảo mật tự tạo ra lỗ
hổng: nếu không viết code pinning nào thì Android vẫn kiểm tra chuỗi chứng chỉ bình thường.

### Cách vá (đã áp dụng)

1. `defaultTrustManager()` lấy TrustManager mặc định từ `TrustManagerFactory` với trust
   store hệ thống.
2. `checkServerTrusted` **uỷ thác cho mặc định trước** (xác thực chuỗi tới root), rồi mới
   kiểm tra pin. `getAcceptedIssuers` trả về issuers thật thay vì mảng rỗng.
3. `pinnedSslContext()` trả về **null** khi chưa cấu hình pin; bên gọi giữ nguyên mặc định
   của Android thay vì cài TrustManager tự viết.
4. `verifyHostname()` luôn chạy `HttpsURLConnection.getDefaultHostnameVerifier()` trước,
   rồi mới áp pin nếu có. Chưa có pin ⇒ dùng đúng hành vi mặc định của Android.

Kiểm chứng: không còn tham chiếu `isPinned` nào; `gradlew assembleDebug` biên dịch thành
công (xem mục 9).

### Việc cần làm khi phát hành

`res/xml/network_security_config.xml` và `res/raw/cert_pins.txt` còn giữ chỗ trống
`REPLACE_WITH_PRIMARY_PIN` / `your-server-domain.example`. **Phải thay bằng giá trị thật
trước khi phát hành**, nếu không domain HTTPS sẽ bị ghim vào một chuỗi không tồn tại và mọi
kết nối tới domain đó sẽ thất bại (lỗi khả dụng, không phải lỗi bảo mật — nhưng người dùng
sẽ thấy app không kết nối được).

---

## 9. Kiểm chứng bản vá Android và sửa môi trường build

Bản vá ở mục 8 đã được **biên dịch thật**:

```
> Task :app:compileDebugKotlin
> Task :app:assembleDebug
BUILD SUCCESSFUL in 52s
33 actionable tasks: 33 executed
```

Chỉ còn 3 cảnh báo `deprecated` có sẵn từ trước (`resolveService`, `NsdServiceInfo.host`,
`WifiManager.startScan`) — không liên quan tới phần vừa sửa.

Để build được, phải sửa **hai lỗi môi trường** (không phải lỗi mã):

| Lỗi | Triệu chứng | Cách sửa |
|---|---|---|
| `android_collector/gradle.properties` ghim `org.gradle.java.home=C:/Program Files/Android/Android Studio/jbr` | Mọi lệnh `gradlew` chết ngay: *"Java home supplied is invalid"*. Android Studio trên máy này đã chuyển sang `E:\Android`. | Bỏ dòng ghim JDK khỏi file được commit; Gradle dùng `JAVA_HOME` của máy. Muốn ghim thì đặt biến môi trường. |
| `local.properties` trỏ `sdk.dir=E:\Android` | `E:\Android` chỉ chứa thư mục Android Studio, **không phải Android SDK** ⇒ Gradle báo thiếu `platforms;android-34` và `build-tools;34.0.0`. | SDK thật nằm ở `%LOCALAPPDATA%\Android\Sdk` (đã có android-33/34/35/36 và build-tools 34.0.0). Trỏ `sdk.dir` về đó. File này đã nằm trong `.gitignore` nên chỉ ảnh hưởng máy này. |

Cả hai lỗi đều **có sẵn từ trước**, không phát sinh do bản vá bảo mật.
