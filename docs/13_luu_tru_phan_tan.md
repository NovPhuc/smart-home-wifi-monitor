# 13 — Lưu trữ phân tán cho trạng thái dùng chung (Redis)

Phiên 2026‑11‑02. Hạng mục "lưu trữ phân tán" trong roadmap `tinhnang.md`.

Trước phiên này, `docker-compose.prod.yml` đã khai báo service `redis` với ghi chú
"Redis cho distributed caching, rate limiting, session sharing", và `app_state.py` +
`security_middleware.py` đã có sẵn nhánh đọc `REDIS_HOST`. **Nhưng chưa ai chạy thử** —
package `redis` thậm chí không có trong `.venv` dù `requirements.txt` ghi `redis>=5.0`.

Chạy thử thì phát hiện nhánh Redis **hỏng hoàn toàn**.

---

## 1. Lỗi NGHIÊM TRỌNG: bật Redis là mọi request API trả HTTP 500

`RateLimiter` trong `server/security_middleware.py` bị **dán hai lần thân class** vào cùng
một file, sinh ra hai định nghĩa `check`:

| Vị trí | Nội dung |
|---|---|
| đầu class | `check()` có nhánh `if self._use_redis: … else: …` |
| cuối class | `check()` đi thẳng vào `with self._lock:` — **không xét `_use_redis`** |

Python giữ **định nghĩa sau cùng**, nên bản chạy là bản chỉ-RAM. Trong khi đó `__init__`
chỉ tạo `_lock`/`_requests`/`_blocked` **khi không dùng Redis**:

```python
def __init__(self) -> None:
    self._redis = _redis_client
    self._use_redis = self._redis is not None
    if not self._use_redis:          # <-- chỉ tạo khi KHÔNG dùng Redis
        self._requests = {}
        self._blocked = {}
        self._lock = threading.Lock()
```

⇒ Hễ đặt `REDIS_HOST` — **đúng cấu hình mà `docker-compose.prod.yml` đang dùng** — thì mọi
request đi qua middleware ném:

```
AttributeError: 'RateLimiter' object has no attribute '_lock'
```

và Flask trả **HTTP 500**.

**Vì sao không bị phát hiện sớm:** `/api/health` nằm trong danh sách miễn giới hạn
(`HEALTH_PATH`), còn `/static/*` không thuộc `/api/`. Kiểm tra sức khỏe và tải trang đều
qua được; chỉ các endpoint `/api/*` thật mới chết. Lần chạy container ở phiên 11 chỉ gọi
`/api/health` nên đã bỏ sót.

### Đã sửa

- Xoá định nghĩa `check` trùng; còn **đúng một** định nghĩa, có nhánh Redis.
- `__init__` **luôn** tạo `_lock`/`_requests`/`_blocked`, kể cả ở chế độ Redis — đường dự
  phòng cần chúng.
- Xoá định nghĩa `_client_id` trùng (cùng kiểu lỗi): bản hiệu lực trước đây chỉ dùng IP,
  còn docstring và `SECURITY.md` lại mô tả "IP + UA". Nay giữ **một** định nghĩa, chỉ IP,
  kèm giải thích: `User-Agent` do client tự đặt nên đưa vào khoá là tự cho kẻ tấn công
  thêm bucket mới mỗi request.

---

## 2. Lỗi thứ hai: rate limit phân tán không nguyên tử

`_check_redis` đọc `ZCARD` rồi mới `ZADD` ở **hai lượt riêng**. Hai request đồng thời cùng
đọc thấy "còn chỗ" nên cùng ghi ⇒ vượt ngưỡng. Đo thật bằng `scripts/rate_limit_probe.py`:

| | Cho qua / 60 request đồng thời, ngưỡng 10 |
|---|---|
| Trước (đọc rồi ghi) | **29** — vượt 19 |
| Sau (một script Lua) | **10** — đúng ngưỡng |

Đã gộp *trim → đếm → kiểm tra chặn → ghi* vào **một script Lua** (`_RATE_LIMIT_LUA`), Redis
chạy trọn script trong một lượt nên không request nào chen vào giữa. Đây cũng là cách Redis
khuyến nghị cho rate limiting.

Kèm theo: member của sorted set nay là `f"{now}-{os.urandom(4).hex()}"` thay vì chính mốc
thời gian — nếu lấy mốc thời gian làm member thì hai request cùng thời điểm ghi đè nhau và
bị **đếm thiếu**.

---

## 3. Lỗi thứ ba: Redis chết thì im lặng

