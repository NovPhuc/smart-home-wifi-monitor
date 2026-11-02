# 12 — Kiểm chứng triển khai Docker + Cloudflare

Phiên 2026‑11‑02. Mục tiêu: đưa đồ án chạy được ở dạng triển khai thật (đóng gói Docker,
đặt sau Cloudflare, có tên miền), và **kiểm chứng từng bước bằng lệnh chạy thật** chứ
không chỉ viết cấu hình rồi cho là xong.

Hướng dẫn thao tác: `DEPLOY.md`. Tài liệu này ghi lại **đã kiểm chứng cái gì và bằng cách nào**.

---

## 1. Sáu lỗi chặn triển khai đã sửa

Cả sáu đều làm stack **không khởi động được**, không phải cảnh báo.

### 1.1. `nginx.conf` khai báo `upstream app_backend` hai lần

Có một khối ở đầu file và một khối nữa ở cuối. nginx từ chối nạp cấu hình:

```
[emerg] duplicate upstream "app_backend"
```

Kiểm chứng bằng cách đếm trong bản cũ (đọc từ git, không phải file đang sửa):

```
git show HEAD:nginx.conf | grep -c 'upstream app_backend'   ->  2
```

### 1.2. `include proxy_params;` trong 7 location

`proxy_params` là file của **gói Debian `nginx-common`**, không có trong image
`nginx:alpine` đang dùng. nginx thoát ngay:

```
[emerg] open() "/etc/nginx/proxy_params" failed (2: No such file or directory)
```

Bản cũ có **7 dòng** như vậy. Các header proxy (`Host`, `X-Real-IP`, `X-Forwarded-*`) đã
được đặt ở cấp `server` nên mọi location thừa hưởng — bỏ hẳn `include` là đủ.

### 1.3. `${DOMAIN:-an-tam.example.com}` — cú pháp của shell, không phải của nginx

Có **4 dòng** dùng dạng này. nginx không có phép thay biến kiểu `${VAR:-default}`; file
lại được mount thẳng vào `/etc/nginx/nginx.conf` nên cơ chế envsubst template của image
cũng không chạy. Đã thay bằng tên miền thật, kèm lệnh đổi một lần cho cả file trong
`DEPLOY.md`.

### 1.4. Chứng chỉ mount sai đường dẫn

`docker-compose.prod.yml` mount thư mục chứng chỉ vào `/etc/nginx/certs`, nhưng
`nginx.conf` đọc `/etc/letsencrypt/live/<domain>/fullchain.pem` — chỗ certbot ghi vào.
nginx không tìm thấy chứng chỉ nên chết. Đã đổi mount thành `/etc/letsencrypt:ro`.

### 1.5. Image production chạy Werkzeug dev server

`docker-compose.prod.yml` ghi chú "Application server (Gunicorn + Flask)" nhưng `Dockerfile`
stage `prod` lại `CMD ["python", "server/app.py"]` — đó là dev server của Werkzeug
(một tiến trình, in cảnh báo đỏ, không có worker pool). `gunicorn` thậm chí không có
trong `requirements-docker.txt`.

Đã sửa:

- Thêm `server/wsgi.py` expose `application` (không gọi `create_app()` lần nữa — sẽ tạo
  hai app và tách đôi các singleton `db`/engine/limiter).
- Thêm `gunicorn>=22.0` vào `requirements-docker.txt`.
- `CMD` chạy gunicorn với worker `gthread`:

```
gunicorn --bind 0.0.0.0:5000 --worker-class gthread --workers 2 --threads 8 \
         --timeout 300 --graceful-timeout 30 server.wsgi:application
```

**Vì sao `gthread` chứ không `sync`:** dashboard dùng Server-Sent Events ở `/api/stream`.
Worker `sync` giữ trọn một tiến trình cho mỗi kết nối SSE và chặn các request khác;
`gthread` cho phép nhiều kết nối SSE cùng tồn tại trong một worker.

### 1.6. Gunicorn 26 báo lỗi control-socket vì `appuser` không có home

`useradd -r` (system account) không tạo thư mục home, nên mỗi lần khởi động:

```
[ERROR] Control server error: [Errno 13] Permission denied: '/home/appuser'
```

Không làm sập server nhưng làm nhiễu log và có thể che lỗi thật. Đã tạo home riêng cho
`appuser` và đặt `ENV HOME=/home/appuser` (không trỏ vào `/app/data` để socket không nằm
lẫn trong volume dữ liệu).

