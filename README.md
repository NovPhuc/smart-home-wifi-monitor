# An Tâm Home — Smart Home WiFi Monitor

Ứng dụng định vị trong nhà ở **mức phòng** bằng WiFi Fingerprinting, phát hiện chuyển động và nhận diện các dấu hiệu sinh hoạt bất thường nhằm hỗ trợ gia đình giám sát an toàn cho người cao tuổi.

> **Giới hạn an toàn:** hệ thống Wi‑Fi-only có thể ước lượng vị trí phòng, mức vận động, bất động kéo dài và quỹ đạo bất thường. Đây không phải thiết bị y tế và không xác nhận một người đã té ngã. Muốn phát hiện té ngã thực sự cần thêm IMU/accelerometer/gyroscope hoặc cảm biến chuyên dụng.

## Tính năng

- Đăng ký/đăng nhập; mỗi tài khoản quản lý nhiều ngôi nhà và tự đặt tên phòng.
- Quy trình hiệu chuẩn bắt buộc: đi trong từng phòng, thu tối thiểu 100 mẫu qua 3 phiên và 3 hướng cầm điện thoại trước khi định vị.
- SQLite lưu dài hạn tài khoản, nhà/phòng, thiết bị, fingerprint, dự đoán, cảm biến và cảnh báo.
- RoomNet‑Lite phân loại fingerprint RSSI; Bayesian Filter làm mượt dự đoán theo topology căn nhà.
- Phát hiện `STILL`, `LIGHT_ACTIVITY`, `MOVING` và `ROOM_CHANGE` từ biến động RSSI.
- Theo dõi thời gian ở phòng, thời gian không hoạt động, số lần chuyển phòng trong một giờ và chất lượng tín hiệu.
- GRU Autoencoder kết hợp rule engine phát hiện lưu trú quá lâu, chuyển phòng bất khả thi và hoạt động ban đêm bất thường.
- Dashboard responsive bằng tiếng Việt, sơ đồ phòng, lịch sử, cảnh báo và chế độ demo không cần điện thoại.
- Android Collector thu scan Wi‑Fi thật, tự nhận hướng cầm máy và xác thực bằng mã ghép nối riêng cho từng nhà.
- PWA cài được lên Màn hình chính iPhone, hỗ trợ safe area, chế độ standalone và cache giao diện.
- Sensor Bridge nhận gia tốc kế iPhone sau khi người dùng cấp quyền để bổ sung tín hiệu vận động/va chạm.
- Dashboard hiển thị Accuracy, Macro F1, Precision/Recall và độ trễ theo đúng tiêu chí đề cương.

## Chạy nhanh

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="src"
$env:SMART_HOME_SECRET_KEY="thay-bang-chuoi-bi-mat-dai-va-ngau-nhien"
python server/app.py
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python server/app.py
```

Mở `http://127.0.0.1:5000`, đăng ký tài khoản, tạo nhà và các phòng. Có thể dùng **Chế độ demo** để xem giao diện trước khi thu dữ liệu thật; dữ liệu demo không được ghi lẫn vào tập huấn luyện.

## Database SQLite

Mặc định dữ liệu nằm tại `data/smarthome.db`. SQLite tự tạo file và dùng WAL để ghi ổn định lâu dài. Có thể đổi vị trí bằng biến môi trường:

```powershell
$env:SMART_HOME_DATABASE="D:\AnTamData\smarthome.db"
```

Mật khẩu được băm, mã thiết bị chỉ hiện đầy đủ một lần và trong database chỉ lưu SHA‑256. Không đưa file `.db`, khóa bí mật hoặc mã ghép nối lên Git. Nên sao lưu cả file `.db` khi server đã dừng hoặc dùng công cụ backup SQLite.

## Chạy trên iPhone

Dashboard hoạt động dưới dạng PWA trên Safari. Để cài và dùng cảm biến chuyển động, iPhone phải truy cập backend qua **HTTPS**:

```powershell
$env:SMART_HOME_SSL_CERT="C:\certs\home-cert.pem"
$env:SMART_HOME_SSL_KEY="C:\certs\home-key.pem"
$env:PYTHONPATH="src"
python server/app.py
```

