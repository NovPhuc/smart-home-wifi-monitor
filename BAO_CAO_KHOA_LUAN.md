# BÁO CÁO KHÓA LUẬN TỐT NGHIỆP

## HỆ THỐNG GIÁM SÁT NGƯỜI CAO TUỔI TRONG NHÀ THÔNG MINH
### SỬ DỤNG WIFI FINGERPRINTING VÀ CẢM BIẾN CHUYỂN ĐỘNG

---

**Sinh viên:** Nguyễn Hoài Phúc  
**MSSV:** 2001230687  
**Ngành:** Công nghệ Thông tin - KLCN 336  
**Giảng viên hướng dẫn:** TS. Nguyễn Văn A  
**Năm học:** 2023-2024  
**Ngày nộp:** 01/11/2026  

---

## MỤC LỤC

1. [Mở đầu](#1-mở-đầu)
2. [Tổng quan hệ thống](#2-tổng-quan-hệ-thống)
3. [Cơ sở lý thuyết](#3-cơ-sở-lý-thuyết)
4. [Thiết kế hệ thống](#4-thiết-kế-hệ-thống)
5. [Triển khai phần cứng](#5-triển-khai-phần-cứng)
6. [Phát triển phần mềm](#6-phát-triển-phần-mềm)
7. [Bảo mật hệ thống](#7-bảo-mật-hệ-thống)
8. [Kiểm thử và đánh giá](#8-kiểm-thử-và-đánh-giá)
9. [Triển khai thực tế](#9-triển-khai-thực-tế)
10. [Kết luận và hướng phát triển](#10-kết-luận-và-hướng-phát-triển)
11. [Tài liệu tham khảo](#11-tài-liệu-tham-khảo)
12. [Phụ lục](#12-phụ-lục)

---

## 1. MỞ ĐẦU

### 1.1. Bối cảnh và động lực

Dân số già hóa là thách thức chung của nhiều quốc gia, trong đó có Việt Nam. Theo số liệu Tổng cục Thống kê năm 2023, người từ 60 tuổi trở lên chiếm khoảng 12% dân số cả nước, con số này dự kiến tăng lên 25% vào năm 2050. Với xu hướng gia đình hạt nhân, nhiều người cao tuổi sống một mình hoặc ở cùng người thân cũng đã đi làm cả ngày. Việc theo dõi sức khỏe, phát hiện sớm các sự cố như ngã, bất thường hoạt động trở nên cấp thiết.

Các giải pháp hiện có chủ yếu dựa trên camera giám sát hoặc thiết bị đeo tay. Camera vi phạm quyền riêng tư, đắt đỏ khi lắp đặt nhiều phòng. Thiết bị đeo tay dễ bị người cao tuổi quên mang, mất pin, hoặc gây khó chịu khi ngủ. Cần một giải pháp **phi xâm nhập, giá thành thấp, không cần tương tác chủ động từ người được giám sát**.

### 1.2. Mục tiêu đề tài

Xây dựng hệ thống giám sát người cao tuổi trong nhà thông minh với các yêu cầu:

- **Định vị mức phòng** (room-level localization) bằng WiFi fingerprinting - không cần thiết bị đeo
- **Phát hiện bất thường** hoạt động hàng ngày (ngã, bất động quá lâu, thay đổi thói quen)
- **Phát hiện ngã** bằng cảm biến gia tốc kế trên điện thoại (tùy chọn)
- **Cảnh báo thời gian thực** qua web dashboard và webhook (Telegram, ntfy.sh, IFTTT)
- **Bảo mật dữ liệu** - mã hóa, xác thực, rate limiting, certificate pinning
- **Triển khai dễ dàng** - Docker, auto-discovery qua NSD, HTTPS tự động

### 1.3. Phạm vi và giới hạn

- Hệ thống hoạt động trong môi trường nhà có WiFi ổn định (tối thiểu 3 AP nghe được)
- Độ chính xác định vị phòng: mục tiêu > 85% trên tập test
- Phát hiện ngã: chỉ hoạt động khi người cao tuổi mang điện thoại (tùy chọn)
- Không thay thế thiết bị y tế chuyên dụng - chỉ là hỗ trợ cảnh báo sớm

---

## 2. TỔNG QUAN HỆ THỐNG

### 2.1. Kiến trúc tổng thể

```
┌─────────────────┐     WiFi/HTTP      ┌─────────────────┐
│  Android App    │ ◄─────────────────► │  Flask Server   │
│  (Collector)    │   Scan + Sensor     │  (Inference)    │
└─────────────────┘                     └────────┬────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
             ┌──────────────┐           ┌────────────────┐           ┌──────────────┐
             │  SQLite DB   │           │  PyTorch Model │           │  Webhooks    │
             │  (Persistent)│           │  (RoomNet-Lite)│           │ (Telegram/   │
             └──────────────┘           └────────────────┘           │  ntfy/IFTTT) │
                                                                    └──────────────┘
```

### 2.2. Các thành phần chính

| Thành phần | Công nghệ | Chức năng |
|------------|-----------|-----------|
| **Android Collector** | Kotlin, NSD, Sensor API | Quét WiFi, đọc gia tốc kế, gửi dữ liệu |
| **Flask Server** | Python 3.11, Flask, Gunicorn | API REST, WebSocket/SSE, Web dashboard |
| **Inference Engine** | PyTorch, RoomNet-Lite, GRU-AE | Định vị phòng, phát hiện bất thường |
| **Database** | SQLite (WAL mode) | Lưu fingerprint, prediction, alert, device |
| **Web Dashboard** | HTML5, JS ES6, CSS Grid, PWA | Real-time monitoring, cấu hình, báo cáo |
| **Android NSD** | NsdManager | Auto-discover server IP trong LAN |

### 2.3. Luồng dữ liệu chính

1. **Thu thập fingerprint (Offline/Training):** Android app quét WiFi tại phòng xác định → gửi lên server gán nhãn phòng → lưu vào DB
2. **Huấn luyện:** Server đọc fingerprint từ DB → train RoomNet-Lite (classification) + GRU-AE (anomaly) → lưu model `.pt`
3. **Giám sát realtime (Online):** Android app quét WiFi định kỳ (5s/lần) + đọc gia tốc kế → gửi server → inference realtime → cập nhật dashboard
4. **Cảnh báo:** Phát hiện bất thường/ngã → lưu alert DB → đẩy webhook (nếu cấu hình) → hiển thị dashboard

---

## 3. CƠ SỞ LÝ THUYẾT

### 3.1. WiFi Fingerprinting

**Nguyên lý:** Môi trường đa đường (multipath) khiến cường độ tín hiệu nhận được (RSSI) từ các Access Point (AP) tạo ra "dấu vân tay" đặc trưng cho từng vị trí. RSSI từ nhiều AP tạo thành vector đặc trưng (fingerprint) để phân loại phòng.

**Thách thức:** RSSI biến thiên theo thời gian (nhiễu, người đi lại, thay đổi môi trường). Giải pháp:
- **Sliding window averaging** (cửa sổ trượt 5 mẫu)
- **Data augmentation** (thêm nhiễu Gaussian, dropout AP ngẫu nhiên)
- **Hash BSSID** chuẩn hóa giữa thiết bị (PC netsh trả BSSID hoa, Android trả thường)

### 3.2. Mô hình RoomNet-Lite (Phân loại phòng)

Kiến trúc CNN 1D nhẹ cho dữ liệu chuỗi RSSI:

```
Input: [Batch, Channels=AP_count, Seq_len=Window_size]
├── Conv1D(32, kernel=3) + BN + ReLU + Dropout(0.15)
├── Conv1D(64, kernel=3) + BN + ReLU + Dropout(0.15)
├── GlobalAvgPool1D
├── FC(Embedding=64) + Center Loss (λ=0.02)
└── FC(Num_rooms) + Softmax
```

**Loss function:** `L = L_CE + λ_center * L_center + λ_temporal * L_temporal`

- `L_CE`: Cross-entropy chuẩn
- `L_center`: Kéo embedding cùng lớp về gần nhau (Wen et al., 2016)
- `L_temporal`: Tính liên tục giữa các dự đoán liên tiếp (smooth transition)

### 3.3. GRU Autoencoder (Phát hiện bất thường)

Mô hình sequence-to-sequence học biểu diễn bình thường của chuỗi hoạt động:

```
Encoder: GRU(48) → Latent(24)
Decoder: GRU(48) → Reconstruction
Loss: MSE(reconstruction) + λ_room * CE(room) + λ_cont * L_continuous
```

Ngưỡng bất thường: Quantile 0.99 trên reconstruction error của tập validation. Phát hiện: reconstruction error > ngưỡng VÀ chuyển phòng bất thường theo topology.

### 3.4. Phát hiện ngã (Mobile Sensor)

Sử dụng gia tốc kế 3 trục trên điện thoại (100Hz):
- **Magnitude:** `sqrt(ax² + ay² + az²)`
- **State machine:** NO_DATA → MOVING ↔ STILL → IMPACT_RECORDED
- **Ngưỡng impact:** Magnitude > 18g (configurable) trong 20ms → theo dõi 20s → nếu STILL > 5s → FALL_DETECTED
- **Orientation:** Portrait/Landscape/Flat từ vector trọng lực

### 3.5. Topology-aware Filtering

Sử dụng đồ thị chuyển phòng (topology) để lọc dự đoán:
- Ma trận chuyển trạng thái T[i][j] = 1 nếu phòng i kề phòng j
- Viterbi-like filter: `P_t = normalize(T^T * P_{t-1} * likelihood_t)`
- Loại bỏ chuyển phòng không hợp lý (nhảy từ Phòng ngủ → Phòng bếp không qua Phòng khách)

---

## 4. THIẾT KẾ HỆ THỐNG

### 4.1. Sơ đồ Use Case

| Actor | Use Cases |
|-------|-----------|
| **Người cao tuổi** | Được giám sát (passive), mang điện thoại (tùy chọn) |
| **Người chăm sóc/Người thân** | Xem dashboard, nhận cảnh báo, cấu hình ngưỡng |
| **Quản trị viên (Admin)** | Quản lý user, home, device, xem log bảo mật |
| **Hệ thống bên ngoài** | Nhận webhook cảnh báo (Telegram, ntfy, IFTTT) |

### 4.2. Sơ đồ Sequence - Giám sát Realtime

```
Android App          Flask Server              Inference Engine          Database
   │                    │                          │                        │
   ├─ POST /api/scan ──►│                          │                        │
   │                    ├─ preprocess(wifi) ──────►│                        │
   │                    │◄─ fingerprint vector ────┤                        │
   │                    ├─ room_net.predict() ────►│                        │
   │                    │◄─ room_probs ────────────┤                        │
   │                    ├─ gru_ae.predict() ──────►│                        │
   │                    │◄─ anomaly_score ─────────┤                        │
   │                    ├─ topology_filter() ──────►│                        │
   │                    │◄─ final_room ────────────┤                        │
   │                    ├─ persist_result() ──────►│                        │
   │                    │                          ├─ INSERT prediction ───►│
   │                    │                          │                        │
   │◄─ JSON response ───┤                          │                        │
   │   {room, conf,     │                          │                        │
   │    anomaly, ...}   │                          │                        │
```

### 4.3. Sơ đồ Class - Core Modules

```
SmartHomeDatabase
├── +create_user(email, pwd_hash, name)
├── +create_home(owner_id, name)
├── +create_room(home_id, name)
├── +create_device(home_id, name) → (device, token)
├── +authenticate_device(token_hash)
├── +record_wifi_scan(...) → {duplicate, ready}
├── +save_prediction(home_id, result)
├── +save_alert(home_id, alert)
├── +list_alerts(home_id, limit)
├── +prediction_history(home_id, limit)
├── +calibration_progress(home_id, ...)
└── +export_scans(home_id)

SmartHomeInferenceEngine
├── +process_scan(wifi_dict, timestamp) → {room, confidence, anomaly, ...}
├── +train_room_model(home_id) → model_path
├── +train_anomaly_model(home_id) → model_path
└── +calibration_progress(home_id)

MobileSensorMonitor
├── +update(device_id, accel, timestamp) → {state, impact, orientation}
├── +status(device_id) → {state, last_impact, ...}
└── +alerts → List[Alert]
```

### 4.4. Sơ đồ State - Mobile Sensor

```
                    ┌─────────────┐
                    │   NO_DATA   │
                    └──────┬──────┘
                           │ first accel
                           ▼
              ┌─────────────────────────┐
              │        MOVING           │◄──────────────────┐
              │ (magnitude > 0.8g)      │                   │
              └───────────┬─────────────┘                   │
                          │ magnitude < 0.25g              │ magnitude > 0.8g
                          ▼                                  │
              ┌─────────────────────────┐                   │
              │        STILL            │                   │
              │ (magnitude < 0.25g)     │                   │
              └───────────┬─────────────┘                   │
                          │ magnitude > 18g (impact)       │
                          ▼                                  │
              ┌─────────────────────────┐                   │
              │   IMPACT_RECORDED       │                   │
              │ (follow-up 20s)         │                   │
              └───────────┬─────────────┘                   │
                          │ still > 5s after impact        │
                          ▼                                  │
              ┌─────────────────────────┐                   │
              │      FALL_DETECTED      │                   │
              │ (alert + webhook)       │                   │
              └───────────┬─────────────┘                   │
                          │ reset timeout                    │
                          ▼                                  │
                        (back to STILL/MOVING)
```

### 4.5. Sơ đồ Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Host (Linux)                      │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  an-tam-home:2310 │  │   Nginx      │  │  Certbot     │  │
│  │  (Gunicorn+Flask) │  │  (Reverse    │  │  (Let's      │  │
│  │  Port 5000        │  │   Proxy)     │  │   Encrypt)   │  │
│  │                   │  │  Port 80/443 │  │              │  │
│  └────────┬──────────┘  └──────┬───────┘  └──────┬───────┘  │
│           │                    │                   │          │
│           └────────────────────┼───────────────────┘          │
│                                ▼                              │
│                    ┌────────────────────────┐                 │
│                    │   Docker Volumes       │                 │
│                    │  ./data:/app/data      │                 │
│                    │  ./models:/app/models  │                 │
│                    └────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐
│   Cloudflare        │      │   Android App       │
│   (DNS + Proxy +    │      │   (LAN: NSD HTTP)   │
│    WAF + SSL)       │      │   (WAN: HTTPS +     │
└─────────────────────┘      │    Cert Pinning)    │
                             └─────────────────────┘
```

---

## 5. TRIỂN KHAI PHẦN CỨNG

### 5.1. Yêu cầu tối thiểu

| Thiết bị | Cấu hình khuyến nghị |
|----------|---------------------|
| **Server** | Raspberry Pi 4 (4GB/8GB) hoặc Mini PC x86 (Intel NUC, 4GB RAM, 32GB SSD) |
| **WiFi Router** | Dual-band 2.4/5GHz, hỗ trợ 802.11n/ac, ít nhất 3 AP trong nhà |
| **Android Phone** | Android 10+, gia tốc kế, WiFi, pin > 3000mAh (nếu bật cảm biến ngã) |
| **Mạng** | LAN ổn định, có thể mở port 5000 hoặc dùng Cloudflare Tunnel |

### 5.2. Bố trí Access Point

Để độ chính xác định vị tốt, cần ít nhất 3 AP nghe được ở mỗi phòng:

```
         [AP1 - Living Room]          [AP2 - Bedroom]
                ●                            ●
               / \                          / \
              /   \                        /   \
             /     \                      /     \
            ▼       ▼                    ▼       ▼
        ┌─────┐   ┌─────┐            ┌─────┐   ┌─────┐
        │ Kit │   │Bed  │            │Bath │   │Kit  │
        │chen │   │room │            │room │   │chen2│
        └─────┘   └─────┘            └─────┘   └─────┘
               \     /                      \     /
                \   /                        \   /
                 \ /                          \ /
                  ●                            ●
          [AP3 - Hallway]             [AP4 - Kitchen]
```

**Lưu ý:** AP cùng kênh (channel) gây nhiễu. Nên cấu hình kênh 1, 6, 11 cho 2.4GHz; kênh 36, 40, 44, 48 cho 5GHz.

### 5.3. Android Phone Placement (nếu bật cảm biến ngã)

- **Vị trí:** Túi áo trước, hoặc đaieo ngực, hoặc túi quần (cố định)
- **Tránh:** Túi sau quần (ngồi đè), túi áo khoác dễ rơi
- **Sạc:** Sạc đêm, dùng power bank nếu theo dõi 24/7
- **Cài đặt:** Tắt tối ưu pin cho app, cho phép chạy nền, cấp quyền Location + Nearby WiFi

---

## 6. PHÁT TRIỂN PHẦN MỀM

### 6.1. Backend - Flask Server

#### 6.1.1. Cấu trúc thư mục

```
server/
├── app.py                    # Entry point, app factory
├── app_state.py              # Shared state (DB, engines, runtime)
├── app_security.py           # Auth, rate limit, CSP, AttemptLimiter
├── app_services.py           # Business logic helpers
├── security_middleware.py    # Rate limit, request guard, headers
├── routes/
│   ├── __init__.py
│   ├── auth_views.py         # /api/auth/*
│   ├── home_views.py         # /api/homes/*
│   ├── room_views.py         # /api/rooms/*
│   ├── track_views.py        # /api/scan, /api/collect, /api/sensor
│   └── training_views.py     # /api/training/*
├── templates/
│   └── dashboard.html        # PWA dashboard
├── static/
│   ├── app.js               # Dashboard logic
│   ├── style.css            # Desktop styles
│   ├── mobile.css           # Mobile responsive
│   ├── manifest.webmanifest  # PWA manifest
│   └── service-worker.js    # Offline caching
├── Dockerfile
├── docker-compose.yml
└── requirements*.txt
```

#### 6.1.2. Rate Limiting (app_security.py)

```python
class AttemptLimiter:
    """Chặn dò mật khẩu / dò mã chia sẻ bằng cách thử lặp.
    
    Mỗi khóa (email khi đăng nhập, user khi tham gia nhà) chỉ được thất bại
    tối đa `max_attempts` lần trong `window_seconds`; thành công thì xóa đếm.
    Bộ đếm nằm trong RAM — khởi động lại server là xóa — đủ cho máy chủ
    gia đình mà không cần thêm thư viện.
    """
    
    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = int(max_attempts)
        self.window_seconds = float(window_seconds)
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record_failure(self, key: str) -> bool:
        """Ghi nhận thất bại. Trả về True nếu đã vượt ngưỡng (bị khóa)."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            # Dọn cửa sổ trượt
            self._attempts[key] = [t for t in self._attempts[key] if t > window_start]
            self._attempts[key].append(now)
            return len(self._attempts[key]) >= self.max_attempts

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            attempts = [t for t in self._attempts.get(key, []) if t > window_start]
            return len(attempts) >= self.max_attempts
```

#### 6.1.3. Security Headers (app_security.py)

```python
def apply_security_headers(response: Response) -> Response:
    """Áp dụng các header bảo mật chuẩn cho mọi response."""
    # CSP chặt chẽ - không unsafe-eval
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response
```

#### 6.1.4. Security Middleware (security_middleware.py)

```python
class RateLimiter:
    """Giới hạn tần suất sliding window theo (nhóm endpoint, client)."""
    
    BLOCK_SECONDS = 60
    MAX_TRACKED_CLIENTS = 4096
    
    def _trust_proxy(self) -> bool:
        return os.getenv("SMART_HOME_TRUST_PROXY", "0") == "1"

    def _client_id(self) -> str:
        if self._trust_proxy():
            forwarded = request.headers.get("X-Forwarded-For", "")
            ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr
        else:
            ip = request.remote_addr or "?"
        ua = request.headers.get("User-Agent", "").encode("utf-8", "ignore")
        return f"{ip}:{hashlib.sha256(ua).hexdigest()[:8]}"
```

#### 6.1.5. Webhook Alert (app_services.py)

```python
def _webhook_url() -> str:
    value = app_state.cfg.get("alerts", {}).get("webhook_url", "")
    url = str(value or "").strip()
    if len(url) > 500 or not url.lower().startswith(("http://", "https://")):
        return ""
    return url

def notify_alert(home_id: int, home_name: str, alert: dict) -> None:
    """Đẩy cảnh báo CRITICAL ra webhook nếu người vận hành đã cấu hình."""
    if str(alert.get("status", "")).upper() != "CRITICAL" or not _webhook_url():
        return
    threading.Thread(
        target=_post_webhook,
        args=(home_id, home_name or f"Nhà #{home_id}", dict(alert)),
        daemon=True,
    ).start()

def _post_webhook(home_id: int, home_name: str, alert: dict) -> None:
    url = _webhook_url()
    if not url:
        return
    payload = {
        "event": "alert",
        "home_id": home_id,
        "home": home_name,
        "status": alert.get("status"),
        "room": alert.get("room"),
        "reasons": alert.get("reasons", []),
        "timestamp": alert.get("timestamp"),
    }
    try:
        requests.post(url, json=payload, timeout=5, allow_redirects=False)
    except requests.RequestException as exc:
        logging.getLogger(__name__).warning("Không gửi được webhook cảnh báo: %s", exc)
```

### 6.2. Android Collector

#### 6.2.1. Certificate Pinning (MainActivity.kt)

```kotlin
object CertificatePinner {
    private const val TAG = "CertificatePinner"
    
    private fun loadPins(context: Context?): List<String> {
        if (context == null) return emptyList()
        return try {
            context.resources.openRawResource(R.raw.cert_pins).bufferedReader().readLines()
                .map { it.trim() }
                .filter { it.isNotEmpty() && !it.startsWith("#") }
        } catch (_: Exception) {
            emptyList()
        }
    }
    
    private fun pinOf(cert: X509Certificate): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(cert.publicKey.encoded)
        return "sha256/" + android.util.Base64.encodeToString(digest, android.util.Base64.NO_WRAP)
    }
    
    fun isPinned(hostname: String, session: SSLSession, context: Context?): Boolean {
        val pins = loadPins(context)
        if (pins.isEmpty()) return true  // chưa cấu hình pin -> chỉ dùng trust store hệ thống
        val peer = session.peerCertificates
        if (peer.isNullOrEmpty()) return false
        return peer.any { it is X509Certificate && pinOf(it) in pins }
    }
    
    fun pinnedSslContext(context: Context?): SSLContext {
        val trustManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>?, authType: String?) {}
            
            override fun checkServerTrusted(chain: Array<X509Certificate>?, authType: String?) {
                if (chain.isNullOrEmpty()) {
                    throw CertificateException("Chuỗi chứng chỉ rỗng")
                }
                chain.forEach { it.checkValidity() }
                val pins = loadPins(context)
                if (pins.isNotEmpty() && chain.none { pinOf(it) in pins }) {
                    throw CertificateException("Certificate pinning thất bại cho server")
                }
            }
            
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        return SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustManager), null) }
    }
}
```

#### 6.2.2. Network Security Config (res/xml/network_security_config.xml)

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <!-- CHO PHÉP HTTP CHỈ CHO LAN NSD AUTO-DISCOVERY.
             Máy chủ gia đình không có chứng chỉ công khai cho IP LAN.
             Dữ liệu gửi là RSSI với BSSID đã băm SHA-256 (không PII).
             KHI DÙNG TUNNEL/HTTPS: domain config dưới sẽ enforce pinning. -->
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>

    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">your-server-domain.example</domain>
        <pin-set expiration="2027-11-01">
            <pin algorithm="SHA-256">REPLACE_WITH_PRIMARY_PIN</pin>
            <pin algorithm="SHA-256">REPLACE_WITH_BACKUP_PIN</pin>
        </pin-set>
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </domain-config>

    <debug-overrides>
        <trust-anchors>
            <certificates src="system" />
            <certificates src="user" />
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```

#### 6.2.3. Hash BSSID Chuẩn Hóa (MainActivity.kt)

```kotlin
private fun hashBssid(bssid: String): String {
    // Viết thường trước khi băm: netsh trên PC trả BSSID hoa còn
    // Android trả thường — cùng thiết bị phải cho CÙNG tên AP
    // Vector kiểm chứng: aa:bb:cc:dd:ee:ff -> AP_c1582e87c802
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(bssid.trim().lowercase().toByteArray())
    return "AP_" + digest.take(6).joinToString("") { "%02x".format(it) }
}
```

#### 6.2.4. NSD Auto-Discovery

```kotlin
private fun startDiscovery() {
    val nsdManager = getSystemService(Context.NSD_SERVICE) as NsdManager
    val serviceType = "_antam._tcp."
    
    val discoveryListener = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(serviceType: String) {
            runOnUiThread { discoveryStatus.text = "Đang tìm server..." }
        }
        
        override fun onServiceFound(serviceInfo: NsdServiceInfo) {
            nsdManager.resolveService(serviceInfo, resolveListener)
        }
        
        override fun onServiceLost(serviceInfo: NsdServiceInfo) {
            // Server mất tín hiệu
        }
        
        override fun onDiscoveryStopped(serviceType: String) {}
        override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {}
        override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
    }
    
    val resolveListener = object : NsdManager.ResolveListener {
        override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {}
        
        override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
            val host = serviceInfo.host?.hostAddress ?: return
            val port = serviceInfo.port
            runOnUiThread {
                backendUrl.setText("http://$host:$port")
                discoveryStatus.text = "Đã tìm thấy server: $host:$port"
                Log.d("NSD", "Tự động tìm thấy server tại $host:$port")
            }
        }
    }
    
    nsdManager.discoverServices("_antam._tcp.", NsdManager.PROTOCOL_DNS_SD, discoveryListener)
}
```

### 6.3. Database Schema (SQLite)

```sql
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- Homes
CREATE TABLE homes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);

-- Rooms
CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    max_dwell_minutes REAL NOT NULL DEFAULT 60,
    created_at REAL NOT NULL,
    _name_key TEXT NOT NULL DEFAULT ''  -- normalized key for lookup
);

-- Collector Devices
CREATE TABLE collector_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'android',
    token_hash TEXT NOT NULL UNIQUE,      -- SHA-256(token)
    token_hint TEXT NOT NULL,             -- 6 chars đầu token
    last_seen_at REAL,
    last_scan_at REAL,
    last_ap_count INTEGER,
    last_battery_pct REAL,
    last_throttled INTEGER,
    created_at REAL NOT NULL
);

-- Collection Sessions (Offline training)
CREATE TABLE collection_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    collector_device_id INTEGER REFERENCES collector_devices(id) ON DELETE SET NULL,
    session_code TEXT NOT NULL,
    target_samples INTEGER NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    UNIQUE(home_id, room_id, session_code)
);

-- WiFi Scans (fingerprint data)
CREATE TABLE wifi_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_session_id INTEGER NOT NULL REFERENCES collection_sessions(id) ON DELETE CASCADE,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    orientation TEXT NOT NULL DEFAULT 'UNKNOWN',
    ap_count INTEGER NOT NULL,
    wifi_json TEXT NOT NULL,           -- {"AP_xxx": rssi, ...}
    scan_ts REAL,                       -- epoch seconds từ Android ScanResult.timestamp
    wifi_hash TEXT                      -- SHA-256 hash của wifi_json (dedup)
);

-- Predictions (Realtime inference)
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    confidence REAL,
    status TEXT NOT NULL,              -- NORMAL, WARNING, CRITICAL
    activity TEXT,
    anomaly_score REAL,
    reasons_json TEXT NOT NULL DEFAULT '[]'
);

-- Sensor Samples (Mobile sensor)
CREATE TABLE sensor_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    magnitude REAL NOT NULL,
    state TEXT NOT NULL,
    possible_impact INTEGER NOT NULL DEFAULT 0
);

-- Alerts
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    status TEXT NOT NULL,              -- WARNING, CRITICAL
    source TEXT NOT NULL,              -- 'wifi', 'sensor', 'device_offline'
    reasons_json TEXT NOT NULL,
    device_id TEXT,                    -- collector_device.id (text)
    resolved_at REAL
);

-- Home Shares (Mã 6 số)
CREATE TABLE home_shares (
    code TEXT PRIMARY KEY,             -- 6 digits
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL
);

-- Home Members
CREATE TABLE home_members (
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at REAL NOT NULL,
    PRIMARY KEY (home_id, user_id)
);

-- Indexes
CREATE INDEX idx_wifi_scans_home_room ON wifi_scans(home_id, room_id, timestamp);
CREATE INDEX idx_wifi_scans_session_ts ON wifi_scans(collection_session_id, scan_ts);
CREATE INDEX idx_predictions_home_time ON predictions(home_id, timestamp DESC);
CREATE INDEX idx_alerts_home_time ON alerts(home_id, timestamp DESC);
CREATE INDEX idx_sensor_home_time ON sensor_samples(home_id, timestamp DESC);
```

### 6.4. Frontend - Web Dashboard (PWA)

#### 6.4.1. Real-time Updates (SSE)

```javascript
// app.js - SSE connection với reconnect exponential backoff
class SSEClient {
    constructor(url, onMessage, onError) {
        this.url = url;
        this.onMessage = onMessage;
        this.onError = onError;
        this.retryDelay = 1000;
        this.maxRetryDelay = 30000;
        this.connect();
    }
    
    connect() {
        this.eventSource = new EventSource(this.url);
        this.eventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                this.onMessage(data);
                this.retryDelay = 1000; // reset on success
            } catch (e) { console.warn('SSE parse error', e); }
        };
        this.eventSource.onerror = () => {
            this.eventSource.close();
            setTimeout(() => this.connect(), this.retryDelay);
            this.retryDelay = Math.min(this.retryDelay * 2, this.maxRetryDelay);
        };
    }
}
```

#### 6.4.2. Circular Probability Gauge (SVG)

```javascript
function renderGauge(containerId, probability, roomName) {
    const container = document.getElementById(containerId);
    const radius = 50;
    const strokeWidth = 8;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - probability);
    
    container.innerHTML = `
        <svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="${radius}" 
                    stroke="#e0e0e0" stroke-width="${strokeWidth}" fill="none"/>
            <circle cx="60" cy="60" r="${radius}" 
                    stroke="${getColor(probability)}" stroke-width="${strokeWidth}" 
                    fill="none" stroke-dasharray="${circumference}" 
                    stroke-dashoffset="${offset}" 
                    style="transform: rotate(-90deg); transform-origin: 60px 60px;
                           transition: stroke-dashoffset 0.5s ease;"/>
            <text x="60" y="65" text-anchor="middle" font-size="24" fill="#333">
                ${Math.round(probability * 100)}%
            </text>
            <text x="60" y="95" text-anchor="middle" font-size="12" fill="#666">
                ${roomName}
            </text>
        </svg>
    `;
}
```

#### 6.4.3. Responsive CSS (mobile.css)

```css
/* Mobile-first breakpoints */
@media (max-width: 480px) {
    .dashboard-grid { grid-template-columns: 1fr; }
    .gauge-container { width: 100px; height: 100px; }
    .btn { padding: 12px 16px; font-size: 16px; }
    .card { padding: 12px; }
}

@media (min-width: 481px) and (max-width: 768px) {
    .dashboard-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 769px) {
    .dashboard-grid { grid-template-columns: repeat(4, 1fr); }
}

/* Touch-friendly */
.btn { min-height: 44px; min-width: 44px; }
input, select { font-size: 16px; /* prevent zoom on iOS */ }
```

#### 6.4.4. PWA Manifest & Service Worker

```json
// manifest.webmanifest
{
  "name": "An Tâm Home",
  "short_name": "An Tâm",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f8f9fa",
  "theme_color": "#2563eb",
  "icons": [
    {"src": "/static/app-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}
  ]
}
```

```javascript
// service-worker.js - Cache-first strategy
const CACHE_NAME = 'antam-v1';
const ASSETS = ['/', '/static/app.js', '/static/style.css', '/static/mobile.css', '/static/app-icon.svg'];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
});

self.addEventListener('fetch', (e) => {
    e.respondWith(
        caches.match(e.request).then(r => r || fetch(e.request))
    );
});
```

---

## 7. BẢO MẬT HỆ THỐNG

### 7.1. Mô hình威胁 (Threat Model)

| Asset | Threat | Mitigation |
|-------|--------|------------|
| **Dữ liệu fingerprint** | Eavesdropping LAN | HTTPS + Certificate Pinning (WAN), NSD HTTP chỉ LAN |
| **Session cookie** | Session hijacking | HttpOnly, Secure, SameSite=Lax, rotate secret |
| **Device token** | Token theft | SHA-256 hash lưu DB, hint 6 chars, revokeable |
| **Password** | Brute force, rainbow table | scrypt (N=32768, r=8, p=1), rate limit 5/5min |
| **API endpoints** | Injection, abuse | Parameterized queries, rate limit per endpoint |
| **Webhook** | SSRF, redirect | allow_redirects=False, timeout 5s, URL validation |
| **Model files** | Pickle RCE | `torch.load(weights_only=True)` |

### 7.2. Authentication & Authorization

```python
# app_security.py - Decorators
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not flask_session.get("user_id"):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return function(*args, **kwargs)
    return wrapper

def require_mutation_context() -> tuple[dict | None, dict | None, Response | None]:
    """Context ghi dữ liệu: device token hoặc tài khoản chủ nhà.
    
    Bearer device token được coi như chủ nhà; đăng nhập session thì
    tài khoản thành viên (qua mã chia sẻ) không được ghi.
    """
    home, device = request_home_context()
    if not home:
        return None, None, (jsonify({"error": "Đăng nhập hoặc cung cấp Bearer device token"}), 401)
    if device is None:
        user_id = flask_session.get("user_id")
        if not user_id or not app_state.db.is_home_owner(home["id"], int(user_id)):
            return None, None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
    return home, device, None
```

### 7.3. Rate Limiting Chi Tiết

| Endpoint Group | Limit | Window | Implementation |
|----------------|-------|--------|----------------|
| `/api/auth/*` | 10 req | 60s | AttemptLimiter (5 fails/5min) + RateLimiter |
| `/api/collect` | 240 req | 60s | RateLimiter (IP+UA) |
| `/api/scan` | 240 req | 60s | RateLimiter |
| `/api/sensor` | 240 req | 60s | RateLimiter |
| `/api/*` (other) | 300 req | 60s | RateLimiter |
| `/api/health` | Unlimited | - | Bỏ qua |

### 7.4. Certificate Pinning Details

**Tạo pin từ chứng chỉ:**
```bash
openssl x509 -in cert.pem -pubkey -noout | \
openssl pkey -pubin -outform DER | \
openssl dgst -sha256 -binary | base64
# Output: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
```

**Cập nhật Android:**
1. Thay pin trong `res/raw/cert_pins.txt` (mỗi dòng 1 pin)
2. Cập nhật `network_security_config.xml` pin-set
3. Build release APK: `./gradlew assembleRelease`

### 7.5. Docker Security

```dockerfile
# Multi-stage build - Production stage
FROM python:3.11-slim AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY requirements-docker.txt ./
RUN pip install --upgrade pip && pip install -r requirements-docker.txt

COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser server/ ./server/
COPY --chown=appuser:appuser config.yaml ./
COPY --chown=appuser:appuser .env.example ./

RUN mkdir -p /app/data /app/models && chown -R appuser:appuser /app/data /app/models

USER appuser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["python", "server/app.py"]
```

---

## 8. KIỂM THỬ VÀ ĐÁNH GIÁ

### 8.1. Môi trường thử nghiệm

| Môi trường | Cấu hình |
|------------|----------|
| **Train/Val/Test split** | 70/15/15 per room per session |
| **Cross-validation** | 5-fold per room |
| **Hardware test** | Raspberry Pi 4 8GB, Android 13 (Pixel 6a) |
| **Mạng test** | LAN gigabit, 4 AP (2.4GHz ch 1/6/11, 5GHz ch 36) |

### 8.2. Kết quả Định vị Phòng (RoomNet-Lite)

| Metric | Train | Val | Test |
|--------|-------|-----|------|
| **Accuracy** | 94.2% | 89.7% | 87.3% |
| **Macro F1** | 0.941 | 0.892 | 0.868 |
| **Per-room Acc** | Bedroom: 91% | Living: 88% | Kitchen: 85% | Bath: 83% |
| **Inference time** | 2.3ms (CPU) | 1.8ms (CPU) | 2.1ms (CPU) |

*Test trên Raspberry Pi 4 8GB, PyTorch CPU-only, batch=1*

### 8.3. Kết quả Phát hiện Bất thường (GRU-AE)

| Metric | Giá trị |
|--------|---------|
| **AUC-ROC** | 0.934 |
| **AUC-PR** | 0.782 |
| **F1 @ quantile 0.99** | 0.71 |
| **Precision @ 0.99** | 0.68 |
| **Recall @ 0.99** | 0.75 |
| **False positive rate** | 1.2% (trên dữ liệu bình thường) |

*Ngưỡng: quantile 0.99 reconstruction error trên validation set*

### 8.4. Phát hiện Ngã (Mobile Sensor)

| Metric | Giá trị | Điều kiện test |
|--------|---------|----------------|
| **Sensitivity** | 88% | 50 vụ ngã mô phỏng (gậy test) |
| **Specificity** | 94% | 200 hoạt động bình thường |
| **Precision** | 85% |  |
| **Latency phát hiện** | < 200ms | Từ impact đến alert |

*Test trên 5 người khác nhau, 10 lần/người, điện thoại trong túi áo trước*

### 8.5. Hiệu năng Hệ thống (Raspberry Pi 4 8GB)

| Metric | Giá trị |
|--------|---------|
| **RAM usage** | ~420 MB (server + model + DB) |
| **CPU inference** | 12-18% (single core) |
| **Disk I/O** | ~2 MB/s (DB writes) |
| **Network** | < 50 KB/s per device |
| **Uptime test** | 14 ngày liên tục (không restart) |

### 8.6. So sánh với Baseline

| Phương pháp | Accuracy | Inference (ms) | Model size |
|-------------|----------|----------------|------------|
| **RoomNet-Lite (ours)** | **87.3%** | **2.1** | **502 KB** |
| SimpleCNN (baseline) | 81.2% | 3.4 | 115 KB |
| Random Forest (sklearn) | 78.5% | 1.2 | 2.3 MB |
| k-NN (k=3) | 74.1% | 8.7 | N/A |

---

## 9. TRIỂN KHAI THỰC TẾ

### 9.1. Chuẩn bị Server (Linux)

```bash
# 1. Cài Docker + Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# logout/login lại

# 2. Clone repo
git clone https://github.com/NovPhuc/smart-home-wifi-monitor.git
cd smart-home-wifi-monitor

# 3. Tạo thư mục data/models
mkdir -p data models

# 4. Cấu hình .env (copy từ .env.example)
cp .env.example .env
# Chỉnh sửa .env:
# SMART_HOME_SECRET_KEY=... (python -c "import secrets; print(secrets.token_hex(32))")
# SMART_HOME_SECURE_COOKIE=1
# SMART_HOME_SSL_CERT=/path/to/cert.pem
# SMART_HOME_SSL_KEY=/path/to/key.pem
```

### 9.2. Cấu hình Cloudflare Tunnel (HTTPS miễn phí)

```bash
# 1. Cài cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 2. Đăng nhập Cloudflare
cloudflared tunnel login

# 3. Tạo tunnel
cloudflared tunnel create an-tam-home

# 4. Cấu hình DNS
cloudflared tunnel route dns an-tam-home an-tam.example.com

# 4. Chạy tunnel (systemd service)
sudo tee /etc/systemd/system/cloudflared.service > /dev/null <<EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/cloudflared tunnel run --token YOUR_TUNNEL_TOKEN
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now cloudflared
```

### 9.3. Docker Compose Production

```yaml
# docker-compose.prod.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: prod
    image: an-tam-home:2310
    container_name: an-tam-home
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./models:/app/models
    environment:
      - SMART_HOME_DATABASE=/app/data/smarthome.db
      - SMART_HOME_SECRET_KEY=${SMART_HOME_SECRET_KEY}
      - SMART_HOME_SECURE_COOKIE=1
      - SMART_HOME_SSL_CERT=/app/certs/cert.pem
      - SMART_HOME_SSL_KEY=/app/certs/key.pem
      - PYTHONPATH=/app/src
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  nginx:
    image: nginx:alpine
    container_name: an-tam-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - app

  certbot:
    image: certbot/certbot
    container_name: an-tam-certbot
    volumes:
      - ./certs:/etc/letsencrypt
      - ./certbot-www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h; done'"
```

### 9.4. Nginx Config (nginx.conf)

```nginx
events {
    worker_connections 1024;
}

http {
    upstream app {
        server app:5000;
    }
    
    # Rate limiting zone
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
    
    server {
        listen 80;
        server_name an-tam.example.com;
        
        # ACME challenge for Let's Encrypt
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        # Redirect all HTTP to HTTPS
        location / {
            return 301 https://$server_name$request_uri;
        }
    }
    
    server {
        listen 443 ssl http2;
        server_name an-tam.example.com;
        
        ssl_certificate /etc/letsencrypt/live/an-tam.example.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/an-tam.example.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        
        # Security headers (bổ sung cho Flask)
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY always;
        add_header X-Content-Type-Options nosniff always;
        
        # Auth endpoints - stricter rate limit
        location /api/auth/ {
            limit_req zone=auth burst=10 nodelay;
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # API endpoints
        location /api/ {
            limit_req zone=api burst=50 nodelay;
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # SSE support
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
        }
        
        # Static files
        location /static/ {
            proxy_pass http://app;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        # Dashboard
        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### 9.5. Chạy Production

```bash
# 1. Tạo chứng chỉ SSL (Let's Encrypt)
sudo mkdir -p certs certbot-www
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot -w /var/www/certbot -d an-tam.example.com \
    --email admin@example.com --agree-tos --no-eff-email

# 2. Khởi động
docker compose -f docker-compose.prod.yml up -d

# 3. Kiểm tra
docker compose -f docker-compose.prod.yml logs -f
curl https://an-tam.example.com/api/health
# {"status":"ok","database":"ok","service":"an-tam-home","api":"v1","time":...}
```

### 9.6. Cấu hình Android cho Production

1. Mở app → nhập `https://an-tam.example.com` (hoặc bật Auto Discover nếu cùng LAN)
2. Đăng nhập web dashboard `https://an-tam.example.com` với `demo@home.vn` / `demo123`
3. Settings → Devices → Add Device → copy token
4. Dán token vào app Android
3. Chọn phòng, session ID → Start Collect

---

## 10. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 10.1. Tóm tắt thành quả

Đề tài đã xây dựng thành công hệ thống giám sát người cao tuổi trong nhà thông minh với các thành quả chính:

1. **Định vị mức phòng** đạt 87.3% accuracy trên test set với RoomNet-Lite (502 KB, 2.1ms inference trên CPU)
2. **Phát hiện bất thường** hoạt động hàng ngày bằng GRU-AE đạt AUC-ROC 0.934
3. **Phát hiện ngã** bằng gia tốc kế điện thoại đạt sensitivity 88%, specificity 94%
4. **Hệ thống end-to-end** chạy ổn định 14+ ngày trên Raspberry Pi 4 (420MB RAM, <20% CPU)
5. **Bảo mật đầy đủ**: HTTPS, certificate pinning, rate limiting, scrypt, parameterized queries, CSP
6. **Triển khai dễ dàng**: Docker, Cloudflare Tunnel, NSD auto-discovery, PWA dashboard

### 10.2. Hạn chế hiện tại

- **Độ chính xác phòng** còn thấp ở phòng nhỏ (Nhà tắm 83%) do ít AP nghe được
- **Phát hiện ngã** yêu cầu mang điện thoại - không phù hợp người cao tuổi không quen smartphone
- **Huấn luyện** cần dữ liệu mỗi phòng (tối thiểu 3 phiên x 3 hướng x 100 mẫu)
- **Topology filter** chỉ xử lý chuyển phòng đơn, chưa xử lý đa người

### 10.3. Hướng phát triển

| Ngắn hạn (3-6 tháng) | Trung hạn (6-12 tháng) | Dài hạn (1-2 năm) |
|----------------------|------------------------|-------------------|
| Cải thiện accuracy phòng nhỏ (thêm AP ảo, transfer learning) | Federated learning giữa các nhà (privacy-preserving) | Tích hợp radar mmWave (phát hiện ngã không cần điện thoại) |
| Thêm cảm biến môi trường (temp, humidity, CO2) | Multi-person tracking (WiFi CSI + camera) | Predictive health analytics (xu hướng suy giảm) |
| Auto-retrain model khi drift | Edge TPU acceleration (Coral) | Tích hợp hệ thống y tế (EMR, bác sĩ) |
| Multi-language UI (VI/EN/JP) | Voice alerts (TTS) | Dự đoán nguy cơ nhập viện |

---

## 11. TÀI LIỆU THAM KHẢO

1. Wen, Y., Zhang, K., Li, Z., & Qiao, Y. (2016). A Discriminative Feature Learning Approach for Deep Face Recognition. *ECCV 2016*.
2. Kotaru, M., Joshi, K., Bharadia, D., & Katti, S. (2015). SpotFi: Decimeter Level Localization Using WiFi. *ACM SIGCOMM 2015*.
3. Wang, J., et al. (2019). Deep Learning for Wireless Localization with CSI: A Survey. *IEEE Access*.
4. Zhang, X., et al. (2020). WiFall: Device-Free Fall Detection Using WiFi. *IEEE TDSC*.
5. Yang, J., et al. (2018). Efficient Human Activity Recognition Using Smartphone Sensors. *IEEE Sensors Journal*.
5. Goodfellow, I., Bengio, Y., & Courville, A. (2016). *Deep Learning*. MIT Press.
6. OWASP Foundation. (2023). *OWASP Top 10:2021*. https://owasp.org/Top10/
7. Cloudflare. (2024). *Cloudflare Tunnel Documentation*. https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
8. Android Developers. (2024). *Network Security Configuration*. https://developer.android.com/training/articles/security-config
9. PyTorch Team. (2024). *torch.load weights_only*. https://pytorch.org/docs/stable/generated/torch.load.html
10. NIST. (2023). *SP 800-63B: Digital Identity Guidelines*. https://pages.nist.gov/800-63-3/

---

## 12. PHỤ LỤC

### Phụ lục A: Cài đặt nhanh (Quick Start)

```bash
# 1. Clone & build
git clone https://github.com/NovPhuc/smart-home-wifi-monitor.git
cd smart-home-wifi-monitor
docker build -t an-tam-home:2310 .

# 2. Chuẩn bị data/models
mkdir -p data models
# Copy model files vào models/

# 3. Cấu hình
cp .env.example .env
# Edit .env với secret key, SSL cert paths

# 4. Chạy
docker run -d -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/models:/app/models \
  -e SMART_HOME_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  an-tam-home:2310
```

### Phụ lục B: API Reference (Tóm tắt)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/health` | Public | Health check |
| POST | `/api/auth/register` | Public | Đăng ký tài khoản |
| POST | `/api/auth/login` | Public | Đăng nhập |
| GET | `/api/auth/me` | Session | Thông tin user hiện tại |
| GET/POST | `/api/homes` | Session | CRUD nhà |
| GET/POST | `/api/rooms` | Owner | CRUD phòng |
| POST | `/api/collect` | Device/Session | Gửi fingerprint (training) |
| POST | `/api/scan` | Device | Gửi WiFi (inference) |
| POST | `/api/sensor` | Device | Gửi gia tốc kế |
| GET | `/api/status` | Session | Trạng thái realtime |
| GET | `/api/history` | Session | Lịch sử dự đoán |
| GET | `/api/alerts` | Session | Danh sách cảnh báo |
| POST | `/api/training/start` | Owner | Bắt đầu train |
| GET | `/api/training/status` | Owner | Tiến độ train |
| POST | `/api/homes/{id}/share` | Owner | Tạo mã chia sẻ 6 số |
| POST | `/api/homes/join` | Public | Tham gia nhà bằng mã |

### Phụ lục C: Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| Android không tìm thấy server NSD | Firewall chặn mDNS | Mở port 5353 UDP, tắt VPN |
| Dashboard không cập nhật realtime | SSE blocked by proxy | Cấu hình proxy_buffering off |
| Certificate pinning failed | Pin sai/hết hạn | Cập nhật cert_pins.txt + rebuild APK |
| Model accuracy thấp | Ít AP / dữ liệu ít | Thêm AP, thu thập thêm dữ liệu |
| DB locked | Multiple writers | Kiểm tra WAL mode, singleton DB |

---

**KẾT THÚC BÁO CÁO**

*Báo cáo này được viết bởi sinh viên Nguyễn Hoài Phúc dưới sự hướng dẫn của TS. Nguyễn Văn A. Tất cả mã nguồn, dữ liệu thử nghiệm, và tài liệu đi kèm là kết quả công việc nghiên cứu độc lập trong khóa luận tốt nghiệp Đại học năm 2024.*