# G2 — SSE realtime cho dashboard

Ngày: 2026-11-01. Phạm vi: bỏ polling 3 request mỗi 2 giây ở dashboard, thay bằng
Server-Sent Events (SSE); vẫn giữ polling làm đường lui. Không đổi API Android,
không đổi tên cookie phiên, không thêm thư viện.

## 1. Hợp đồng endpoint

`GET /api/stream` — yêu cầu đăng nhập và nhà đang chọn, giống `/api/status`.

Headers:

```text
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-store
X-Accel-Buffering: no
Connection: keep-alive
```

Các event:

| Event | Dữ liệu | Khi nào |
|---|---|---|
| `status` | giống `GET /api/status` | khi payload đổi, và chậm nhất mỗi 15 giây |
| `history` | giống `GET /api/history` | khi payload đổi |
| `alerts` | giống `GET /api/alerts` | khi payload đổi |
| `auth` | `{"error":"HOME_ACCESS_REVOKED"}` | khi tài khoản không còn quyền xem nhà |

Mỗi vòng lặp cách 2 giây. Chỉ event có nội dung thay đổi mới được gửi; `status`
được gửi lại định kỳ để dashboard vẫn cập nhật được nhãn "Dữ liệu đã cũ". Ngoài
các event, server gửi comment `: heartbeat` mỗi 15 giây.

Khi vượt 32 kết nối đồng thời: `503` JSON `TOO_MANY_STREAMS` + `Retry-After: 30`.
Giới hạn này tránh việc mở nhiều tab làm cạn thread của Flask.

## 2. Thay đổi phía server

`server/routes/track_views.py`:

- Tách `_status_payload()`, `_history_payload()`, `_alerts_payload()` để REST và SSE
  dùng chung một nguồn dữ liệu, tránh hai bản logic lệch nhau.
- `_dashboard_stream(home, user_id)` sinh event; không dùng
  `stream_with_context` vì generator chỉ đọc `app_state` và bản chụp `home`, không
  cần giữ request context trong suốt thời gian stream.
- Mỗi vòng kiểm tra lại `db.get_home(user_id, home_id)`. Nếu chủ nhà gỡ thành viên
  hoặc xóa nhà, stream gửi `auth` rồi kết thúc — không để thành viên đã bị gỡ tiếp
  tục nhận dữ liệu.
- `_StreamSlots` dùng `threading.BoundedSemaphore(32)`; giải phóng bằng
  `response.call_on_close()` để không rò slot khi client ngắt giữa chừng.

Không đổi các route REST: `/api/status`, `/api/history`, `/api/alerts` vẫn trả cùng
JSON như trước, nên Android Collector và PWA cũ không bị ảnh hưởng.

## 3. Thay đổi phía dashboard

Sau khi tách module (xem `docs/14_frontend_modules.md`), phần SSE nằm ở
`server/static/js/dashboard.js`, phần vẽ dùng chung nằm ở
`server/static/js/monitoring.js`; `server/static/app.js` chỉ còn là entry.

- `startLiveUpdates()` mở `EventSource('/api/stream')` sau khi đăng nhập và sau mỗi
  lần `loadHome()` (đổi nhà, tạo/join nhà, sửa phòng…).
- `applyStatus()`, `applyHistory()`, `applyAlerts()` là phần vẽ dùng chung cho SSE và
  polling; `lastRenderKey` vẫn chặn vẽ lại khi dữ liệu không đổi.
- Lỗi stream: đóng `EventSource`, bật polling 3 endpoint để dashboard vẫn có dữ liệu
  và phát hiện phiên hết hạn, hẹn mở lại SSE sau 15 giây. Khi SSE mở thành công,
  polling tự dừng.
- `visibilitychange`/`pagehide` đóng stream; quay lại tab thì mở lại và refresh ngay.
- Event `auth` đóng stream và `location.reload()` để nạp lại phiên/nhà.