Trên iPhone, mở URL HTTPS của máy chủ bằng Safari, chọn **Chia sẻ → Thêm vào MH chính**, rồi mở ứng dụng và bấm **Bật cảm biến iPhone**.

Giới hạn nền tảng: iOS không cung cấp API công khai để ứng dụng thường quét danh sách access point và RSSI xung quanh như Android. Vì vậy:

- Android, ESP32 hoặc access point/router vẫn là nguồn fingerprint Wi‑Fi cho mô hình định vị phòng.
- iPhone dùng để xem dashboard, nhận cảnh báo và gửi dữ liệu gia tốc kế khi PWA đang mở.
- Sensor Bridge chỉ ghi nhận tín hiệu va chạm cần kiểm tra, không xác nhận té ngã.

## Kiến trúc

```text
Android WiFi Collector / Demo fingerprints
                 │ RSSI theo AP/BSSID
                 ▼
    Absolute RSSI + Relative RSSI + Missing Mask
                 ▼
       RoomNet-Lite + Bayesian Topology Filter
                 │
          vị trí mức phòng
          ┌──────┴────────┐
          ▼               ▼
  RSSI Activity Monitor   GRU Autoencoder + Rules
          └──────┬────────┘
                 ▼
       NORMAL / WARNING / CRITICAL
                 ▼
          Flask API + Dashboard
```

## API chính

| Method | Endpoint | Công dụng |
|---|---|---|
| `POST` | `/api/auth/register`, `/api/auth/login` | Tạo tài khoản, đăng nhập bằng session bảo mật |
| `GET/POST` | `/api/homes` | Liệt kê hoặc tạo nhà |
| `GET/POST` | `/api/rooms` | Liệt kê hoặc tạo phòng trong nhà đang chọn |
| `PATCH/DELETE` | `/api/rooms/<id>` | Đổi tên/ngưỡng lưu trú hoặc xóa phòng |
| `POST` | `/api/devices` | Tạo mã ghép nối Android; mã đầy đủ chỉ trả về một lần |
| `GET` | `/api/calibration` | Tiến độ mẫu, phiên và hướng cầm theo từng phòng |
| `POST` | `/api/scan` | Định vị từ RSSI thật sau khi hiệu chuẩn và huấn luyện xong |
| `POST` | `/api/collect` | Lưu fingerprint có nhãn phòng vào SQLite |
| `POST` | `/api/training/start` | Huấn luyện model riêng cho nhà đang chọn ở tiến trình nền |
| `GET` | `/api/export/scans.csv` | Xuất dữ liệu fingerprint của nhà đang chọn |
| `GET` | `/api/status` | Vị trí, vận động, tín hiệu và mức an toàn hiện tại |
| `GET` | `/api/history` | Dòng thời gian dự đoán |
| `GET` | `/api/alerts` | Danh sách cảnh báo |
| `GET` | `/api/stream` | SSE realtime: đẩy `status`, `history`, `alerts`; dashboard tự fallback về polling nếu stream lỗi |
| `POST` | `/api/demo/scan` | Phát một fingerprint mẫu; có thể truyền `{ "room": "Kitchen" }` |
| `GET` | `/api/config` | Danh sách phòng và topology công khai |
| `GET` | `/api/metrics` | Accuracy, F1, Precision/Recall, độ trễ và baseline |
| `POST` | `/api/sensor` | Nhận gia tốc tuyến tính `{x, y, z}` từ iPhone/PWA |
| `GET` | `/api/sensor/status` | Trạng thái cảm biến điện thoại gần nhất |
| `POST` | `/api/reset` | Bắt đầu lại phiên giám sát |
| `GET` | `/api/health` | Health check công khai: trạng thái server và database |

## Bảo mật và vận hành