`get_redis_client()` bọc `except Exception: return None`, nên khi `REDIS_HOST` được đặt mà
Redis không nối được, ứng dụng **âm thầm** chạy RAM. Người vận hành tưởng hạn mức vẫn chia sẻ
giữa các instance trong khi thực tế mỗi instance đếm riêng — mức bảo vệ giảm mà không có dấu hiệu.

Đã sửa: ghi cảnh báo rõ ràng, phân biệt hai trường hợp.

- Không đặt `REDIS_HOST` → chạy RAM, **không log** (đúng ý người vận hành).
- Đặt mà nối không được → log `[Redis] Không nối được … RATE LIMIT CHẠY RAM, không chia sẻ
  giữa các instance`.
- Redis lỗi giữa chừng → log lý do rồi lùi về RAM cho tiến trình đó.

`reset()` cũng được sửa để **xoá cả khoá trên Redis**, không chỉ RAM — nếu không, ở chế độ
phân tán bộ đếm của lần chạy trước còn nguyên và các test ảnh hưởng lẫn nhau.

---

## 4. Bằng chứng kiểm chứng

Redis thật: `docker run -d --name an-tam-redis-test -p 6399:6379 redis:7-alpine`.

### 4.1. `scripts/rate_limit_probe.py`

```
=== chế độ REDIS (phân tán) ===
1. Tính nguyên tử (60 request đồng thời, ngưỡng 10)
   cho qua 10/60       => đúng ngưỡng: có nguyên tử
2. Chia sẻ giữa hai tiến trình (mỗi bên 5 request, ngưỡng 5)
   tiến trình con 5 + tiến trình cha 0 = 5   => chia sẻ đúng
```

Đối chiếu chế độ RAM: nguyên tử (đúng 10) nhưng **không** chia sẻ (5 + 5 = 10 > 5) — đúng
như thiết kế, và cho thấy vì sao cần Redis khi chạy nhiều instance.

### 4.2. Ứng dụng thật dùng Redis (không lặng lẽ rơi về RAM)

Chạy ứng dụng với `REDIS_HOST=127.0.0.1`, `REDIS_PORT=6399`, gọi 3 request API:

```
module _redis_client : CO
RateLimiter._use_redis: True
dbsize sau 3 request : 2
keys                 : ratelimit:auth:127.0.0.1
                       ratelimit:api:127.0.0.1
cmdstat_evalsha      : calls=3        (đúng bằng số request)
```

`evalsha` chạy đúng 3 lần cho 3 request ⇒ script Lua là đường thực thi thật, không phải
nhánh RAM. Khoá chỉ chứa IP ⇒ xác nhận bản vá `_client_id`.

Lưu ý khi đo: máy này có **hai** tiến trình `server/app.py` cùng chạy, tiến trình cũ giữ cổng
5000 nên request đi vào nó (không có `REDIS_HOST`) và cho kết quả `dbsize=0` sai lệch. Phép đo
đúng phải chạy trên cổng riêng.

### 4.3. Test hồi quy

`tests/test_rate_limit.py` — 7 test, **không cần Redis thật** (dùng Redis giả):

- class chỉ có **một** định nghĩa `check` và **một** định nghĩa `_client_id`
- chế độ Redis vẫn tạo sẵn `_lock`/`_requests`/`_blocked`
- chế độ Redis gọi script và không ném lỗi
- Redis lỗi giữa chừng → lùi về RAM, không ném ra ngoài
- `_client_id` không phụ thuộc `User-Agent`
- chế độ RAM nguyên tử với 60 luồng, ngưỡng 10

```
pytest tests -q   ->  91 passed
```

---

## 5. Cách bật

Đã có sẵn trong `docker-compose.prod.yml` (`REDIS_HOST=redis`, `depends_on: redis healthy`).
Chạy trực tiếp thì đặt biến môi trường:

```powershell
$env:REDIS_HOST='127.0.0.1'; $env:REDIS_PORT='6379'
$env:REDIS_DB='0'            # tuỳ chọn
$env:REDIS_PASSWORD='...'    # tuỳ chọn
```

Không đặt gì thì chạy RAM như trước — không cần Redis cho một tiến trình duy nhất.

## 6. Còn lại

- `MobileSensorMonitor`, `last_results`, `runtime_histories`, `training_jobs` vẫn là trạng
  thái **trong RAM của từng tiến trình**. Muốn chạy nhiều instance thật thì các phần này
  cũng phải chuyển sang Redis hoặc phải ghim mỗi nhà vào một instance (sticky session);
  hiện chưa làm.
- `redis` đã được thêm vào `.venv` nhưng **cài đặt cục bộ chưa được commit** (không commit
  `.venv`); `requirements.txt` vốn đã có `redis>=5.0` từ trước.