`service-worker.js` đã bỏ qua `/api/*` từ trước, nên SSE không bị cache. Cache
`an-tam-home-v6` nạp sẵn app shell (`app.js`, 10 module trong `js/`, CSS, manifest,
icon); các tài nguyên tĩnh khác được cache thêm khi tải.

## 4. Kiểm chứng thật

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m pytest tests -q
```

Kết quả: **67 passed** (63 test trước G2 + 4 test SSE mới).

Test SSE mới:

- `test_stream_requires_login`: chưa đăng nhập → 401 `AUTH_REQUIRED`.
- `test_stream_emits_initial_dashboard_events`: đúng content-type/header, nhận đủ
  `status`, `history`, `alerts`; status mới là `NO_DATA`.
- `test_dashboard_stream_pushes_only_changed_status`: sau khi ghi kết quả mới,
  generator đẩy `status` có `"room":"Bedroom"` mà không cần gọi REST.
- `test_stream_stops_after_member_access_is_revoked`: gỡ thành viên → stream gửi
  `auth` với `HOME_ACCESS_REVOKED` rồi dừng.

Kiểm tra tĩnh:

```text
py_compile server/routes/track_views.py server/app.py server/security_middleware.py  → OK
node --check server/static/service-worker.js                                        → OK
node --input-type=module --check (app.js + 10 module trong js/)                     → 11/11 OK
ESLint 9 no-undef/no-unused-vars (app.js + js/)                                     → 0 error, 0 warning
```

Smoke test HTTP thật (Flask `make_server`, DB tạm trong `%TEMP%`, không dùng
`data/smarthome.db`):

1. `GET /api/health` → 200, `database=ok`.
2. Đăng ký tài khoản → 201.
3. `GET /api/stream` không cookie → 401.
4. `GET /api/stream` có cookie → 200, `text/event-stream`, `X-Accel-Buffering: no`;
   nhận đủ `status`, `history`, `alerts`.
5. Ghi một kết quả mới (`room=Bedroom`) → SSE đẩy `status` mới trong cùng kết nối.
6. `GET /api/status` → thấy `room=Bedroom`.

Kết quả: **SMOKE OK**. Sau khi chạy, `data/smarthome.db` vẫn có **0 alert, 0
prediction** — test không ghi nhầm dữ liệu gốc.

## 5. Giới hạn còn lại

- Mỗi kết nối SSE vẫn truy vấn SQLite mỗi 2 giây (status/history/alerts + kiểm tra
  quyền). Với 1–3 thiết bị trong nhà thì nhẹ; nếu sau này có nhiều client, nên gom
  thành một broadcaster chung thay vì mỗi stream tự truy vấn.
- `_StreamSlots` nằm trong RAM của từng tiến trình. Chạy nhiều worker (gunicorn/
  waitress nhiều process) thì giới hạn 32 là theo từng process.
- Nếu người dùng đổi nhà ở tab khác, stream đang mở vẫn giữ nhà cũ cho tới khi tab
  đó reload/đổi nhà. Đây không phải lỗi phân quyền: mỗi vòng vẫn kiểm tra lại quyền
  xem nhà đang stream.
- Session là cookie phía client: nếu người dùng đăng xuất ở tab khác, tab đang mở
  stream vẫn nhận dữ liệu tới khi reload/ẩn tab. Muốn thu hồi tức thì cần session
  phía server (ví dụ `session_epoch` trong DB) — chưa làm trong G2.
- Polling dự phòng vẫn là 3 request mỗi 2 giây; chỉ dùng khi SSE không mở được.
- SSE giữ một thread cho mỗi kết nối. Flask dev server mặc định `threaded=True`;
  nếu triển khai bằng waitress/gunicorn, phải cấu hình đủ thread/worker, nếu không
  vài stream sẽ chiếm hết chỗ xử lý request thường.
- Chưa nén event. Payload `history` tối đa 300 dòng và chỉ gửi khi đổi, nên băng
  thông trong LAN không đáng kể.
