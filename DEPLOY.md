# Triển khai An Tâm Home

Hai đường triển khai, chọn một:

| | **A. Cloudflare Tunnel** (khuyến nghị) | **B. VPS + Let's Encrypt** |
|---|---|---|
| Mở cổng ra Internet | Không cần | Cần 80 và 443 |
| Chứng chỉ TLS | Cloudflare cấp, tự gia hạn | certbot tự gia hạn |
| Cần IP tĩnh / domain trỏ về | Không | Có |
| Lộ IP máy chủ | Không | Có |
| Dùng service nào trong compose | `app` + `cloudflared` | `app` + `nginx` + `certbot` |

Cả hai đều chạy ứng dụng bằng **gunicorn** (`server/wsgi.py:application`), không phải
Werkzeug dev server — xem `docs/12_trien_khai.md` để biết vì sao và đã kiểm chứng thế nào.

---

## 0. Chuẩn bị chung

```powershell
copy .env.prod.example .env.prod
```

Sửa `.env.prod`:

- `DOMAIN` — tên miền thật.
- `CERTBOT_EMAIL` — email nhận cảnh báo hết hạn chứng chỉ (chỉ cần ở đường B).
- `SMART_HOME_SECRET_KEY` — sinh bằng
  `python -c "import secrets; print(secrets.token_hex(32))"`.
  Để trống thì ứng dụng tự sinh và lưu `data/secret_key`; chạy được, nhưng xóa volume
  `data/` là mất hết phiên đăng nhập.

Nếu dùng đường B, **phải đổi tên miền trong `nginx.conf` cho khớp `DOMAIN`** — nginx đọc
file này trực tiếp nên không thay biến môi trường được:

```powershell
(Get-Content nginx.conf -Raw) -replace 'an-tam\.example\.com', 'ten-mien-cua-ban' |
    Set-Content nginx.conf -Encoding UTF8
```

Kiểm tra lại trước khi chạy:

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet   # cú pháp compose
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm nginx nginx -t   # cú pháp nginx
```

---

## A. Cloudflare Tunnel

Không mở cổng nào ra Internet; `cloudflared` tạo kết nối đi ra tới Cloudflare, Cloudflare
mới là bên nhận lưu lượng và giữ TLS.

1. Vào **Cloudflare Zero Trust → Networks → Tunnels → Create a tunnel**, chọn loại
   `cloudflared`, đặt tên (ví dụ `an-tam-home`).
2. Copy **token** dán vào `CLOUDFLARE_TUNNEL_TOKEN` trong `.env.prod`.
3. Trong tab **Public Hostname** của tunnel, thêm một hostname:
   - Subdomain/domain: tên miền của bạn.
   - Service: `HTTP` → `app:5000` (KHÔNG phải `https` và không phải `nginx`).
4. Chạy:

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile tunnel up -d app cloudflared
```

Cloudflare tự cấp chứng chỉ cho hostname đã khai. Không cần `nginx`, `certbot`, cũng
không cần mở cổng 80/443.

Kiểm tra:

```powershell
docker compose -f docker-compose.prod.yml logs -f cloudflared   # phải thấy "Registered tunnel connection"
curl.exe https://ten-mien-cua-ban/api/health
```

Lưu ý: header `CF-Connecting-IP` và dải `set_real_ip_from` trong `nginx.conf` **không
dùng đến** ở đường này (không có nginx trong luồng). Muốn rate limit theo IP thật thì
đặt `SMART_HOME_TRUST_PROXY=1` (đã đặt sẵn trong compose) — khi đó ứng dụng đọc
`X-Forwarded-For`, và chỉ an toàn vì lưu lượng bắt buộc đi qua Cloudflare.

---

## B. VPS + nginx + Let's Encrypt

Trỏ bản ghi `A` của tên miền về IP máy chủ trước, và mở cổng 80/443.