- **HTTPS:** đặt `SMART_HOME_SSL_CERT` + `SMART_HOME_SSL_KEY`; khi đó cookie session tự bật `Secure` và server gửi HSTS. Chạy HTTP trong LAN thì không gửi HSTS (tránh trình duyệt ghi nhớ nhầm).
- **Session:** cookie tên `session`, `HttpOnly`, `SameSite=Lax`. Không đổi tên cookie vì Android Collector lưu/khôi phục phiên theo tên này.
- **Rate limit:** chỉ áp lên `/api/*` (dashboard/static không bị chặn). Vượt ngưỡng trả `429` kèm `Retry-After`. Nếu server nằm sau reverse proxy tin cậy, đặt `SMART_HOME_TRUST_PROXY=1` để dùng `X-Forwarded-For`; **không bật** khi client kết nối trực tiếp, nếu không client tự giả header sẽ vượt được giới hạn.
- **Realtime:** dashboard mở `EventSource('/api/stream')`; máy chủ chỉ đẩy event khi dữ liệu đổi, gửi heartbeat 15 giây và giới hạn 32 kết nối. Stream kiểm tra lại quyền xem mỗi 2 giây nên thành viên bị gỡ sẽ mất kết nối. Nếu SSE lỗi, dashboard tự quay về polling 3 endpoint như cũ.
- **Giao diện:** `server/static/app.js` chỉ là entry; các phần xác thực, dashboard, SSE, phòng/thiết bị, demo, cảm biến, huấn luyện và chia sẻ nằm trong `server/static/js/`. Không cần bước build; service worker cache `an-tam-home-v6` chứa đủ module.
- **Ghi dữ liệu:** mọi `POST/PUT/PATCH/DELETE` có body phải gửi `Content-Type: application/json` (lớp phòng thủ CSRF thứ hai). Các POST không body như `/api/auth/logout`, `/api/reset`, `/api/training/start` vẫn hợp lệ.
- **Lỗi API:** luôn trả JSON `{"error": "...", "message": "..."}` cho `/api/*`, kể cả 400/404/413/500.
- **Webhook cảnh báo:** đặt `alerts.webhook_url` trong `config.yaml` để nhận POST JSON khi có cảnh báo `CRITICAL` (timeout 5 giây, không theo redirect). Để trống thì tắt.
- **Android:** `android:allowBackup="false"` để session cookie/token không bị lôi ra qua backup ADB hoặc cloud backup.

## Thu dữ liệu thật bằng Android

1. Trên dashboard: đăng nhập → chọn/tạo nhà → tạo tất cả phòng → **Tạo mã ghép nối**.
2. Build APK debug bằng Android Studio (mở thư mục `android_collector/` rồi Run) hoặc chạy `gradlew assembleDebug`; APK nằm tại `android_collector/app/build/outputs/apk/debug/app-debug.apk` (không lưu trong Git để repo gọn).
3. Điện thoại và server dùng cùng LAN. Nhập URL server, ví dụ `http://192.168.1.10:5000`, rồi dán mã ghép nối.
4. Chọn đúng tên phòng và mã phiên (`S01`, `S02`, `S03`). Bấm **Thu tự động**, đi khắp phòng và lần lượt cầm máy dọc, ngang, đặt phẳng.
5. Mỗi phòng cần tổng ít nhất 100 mẫu, 3 phiên và 3 hướng. Thu các phiên ở thời điểm/vị trí khác nhau; dashboard hiển thị tiến độ.
6. Khi mọi phòng đạt chuẩn, bấm **Huấn luyện mô hình** trên dashboard. Định vị thật chỉ được mở khóa sau khi model của nhà ở trạng thái `READY`.

Huấn luyện thủ công cho một nhà (thay `1` bằng ID nhà):

```powershell
$env:PYTHONPATH="src"
python scripts/train_home.py --home-id 1
```

Android băm BSSID trước khi gửi (`AP_...`), không lưu SSID/mật khẩu Wi‑Fi. Android có thể giới hạn tần suất quét; collector dùng chu kỳ 3 giây và kết quả vẫn phụ thuộc thiết bị/router thực tế.

## Kiểm thử

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python.exe -m pytest -q
```

Các model `.pt` đi kèm được huấn luyện bằng dữ liệu tổng hợp để kiểm tra pipeline và demo. Kết quả nghiên cứu chính thức phải dùng RSSI thu trong căn nhà thực tế, trên thiết bị mục tiêu, và chia train/validation/test theo session hoặc theo ngày để tránh rò rỉ dữ liệu.

Tài liệu phương pháp và thực nghiệm chi tiết nằm trong thư mục [`docs/`](docs/).