---

## 2. Bằng chứng kiểm chứng

Máy có Docker 29.9.2; đã bật Docker Desktop và chạy thật từng bước.

### 2.1. Cấu hình nginx

```
docker run --rm --add-host app:127.0.0.1 \
  -v ./nginx.conf:/etc/nginx/nginx.conf:ro \
  -v ./certs:/etc/letsencrypt:ro \
  -v ./certbot-www:/var/www/certbot:ro \
  nginx:alpine nginx -t
```

Kết quả:

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

Cảnh báo còn lại duy nhất là `"ssl_stapling" ignored, issuer certificate not found` — do
lần thử dùng chứng chỉ tự ký; chứng chỉ Let's Encrypt thật có issuer nên không gặp.

### 2.2. Cấu hình Docker Compose

```
docker compose -f docker-compose.prod.yml config --quiet    -> exit 0
docker compose -f docker-compose.yml config --quiet         -> exit 0
```

### 2.3. Điểm vào WSGI phục vụ được (không qua test client)

Gọi thẳng giao diện WSGI thô để chắc chắn `server/wsgi.py` dùng được với gunicorn:

```
application : Flask
so route    : 37
WSGI /api/health -> 200 OK {"api":"v1","database":"ok","service":"an-tam-home",...}
```

### 2.4. Build image production

```
docker build --target prod -t an-tam-home:2310-prod .
...
Successfully installed ... gunicorn-26.2.0 ... torch-2.15.0+cpu ...
naming to docker.io/library/an-tam-home:2310-prod done
```

### 2.5. Chạy container thật

```
docker run -d --name an-tam-test -p 5099:5000 \
  -e SMART_HOME_SECRET_KEY=<hex 64> \
  -v ./data:/app/data -v ./models:/app/models an-tam-home:2310-prod
```

Log khởi động:

```
[INFO] Starting gunicorn 26.2.0
[INFO] Listening at: http://0.0.0.0:5000 (1)
[INFO] Using worker: gthread
[INFO] Booting worker with pid: 7
[INFO] Booting worker with pid: 8
[INFO] Control socket listening at /home/appuser/.gunicorn/gunicorn.ctl
"GET /api/health HTTP/1.1" 200 85
```

| Kiểm tra | Kết quả |
|---|---|
| `docker ps` | `Up 11 seconds (healthy)` |
| Số dòng `[ERROR]` trong log | **0** |
| `GET /api/health` | **200** `{"status":"ok","database":"ok"}` |
| `GET /` | **200**, có header `Content-Security-Policy` |
| `GET /api/stream` khi chưa đăng nhập | **401** — SSE vẫn được bảo vệ đúng |

---

## 3. Việc chưa kiểm chứng được ở máy này

Nói rõ để không ai tưởng đã thử hết:

- **Đường Cloudflare Tunnel**: cần token và tài khoản Cloudflare thật. Cấu hình đã có
  (`cloudflared` trong profile `tunnel`, hướng dẫn trong `DEPLOY.md`), nhưng **chưa bắt
  tay vào Cloudflare** nên chưa xác nhận được hostname công khai.
- **Let's Encrypt thật**: cần tên miền trỏ về IP công khai và cổng 80 mở. Lần thử ở đây
  dùng chứng chỉ tự ký để `nginx -t` kiểm tra được cả phần `ssl`.
- **Stack đầy đủ 4 service** (`app` + `redis` + `nginx` + `certbot`): đã kiểm từng phần
  (image, cấu hình nginx, cấu hình compose) nhưng chưa `up` cả cụm cùng lúc.

---

## 4. Ghi chú

- `certs/` và `certbot-www/` **không được commit** — `certs/` chứa khoá riêng TLS. Đã
  thêm vào `.gitignore`; chứng chỉ tự ký dùng để thử đã xoá khỏi cây làm việc.
- `.env.prod` cũng không được commit (đã có `.env*` trong `.gitignore`); mẫu nằm ở
  `.env.prod.example`.
- Ảnh production hiện vẫn cài `pytest` (nằm trong `requirements-docker.txt`) — chỉ dùng
  cho `security_audit`, không cần lúc chạy. Bỏ được để image nhỏ hơn, nhưng chưa làm vì
  `DEPLOY.md` có hướng dẫn chạy audit trong container.