1. Cấp chứng chỉ lần đầu (chạy một lần, cần cổng 80 đã mở):

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile ssl-init run --rm certbot-init
```

2. Chạy toàn bộ stack:

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

3. Tiện ích gia hạn (`certbot` trong profile `ssl`, chạy vòng lặp 12 giờ):

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile ssl up -d certbot
```

Kiểm tra:

```powershell
docker compose -f docker-compose.prod.yml ps
curl.exe https://ten-mien-cua-ban/api/health
```

---

## Kiểm tra sau khi chạy

```powershell
curl.exe https://<domain>/api/health                 # {"status":"ok","database":"ok",...}
curl.exe -I https://<domain>/                        # có Strict-Transport-Security, X-Frame-Options
curl.exe -N https://<domain>/api/stream              # SSE: phải thấy dữ liệu đẩy về, không bị cắt
```

Trong ứng dụng: đăng ký một tài khoản, thêm hai phòng, chạy demo — nếu lưới phòng sáng
và dòng thời gian có sự kiện thì pipeline đã thông.

Bộ kiểm tra bảo mật (xem `SECURITY.md` §5):

```powershell
docker compose -f docker-compose.prod.yml exec app python scripts/security_audit.py
docker compose -f docker-compose.prod.yml exec app python scripts/full_security_audit.py
```

---

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `nginx: [emerg] duplicate upstream "app_backend"` | `nginx.conf` khai báo upstream hai lần | Đã sửa: chỉ còn một khối `upstream` |
| `nginx: [emerg] open() "/etc/nginx/proxy_params" failed` | `include proxy_params;` — file này thuộc gói Debian, **không có trong `nginx:alpine`** | Đã sửa: bỏ hẳn, header proxy đặt ở cấp `server` |
| `nginx: [emerg] unknown directive "${DOMAIN:-...}"` | nginx không hiểu cú pháp shell | Đã sửa: ghi tên miền thật vào `nginx.conf` |
| `nginx: [emerg] cannot load certificate ... fullchain.pem` | compose mount cert vào `/etc/nginx/certs` còn config đọc `/etc/letsencrypt/...` | Đã sửa: mount vào `/etc/letsencrypt` |
| Container `app` khởi động rồi thoát, log có `WARNING: This is a development server` | Dockerfile stage `prod` chạy `python server/app.py` | Đã sửa: chạy gunicorn với worker `gthread` |
| SSE bị ngắt sau ~30 giây | Worker `sync` của gunicorn hoặc `proxy_read_timeout` quá ngắn | Đã sửa: `gthread` + `--timeout 300`, nginx `proxy_read_timeout 300s` |
| `502 Bad Gateway` | Service `app` chưa healthy | `docker compose logs app`; kiểm tra `/api/health` trong container |
| Trang cũ vẫn hiện sau khi cập nhật | Service worker giữ bản cache | `nginx.conf` đã đặt `no-store` cho `/service-worker.js`; xóa cache trình duyệt một lần |

---

## Ghi chú vận hành

- **Volume**: `./data` (SQLite + `secret_key`) và `./models` (model đã huấn luyện) là dữ
  liệu thật, phải sao lưu. Chúng được mount ra ngoài container nên `docker compose down`
  không xóa.
- **Sao lưu**:
  `docker compose -f docker-compose.prod.yml exec app sqlite3 /app/data/smarthome.db ".backup '/app/data/backup.db'"`
- **Cập nhật phiên bản**: `docker compose build app && docker compose up -d app`.
- **Nhật ký**: `docker compose logs -f app`, `... -f nginx`. Log tầng bảo mật có tiền tố
  `[Bao mat]` (rate limit, mẫu tấn công bị chặn).
- **Ảnh production còn cài `pytest`** (nằm trong `requirements-docker.txt`). Chỉ dùng cho
  `security_audit`, không cần lúc chạy; bỏ được để image nhỏ hơn nếu muốn.
